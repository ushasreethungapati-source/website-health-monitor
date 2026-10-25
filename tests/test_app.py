import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import requests

from app import create_app
from database import init_db, get_websites, get_recent_alerts, get_recent_checks


@pytest.fixture
def app_instance():
    """Create and configure a clean testing app instance with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["TESTING"] = "true"
    os.environ["DISABLE_SCHEDULER"] = "1"

    test_config = {
        "TESTING": True,
        "DATABASE_PATH": db_path,
        "SECRET_KEY": "test-key",
    }

    app = create_app(test_config)

    yield app

    os.close(db_fd)
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest.fixture
def client(app_instance):
    """Test client fixture."""
    return app_instance.test_client()


def create_mock_response(status_code=200, text="OK"):
    """Helper to create a fake requests.Response object."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.text = text
    mock_resp.ok = (200 <= status_code < 400)
    return mock_resp


# ==============================================================================
# 1. Homepage & Static Routes
# ==============================================================================

def test_homepage_loads(client):
    """Verify homepage serves HTML successfully with HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Website Health Monitor" in response.data


# ==============================================================================
# 2. Website Creation & Validation Tests
# ==============================================================================

def test_add_valid_website(client):
    """Verify adding a valid website creates entry and triggers initial check."""
    with patch("requests.get", return_value=create_mock_response(200)):
        res = client.post(
            "/api/websites",
            json={"url": "https://example.com", "name": "Example Test"},
        )
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["name"] == "Example Test"
    assert data["data"]["status"] == "online"
    assert data["data"]["status_code"] == 200


def test_add_duplicate_website_rejected(client):
    """Verify adding the same URL twice is rejected with 409 Conflict."""
    with patch("requests.get", return_value=create_mock_response(200)):
        res1 = client.post("/api/websites", json={"url": "https://example.com"})
        assert res1.status_code == 201

        res2 = client.post("/api/websites", json={"url": "https://example.com"})
        assert res2.status_code == 409
        assert "already monitored" in res2.get_json()["error"]


def test_reject_invalid_urls(client):
    """Verify malformed and non-HTTP/HTTPS URLs are rejected with 400."""
    # Empty
    res1 = client.post("/api/websites", json={"url": ""})
    assert res1.status_code == 400

    # Non-HTTP scheme
    res2 = client.post("/api/websites", json={"url": "ftp://files.example.com"})
    assert res2.status_code == 400
    assert "Only HTTP and HTTPS" in res2.get_json()["error"]

    # File scheme
    res3 = client.post("/api/websites", json={"url": "file:///etc/passwd"})
    assert res3.status_code == 400


def test_reject_ssrf_and_private_ips(client):
    """Verify SSRF targets (localhost, private IPs, metadata) are strictly blocked."""
    # Localhost
    res1 = client.post("/api/websites", json={"url": "http://localhost:5000"})
    assert res1.status_code == 400
    assert "localhost" in res1.get_json()["error"].lower()

    # Private IP 127.0.0.1
    res2 = client.post("/api/websites", json={"url": "http://127.0.0.1/admin"})
    assert res2.status_code == 400
    assert "restricted" in res2.get_json()["error"].lower()

    # Private LAN IP 192.168.1.1
    res3 = client.post("/api/websites", json={"url": "http://192.168.1.1"})
    assert res3.status_code == 400
    assert "restricted" in res3.get_json()["error"].lower()

    # Cloud metadata endpoint
    res4 = client.post("/api/websites", json={"url": "http://169.254.169.254/latest/meta-data/"})
    assert res4.status_code == 400
    assert "metadata" in res4.get_json()["error"].lower()


# ==============================================================================
# 3. Listing, Checking, and Removing Websites
# ==============================================================================

def test_list_websites(client):
    """Verify listing all monitored websites."""
    with patch("requests.get", return_value=create_mock_response(200)):
        client.post("/api/websites", json={"url": "https://site-a.com", "name": "Site A"})
        client.post("/api/websites", json={"url": "https://site-b.com", "name": "Site B"})

    res = client.get("/api/websites")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 2
    names = [s["name"] for s in data["data"]]
    assert "Site A" in names
    assert "Site B" in names


def test_remove_website(client):
    """Verify removing a monitored website and 404 for invalid IDs."""
    with patch("requests.get", return_value=create_mock_response(200)):
        add_res = client.post("/api/websites", json={"url": "https://removetest.com"})
        site_id = add_res.get_json()["data"]["id"]

    del_res = client.delete(f"/api/websites/{site_id}")
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True

    # Check that it's no longer listed
    list_res = client.get("/api/websites")
    assert len(list_res.get_json()["data"]) == 0

    # Delete non-existent ID
    del_404 = client.delete(f"/api/websites/{site_id}")
    assert del_404.status_code == 404


def test_check_website_on_demand(client):
    """Verify manual check endpoint executes HTTP check and updates data."""
    with patch("requests.get", return_value=create_mock_response(200)):
        add_res = client.post("/api/websites", json={"url": "https://ondemand.com"})
        site_id = add_res.get_json()["data"]["id"]

    # Manual check with 404 (requirement 6: 404 is still considered Online since HTTP response arrived)
    with patch("requests.get", return_value=create_mock_response(404)):
        check_res = client.post(f"/api/websites/{site_id}/check")

    assert check_res.status_code == 200
    site_data = check_res.get_json()["data"]
    assert site_data["status"] == "online"
    assert site_data["status_code"] == 404


def test_check_all_websites(client):
    """Verify check-all endpoint runs checks for all monitored sites."""
    with patch("requests.get", return_value=create_mock_response(200)):
        client.post("/api/websites", json={"url": "https://site1.com"})
        client.post("/api/websites", json={"url": "https://site2.com"})

    with patch("requests.get", return_value=create_mock_response(200)):
        res = client.post("/api/websites/check-all")

    assert res.status_code == 200
    results = res.get_json()["data"]
    assert len(results) == 2


# ==============================================================================
# 4. History and Statistics
# ==============================================================================

def test_monitoring_history_recording(client):
    """Verify health checks are recorded in history and retrievable."""
    with patch("requests.get", return_value=create_mock_response(200)):
        add_res = client.post("/api/websites", json={"url": "https://historytest.com"})
        site_id = add_res.get_json()["data"]["id"]

        # Run 2 additional checks
        client.post(f"/api/websites/{site_id}/check")
        client.post(f"/api/websites/{site_id}/check")

    # Specific website history
    res1 = client.get(f"/api/websites/{site_id}/history")
    assert res1.status_code == 200
    history = res1.get_json()["data"]
    assert len(history) == 3  # 1 initial + 2 manual checks

    # Global history
    res2 = client.get("/api/history")
    assert res2.status_code == 200
    assert len(res2.get_json()["data"]) >= 3


def test_dashboard_summary_statistics(client):
    """Verify summary API returns correct totals for sites, status, and alerts."""
    with patch("requests.get", return_value=create_mock_response(200)):
        client.post("/api/websites", json={"url": "https://up1.com"})
        client.post("/api/websites", json={"url": "https://up2.com"})

    # Add a site that fails
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Down")):
        client.post("/api/websites", json={"url": "https://down1.com"})

    summary_res = client.get("/api/summary")
    assert summary_res.status_code == 200
    stats = summary_res.get_json()["data"]

    assert stats["total_websites"] == 3
    assert stats["online_websites"] == 2
    assert stats["offline_websites"] == 1
    assert stats["avg_response_time_ms"] is not None


# ==============================================================================
# 5. Downtime and Recovery Transition Logic & Alerts
# ==============================================================================

def test_downtime_and_recovery_alert_transitions(client):
    """
    Test state transitions:
    1. Online -> Offline: Triggers downtime alert
    2. Offline -> Offline: DOES NOT trigger duplicate alert
    3. Offline -> Online: Triggers recovery alert
    """
    # Step 1: Start with site Online
    with patch("requests.get", return_value=create_mock_response(200)):
        add_res = client.post("/api/websites", json={"url": "https://transition-test.com", "name": "Transition Test"})
        site_id = add_res.get_json()["data"]["id"]

    alerts_res = client.get("/api/alerts")
    assert len(alerts_res.get_json()["data"]) == 0  # No alerts yet

    # Step 2: Site goes DOWN (Online -> Offline)
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
        client.post(f"/api/websites/{site_id}/check")

    alerts_res2 = client.get("/api/alerts")
    alerts2 = alerts_res2.get_json()["data"]
    assert len(alerts2) == 1
    assert alerts2[0]["alert_type"] == "downtime"
    assert "timed out" in alerts2[0]["error_message"].lower()

    # Step 3: Site is STILL DOWN (Offline -> Offline) - MUST NOT send duplicate alert!
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Still down")):
        client.post(f"/api/websites/{site_id}/check")

    alerts_res3 = client.get("/api/alerts")
    alerts3 = alerts_res3.get_json()["data"]
    assert len(alerts3) == 1  # Still exactly 1 alert, no duplicate!

    # Step 4: Site RECOVERS (Offline -> Online)
    with patch("requests.get", return_value=create_mock_response(200)):
        client.post(f"/api/websites/{site_id}/check")

    alerts_res4 = client.get("/api/alerts")
    alerts4 = alerts_res4.get_json()["data"]
    assert len(alerts4) == 2
    # Most recent alert should be recovery
    assert alerts4[0]["alert_type"] == "recovery"
    assert alerts4[1]["alert_type"] == "downtime"


def test_alert_when_smtp_not_configured(client, monkeypatch):
    """Verify alert record is logged with status 'skipped_no_smtp' when SMTP is unconfigured."""
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("ALERT_TO_EMAIL", "")

    # Site starts online
    with patch("requests.get", return_value=create_mock_response(200)):
        add_res = client.post("/api/websites", json={"url": "https://no-smtp.com"})
        site_id = add_res.get_json()["data"]["id"]

    # Site goes down
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Down")):
        client.post(f"/api/websites/{site_id}/check")

    alerts = client.get("/api/alerts").get_json()["data"]
    assert len(alerts) == 1
    assert alerts[0]["delivery_status"] == "skipped_no_smtp"
    assert "not configured" in alerts[0]["delivery_error"].lower()


def test_alert_when_smtp_is_configured(client, monkeypatch):
    """Verify alert triggers SMTP email dispatch when credentials are set."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "alerts@example.com")
    monkeypatch.setenv("SMTP_PASS", "secret-pass")
    monkeypatch.setenv("ALERT_FROM_EMAIL", "alerts@example.com")
    monkeypatch.setenv("ALERT_TO_EMAIL", "admin@example.com")

    # Site starts online
    with patch("requests.get", return_value=create_mock_response(200)):
        add_res = client.post("/api/websites", json={"url": "https://smtp-success.com"})
        site_id = add_res.get_json()["data"]["id"]

    # Mock smtplib.SMTP
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = mock_smtp_class.return_value
        mock_server.__enter__.return_value = mock_server

        # Trigger downtime
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Down")):
            client.post(f"/api/websites/{site_id}/check")

        # Verify sendmail was called on SMTP server
        assert mock_server.sendmail.called
        call_args = mock_server.sendmail.call_args[0]
        assert call_args[0] == "alerts@example.com"
        assert call_args[1] == ["admin@example.com"]

    alerts = client.get("/api/alerts").get_json()["data"]
    assert len(alerts) == 1
    assert alerts[0]["delivery_status"] == "sent"


