"""
Website Health Monitor with Auto-Alerts - Demo Data Seeder
Populates the database with realistic monitored websites, time-series health checks,
and alert events for college project demonstrations and UI exploration.
"""

import os
import random
from datetime import datetime, timezone, timedelta
from database import get_connection, init_db

def seed_database(db_path=None):
    """Seed SQLite database with rich sample data."""
    init_db(db_path)
    conn = get_connection(db_path)

    try:
        with conn:
            # Clear existing records to ensure clean presentation dataset
            conn.execute("DELETE FROM alerts;")
            conn.execute("DELETE FROM health_checks;")
            conn.execute("DELETE FROM websites;")

            now = datetime.now(timezone.utc)

            # 1. Monitored Websites Definition
            demo_sites = [
                {
                    "url": "https://www.wikipedia.org",
                    "name": "Wikipedia Global Portal",
                    "status": "online",
                    "status_code": 200,
                    "response_time_ms": 78.4,
                    "error_message": None,
                    "base_latency": 75,
                },
                {
                    "url": "https://api.github.com",
                    "name": "GitHub Public REST API",
                    "status": "online",
                    "status_code": 200,
                    "response_time_ms": 182.6,
                    "error_message": None,
                    "base_latency": 170,
                },
                {
                    "url": "https://www.python.org",
                    "name": "Python Language Foundation",
                    "status": "online",
                    "status_code": 200,
                    "response_time_ms": 142.1,
                    "error_message": None,
                    "base_latency": 135,
                },
                {
                    "url": "https://developer.mozilla.org",
                    "name": "MDN Developer Documentation",
                    "status": "online",
                    "status_code": 200,
                    "response_time_ms": 115.8,
                    "error_message": None,
                    "base_latency": 110,
                },
                {
                    "url": "https://www.cloudflare.com",
                    "name": "Cloudflare Edge CDN",
                    "status": "online",
                    "status_code": 200,
                    "response_time_ms": 52.3,
                    "base_latency": 50,
                    "error_message": None,
                },
                {
                    "url": "https://payment-service.fintech-demo.internal",
                    "name": "Payment Gateway Microservice (Simulated Outage)",
                    "status": "offline",
                    "status_code": None,
                    "response_time_ms": None,
                    "error_message": "Connection timed out after 8.0 seconds (Host unreachable)",
                    "base_latency": None,
                },
            ]

            site_ids = {}

            for site in demo_sites:
                site_created_at = (now - timedelta(days=5)).isoformat()
                last_checked_at = (now - timedelta(minutes=random.randint(1, 5))).isoformat()

                cursor = conn.execute(
                    """
                    INSERT INTO websites (
                        url, name, created_at, last_checked, status,
                        status_code, response_time_ms, error_message, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        site["url"],
                        site["name"],
                        site_created_at,
                        last_checked_at,
                        site["status"],
                        site["status_code"],
                        site["response_time_ms"],
                        site["error_message"],
                    ),
                )
                site_ids[site["name"]] = (cursor.lastrowid, site)

            # 2. Historical Health Checks (Past 12 Hours, every 30 minutes)
            check_intervals = 24  # 24 data points = 12 hours
            for name, (site_id, site_meta) in site_ids.items():
                is_offline_site = site_meta["status"] == "offline"

                for i in range(check_intervals, 0, -1):
                    check_time = (now - timedelta(minutes=i * 30)).isoformat()

                    if is_offline_site:
                        # Offline site failed its last 10 checks, but was online before that
                        if i <= 10:
                            conn.execute(
                                """
                                INSERT INTO health_checks (
                                    website_id, checked_at, status, status_code,
                                    response_time_ms, error_message
                                ) VALUES (?, ?, 'offline', NULL, NULL, ?)
                                """,
                                (site_id, check_time, site_meta["error_message"]),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT INTO health_checks (
                                    website_id, checked_at, status, status_code,
                                    response_time_ms, error_message
                                ) VALUES (?, ?, 'online', 200, ?, NULL)
                                """,
                                (site_id, check_time, round(random.uniform(220, 310), 1)),
                            )
                    else:
                        base = site_meta["base_latency"]
                        # Realistic latency jitter (+/- 15%) with occasional minor spikes
                        jitter = random.uniform(-0.15, 0.20)
                        latency = round(base * (1.0 + jitter), 1)

                        conn.execute(
                            """
                            INSERT INTO health_checks (
                                website_id, checked_at, status, status_code,
                                response_time_ms, error_message
                            ) VALUES (?, ?, 'online', 200, ?, NULL)
                            """,
                            (site_id, check_time, latency),
                        )

            # 3. Alert Events (Downtime and Recovery Incidents)
            payment_site_id = site_ids["Payment Gateway Microservice (Simulated Outage)"][0]
            github_site_id = site_ids["GitHub Public REST API"][0]
            wiki_site_id = site_ids["Wikipedia Global Portal"][0]

            alerts_data = [
                # Recent downtime on payment gateway (Active Incident)
                (
                    payment_site_id,
                    "downtime",
                    (now - timedelta(hours=5)).isoformat(),
                    None,
                    "Connection timed out after 8.0 seconds (Host unreachable)",
                    "skipped_no_smtp",
                    "SMTP credentials not configured in environment variables",
                ),
                # Recovery event on GitHub API 2 days ago
                (
                    github_site_id,
                    "recovery",
                    (now - timedelta(days=1, hours=4)).isoformat(),
                    200,
                    None,
                    "skipped_no_smtp",
                    "SMTP credentials not configured in environment variables",
                ),
                # Downtime on GitHub API 2 days ago
                (
                    github_site_id,
                    "downtime",
                    (now - timedelta(days=1, hours=5)).isoformat(),
                    503,
                    "HTTP 503 Service Unavailable",
                    "skipped_no_smtp",
                    "SMTP credentials not configured in environment variables",
                ),
                # Recovery on Wikipedia
                (
                    wiki_site_id,
                    "recovery",
                    (now - timedelta(days=3)).isoformat(),
                    200,
                    None,
                    "skipped_no_smtp",
                    "SMTP credentials not configured in environment variables",
                ),
            ]

            for a in alerts_data:
                conn.execute(
                    """
                    INSERT INTO alerts (
                        website_id, alert_type, created_at, status_code,
                        error_message, delivery_status, delivery_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    a,
                )

        print(f"[SUCCESS] Seeded database with {len(demo_sites)} websites, "
              f"{len(demo_sites) * check_intervals} health checks, and {len(alerts_data)} alerts.")
        return True

    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
