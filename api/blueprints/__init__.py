from flask import Blueprint

def register_blueprints(app):
    from .scan import bp as scan_bp
    from .keywords import bp as kw_bp
    from .ops import bp as ops_bp
    from .search import bp as search_bp
    from .auth import bp as auth_bp
    from .db_view import bp as db_bp
    from .db_save import bp as db_save_bp
    
    # Prefix all with /full as per original design
    app.register_blueprint(scan_bp, url_prefix="/full")
    app.register_blueprint(kw_bp, url_prefix="/full")
    app.register_blueprint(ops_bp, url_prefix="/full")
    app.register_blueprint(search_bp, url_prefix="/full")
    app.register_blueprint(auth_bp, url_prefix="/full")
    app.register_blueprint(db_bp, url_prefix="/db")
    app.register_blueprint(db_save_bp, url_prefix="/full")
