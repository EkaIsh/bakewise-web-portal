from __future__ import annotations

import os

from dotenv import load_dotenv

# Load values from a local .env file before Flask reads the configuration.
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    # gunicorn handles serving in production (Render/Docker).
    # This branch is for local `python run.py` convenience only.
    host = app.config.get("HOST", "0.0.0.0")
    port = app.config.get("PORT", 5000)
    debug = app.config.get("DEBUG", False)
    app.run(host=host, port=port, debug=debug)
