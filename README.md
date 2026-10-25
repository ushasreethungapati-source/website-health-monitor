# Website Health Monitor with Auto-Alerts

A modern, full-stack website health and uptime monitoring web application with real-time analytics, automated periodic background checking, response time tracking, and instant email alerting on downtime and recovery transitions.

Designed for college project demonstrations, personal homelabs, and production service monitoring.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Immediate vs. Configured Features](#-immediate-vs-configured-features)
- [Technology Stack](#-technology-stack)
- [Project Directory Structure](#-project-directory-structure)
- [Prerequisites](#-prerequisites)
- [Installation & Setup (Windows PowerShell)](#-installation--setup-windows-powershell)
- [Running the Application](#-running-the-application)
- [Running Automated Tests](#-running-automated-tests)
- [Configuring Real Email Alerts (SMTP)](#-configuring-real-email-alerts-smtp)
- [Configuration & Environment Variables](#-configuration--environment-variables)
- [Database & Retention Policy](#-database--retention-policy)
- [Security & SSRF Protections](#-security--ssrf-protections)
- [Known Limitations](#-known-limitations)

---

## 🌟 Overview

**Website Health Monitor with Auto-Alerts** provides a clean, responsive SaaS administration dashboard inspired by modern cloud monitoring platforms. Users can add websites and API endpoints to track availability, latency (in milliseconds), HTTP status codes, and historical performance.

A lightweight, non-blocking background scheduler continuously verifies registered sites. When an active site goes down or recovers, the system logs the incident to a local SQLite database and optionally sends an alert email via SMTP.

---

## 🚀 Key Features

- **Real-Time Health Status Tracking**: Live detection of online vs. offline states with animated pulsing badges.
- **Accurate Latency Measurement**: High-precision HTTP response time measurement recorded in milliseconds (`time.perf_counter`).
- **HTTP Code Audit**: Displays HTTP response codes (e.g. 200, 301, 404, 500) and error messages (DNS failure, timeouts, SSL handshake errors).
- **Interactive Response Time Trends**: Chart.js spline line chart visualizing historical latency over time with site-specific filtering.
- **On-Demand Manual Health Checks**: Instant single-site ("Check") and batch ("Check All Now") health checks with loading indicators.
- **Downtime & Recovery Transitions**: Detects state changes (`online` &rarr; `offline` and `offline` &rarr; `online`).
- **Suppression of Duplicate Alerts**: Prevents continuous notification spam while a website remains offline.
- **Automated Background Monitoring**: Daemon thread scheduler checks websites periodically without freezing the web interface.
- **SSRF & Host Protections**: Strict backend URL safety checks block `localhost`, loopback, internal RFC 1918 IPs, and cloud metadata endpoints (`169.254.169.254`).
- **Automated Data Retention**: Auto-prunes health check history older than a configurable retention period (default 30 days).
- **Responsive SaaS UI**: Dark navy sidebar (`#0f172a`), crisp white workspace, metric summary cards, custom modal dialogs, and toast notifications.

---

## ⚡ Immediate vs. Configured Features

| Feature | Status Out-of-the-Box | Requirements |
| :--- | :--- | :--- |
| Web Dashboard UI | ✅ Works immediately | Python & dependencies installed |
| Adding & Removing Sites | ✅ Works immediately | Valid public HTTP/HTTPS URL |
| Health Checks (Online/Offline) | ✅ Works immediately | Internet connectivity |
| Latency Measurement & Charts | ✅ Works immediately | Chart.js loaded via CDN |
| SQLite Database Persistence | ✅ Works immediately | Created automatically at `instance/health_monitor.db` |
| Background Periodic Checks | ✅ Works immediately | Defaults to 60-second cycle |
| Alert History Logging | ✅ Works immediately | Logged to database and displayed in UI |
| **Real Email Alerts Dispatch** | ⚠️ Requires configuration | Set SMTP credentials in `.env` |

> [!NOTE]
> If SMTP credentials are not configured, monitoring operates normally. The UI displays an informative status banner and records all alert events with status `skipped_no_smtp`.

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, Vanilla CSS3 (Custom SaaS design system with CSS variables), JavaScript (Fetch API, DOM manipulation).
- **Charts**: [Chart.js 4.4](https://www.chartjs.org/) (loaded via jsDelivr CDN).
- **Backend**: Python 3.10+ with [Flask 3](https://flask.palletsprojects.com/).
- **HTTP Engine**: [Python Requests](https://requests.readthedocs.io/) with configurable timeouts and custom User-Agent.
- **Database**: SQLite with `PRAGMA foreign_keys = ON` and indexed queries.
- **Scheduler**: Python standard library `threading.Thread` daemon worker with Werkzeug reloader guards.
- **Testing**: [pytest 8+](https://docs.pytest.org/) with isolated in-memory/temporary SQLite databases and mocked network/SMTP calls.

---

## 📁 Project Directory Structure

```text
Website-Health-Monitor/
├── .env.example              # Sample environment configuration template
├── README.md                 # Complete project documentation
├── requirements.txt          # Python dependency specifications
├── app.py                    # Flask application factory, routes, and entry point
├── database.py               # SQLite schema creation, CRUD queries, and pruning
├── monitor.py                # Health checking logic, latency timer, and SSRF guard
├── alerts.py                 # State transition alerts and SMTP email dispatcher
├── scheduler.py              # Background daemon thread scheduler
├── static/
│   ├── style.css             # SaaS dashboard stylesheet, colors, and responsive grid
│   └── script.js             # Client-side API integration, Chart.js, modals, and toasts
├── templates/
│   └── index.html            # Main dashboard HTML template
├── tests/
│   └── test_app.py           # Automated unit and integration test suite (18 tests)
└── instance/                 # Dedicated directory created automatically at runtime
    └── health_monitor.db     # Persistent SQLite database file
```

---

## 💻 Prerequisites

- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Python 3.10, 3.11, 3.12, or 3.13.
- **PowerShell**: Built-in Windows PowerShell or PowerShell 7.

---

## ⚙️ Installation & Setup (Windows PowerShell)

Open Windows PowerShell in the project directory:

```powershell
# 1. Verify Python is installed and accessible
python --version

# 2. (Recommended) Create a virtual environment
python -m venv venv

# 3. Activate the virtual environment
.\venv\Scripts\Activate.ps1
# Note: If script execution is restricted on Windows, run:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4. Install all required dependencies
pip install -r requirements.txt

# 5. Create a local environment configuration file
Copy-Item .env.example .env
```

---

## 🚀 Running the Application

### Starting the Flask Server

With your virtual environment activated:

```powershell
python app.py
```

You should see output similar to:
```text
=======================================================
  Website Health Monitor with Auto-Alerts
  Server running at: http://127.0.0.1:5000
=======================================================
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Running Automated Tests

The application includes an automated test suite covering homepage rendering, input validation, SSRF blocking, CRUD operations, on-demand checks, history recording, downtime/recovery transitions, and SMTP mocking:

```powershell
# Run the complete test suite
python -m pytest -v
```

Expected output:
```text
tests/test_app.py::test_homepage_loads PASSED                            [  5%]
tests/test_app.py::test_add_valid_website PASSED                         [ 11%]
tests/test_app.py::test_add_duplicate_website_rejected PASSED            [ 16%]
tests/test_app.py::test_reject_invalid_urls PASSED                       [ 22%]
tests/test_app.py::test_reject_ssrf_and_private_ips PASSED               [ 27%]
tests/test_app.py::test_list_websites PASSED                             [ 33%]
tests/test_app.py::test_remove_website PASSED                            [ 38%]
tests/test_app.py::test_check_website_on_demand PASSED                   [ 44%]
tests/test_app.py::test_check_all_websites PASSED                        [ 50%]
tests/test_app.py::test_monitoring_history_recording PASSED              [ 55%]
tests/test_app.py::test_dashboard_summary_statistics PASSED              [ 61%]
tests/test_app.py::test_downtime_and_recovery_alert_transitions PASSED   [ 66%]
tests/test_app.py::test_alert_when_smtp_not_configured PASSED            [ 72%]
tests/test_app.py::test_alert_when_smtp_is_configured PASSED             [ 77%]
tests/test_app.py::test_system_status_endpoint PASSED                    [ 83%]
tests/test_app.py::test_http_500_is_considered_online PASSED             [ 88%]
tests/test_app.py::test_cascade_deletion_cleans_history PASSED           [ 94%]
tests/test_app.py::test_prune_old_history PASSED                         [100%]

============================= 18 passed in ~2.5s ==============================
```

---

## 📧 Configuring Real Email Alerts (SMTP)

To receive real email notifications whenever a website transitions from Online to Offline or recovers, configure your SMTP server credentials in `.env`:

### Gmail Configuration Example

1. Go to your **Google Account** &rarr; **Security** &rarr; Enable **2-Step Verification**.
2. Under "2-Step Verification", generate an **App Password** (Select App: "Mail", Device: "Windows Computer").
3. Edit your `.env` file:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_16_digit_app_password
ALERT_FROM_EMAIL=your_email@gmail.com
ALERT_TO_EMAIL=recipient_email@gmail.com
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

### Outlook / Office 365 Example

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=your_email@outlook.com
SMTP_PASS=your_app_password
ALERT_FROM_EMAIL=your_email@outlook.com
ALERT_TO_EMAIL=admin@yourdomain.com
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

Restart the Flask server after modifying `.env`. The sidebar indicator will turn green and read `Email: Active`.

---

## 🔧 Configuration & Environment Variables

All settings can be customized via the `.env` file:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `CHECK_INTERVAL` | `60` | Background monitoring interval in seconds (minimum 10s). |
| `REQUEST_TIMEOUT` | `8` | Maximum seconds to wait for an HTTP response before marking offline. |
| `HISTORY_RETENTION_DAYS` | `30` | Number of days to retain historical check records in SQLite. |
| `MAX_WEBSITES` | `50` | Maximum number of monitored websites allowed. |
| `PORT` | `5000` | Port for the Flask web server. |
| `HOST` | `127.0.0.1` | Network interface to bind. |
| `SECRET_KEY` | `dev-key` | Flask session secret key. |

---

## 🗄️ Database & Retention Policy

- **Location**: `instance/health_monitor.db`
- **Schema**:
  - `websites`: Stores website metadata, target URL, display name, current status, last status code, and latency.
  - `health_checks`: Logs every individual health check attempt with timestamp, HTTP status code, latency, and error details.
  - `alerts`: Logs downtime and recovery events, timestamp, delivery status (`sent`, `failed`, `skipped_no_smtp`), and delivery errors.
- **Retention**: To prevent unbounded database growth, records older than `HISTORY_RETENTION_DAYS` (default 30 days) are pruned once per 24-hour cycle by the background worker.

---

## 🛡️ Security & SSRF Protections

To protect the host machine and internal networks from Server-Side Request Forgery (SSRF):
1. **Scheme Validation**: Only `http://` and `https://` schemes are accepted.
2. **Localhost & Internal Names**: Rejects `localhost`, `*.localhost`, `*.local`, `*.internal`, and `*.lan`.
3. **Cloud Metadata Endpoints**: Rejects AWS/GCP/Azure link-local addresses (`169.254.169.254`, `metadata.google.internal`).
4. **DNS Resolution Verification**: Performs live DNS lookups via `socket.getaddrinfo` and evaluates resolved IPs with Python's standard `ipaddress` module to reject private (RFC 1918), loopback, link-local, and reserved IP ranges.
5. **SQL Injection Defense**: Uses parameterized SQL queries (`?`) exclusively.

---

## ⚠️ Known Limitations

1. **Simulated Email Mode**: When SMTP credentials are not configured in `.env`, email dispatch is skipped and logged to SQLite as `skipped_no_smtp` so monitoring remains uninterrupted.
2. **Network Firewalls**: If your local network or ISP blocks outbound SMTP ports (e.g. port 25 or 587), use TLS on port 587 or SSL on port 465.
3. **Headless Browser Automated Tests**: Microsoft Playwright browser binaries may encounter corporate firewall/network restrictions when attempting to download third-party browser drivers; all functionality is tested via unit/integration tests and Python test clients.

---

## 🎓 College Presentation Demo Guide

1. **Start the App**: Run `python app.py` and open `http://127.0.0.1:5000`.
2. **Explain the Architecture**:
   - Flask REST API + SQLite backend.
   - Background daemon thread scheduler for non-blocking periodic checks.
   - Dynamic Chart.js and Vanilla CSS SaaS dashboard on frontend.
3. **Live Demonstration**:
   - Add a fast website like `https://example.com` &rarr; observe immediate 200 OK status and latency card.
   - Add an API like `https://httpbin.org` &rarr; click "Check All Now" and demonstrate live batch checking.
   - Demonstrate the Response Time chart updating dynamically.
   - Explain how SSRF protection blocks inputs like `http://127.0.0.1` or `http://localhost`.
   - Point out the honest SMTP status banner and explain how email alerting transitions work.
4. **Run Tests**: Run `python -m pytest -v` in the terminal to show all 18 automated tests passing cleanly.
