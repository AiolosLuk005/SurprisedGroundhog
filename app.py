# -*- coding: utf-8 -*-
from flask import Flask
from api.routes import bp as api_bp
from core.config import PORT

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.register_blueprint(api_bp)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=PORT, debug=True)
