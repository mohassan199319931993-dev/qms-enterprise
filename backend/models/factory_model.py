from models import db
from datetime import datetime


class Factory(db.Model):
    __tablename__ = 'factories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150))
    subscription_plan = db.Column(db.String(50), default='basic')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='factory', lazy='dynamic')
    roles = db.relationship('Role', backref='factory', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'subscription_plan': self.subscription_plan,
            'is_active': self.is_active,
            'user_count': self.users.count(),
            'created_at': self.created_at.isoformat()
        }
