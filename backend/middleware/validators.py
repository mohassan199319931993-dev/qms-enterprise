"""
Input Validation Middleware
"""
import re


EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
PASSWORD_MIN = 8


def validate_password_strength(password: str) -> str | None:
    if len(password) < PASSWORD_MIN:
        return f'Password must be at least {PASSWORD_MIN} characters'
    if not re.search(r'[A-Z]', password):
        return 'Password must contain at least one uppercase letter'
    if not re.search(r'[0-9]', password):
        return 'Password must contain at least one number'
    return None


def validate_login(data: dict) -> list:
    errors = []
    if not data:
        return ['Request body is required']
    if not data.get('email') or not EMAIL_RE.match(data['email']):
        errors.append('Valid email is required')
    if not data.get('password'):
        errors.append('Password is required')
    return errors


def validate_register(data: dict) -> list:
    errors = []
    if not data:
        return ['Request body is required']
    if not data.get('name') or len(data['name'].strip()) < 2:
        errors.append('Name must be at least 2 characters')
    if not data.get('email') or not EMAIL_RE.match(data['email']):
        errors.append('Valid email is required')
    if not data.get('password'):
        errors.append('Password is required')
    else:
        pw_err = validate_password_strength(data['password'])
        if pw_err:
            errors.append(pw_err)
    if data.get('confirm_password') and data['confirm_password'] != data['password']:
        errors.append('Passwords do not match')
    if not data.get('factory_id'):
        errors.append('Factory selection is required')
    return errors


def validate_admin_register(data: dict) -> list:
    errors = []
    if not data:
        return ['Request body is required']
    if not data.get('factory_name') or len(data['factory_name'].strip()) < 2:
        errors.append('Factory name must be at least 2 characters')
    if not data.get('admin_name') or len(data['admin_name'].strip()) < 2:
        errors.append('Admin name must be at least 2 characters')
    if not data.get('admin_email') or not EMAIL_RE.match(data['admin_email']):
        errors.append('Valid admin email is required')
    if not data.get('password'):
        errors.append('Password is required')
    else:
        pw_err = validate_password_strength(data['password'])
        if pw_err:
            errors.append(pw_err)
    if data.get('confirm_password') and data['confirm_password'] != data['password']:
        errors.append('Passwords do not match')
    return errors


def validate_forgot_password(data: dict) -> list:
    errors = []
    if not data:
        return ['Request body is required']
    if not data.get('email') or not EMAIL_RE.match(data['email']):
        errors.append('Valid email is required')
    return errors


def validate_reset_password(data: dict) -> list:
    errors = []
    if not data:
        return ['Request body is required']
    if not data.get('token'):
        errors.append('Reset token is required')
    if not data.get('password'):
        errors.append('Password is required')
    else:
        pw_err = validate_password_strength(data['password'])
        if pw_err:
            errors.append(pw_err)
    if data.get('confirm_password') and data['confirm_password'] != data['password']:
        errors.append('Passwords do not match')
    return errors
