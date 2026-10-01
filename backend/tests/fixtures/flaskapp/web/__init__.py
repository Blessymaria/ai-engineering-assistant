from flask import Flask


def create_app():
    app = Flask(__name__)
    from web.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    from web.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    return app
