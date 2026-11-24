"""
VaultPay - Admin Module
========================
Admin panel functions with RBAC enforcement.
Demonstrates SSE Concept #3 (Role-Based Access Control).

Authorization is enforced in Python functions — not merely
by hiding navigation options in the UI.
"""

from database import get_connection
from security import log_audit


# ══════════════════════════════════════════════════════════════════
#  RBAC GATE  (SSE Concept #3)
# ══════════════════════════════════════════════════════════════════

def require_admin(user_data):
    """
    Verify the caller has the 'admin' role.
    Returns (is_admin: bool, message: str).
    """
    if not user_data:
        return False, "Authentication required."
    if user_data.get("role") != "admin":
        return False, "Access denied. Admin privileges required."
    return True, "Authorized."


# ══════════════════════════════════════════════════════════════════
#  DATA RETRIEVAL  (admin only — caller must pass RBAC gate first)
# ══════════════════════════════════════════════════════════════════

def get_all_users():
    """List every registered user (passwords/PINs excluded)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT user_id, name, username, email, role, "
            "       failed_attempts, is_locked, created_at "
            "FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_wallets():
    """List every wallet with its owner."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT u.username, u.name, w.balance "
            "FROM wallets w JOIN users u ON w.user_id = u.user_id "
            "ORDER BY w.balance DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_transactions():
    """List every transaction across all users."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT t.transaction_id, t.transaction_type, t.amount, "
            "       t.status, t.timestamp, "
            "       s.username AS sender, r.username AS receiver "
            "FROM transactions t "
            "LEFT JOIN users s ON t.sender_id   = s.user_id "
            "LEFT JOIN users r ON t.receiver_id  = r.user_id "
            "ORDER BY t.timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_audit_logs():
    """Return all audit log entries."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT a.log_id, a.action, a.details, a.timestamp, "
            "       u.username "
            "FROM audit_logs a "
            "LEFT JOIN users u ON a.user_id = u.user_id "
            "ORDER BY a.timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_failed_logins():
    """Return users with at least one failed attempt or a locked account."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT user_id, username, name, failed_attempts, is_locked "
            "FROM users "
            "WHERE failed_attempts > 0 OR is_locked = 1 "
            "ORDER BY failed_attempts DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_dashboard_stats():
    """Aggregate statistics for the admin dashboard."""
    conn = get_connection()
    try:
        total_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role = 'user'"
        ).fetchone()["c"]

        locked_accounts = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE is_locked = 1"
        ).fetchone()["c"]

        total_txns = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions"
        ).fetchone()["c"]

        # Calculate total wallet balance across all users
        total_balance = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) AS b FROM wallets"
        ).fetchone()["b"]

        return {
            "total_users":     total_users,
            "locked_accounts": locked_accounts,
            "total_txns":      total_txns,
            "total_balance":   total_balance,
            "total_volume":    total_balance,
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
#  ACCOUNT MANAGEMENT
# ══════════════════════════════════════════════════════════════════

def unlock_user(admin_user_id, target_username):
    """Unlock an account and reset its failed-attempt counter."""
    conn = get_connection()
    try:
        if not conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (target_username,)
        ).fetchone():
            return False, "User not found."

        conn.execute(
            "UPDATE users SET is_locked = 0, failed_attempts = 0 "
            "WHERE username = ?",
            (target_username,),
        )
        conn.commit()

        log_audit(admin_user_id, "ADMIN_UNLOCK",
                  f"Unlocked account: {target_username}")
        return True, f"Account '{target_username}' has been unlocked."

    except Exception as e:
        conn.rollback()
        return False, f"Unlock failed: {e}"
    finally:
        conn.close()


def lock_user(admin_user_id, target_username):
    """Manually lock a user account (cannot lock another admin)."""
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT role FROM users WHERE username = ?", (target_username,)
        ).fetchone()
        if not user:
            return False, "User not found."
        if user["role"] == "admin":
            return False, "Cannot lock an admin account."

        conn.execute(
            "UPDATE users SET is_locked = 1 WHERE username = ?",
            (target_username,),
        )
        conn.commit()

        log_audit(admin_user_id, "ADMIN_LOCK",
                  f"Locked account: {target_username}")
        return True, f"Account '{target_username}' has been locked."

    except Exception as e:
        conn.rollback()
        return False, f"Lock failed: {e}"
    finally:
        conn.close()
