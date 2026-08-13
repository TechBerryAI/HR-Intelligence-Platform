"""WSGI entry point for the Flask application."""
import os
import sys

os.environ['HCIP_PROCESS_ROLE'] = 'web'

from app.bootstrap.create_app import create_app

app = create_app()

if __name__ == '__main__':
    from app.config.env_validator import is_production_like

    if is_production_like():
        print(
            "[SERVER] Refusing the Flask builtin server in production.\n"
            "Migrate once, then start Gunicorn:\n"
            "  cd apps/backend\n"
            "  HCIP_PROCESS_ROLE=migrate alembic upgrade head\n"
            "  MIGRATIONS_ALREADY_APPLIED=true gunicorn -c gunicorn.conf.py wsgi:app"
        )
        sys.exit(1)

    port = int(os.getenv('PORT', '3000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    use_reloader = debug_mode and os.getenv('FLASK_USE_RELOADER', 'false').lower() == 'true'

    print(f"[SERVER] Starting Flask server on port {port}...")
    print(f"[SERVER] Debug mode: {debug_mode}, Reloader: {use_reloader}")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=use_reloader,
        threaded=True,
    )