def test_system_status_endpoint(client):
    """Verify system status reports check interval and configuration."""
    res = client.get("/api/system-status")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "check_interval_seconds" in data
    assert "smtp_configured" in data


def test_http_500_is_considered_online(client):
    """
    Requirement 6: Mark the website Online when a valid HTTP response is received,
    including HTTP error responses such as 500.
    """
    with patch("requests.get", return_value=create_mock_response(500)):
        res = client.post("/api/websites", json={"url": "https://server-err.com"})

    assert res.status_code == 201
    site = res.get_json()["data"]
    assert site["status"] == "online"
    assert site["status_code"] == 500


def test_cascade_deletion_cleans_history(client, app_instance):
    """Verify deleting a website completely cascades and cleans its health checks and alerts."""
    from database import get_recent_checks, get_recent_alerts

    db_path = app_instance.config.get("DATABASE_PATH")
    with patch("requests.get", return_value=create_mock_response(200)):
        add_res = client.post("/api/websites", json={"url": "https://cascade-test.com"})
        site_id = add_res.get_json()["data"]["id"]

    # Trigger downtime alert
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Down")):
        client.post(f"/api/websites/{site_id}/check")

    assert len(get_recent_checks(site_id, db_path=db_path)) >= 2
    assert len(get_recent_alerts(db_path=db_path)) >= 1

    # Delete website
    del_res = client.delete(f"/api/websites/{site_id}")
    assert del_res.status_code == 200

    # Checks and alerts for that site must be gone
    assert len(get_recent_checks(site_id, db_path=db_path)) == 0
    remaining_alerts = [a for a in get_recent_alerts(db_path=db_path) if a["website_id"] == site_id]
    assert len(remaining_alerts) == 0


def test_prune_old_history(app_instance):
    """Verify retention policy prunes checks older than specified days."""
    from database import record_health_check, prune_old_history, get_recent_checks, add_website
    from datetime import datetime, timezone, timedelta

    db_path = app_instance.config.get("DATABASE_PATH")
    site = add_website("https://prune-test.com", "Prune Test", db_path=db_path)

    old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    record_health_check(site["id"], "online", 200, 100.0, None, checked_at=old_date, db_path=db_path)
    record_health_check(site["id"], "online", 200, 110.0, None, db_path=db_path)

    assert len(get_recent_checks(site["id"], db_path=db_path)) == 2

    # Prune records older than 30 days
    pruned_count = prune_old_history(retention_days=30, db_path=db_path)
    assert pruned_count == 1
    assert len(get_recent_checks(site["id"], db_path=db_path)) == 1

