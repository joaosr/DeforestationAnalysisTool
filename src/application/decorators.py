"""
decorators.py

Decorators for URL handlers

"""

from functools import wraps
from google.appengine.api import users, oauth
from flask import redirect, request, render_template
from models import User
import logging

scope = 'https://www.googleapis.com/auth/userinfo.email'

def login_required(func):
    """Requires standard login credentials"""
    @wraps(func)
    def decorated_view(*args, **kwargs):
        user = oauth.get_current_user(scope)
        if not User.get_user(user):
            #login_url = users.create_login_url(request.url)
            #return render_template('login.html', login_url=login_url)
            return render_template('login.html')
        return func(*args, **kwargs)

    return decorated_view


def admin_required(func):
    """Requires App Engine admin credentials"""
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.is_current_user_admin():
            return redirect(users.create_login_url(request.url))
        return func(*args, **kwargs)
    return decorated_view

