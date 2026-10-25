import os
import time
import socket
import ipaddress
import urllib.parse
from typing import Dict, Any, Optional, Tuple
import requests

from database import (
    get_website_by_id,
    get_websites,
    update_website_status,
    record_health_check,
)
from alerts import trigger_alert

DEFAULT_TIMEOUT = 8  # seconds


def is_private_or_restricted_ip(ip_str: str) -> bool:
    """Check if an IP string is private, loopback, link-local, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        # Not a raw IP literal (e.g. standard domain name)
        return False


def validate_url_safety(url: str) -> Tuple[bool, str]:
    """
    Validate that the URL uses HTTP/HTTPS and does not target internal / SSRF destinations.
    Returns (is_valid: bool, error_message: str).
    """
    if not url or not isinstance(url, str):
        return False, "URL cannot be empty."

    url = url.strip()
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, "Malformed URL format."

    if parsed.scheme.lower() not in ("http", "https"):
        return False, "Only HTTP and HTTPS URLs are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must include a valid host name."

    hostname_lower = hostname.lower()

    # Reject localhost & internal hostnames
    if (
        hostname_lower == "localhost"
        or hostname_lower.endswith(".localhost")
        or hostname_lower.endswith(".local")
        or hostname_lower.endswith(".internal")
        or hostname_lower.endswith(".lan")
    ):
        return False, "Targeting localhost or internal network domains is not permitted."

    # Reject known cloud metadata hostnames
    if hostname_lower in (
        "169.254.169.254",
        "metadata.google.internal",
        "instance-data",
        "metadata.packet.net",
    ):
        return False, "Access to cloud instance metadata services is blocked."

    # If test mode is enabled, skip live DNS lookup to allow mock domains in pytest
    if os.environ.get("TESTING", "").lower() in ("true", "1") or os.environ.get("FLASK_ENV") == "testing":
        # Still reject direct IP literals that are private
        try:
            if is_private_or_restricted_ip(hostname_lower):
                return False, "Target resolves to a private or restricted IP address."
        except Exception:
            pass
        return True, ""

    # Live DNS resolution SSRF verification
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if is_private_or_restricted_ip(ip_str):
                return False, f"Target resolves to a restricted IP address ({ip_str})."
    except socket.gaierror:
        # Host cannot be resolved right now
        return False, f"Could not resolve host '{hostname}'. Please check domain spelling."
    except Exception as exc:
        return False, f"URL validation error: {str(exc)}"

    return True, ""


def check_website_health(url: str, timeout: Optional[int] = None) -> Dict[str, Any]:
    """
    Perform a live HTTP request to check website availability, response time, and status code.
    Returns:
        status: 'online' or 'offline'
        status_code: int or None
        response_time_ms: float or None
        error_message: str or None
    """
    if timeout is None:
        try:
            timeout = int(os.environ.get("REQUEST_TIMEOUT", DEFAULT_TIMEOUT))
        except ValueError:
            timeout = DEFAULT_TIMEOUT

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; WebsiteHealthMonitor/1.0; +https://github.com/website-health-monitor)",
        "Accept": "*/*",
    }

    start_time = time.perf_counter()
    try:
        # Note: requests.get will follow standard redirects
        response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Requirement 6: Mark website Online when a valid HTTP response is received,
        # including HTTP error responses such as 404 or 500.
        return {
            "status": "online",
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "error_message": None,
        }

    except requests.exceptions.Timeout:
        return {
            "status": "offline",
            "status_code": None,
            "response_time_ms": None,
            "error_message": f"Connection timed out after {timeout} seconds",
        }
    except requests.exceptions.SSLError as exc:
        return {
            "status": "offline",
            "status_code": None,
            "response_time_ms": None,
            "error_message": f"SSL/TLS Certificate verification failed: {str(exc).splitlines()[0]}",
        }
    except requests.exceptions.ConnectionError as exc:
        return {
            "status": "offline",
            "status_code": None,
            "response_time_ms": None,
            "error_message": "Connection failed / host unreachable or DNS failure",
        }
    except requests.exceptions.RequestException as exc:
        return {
            "status": "offline",
            "status_code": None,
            "response_time_ms": None,
            "error_message": f"Request failed: {str(exc).splitlines()[0]}",
        }
    except Exception as exc:
        return {
            "status": "offline",
            "status_code": None,
            "response_time_ms": None,
            "error_message": f"Unexpected error: {str(exc)}",
        }


def check_and_update_website(
    website_id: int,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Perform a health check on a specific website, update its state in the database,
    log the health check record, and trigger alerts if a state transition occurs.
    """
    website = get_website_by_id(website_id, db_path)
    if not website:
        return None

    previous_status = website["status"]
    url = website["url"]
    name = website["name"]

    # Perform actual HTTP health check
    check_result = check_website_health(url)
    new_status = check_result["status"]
    status_code = check_result["status_code"]
    response_time_ms = check_result["response_time_ms"]
    error_message = check_result["error_message"]

    # Record historical check in SQLite
    record_health_check(
        website_id=website_id,
        status=new_status,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error_message=error_message,
        db_path=db_path,
    )

    # Update website's current snapshot in SQLite
    update_website_status(
        website_id=website_id,
        status=new_status,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error_message=error_message,
        db_path=db_path,
    )

    # State transition alert logic
    # 1. Online -> Offline transition => Downtime alert
    if previous_status == "online" and new_status == "offline":
        trigger_alert(
            website_id=website_id,
            website_name=name,
            website_url=url,
            alert_type="downtime",
            status_code=status_code,
            error_message=error_message,
            response_time_ms=response_time_ms,
            db_path=db_path,
        )
    # 2. Offline -> Online transition => Recovery alert
    elif previous_status == "offline" and new_status == "online":
        trigger_alert(
            website_id=website_id,
            website_name=name,
            website_url=url,
            alert_type="recovery",
            status_code=status_code,
            error_message=error_message,
            response_time_ms=response_time_ms,
            db_path=db_path,
        )

    return get_website_by_id(website_id, db_path)


def check_all_websites(db_path: Optional[str] = None) -> list:
    """Check all active monitored websites sequentially."""
    websites = get_websites(db_path)
    results = []
    for site in websites:
        res = check_and_update_website(site["id"], db_path)
        if res:
            results.append(res)
    return results
