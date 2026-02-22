from models import db
from datetime import datetime

# Junction table
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)


class Permission(db.Model):
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    module = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'module': self.module,
            'action': self.action,
            'description': self.description
        }


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    factory_id = db.Column(db.Integer, db.ForeignKey('factories.id', ondelete='CASCADE'))
    is_system_role = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles', lazy='subquery')
    users = db.relationship('User', backref='role', lazy='dynamic')

    def to_dict(self, include_permissions=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'factory_id': self.factory_id,
            'is_system_role': self.is_system_role,
            'user_count': self.users.count(),
            'created_at': self.created_at.isoformat()
        }
        if include_permissions:
            data['permissions'] = [p.to_dict() for p in self.permissions]
        return data

    def has_permission(self, permission_name):
        return any(p.name == permission_name for p in self.permissions)
