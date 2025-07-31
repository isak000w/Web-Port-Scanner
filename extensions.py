# extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_migrate    import Migrate
from flask_login      import LoginManager
from flask_socketio   import SocketIO

db            = SQLAlchemy()
migrate       = Migrate()
login_manager = LoginManager()
from apscheduler.schedulers.background import BackgroundScheduler
socketio      = SocketIO(async_mode='eventlet')
scheduler     = BackgroundScheduler()