import os
from flask import Flask, g
from extensions import db, migrate, login_manager, socketio, scheduler
from models import User


# import blueprints
from routes.main    import main_bp
from routes.auth    import auth_bp
from routes.scan    import scan_bp
from routes.history import history_bp
from routes.export  import export_bp
from routes.view    import view_bp
from routes.health  import health_bp
from routes.schedule import schedule_bp

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # 1) load default config from config.py
    app.config.from_object('config.Config')
    # 2) override with instance/config.py if present
    app.config.from_pyfile('config.py', silent=True)

    # initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    socketio.init_app(app)
    scheduler.start()

    # Flask-Login config
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        # our PKs are ints
        try:
            return User.query.get(int(user_id))
        except (ValueError, TypeError):
            return None


    # seed admin on first request
    @app.before_request
    def _seed_admin_once():
        from flask import g
        if not getattr(g, '_admin_seeded', False):
            if not User.query.filter_by(username='admin').first():
                admin = User(
                    username='admin',
                    email='admin@example.com'
                )
                admin.set_password('pass')
                db.session.add(admin)
                db.session.commit()
            g._admin_seeded = True

    # register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(view_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(schedule_bp, url_prefix='/schedule')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    return app

if __name__ == '__main__':
    socketio.run(
        create_app(),
        host='0.0.0.0',
        port=5002,
        debug=True
    )