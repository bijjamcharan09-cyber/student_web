"""
Entry point to run the Student Management System Flask application.
"""

import os
from app import create_app

env = os.getenv("FLASK_ENV", "development")
app = create_app(config_name=env)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"Starting Student Management System server on port {port} (env: {env})...")
    app.run(host="0.0.0.0", port=port, debug=debug)
