import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "health_monitor.db")


def get_db_path(custom_path: Optional[str] = None) -> str:
    """Return database path from parameter, env, or default instance location."""
    if custom_path:
        return custom_path
    return os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Establish and return a SQLite database connection with row factory enabled
    and foreign keys enforced.
    """
    path = get_db_path(db_path)
    if path != ":memory:":
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes if they do not exist."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS websites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    last_checked TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    status_code INTEGER,
                    response_time_ms REAL,
                    error_message TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS health_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    checked_at TIMESTAMP NOT NULL,
                    status TEXT NOT NULL,
                    status_code INTEGER,
                    response_time_ms REAL,
                    error_message TEXT,
                    FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    status_code INTEGER,
                    error_message TEXT,
                    delivery_status TEXT NOT NULL,
                    delivery_error TEXT,
                    FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_health_checks_website
                    ON health_checks(website_id, checked_at DESC);

                CREATE INDEX IF NOT EXISTS idx_health_checks_checked_at
                    ON health_checks(checked_at);

                CREATE INDEX IF NOT EXISTS idx_alerts_website
                    ON alerts(website_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_alerts_created_at
                    ON alerts(created_at DESC);
            """)
    finally:
        conn.close()


def add_website(url: str, name: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Add a new website to be monitored. Raises ValueError if already exists."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO websites (url, name, created_at, status)
                VALUES (?, ?, ?, 'unknown')
                """,
                (url, name, now),
            )
            website_id = cursor.lastrowid
        return get_website_by_id(website_id, db_path)
    except sqlite3.IntegrityError:
        raise ValueError(f"Website with URL '{url}' is already monitored.")
    finally:
        conn.close()


def get_websites(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all monitored websites."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, url, name, created_at, last_checked, status,
                   status_code, response_time_ms, error_message, is_active
            FROM websites
            WHERE is_active = 1
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_website_by_id(website_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single website by ID."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, url, name, created_at, last_checked, status,
                   status_code, response_time_ms, error_message, is_active
            FROM websites
            WHERE id = ?
            """,
            (website_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_website_by_url(url: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a website by its URL."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, url, name, created_at, last_checked, status,
                   status_code, response_time_ms, error_message, is_active
            FROM websites
            WHERE url = ?
            """,
            (url,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_website(website_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a monitored website along with its health check and alert history."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("DELETE FROM websites WHERE id = ?", (website_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def update_website_status(
    website_id: int,
    status: str,
    status_code: Optional[int],
    response_time_ms: Optional[float],
    error_message: Optional[str],
    checked_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Update current status information for a website."""
    if checked_at is None:
        checked_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE websites
                SET last_checked = ?,
                    status = ?,
                    status_code = ?,
                    response_time_ms = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (checked_at, status, status_code, response_time_ms, error_message, website_id),
            )
    finally:
        conn.close()


def record_health_check(
    website_id: int,
    status: str,
    status_code: Optional[int],
    response_time_ms: Optional[float],
    error_message: Optional[str],
    checked_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Record a health check entry in health_checks history table."""
    if checked_at is None:
        checked_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO health_checks (
                    website_id, checked_at, status, status_code,
                    response_time_ms, error_message
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (website_id, checked_at, status, status_code, response_time_ms, error_message),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def record_alert(
    website_id: int,
    alert_type: str,
    status_code: Optional[int],
    error_message: Optional[str],
    delivery_status: str,
    delivery_error: Optional[str] = None,
    created_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Record an alert event (downtime or recovery) in the alerts table."""
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO alerts (
                    website_id, alert_type, created_at, status_code,
                    error_message, delivery_status, delivery_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    website_id,
                    alert_type,
                    created_at,
                    status_code,
                    error_message,
                    delivery_status,
                    delivery_error,
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_recent_checks(
    website_id: Optional[int] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve recent health check history entries with website info."""
    conn = get_connection(db_path)
    try:
        if website_id:
            rows = conn.execute(
                """
                SELECT h.id, h.website_id, h.checked_at, h.status,
                       h.status_code, h.response_time_ms, h.error_message,
                       w.name AS website_name, w.url AS website_url
                FROM health_checks h
                JOIN websites w ON h.website_id = w.id
                WHERE h.website_id = ?
                ORDER BY h.checked_at DESC
                LIMIT ?
                """,
                (website_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.id, h.website_id, h.checked_at, h.status,
                       h.status_code, h.response_time_ms, h.error_message,
                       w.name AS website_name, w.url AS website_url
                FROM health_checks h
                JOIN websites w ON h.website_id = w.id
                ORDER BY h.checked_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_recent_alerts(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent alerts with website details."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT a.id, a.website_id, a.alert_type, a.created_at,
                   a.status_code, a.error_message, a.delivery_status, a.delivery_error,
                   w.name AS website_name, w.url AS website_url
            FROM alerts a
            JOIN websites w ON a.website_id = w.id
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_summary_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve aggregated stats for dashboard counters."""
    conn = get_connection(db_path)
    try:
        # Total websites and breakdown by status
        site_counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) AS online,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) AS offline,
                SUM(CASE WHEN status = 'unknown' THEN 1 ELSE 0 END) AS unknown
            FROM websites
            WHERE is_active = 1
            """
        ).fetchone()

        total = site_counts["total"] or 0
        online = site_counts["online"] or 0
        offline = site_counts["offline"] or 0
        unknown = site_counts["unknown"] or 0

        # Total alerts count
        alert_count_row = conn.execute("SELECT COUNT(*) AS count FROM alerts").fetchone()
        total_alerts = alert_count_row["count"] or 0

        # Average response time for online websites across latest checks
        avg_rt_row = conn.execute(
            """
            SELECT AVG(response_time_ms) AS avg_rt
            FROM websites
            WHERE is_active = 1 AND status = 'online' AND response_time_ms IS NOT NULL
            """
        ).fetchone()
        avg_rt = round(avg_rt_row["avg_rt"], 1) if (avg_rt_row and avg_rt_row["avg_rt"] is not None) else None

        return {
            "total_websites": total,
            "online_websites": online,
            "offline_websites": offline,
            "unknown_websites": unknown,
            "total_alerts": total_alerts,
            "avg_response_time_ms": avg_rt,
        }
    finally:
        conn.close()


def prune_old_history(retention_days: int = 30, db_path: Optional[str] = None) -> int:
    """Delete health checks older than retention_days. Returns count of deleted rows."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                "DELETE FROM health_checks WHERE checked_at < ?",
                (cutoff,),
            )
            return cursor.rowcount
    finally:
        conn.close()
