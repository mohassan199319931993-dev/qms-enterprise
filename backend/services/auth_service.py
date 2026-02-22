"""
Authentication Service Layer — QMS Enterprise
Handles all auth business logic: login, register, tokens, password reset.
"""
import secrets
from datetime import datetime, timedelta
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token

from models import db, bcrypt
from models.user_model import User, PasswordReset, RefreshToken, AuditLog
from models.factory_model import Factory
from models.role_model import Role


class AuthService:

    @staticmethod
    def login(email: str, password: str, ip_address: str = None) -> dict:
        """Authenticate user, return tokens + user data."""
        user = User.query.filter_by(email=email.lower().strip()).first()

        if not user:
            raise ValueError('Invalid credentials')

        if user.is_locked():
            remaining = max(0, (user.locked_until - datetime.utcnow()).seconds // 60)
            raise PermissionError(f'Account locked. Try again in {remaining} minutes')

        if not bcrypt.check_password_hash(user.password_hash, password):
            user.login_attempts = (user.login_attempts or 0) + 1
            max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)

            if user.login_attempts >= max_attempts:
                lockout_minutes = current_app.config.get('LOCKOUT_DURATION_MINUTES', 15)
                user.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
                db.session.commit()
                raise PermissionError(f'Account locked for {lockout_minutes} minutes')

            db.session.commit()
            raise ValueError('Invalid credentials')

        if not user.is_active:
            raise PermissionError('Account is deactivated')

        # Reset on success
        user.login_attempts = 0
        user.locked_until   = None
        user.last_login      = datetime.utcnow()
        db.session.commit()

        # Build JWT with extra claims so frontend can decode user info directly
        additional_claims = {
            'name':         user.name,
            'email':        user.email,
            'factory_id':   user.factory_id,
            'factory_name': user.factory.name if user.factory else '',
            'role_name':    user.role.name if user.role else '',
        }

        access_token  = create_access_token(identity=str(user.id), additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=str(user.id))

        expires_at = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        db.session.add(RefreshToken(user_id=user.id, token=refresh_token, expires_at=expires_at))
        db.session.commit()

        AuthService._log(user.id, 'login_success', 'auth', {}, ip_address, user.factory_id)

        return {
            'access_token':  access_token,
            'refresh_token': refresh_token,
            'user':          user.to_dict()
        }

    @staticmethod
    def register(name: str, email: str, password: str, factory_id: int,
                 ip_address: str = None) -> dict:
        """Register new user in existing factory."""
        email = email.lower().strip()

        if User.query.filter_by(email=email).first():
            raise ValueError('Email already registered')

        factory = Factory.query.get(factory_id)
        if not factory or not factory.is_active:
            raise ValueError('Factory not found or inactive')

        role = Role.query.filter_by(factory_id=factory_id, name='Viewer').first() \
            or Role.query.filter_by(factory_id=factory_id).first()

        user = User(
            name=name.strip(),
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            role_id=role.id if role else None,
            factory_id=factory_id,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        additional_claims = {
            'name':         user.name,
            'email':        user.email,
            'factory_id':   user.factory_id,
            'factory_name': factory.name,
            'role_name':    role.name if role else '',
        }
        access_token  = create_access_token(identity=str(user.id), additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=str(user.id))

        expires_at = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        db.session.add(RefreshToken(user_id=user.id, token=refresh_token, expires_at=expires_at))
        db.session.commit()

        AuthService._log(user.id, 'user_registered', 'auth', {'email': email}, ip_address, factory_id)

        return {
            'access_token':  access_token,
            'refresh_token': refresh_token,
            'user':          user.to_dict()
        }

    @staticmethod
    def admin_register(factory_name: str, location: str, subscription_plan: str,
                       admin_name: str, admin_email: str, password: str,
                       ip_address: str = None) -> dict:
        """Register new factory + admin user."""
        admin_email = admin_email.lower().strip()

        if User.query.filter_by(email=admin_email).first():
            raise ValueError('Email already registered')

        factory = Factory(
            name=factory_name.strip(),
            location=location.strip() if location else None,
            subscription_plan=subscription_plan or 'basic'
        )
        db.session.add(factory)
        db.session.flush()

        # Default roles
        roles_data = [
            ('Admin',           'Full system access',          True),
            ('Quality Manager', 'Quality management access',   False),
            ('Inspector',       'Inspection and data entry',   False),
            ('Viewer',          'Read-only access',            False),
        ]
        admin_role = None
        for rname, rdesc, rsys in roles_data:
            role = Role(name=rname, description=rdesc, factory_id=factory.id, is_system_role=rsys)
            db.session.add(role)
            if rname == 'Admin':
                admin_role = role
        db.session.flush()

        admin_user = User(
            name=admin_name.strip(),
            email=admin_email,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            role_id=admin_role.id,
            factory_id=factory.id,
            is_active=True,
            email_verified=True,
        )
        db.session.add(admin_user)
        db.session.commit()

        additional_claims = {
            'name':         admin_user.name,
            'email':        admin_user.email,
            'factory_id':   factory.id,
            'factory_name': factory.name,
            'role_name':    'Admin',
        }
        access_token  = create_access_token(identity=str(admin_user.id), additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=str(admin_user.id))

        expires_at = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        db.session.add(RefreshToken(user_id=admin_user.id, token=refresh_token, expires_at=expires_at))
        db.session.commit()

        AuthService._log(admin_user.id, 'admin_registered', 'auth',
                         {'factory': factory_name}, ip_address, factory.id)

        return {
            'access_token':  access_token,
            'refresh_token': refresh_token,
            'user':          admin_user.to_dict(),
            'factory':       factory.to_dict()
        }

    @staticmethod
    def refresh_tokens(refresh_token_str: str, ip_address: str = None) -> dict:
        """Rotate refresh token, issue new access token."""
        db_token = RefreshToken.query.filter_by(token=refresh_token_str).first()

        if not db_token or not db_token.is_valid():
            raise PermissionError('Invalid or expired refresh token')

        user = User.query.get(db_token.user_id)
        if not user or not user.is_active:
            raise PermissionError('User not found or inactive')

        db_token.revoked = True

        additional_claims = {
            'name':         user.name,
            'email':        user.email,
            'factory_id':   user.factory_id,
            'factory_name': user.factory.name if user.factory else '',
            'role_name':    user.role.name if user.role else '',
        }
        access_token  = create_access_token(identity=str(user.id), additional_claims=additional_claims)
        new_refresh   = create_refresh_token(identity=str(user.id))

        expires_at = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        db.session.add(RefreshToken(user_id=user.id, token=new_refresh, expires_at=expires_at))
        db.session.commit()

        return {'access_token': access_token, 'refresh_token': new_refresh}

    @staticmethod
    def forgot_password(email: str, ip_address: str = None) -> str:
        user = User.query.filter_by(email=email.lower().strip()).first()
        if not user:
            return None

        PasswordReset.query.filter_by(user_id=user.id, used=False).update({'used': True})

        token = secrets.token_urlsafe(32)
        expires_hours = current_app.config.get('PASSWORD_RESET_EXPIRES_HOURS', 2)
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

        db.session.add(PasswordReset(user_id=user.id, token=token, expires_at=expires_at))
        db.session.commit()

        return token

    @staticmethod
    def reset_password(token: str, new_password: str, ip_address: str = None) -> bool:
        reset = PasswordReset.query.filter_by(token=token).first()
        if not reset or not reset.is_valid():
            raise ValueError('Invalid or expired reset token')

        user = User.query.get(reset.user_id)
        if not user:
            raise ValueError('User not found')

        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.login_attempts = 0
        user.locked_until   = None
        reset.used = True

        RefreshToken.query.filter_by(user_id=user.id).update({'revoked': True})
        db.session.commit()
        return True

    @staticmethod
    def _log(user_id, action, module, details, ip_address, factory_id):
        try:
            db.session.add(AuditLog(
                user_id=user_id, action=action, module=module,
                details=details, ip_address=ip_address, factory_id=factory_id
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
