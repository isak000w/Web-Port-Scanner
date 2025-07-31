# routes/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        flash('Invalid username or password', 'error')
        return redirect(url_for('auth.login'))
    login_user(user)
    return redirect(url_for('main.index'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))