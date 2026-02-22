"""
Seed Admin — Creates the default admin user at first startup.
Run: python seed_admin.py
Or call seed_admin() from app startup.
"""
import os
import sys

# Must be run from backend/ directory
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, bcrypt
from models.user_model import User
from models.factory_model import Factory
from models.role_model import Role


def seed_admin(
    factory_name='Demo Factory',
    location='Cairo, Egypt',
    plan='enterprise',
    admin_name='QMS Admin',
    admin_email='admin@qms.com',
    admin_password='Admin@123!'
):
    app, _ = create_app()
    with app.app_context():
        # Check if already exists
        existing = User.query.filter_by(email=admin_email).first()
        if existing:
            print(f"[seed] Admin {admin_email} already exists — skipping.")
            return

        # Get or create factory
        factory = Factory.query.get(1)
        if not factory:
            factory = Factory(
                id=1, name=factory_name,
                location=location, subscription_plan=plan
            )
            db.session.add(factory)
            db.session.flush()
            print(f"[seed] Created factory: {factory_name}")

        # Get Admin role
        role = Role.query.filter_by(factory_id=1, name='Admin').first()
        if not role:
            role = Role(name='Admin', description='Full system access',
                        factory_id=1, is_system_role=True)
            db.session.add(role)
            db.session.flush()
            print("[seed] Created Admin role")

        # Create admin user with proper bcrypt hash
        pw_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
        user = User(
            name=admin_name,
            email=admin_email,
            password_hash=pw_hash,
            role_id=role.id,
            factory_id=factory.id,
            is_active=True,
            email_verified=True,
        )
        db.session.add(user)
        db.session.commit()
        print(f"[seed] ✅ Admin created: {admin_email} / {admin_password}")


if __name__ == '__main__':
    seed_admin()
