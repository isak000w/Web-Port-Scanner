import json
from datetime import datetime

from extensions import db
from flask_login import UserMixin


user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)


class Role(db.Model):
    __tablename__ = 'role'
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(32), unique=True, nullable=False)
    email         = db.Column(db.String(128), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    roles = db.relationship('Role', secondary=user_roles, backref='users')

    def set_password(self, pw):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(pw, method='scrypt')

    def check_password(self, pw):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, pw)


class ScanResult(db.Model):
    __tablename__ = 'scan_result'
    id           = db.Column(db.Integer, primary_key=True)
    target       = db.Column(db.String(100), nullable=False)
    ports        = db.Column(db.String(100), nullable=True)
    flags        = db.Column(db.String(200), nullable=True)
    mode         = db.Column(db.String(20),  nullable=False)
    status       = db.Column(db.String(20),  nullable=False, default='Pending')
    timestamp    = db.Column(db.DateTime,     default=datetime.utcnow, nullable=False)
    results_json = db.Column(db.Text,         nullable=True)

    # all the ChangeLog entries where this scan was the “new” scan
    changelogs   = db.relationship(
        'ChangeLog',
        backref='scan',
        foreign_keys='ChangeLog.scan_id'
    )


class ChangeLog(db.Model):
    __tablename__ = 'change_log'
    id               = db.Column(db.Integer, primary_key=True)
    scan_id          = db.Column(db.Integer, db.ForeignKey('scan_result.id'), nullable=False)
    previous_scan_id = db.Column(db.Integer, db.ForeignKey('scan_result.id'), nullable=True)
    diff             = db.Column(db.Text,    nullable=False)
    timestamp        = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    previous_scan = db.relationship(
        'ScanResult',
        foreign_keys=[previous_scan_id],
        backref='rescan_of'
    )