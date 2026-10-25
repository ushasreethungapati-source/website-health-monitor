import os
import urllib.parse
from typing import Optional, Dict, Any
from flask import Flask, render_template, request, jsonify, abort
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

from database import (
    init_db,
    add_website,
    get_websites,
    get_website_by_id,
    get_website_by_url,
    delete_website,
    get_recent_checks,
    get_recent_alerts,
    get_summary_stats,
    get_db_path,
)
from monitor import (
    validate_url_safety,
    check_and_update_website,
    check_all_websites,
)
from alerts import get_smtp_config
from scheduler import (
    start_scheduler,
    is_scheduler_running,
    get_check_interval,
)


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    """Application factory for Flask app."""
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )

    # Configuration defaults
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "health-monitor-secret-key-default"),
        DATABASE_PATH=os.environ.get("DATABASE_PATH"),
        MAX_WEBSITES=int(os.environ.get("MAX_WEBSITES", 50)),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    # Initialize the SQLite database tables
    db_path = app.config.get("DATABASE_PATH")
    init_db(db_path)

    # Start the periodic background scheduler (unless in testing mode)
    if not app.config.get("TESTING") and os.environ.get("DISABLE_SCHEDULER") != "1":
        start_scheduler(db_path)

    # --------------------------------------------------------------------------
    # Frontend Routes
    # --------------------------------------------------------------------------
    @app.route("/")
    def index():
        """Serve the main health monitoring single-page dashboard."""
        return render_template("index.html")

    # --------------------------------------------------------------------------
    # API Routes
    # --------------------------------------------------------------------------

    @app.route("/api/summary", methods=["GET"])
    def api_summary():
        """Return aggregated statistics for dashboard summary cards."""
        stats = get_summary_stats(app.config.get("DATABASE_PATH"))
        return jsonify({"success": True, "data": stats})

    @app.route("/api/system-status", methods=["GET"])
    def api_system_status():
        """Return runtime configuration status including SMTP and scheduler interval."""
        smtp_cfg = get_smtp_config()
        return jsonify({
            "success": True,
            "data": {
                "smtp_configured": smtp_cfg["is_configured"],
                "smtp_host": smtp_cfg["host"] or None,
                "alert_recipient": smtp_cfg["to_email"] or None,
                "check_interval_seconds": get_check_interval(),
                "scheduler_running": is_scheduler_running(),
            },
        })

    @app.route("/api/websites", methods=["GET"])
    def api_get_websites():
        """Retrieve all currently monitored websites."""
        sites = get_websites(app.config.get("DATABASE_PATH"))
        return jsonify({"success": True, "data": sites, "count": len(sites)})

    @app.route("/api/websites", methods=["POST"])
    def api_add_website():
        """
        Add a new website to monitor.
        Accepts JSON: { "url": "https://...", "name": "Optional Name" }
        """
        data = request.get_json(silent=True) or {}
        raw_url = data.get("url", "").strip()
        custom_name = data.get("name", "").strip()

        if not raw_url:
            return jsonify({"success": False, "error": "Website URL is required."}), 400

        # Parse scheme and validate
        parsed = urllib.parse.urlparse(raw_url)
        if not parsed.scheme:
            raw_url = "https://" + raw_url
        elif parsed.scheme.lower() not in ("http", "https"):
            return jsonify({"success": False, "error": "Only HTTP and HTTPS URLs are permitted."}), 400

        # Validate URL syntax and SSRF protections
        is_safe, error_msg = validate_url_safety(raw_url)
        if not is_safe:
            return jsonify({"success": False, "error": error_msg}), 400

        # Enforce maximum monitored websites limit
        current_sites = get_websites(app.config.get("DATABASE_PATH"))
        max_sites = app.config.get("MAX_WEBSITES", 50)
        if len(current_sites) >= max_sites:
            return jsonify({
                "success": False,
                "error": f"Maximum limit of {max_sites} monitored websites reached.",
            }), 400

        # Derive display name from URL hostname if none provided
        parsed = urllib.parse.urlparse(raw_url)
        name = custom_name if custom_name else parsed.hostname

        try:
            site = add_website(url=raw_url, name=name, db_path=app.config.get("DATABASE_PATH"))
        except ValueError as err:
            return jsonify({"success": False, "error": str(err)}), 409

        # Trigger an immediate first health check
        updated_site = check_and_update_website(site["id"], db_path=app.config.get("DATABASE_PATH"))
        return jsonify({
            "success": True,
            "message": f"Website '{name}' added and checked successfully.",
            "data": updated_site or site,
        }), 201

    @app.route("/api/websites/<int:website_id>", methods=["DELETE"])
    def api_delete_website(website_id: int):
        """Remove a website and its health check/alert records from monitoring."""
        site = get_website_by_id(website_id, app.config.get("DATABASE_PATH"))
        if not site:
            return jsonify({"success": False, "error": f"Website #{website_id} not found."}), 404

        deleted = delete_website(website_id, app.config.get("DATABASE_PATH"))
        if deleted:
            return jsonify({
                "success": True,
                "message": f"Website '{site['name']}' was removed successfully.",
            })
        return jsonify({"success": False, "error": "Failed to remove website."}), 500

    @app.route("/api/websites/<int:website_id>/check", methods=["POST"])
    def api_check_website(website_id: int):
        """Perform an immediate on-demand health check for a single website."""
        site = get_website_by_id(website_id, app.config.get("DATABASE_PATH"))
        if not site:
            return jsonify({"success": False, "error": f"Website #{website_id} not found."}), 404

        result = check_and_update_website(website_id, app.config.get("DATABASE_PATH"))
        return jsonify({
            "success": True,
            "message": f"Check completed for '{site['name']}'.",
            "data": result,
        })

    @app.route("/api/websites/check-all", methods=["POST"])
    def api_check_all_websites():
        """Perform an immediate on-demand health check for all monitored websites."""
        results = check_all_websites(app.config.get("DATABASE_PATH"))
        return jsonify({
            "success": True,
            "message": f"Completed check for {len(results)} website(s).",
            "data": results,
        })

    @app.route("/api/websites/<int:website_id>/history", methods=["GET"])
    def api_website_history(website_id: int):
        """Retrieve historical checks for a specific website."""
        site = get_website_by_id(website_id, app.config.get("DATABASE_PATH"))
        if not site:
            return jsonify({"success": False, "error": f"Website #{website_id} not found."}), 404

        limit = request.args.get("limit", 50, type=int)
        history = get_recent_checks(website_id=website_id, limit=limit, db_path=app.config.get("DATABASE_PATH"))
        return jsonify({
            "success": True,
            "website": site,
            "data": history,
            "count": len(history),
        })

    @app.route("/api/history", methods=["GET"])
    def api_all_history():
        """Retrieve recent checks across all monitored websites."""
        limit = request.args.get("limit", 50, type=int)
        history = get_recent_checks(website_id=None, limit=limit, db_path=app.config.get("DATABASE_PATH"))
        return jsonify({
            "success": True,
            "data": history,
            "count": len(history),
        })

    @app.route("/api/alerts", methods=["GET"])
    def api_alerts():
        """Retrieve recent alert events."""
        limit = request.args.get("limit", 50, type=int)
        alerts_list = get_recent_alerts(limit=limit, db_path=app.config.get("DATABASE_PATH"))
        return jsonify({
            "success": True,
            "data": alerts_list,
            "count": len(alerts_list),
        })

    @app.route("/api/seed-demo", methods=["POST"])
    def api_seed_demo():
        """Populate database with sample websites, historical checks, and alerts for demo."""
        from seed_data import seed_database
        seed_database(app.config.get("DATABASE_PATH"))
        return jsonify({
            "success": True,
            "message": "Demo data successfully loaded! 6 websites, time-series history, and alerts added.",
        })

    # --------------------------------------------------------------------------
    # Error Handlers
    # --------------------------------------------------------------------------
    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Requested API endpoint not found."}), 404
        return render_template("index.html"), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        return jsonify({
            "success": False,
            "error": "Internal server error occurred.",
        }), 500

    return app


# Default app instance for Flask CLI / gunicorn / runner
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1")
    print(f"\n=======================================================")
    print(f"  Website Health Monitor with Auto-Alerts")
    print(f"  Server running at: http://{host}:{port}")
    print(f"=======================================================\n")
    app.run(host=host, port=port, debug=debug_mode)
