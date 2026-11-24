"""
VaultPay - Security Module
==========================
Input validation, audit logging, and helper utilities.
Demonstrates SSE Concept #2 (Input Validation) and #5 (Audit Logging).
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from database import get_connection

# Maximum single transaction: ₹50,000 = 5,000,000 paise
MAX_TRANSACTION_PAISE = 5_000_000


# ══════════════════════════════════════════════════════════════════
#  INPUT VALIDATION  (SSE Concept #2)
# ══════════════════════════════════════════════════════════════════

def validate_amount(amount_str):
    """
    Validate a monetary amount entered by the user.

    Returns
    -------
    (amount_in_paise : int | None, error_message : str | None)
        On success error_message is None; on failure amount_in_paise is None.
    """
    try:
        amount = Decimal(str(amount_str).strip())
    except (InvalidOperation, ValueError):
        return None, "Invalid amount format."

    if amount <= 0:
        return None, "Amount must be greater than zero."

    # Convert rupees -> paise (×100) using integer arithmetic
    amount_paise = int(amount * 100)

    if amount_paise <= 0:
        return None, "Amount must be greater than zero."

    if amount_paise > MAX_TRANSACTION_PAISE:
        return None, "Amount exceeds the maximum transaction limit of ₹50,000."

    return amount_paise, None


def validate_username(username):
    """Username: 3-30 chars, letters/digits/underscores only."""
    if not username or len(username.strip()) == 0:
        return False, "Username cannot be empty."
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(username) > 30:
        return False, "Username must not exceed 30 characters."
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores."
    return True, None


def validate_email(email):
    """Basic email format validation."""
    if not email or len(email.strip()) == 0:
        return False, "Email cannot be empty."
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email.strip()):
        return False, "Invalid email format."
    return True, None


def validate_password(password):
    """Password: ≥8 chars, at least one uppercase, one lowercase, one digit."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit."
    return True, None


def validate_pin(pin):
    """Transaction PIN: exactly 4–6 digits."""
    if not pin:
        return False, "Transaction PIN cannot be empty."
    if not re.match(r'^\d{4,6}$', pin):
        return False, "Transaction PIN must be 4 to 6 digits."
    return True, None


def validate_name(name):
    """Full name: at least 2 non-whitespace characters."""
    if not name or len(name.strip()) == 0:
        return False, "Name cannot be empty."
    if len(name.strip()) < 2:
        return False, "Name must be at least 2 characters."
    return True, None


# ══════════════════════════════════════════════════════════════════
#  DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════

def paise_to_rupees(paise):
    """Format an integer paise value as a readable ₹ string."""
    rupees = paise / 100
    return f"₹{rupees:,.2f}"


def rupees_float(paise):
    """Convert paise to a plain float (for table display)."""
    return paise / 100


# ══════════════════════════════════════════════════════════════════
#  AUDIT LOGGING  (SSE Concept #5)
# ══════════════════════════════════════════════════════════════════

def log_audit(user_id, action, details):
    """
    Record an audit-log entry.

    IMPORTANT — Never log passwords, PINs, or other authentication secrets.
    Audit logging failures are silently swallowed so they never break the
    main application flow.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, details, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, action, details, datetime.now().isoformat()),
        )
        conn.commit()
    except Exception:
        pass  # Logging must not break the application
    finally:
        conn.close()
