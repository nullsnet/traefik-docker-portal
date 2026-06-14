from flask import Blueprint

def register_blueprints(app):
    from routes.index import index_bp
    from routes.api import api_bp
    from routes.favicon import favicon_bp
    app.register_blueprint(index_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(favicon_bp)
