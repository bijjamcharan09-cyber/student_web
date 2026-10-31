"""
Entry point to run the Student Management System Flask application.
"""

import os
from app import create_app

env = os.getenv("FLASK_ENV", "development").strip().lower()
app = create_app(config_name=env)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # Production must NEVER enable debug mode
    if env == "production":
        debug = False
    else:
        # Default debug to disabled unless explicitly set to 1 or true
        debug = os.getenv("FLASK_DEBUG", "0").strip().lower() in ("1", "true")

    # Configurable bind address (default 127.0.0.1 for local dev, or explicit HOST env)
    default_host = "127.0.0.1" if debug else "0.0.0.0"
    host = os.getenv("HOST", default_host)

    print(f"Starting Student Management System server on {host}:{port} (env: {env}, debug: {debug})...")
    app.run(host=host, port=port, debug=debug)
