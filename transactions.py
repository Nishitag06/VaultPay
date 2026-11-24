"""
VaultPay - Transactions Module
===============================
Deposits, withdrawals, peer-to-peer transfers, and transaction history.
Demonstrates SSE Concept #4 (Data Integrity & Secure Transaction Processing).

All monetary values are stored as INTEGER paise (1 ₹ = 100 paise)
to avoid floating-point precision problems.
"""

from datetime import datetime
from database import get_connection
from security import validate_amount, log_audit, paise_to_rupees
from auth import verify_secret


# ══════════════════════════════════════════════════════════════════
#  BALANCE & SUMMARY
# ══════════════════════════════════════════════════════════════════

def get_wallet_balance(user_id):
    """Return the current wallet balance in paise."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["balance"] if row else 0
    finally:
        conn.close()


def get_wallet_summary(user_id):
    """
    Dashboard statistics: balance, total deposits, total withdrawals,
    total transfer volume (sent + received).
    """
    conn = get_connection()
    try:
        bal = conn.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
        balance = bal["balance"] if bal else 0

        total_deposits = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM transactions "
            "WHERE receiver_id = ? AND transaction_type = 'DEPOSIT' AND status = 'SUCCESS'",
            (user_id,),
        ).fetchone()["t"]

        total_withdrawals = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM transactions "
            "WHERE sender_id = ? AND transaction_type = 'WITHDRAWAL' AND status = 'SUCCESS'",
            (user_id,),
        ).fetchone()["t"]

        total_sent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM transactions "
            "WHERE sender_id = ? AND transaction_type = 'TRANSFER' AND status = 'SUCCESS'",
            (user_id,),
        ).fetchone()["t"]

        total_received = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM transactions "
            "WHERE receiver_id = ? AND transaction_type = 'TRANSFER' AND status = 'SUCCESS'",
            (user_id,),
        ).fetchone()["t"]

        return {
            "balance":           balance,
            "total_deposits":    total_deposits,
            "total_withdrawals": total_withdrawals,
            "total_transfers":   total_sent + total_received,
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
#  DEPOSIT
# ══════════════════════════════════════════════════════════════════

def deposit(user_id, amount_str, pin):
    """
    Add simulated money to the user's wallet.
    Returns (success, message).
    """
    amount_paise, err = validate_amount(amount_str)
    if err:
        return False, err

    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT pin_hash FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not user:
            return False, "User not found."

        # Verify transaction PIN before proceeding
        if not verify_secret(pin, user["pin_hash"]):
            log_audit(user_id, "DEPOSIT_FAILED", "Invalid transaction PIN")
            return False, "Invalid transaction PIN."

        # Update balance and record transaction
        conn.execute(
            "UPDATE wallets SET balance = balance + ? WHERE user_id = ?",
            (amount_paise, user_id),
        )
        conn.execute(
            "INSERT INTO transactions "
            "(sender_id, receiver_id, transaction_type, amount, status, timestamp) "
            "VALUES (NULL, ?, 'DEPOSIT', ?, 'SUCCESS', ?)",
            (user_id, amount_paise, datetime.now().isoformat()),
        )
        conn.commit()

        log_audit(user_id, "DEPOSIT",
                  f"Deposited {paise_to_rupees(amount_paise)}")
        return True, f"Successfully deposited {paise_to_rupees(amount_paise)}."

    except Exception as e:
        conn.rollback()
        log_audit(user_id, "DEPOSIT_FAILED", f"Error: {e}")
        return False, f"Deposit failed: {e}"
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
#  WITHDRAWAL
# ══════════════════════════════════════════════════════════════════

def withdraw(user_id, amount_str, pin):
    """
    Remove simulated money from the user's wallet.
    Returns (success, message).
    """
    amount_paise, err = validate_amount(amount_str)
    if err:
        return False, err

    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT pin_hash FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not user:
            return False, "User not found."

        if not verify_secret(pin, user["pin_hash"]):
            log_audit(user_id, "WITHDRAWAL_FAILED", "Invalid transaction PIN")
            return False, "Invalid transaction PIN."

        # Check sufficient balance
        wallet = conn.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not wallet or wallet["balance"] < amount_paise:
            log_audit(user_id, "WITHDRAWAL_FAILED", "Insufficient balance")
            return False, "Insufficient wallet balance."

        # Deduct and record
        conn.execute(
            "UPDATE wallets SET balance = balance - ? WHERE user_id = ?",
            (amount_paise, user_id),
        )
        conn.execute(
            "INSERT INTO transactions "
            "(sender_id, receiver_id, transaction_type, amount, status, timestamp) "
            "VALUES (?, NULL, 'WITHDRAWAL', ?, 'SUCCESS', ?)",
            (user_id, amount_paise, datetime.now().isoformat()),
        )
        conn.commit()

        log_audit(user_id, "WITHDRAWAL",
                  f"Withdrew {paise_to_rupees(amount_paise)}")
        return True, f"Successfully withdrew {paise_to_rupees(amount_paise)}."

    except Exception as e:
        conn.rollback()
        log_audit(user_id, "WITHDRAWAL_FAILED", f"Error: {e}")
        return False, f"Withdrawal failed: {e}"
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
#  PEER-TO-PEER TRANSFER  (atomic SQLite transaction)
# ══════════════════════════════════════════════════════════════════

def transfer(sender_id, receiver_username, amount_str, pin):
    """
    Transfer money from one user to another.

    IMPORTANT: The deduction, credit, and transaction record are wrapped
    in a single SQLite transaction.  If any step fails the entire
    operation is rolled back — no money is lost or duplicated.

    Returns (success, message).
    """
    amount_paise, err = validate_amount(amount_str)
    if err:
        return False, err

    conn = get_connection()
    try:
        # ── Sender verification ───────────────────────────────
        sender = conn.execute(
            "SELECT user_id, username, pin_hash FROM users WHERE user_id = ?",
            (sender_id,),
        ).fetchone()
        if not sender:
            return False, "Sender not found."

        if not verify_secret(pin, sender["pin_hash"]):
            log_audit(sender_id, "TRANSFER_FAILED", "Invalid transaction PIN")
            return False, "Invalid transaction PIN."

        # ── Receiver lookup ───────────────────────────────────
        receiver = conn.execute(
            "SELECT user_id, username FROM users WHERE username = ?",
            (receiver_username.strip(),),
        ).fetchone()
        if not receiver:
            log_audit(sender_id, "TRANSFER_FAILED",
                      f"Receiver not found: {receiver_username}")
            return False, "Receiver username not found."

        # Prevent self-transfer
        if receiver["user_id"] == sender_id:
            return False, "You cannot transfer money to yourself."

        # ── Balance check ─────────────────────────────────────
        sender_wallet = conn.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (sender_id,)
        ).fetchone()
        if not sender_wallet or sender_wallet["balance"] < amount_paise:
            log_audit(sender_id, "TRANSFER_FAILED", "Insufficient balance")
            return False, "Insufficient wallet balance."

        # ── ATOMIC: deduct -> credit -> record ─────────────────
        conn.execute(
            "UPDATE wallets SET balance = balance - ? WHERE user_id = ?",
            (amount_paise, sender_id),
        )
        conn.execute(
            "UPDATE wallets SET balance = balance + ? WHERE user_id = ?",
            (amount_paise, receiver["user_id"]),
        )
        conn.execute(
            "INSERT INTO transactions "
            "(sender_id, receiver_id, transaction_type, amount, status, timestamp) "
            "VALUES (?, ?, 'TRANSFER', ?, 'SUCCESS', ?)",
            (sender_id, receiver["user_id"], amount_paise,
             datetime.now().isoformat()),
        )

        # Commit all three operations as one atomic unit
        conn.commit()

        log_audit(sender_id, "TRANSFER_SENT",
                  f"Sent {paise_to_rupees(amount_paise)} to {receiver['username']}")
        log_audit(receiver["user_id"], "TRANSFER_RECEIVED",
                  f"Received {paise_to_rupees(amount_paise)} from {sender['username']}")

        return (True,
                f"Successfully transferred {paise_to_rupees(amount_paise)} "
                f"to {receiver['username']}.")

    except Exception as e:
        # Rollback everything if ANY step fails
        conn.rollback()
        log_audit(sender_id, "TRANSFER_FAILED", f"Error: {e}")
        return False, f"Transfer failed: {e}"
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
#  TRANSACTION HISTORY
# ══════════════════════════════════════════════════════════════════

def get_transaction_history(user_id):
    """
    Return all transactions involving this user.
    Users can ONLY see their own history (SSE Concept #3 — least privilege).
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT t.transaction_id, t.transaction_type, t.amount,
                      t.status, t.timestamp,
                      s.username AS sender_username,
                      r.username AS receiver_username
               FROM transactions t
               LEFT JOIN users s ON t.sender_id   = s.user_id
               LEFT JOIN users r ON t.receiver_id  = r.user_id
               WHERE t.sender_id = ? OR t.receiver_id = ?
               ORDER BY t.timestamp DESC""",
            (user_id, user_id),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=5):
    """Return the N most recent transactions for the dashboard."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT t.transaction_id, t.transaction_type, t.amount,
                      t.status, t.timestamp,
                      s.username AS sender_username,
                      r.username AS receiver_username
               FROM transactions t
               LEFT JOIN users s ON t.sender_id   = s.user_id
               LEFT JOIN users r ON t.receiver_id  = r.user_id
               WHERE t.sender_id = ? OR t.receiver_id = ?
               ORDER BY t.timestamp DESC
               LIMIT ?""",
            (user_id, user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
