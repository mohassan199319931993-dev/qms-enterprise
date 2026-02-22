from models import db
from datetime import datetime


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='SET NULL'), nullable=True)
    factory_id = db.Column(db.Integer, db.ForeignKey('factories.id', ondelete='CASCADE'))
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    password_resets = db.relationship('PasswordReset', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    refresh_tokens = db.relationship('RefreshToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def to_dict(self, include_role=True):
        data = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'factory_id': self.factory_id,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat()
        }
        if include_role and self.role:
            data['role'] = {
                'id': self.role.id,
                'name': self.role.name,
                'permissions': [p.name for p in self.role.permissions]
            }
        elif include_role:
            data['role'] = None

        if self.factory:
            data['factory'] = {
                'id': self.factory.id,
                'name': self.factory.name
            }
        return data

    def is_locked(self):
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def has_permission(self, permission_name):
        if self.role:
            return self.role.has_permission(permission_name)
        return False


class PasswordReset(db.Model):
    __tablename__ = 'password_resets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(255), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        return not self.used and self.expires_at > datetime.utcnow()


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.Text, nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        return not self.revoked and self.expires_at > datetime.utcnow()


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    module = db.Column(db.String(100))
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    factory_id = db.Column(db.Integer, db.ForeignKey('factories.id', ondelete='CASCADE'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'module': self.module,
            'details': self.details,
            'ip_address': self.ip_address,
            'factory_id': self.factory_id,
            'timestamp': self.timestamp.isoformat()
        }
