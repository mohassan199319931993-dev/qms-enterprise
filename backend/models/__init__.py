"""
QMS Enterprise — Database Extensions
Single source of truth for db and bcrypt instances.
Import from here everywhere — never from app.py
"""
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()
