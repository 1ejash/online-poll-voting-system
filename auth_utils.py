import re
import secrets
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort

GMAIL_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9.]{4,28}[a-z0-9])?@gmail\.com$")

def is_valid_gmail(email: str) -> tuple[bool, str]:
    """
    Validate that an email is an authentic @gmail.com address adhering
    strictly to Google Gmail address standards:
    - Must end with @gmail.com (case-insensitive).
    - Username length between 6 and 30 characters.
    - Characters allowed: letters (a-z), numbers (0-9), and periods (.).
    - Cannot start or end with a period.
    - Cannot contain consecutive periods (..).
    """
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    
    email = email.strip().lower()
    
    if not email.endswith("@gmail.com"):
        return False, "Access restricted: Only genuine @gmail.com accounts are permitted."
    
    parts = email.split("@")
    if len(parts) != 2:
        return False, "Invalid email format."
    
    username = parts[0]
    
    if len(username) < 6:
        return False, "Gmail username must be at least 6 characters long."
    
    if len(username) > 30:
        return False, "Gmail username cannot exceed 30 characters."
    
    if username.startswith(".") or username.endswith("."):
        return False, "Gmail username cannot begin or end with a period."
    
    if ".." in username:
        return False, "Gmail username cannot contain consecutive periods."
    
    if not GMAIL_REGEX.match(email):
        return False, "Gmail username contains invalid characters. Only letters (a-z), numbers (0-9), and single dots are allowed."
    
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password meets minimum safety criteria."""
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    return True, ""


def get_csrf_token() -> str:
    """Generate or retrieve a per-session CSRF token."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(24)
    return session["_csrf_token"]


def validate_csrf_token(token: str) -> bool:
    """Validate submitted CSRF token against session token."""
    session_token = session.get("_csrf_token")
    if not session_token or not token:
        return False
    return secrets.compare_digest(session_token, token)


def login_required(view_func):
    """Decorator to require an authenticated voter or admin session."""
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in with your Gmail account to continue.", "warning")
            return redirect(url_for("user_login", next=request.path))
        return view_func(*args, **kwargs)
    return decorated_view


def admin_required(view_func):
    """Decorator to require an admin session."""
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Admin login required to access this area.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        if session.get("user_role") != "admin":
            flash("Unauthorized access. Admin privileges required.", "danger")
            return redirect(url_for("polls"))
        return view_func(*args, **kwargs)
    return decorated_view
