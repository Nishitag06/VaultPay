"""
VaultPay - Authentication Module
=================================
User registration, login, session management, and account security.
Demonstrates SSE Concept #1 (Authentication).
"""

import bcrypt
import secrets
from datetime import datetime
from database import get_connection
from security import (
    validate_username, validate_email, validate_password,
    validate_pin, validate_name, log_audit,
)

# Lock the account after this many consecutive failures
MAX_FAILED_ATTEMPTS = 5


# ══════════════════════════════════════════════════════════════════
#  PASSWORD / PIN HASHING  (bcrypt)
# ══════════════════════════════════════════════════════════════════

def hash_secret(plaintext):
    """Hash a password or PIN with bcrypt. Never store plaintext."""
    return bcrypt.hashpw(
        plaintext.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_secret(plaintext, hashed):
    """Verify a plaintext value against its bcrypt hash."""
    return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))


# ══════════════════════════════════════════════════════════════════
#  USER REGISTRATION
# ══════════════════════════════════════════════════════════════════

def register_user(name, username, email, password, pin):
    """
    Register a new standard user.
    Returns (success: bool, message: str).
    """
    # ── Validate every input ──────────────────────────────────
    for validator, value in [
        (validate_name, name),
        (validate_username, username),
        (validate_email, email),
        (validate_password, password),
        (validate_pin, pin),
    ]:
        ok, msg = validator(value)
        if not ok:
            return False, msg

    conn = get_connection()
    try:
        # Prevent duplicate usernames (parameterized query)
        if conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username.strip(),)
        ).fetchone():
            return False, "Username already exists. Please choose a different one."

        # Hash password and PIN — never store plaintext
        pw_hash = hash_secret(password)
        pin_hash = hash_secret(pin)

        cursor = conn.execute(
            """INSERT INTO users
               (name, username, email, password_hash, pin_hash,
                role, failed_attempts, is_locked, created_at)
               VALUES (?, ?, ?, ?, ?, 'user', 0, 0, ?)""",
            (name.strip(), username.strip(), email.strip(),
             pw_hash, pin_hash, datetime.now().isoformat()),
        )
        user_id = cursor.lastrowid

        # Create wallet with ₹0 balance (0 paise)
        conn.execute(
            "INSERT INTO wallets (user_id, balance) VALUES (?, 0)",
            (user_id,),
        )
        conn.commit()

        # Audit — do NOT log the password or PIN
        log_audit(user_id, "REGISTRATION",
                  f"New user registered: {username.strip()}")
        return True, "Registration successful! You can now log in."

    except Exception as e:
        conn.rollback()
        return False, f"Registration failed: {e}"
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
#  USER LOGIN  (with account-lockout)
# ══════════════════════════════════════════════════════════════════

def login_user(username, password, pin):
    """
    Authenticate a user with username + password + PIN.
    Implements account lockout after MAX_FAILED_ATTEMPTS.
    Returns (success, message, user_data_dict | None).
    """
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()

        if not user:
            return False, "Invalid username or password.", None

        # ── Locked account? ───────────────────────────────────
        if user["is_locked"]:
            log_audit(user["user_id"], "LOGIN_ATTEMPT_LOCKED",
                      f"Login attempt on locked account: {username}")
            return (False,
                    "Account is locked due to too many failed attempts. "
                    "Contact an administrator.",
                    None)

        # ── Verify password ───────────────────────────────────
        if not verify_secret(password, user["password_hash"]):
            return _record_failure(conn, user, username)

        # ── Verify transaction PIN ────────────────────────────
        if not verify_secret(pin, user["pin_hash"]):
            return _record_failure(conn, user, username, pin_fail=True)

        # ── Success — reset counter ──────────────────────────
        conn.execute(
            "UPDATE users SET failed_attempts = 0 WHERE user_id = ?",
            (user["user_id"],),
        )
        conn.commit()

        log_audit(user["user_id"], "LOGIN_SUCCESS",
                  f"User logged in: {username}")

        return True, "Login successful!", {
            "user_id":  user["user_id"],
            "name":     user["name"],
            "username": user["username"],
            "email":    user["email"],
            "role":     user["role"],
        }

    except Exception as e:
        return False, f"Login error: {e}", None
    finally:
        conn.close()


def _record_failure(conn, user, username, pin_fail=False):
    """Increment failed attempts; lock if threshold reached."""
    new_attempts = user["failed_attempts"] + 1
    locked = 1 if new_attempts >= MAX_FAILED_ATTEMPTS else 0

    conn.execute(
        "UPDATE users SET failed_attempts = ?, is_locked = ? WHERE user_id = ?",
        (new_attempts, locked, user["user_id"]),
    )
    conn.commit()

    kind = "PIN" if pin_fail else "password"
    if locked:
        log_audit(user["user_id"], "ACCOUNT_LOCKED",
                  f"Account locked after {MAX_FAILED_ATTEMPTS} failed {kind} attempts: {username}")
        return (False,
                "Account locked due to too many failed attempts. Contact an administrator.",
                None)

    remaining = MAX_FAILED_ATTEMPTS - new_attempts
    log_audit(user["user_id"], "LOGIN_FAILED",
              f"Failed {kind} attempt for: {username}")
    return (False,
            f"Invalid credentials. {remaining} attempt(s) remaining.",
            None)


# ══════════════════════════════════════════════════════════════════
#  ADMIN SETUP  (secure first-time creation)
# ══════════════════════════════════════════════════════════════════

def admin_exists():
    """Return True if at least one admin account already exists."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT 1 FROM users WHERE role = 'admin'"
        ).fetchone() is not None
    finally:
        conn.close()


def generate_setup_key():
    """Generate a cryptographically secure one-time setup key."""
    return secrets.token_hex(16)


def create_admin(name, username, email, password, pin, setup_key, expected_key):
    """
    Create the initial admin account.
    Requires the setup key printed to the server console.
    Returns (success, message).
    """
    if setup_key != expected_key:
        return False, "Invalid setup key."

    for validator, value in [
        (validate_name, name),
        (validate_username, username),
        (validate_email, email),
        (validate_password, password),
        (validate_pin, pin),
    ]:
        ok, msg = validator(value)
        if not ok:
            return False, msg

    conn = get_connection()
    try:
        if conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username.strip(),)
        ).fetchone():
            return False, "Username already exists."

        pw_hash = hash_secret(password)
        pin_hash = hash_secret(pin)

        cursor = conn.execute(
            """INSERT INTO users
               (name, username, email, password_hash, pin_hash,
                role, failed_attempts, is_locked, created_at)
               VALUES (?, ?, ?, ?, ?, 'admin', 0, 0, ?)""",
            (name.strip(), username.strip(), email.strip(),
             pw_hash, pin_hash, datetime.now().isoformat()),
        )
        user_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO wallets (user_id, balance) VALUES (?, 0)", (user_id,),
        )
        conn.commit()

        log_audit(user_id, "ADMIN_CREATED",
                  f"Admin account created: {username.strip()}")
        return True, "Admin account created successfully!"

    except Exception as e:
        conn.rollback()
        return False, f"Admin creation failed: {e}"
    finally:
        conn.close()
