"""
Settle Up - Authentication & Authorization Layer
Provides secure token generation, validation, route protection decorators,
and strict input validation for email, password, and user profiles.
"""

import re
from functools import wraps
from flask import request, jsonify, current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from .models import db, User

# Token expiration: 7 days in seconds
DEFAULT_TOKEN_MAX_AGE = 7 * 24 * 60 * 60

# RFC 5322 compliant simplified email regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


def get_serializer():
    """Returns timed serializer initialized with Flask SECRET_KEY."""
    secret_key = current_app.config.get('SECRET_KEY', 'settleup-default-secret-key-2026')
    return URLSafeTimedSerializer(secret_key, salt='settleup-auth-token')


def generate_auth_token(user_id, email=None):
    """Generates a secure, signed time-stamped authentication token."""
    serializer = get_serializer()
    payload = {
        'user_id': str(user_id),
        'email': (email or '').strip().lower()
    }
    return serializer.dumps(payload)


def verify_auth_token(token, max_age=DEFAULT_TOKEN_MAX_AGE):
    """
    Verifies token validity and signature.
    Returns payload dict {'user_id': ..., 'email': ...} if valid, or None if invalid/expired.
    """
    if not token:
        return None
    serializer = get_serializer()
    try:
        payload = serializer.loads(token, max_age=max_age)
        return payload
    except (SignatureExpired, BadSignature, Exception):
        return None


def extract_token_from_request():
    """Extracts Bearer token from Authorization header or query param."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
    # Check X-Auth-Token header fallback
    x_token = request.headers.get('X-Auth-Token')
    if x_token:
        return x_token.strip()
    return None


def get_current_user_from_request():
    """Resolves and returns User ORM object for current request token, or None."""
    token = extract_token_from_request()
    if not token:
        return None
    payload = verify_auth_token(token)
    if not payload or 'user_id' not in payload:
        return None
    user = db.session.get(User, payload['user_id'])
    return user


def token_required(f):
    """Decorator to enforce authenticated session via Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = extract_token_from_request()
        if not token:
            return jsonify({
                'error': 'Authentication token is required',
                'status': 401,
                'code': 'UNAUTHORIZED'
            }), 401

        payload = verify_auth_token(token)
        if not payload or 'user_id' not in payload:
            return jsonify({
                'error': 'Invalid or expired authentication token',
                'status': 401,
                'code': 'INVALID_TOKEN'
            }), 401

        current_user = db.session.get(User, payload['user_id'])
        if not current_user:
            return jsonify({
                'error': 'Authenticated user no longer exists',
                'status': 401,
                'code': 'USER_NOT_FOUND'
            }), 401

        request.current_user = current_user
        return f(*args, **kwargs)
    return decorated


import time
import math
from collections import defaultdict

# Rate limiting storage: ip -> list of request timestamps
_rate_limit_records = defaultdict(list)


def rate_limit(max_requests=15, window_seconds=60):
    """
    Decorator for sliding-window IP rate limiting.
    Protects sensitive auth endpoints against brute force and credential stuffing.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if current_app and current_app.config.get('TESTING'):
                return f(*args, **kwargs)

            # Resolve client IP address (supporting X-Forwarded-For if behind reverse proxy/Vercel)
            client_ip = request.headers.get('X-Forwarded-For', getattr(request, 'remote_addr', None) or '127.0.0.1') or '127.0.0.1'
            if ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()

            now = time.time()
            cutoff = now - window_seconds

            timestamps = _rate_limit_records[client_ip]
            # Prune old timestamps
            _rate_limit_records[client_ip] = [t for t in timestamps if t > cutoff]

            if len(_rate_limit_records[client_ip]) >= max_requests:
                return jsonify({
                    'error': 'Too many requests. Please slow down and try again later.',
                    'status': 429,
                    'code': 'RATE_LIMITED'
                }), 429

            _rate_limit_records[client_ip].append(now)
            return f(*args, **kwargs)
        return decorated
    return decorator


def optional_auth(f):
    """Decorator that attaches current_user to request if valid token exists, but doesn't block unauthenticated requests."""
    @wraps(f)
    def decorated(*args, **kwargs):
        request.current_user = get_current_user_from_request()
        return f(*args, **kwargs)
    return decorated


# =========================================================================
# Input Validation & Sanitization Helpers
# =========================================================================

def validate_email(email):
    """Validates email format."""
    if not email or not isinstance(email, str):
        return False, "Email is required."
    clean = email.strip().lower()
    if len(clean) > 150:
        return False, "Email cannot exceed 150 characters."
    if not EMAIL_REGEX.match(clean):
        return False, "Invalid email address format."
    return True, clean


def validate_password(password):
    """Validates password strength (minimum 8 characters)."""
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password cannot exceed 128 characters."
    return True, password


def validate_name(name):
    """Validates user or member name."""
    if not name or not isinstance(name, str):
        return False, "Name is required."
    clean = name.strip()
    if len(clean) < 2:
        return False, "Name must be at least 2 characters long."
    if len(clean) > 120:
        return False, "Name cannot exceed 120 characters."
    return True, clean


def sanitize_str(val, max_len=100):
    """Trims string, strips null bytes and restricts maximum length."""
    if val is None:
        return None
    clean = str(val).replace('\x00', '').strip()
    return clean[:max_len] if clean else None


def parse_positive_finite_float(val, min_val=0.01, max_val=100_000_000.0):
    """
    Safely converts arbitrary input to a finite positive float within [min_val, max_val].
    Strictly rejects NaN, Infinity, -Infinity, negative numbers, or non-numeric types.
    Returns (float_value, is_valid, error_message).
    """
    if val is None:
        return 0.0, False, "Amount value is required."

    try:
        f_val = float(val)
    except (ValueError, TypeError):
        return 0.0, False, "Amount must be a valid numeric number."

    if math.isnan(f_val) or math.isinf(f_val):
        return 0.0, False, "Amount must be a valid finite number."

    if f_val < min_val:
        return 0.0, False, f"Amount must be at least {min_val:.2f}."

    if f_val > max_val:
        return 0.0, False, f"Amount exceeds maximum allowed limit of {max_val:,.2f}."

    return round(f_val, 2), True, None

