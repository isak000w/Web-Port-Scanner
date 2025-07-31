import os

# Base directory of the project
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # secret key for signing cookies / sessions
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # point at your SQLite file in instance/
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'scanner.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # APScheduler
    SCHEDULER_API_ENABLED = True
    DEFAULT_THREADS = 100
    DEFAULT_MODE    = 'Basic'