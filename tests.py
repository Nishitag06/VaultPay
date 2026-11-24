"""
VaultPay - Automated Security & Functional Tests
==================================================
Covers the 13 test scenarios specified in the project requirements.

Run with:  python tests.py
"""

import os
import sys
import sqlite3

# Ensure imports work from the project directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use a separate test database so production data is not affected
os.environ["VAULTPAY_TEST"] = "1"

import database
TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vaultpay_test.db")
database.DB_PATH = TEST_DB  # Redirect before any other module uses it

from database import init_db, get_connection
from auth import register_user, login_user, hash_secret, create_admin
from transactions import deposit, withdraw, transfer, get_wallet_balance
from admin import require_admin
from security import validate_amount


# ── Helpers ──────────────────────────────────────────────────────

passed = 0
failed = 0


def _reset_db():
    """Drop and recreate the test database."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db()


def test(name, condition, detail=""):
    """Record a test result."""
    global passed, failed
    status = "PASS" if condition else "FAIL"
    if not condition:
        failed += 1
    else:
        passed += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  {status}  {name}{suffix}")


# ══════════════════════════════════════════════════════════════════
#  TEST SUITE
# ══════════════════════════════════════════════════════════════════

def run_tests():
    global passed, failed
    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("  VaultPay — Automated Security & Functional Tests")
    print("=" * 60)

    _reset_db()

    # ── 1. Successful user registration ───────────────────────
    print("\n── Registration Tests ──")
    ok, msg = register_user("Alice Smith", "alice", "alice@test.com",
                            "Secure1Pass", "1234")
    test("1. Successful user registration", ok, msg)

    # Register a second user for transfer tests
    register_user("Bob Jones", "bob", "bob@test.com", "Secure2Pass", "5678")

    # ── 2. Duplicate username registration ────────────────────
    ok, msg = register_user("Alice Clone", "alice", "clone@test.com",
                            "Secure1Pass", "1234")
    test("2. Duplicate username rejected", not ok, msg)

    # ── 3. Successful login (User & Admin) ────────────────────
    print("\n── Authentication Tests (User & Admin Logins) ──")
    # 3a. User Login
    ok, msg, user = login_user("alice", "Secure1Pass", "1234")
    test("3a. Successful User login", ok and user is not None and user["role"] == "user", msg)
    alice_id = user["user_id"] if user else None

    # 3b. Admin Setup & Admin Login
    ok_admin_setup, msg_setup = create_admin("Admin User", "superadmin", "admin@vaultpay.local",
                                             "AdminSecure1Pass", "9999", "secretkey123", "secretkey123")
    test("3b. Admin account creation via secure setup key", ok_admin_setup, msg_setup)

    ok_admin, msg_admin, admin_user = login_user("superadmin", "AdminSecure1Pass", "9999")
    test("3c. Successful Admin login", ok_admin and admin_user is not None and admin_user["role"] == "admin", msg_admin)

    # ── 4. Account lockout after 5 failed attempts ────────────
    for i in range(5):
        login_user("alice", "WrongPassword", "0000")
    ok, msg, _ = login_user("alice", "Secure1Pass", "1234")
    test("4. Account lockout after 5 failures", not ok and "locked" in msg.lower(), msg)

    # Unlock alice for further tests
    conn = get_connection()
    conn.execute("UPDATE users SET is_locked = 0, failed_attempts = 0 "
                 "WHERE username = 'alice'")
    conn.commit()
    conn.close()

    # ── 5. Negative deposit rejection ─────────────────────────
    print("\n── Transaction Validation Tests ──")
    ok, msg = deposit(alice_id, "-100", "1234")
    test("5. Negative deposit rejected", not ok, msg)

    # ── 6. Zero withdrawal rejection ──────────────────────────
    ok, msg = withdraw(alice_id, "0", "1234")
    test("6. Zero withdrawal rejected", not ok, msg)

    # ── 7. Withdrawal exceeding balance ───────────────────────
    # Deposit some money first
    deposit(alice_id, "1000", "1234")
    ok, msg = withdraw(alice_id, "5000", "1234")
    test("7. Withdrawal exceeding balance rejected", not ok, msg)

    # ── 8. Transfer to nonexistent user ───────────────────────
    print("\n── Transfer Tests ──")
    ok, msg = transfer(alice_id, "ghost_user", "500", "1234")
    test("8. Transfer to nonexistent user rejected", not ok, msg)

    # ── 9. Transfer exceeding transaction limit ───────────────
    ok, msg = transfer(alice_id, "bob", "60000", "1234")
    test("9. Transfer exceeding ₹50,000 limit rejected", not ok, msg)

    # ── 10. Normal user accessing admin functionality ─────────
    print("\n── RBAC Tests ──")
    normal_user = {"user_id": alice_id, "role": "user", "username": "alice"}
    is_admin, msg = require_admin(normal_user)
    test("10. Normal user denied admin access", not is_admin, msg)

    # ── 11. Incorrect transaction PIN ─────────────────────────
    print("\n── PIN Verification Tests ──")
    ok, msg = deposit(alice_id, "100", "9999")
    test("11. Incorrect PIN rejected", not ok, msg)

    # ── 12. Successful transfer between two users ─────────────
    print("\n── Transfer Execution Tests ──")
    # Get bob's ID
    conn = get_connection()
    bob = conn.execute("SELECT user_id FROM users WHERE username = 'bob'").fetchone()
    bob_id = bob["user_id"]
    conn.close()

    alice_before = get_wallet_balance(alice_id)
    bob_before = get_wallet_balance(bob_id)

    ok, msg = transfer(alice_id, "bob", "200", "1234")
    test("12a. Transfer succeeds", ok, msg)

    alice_after = get_wallet_balance(alice_id)
    bob_after = get_wallet_balance(bob_id)

    # 200 rupees = 20000 paise
    test("12b. Sender balance decreased correctly",
         alice_after == alice_before - 20000,
         f"Before: {alice_before}, After: {alice_after}")
    test("12c. Receiver balance increased correctly",
         bob_after == bob_before + 20000,
         f"Before: {bob_before}, After: {bob_after}")

    # ── 13. Database rollback on transfer failure ─────────────
    print("\n── Data Integrity Tests ──")
    alice_bal = get_wallet_balance(alice_id)
    bob_bal = get_wallet_balance(bob_id)

    # Try to transfer more than balance — should fail and rollback
    ok, msg = transfer(alice_id, "bob", "999999", "1234")

    alice_bal_after = get_wallet_balance(alice_id)
    bob_bal_after = get_wallet_balance(bob_id)

    test("13a. Over-balance transfer rejected", not ok, msg)
    test("13b. Sender balance unchanged after rollback",
         alice_bal == alice_bal_after)
    test("13c. Receiver balance unchanged after rollback",
         bob_bal == bob_bal_after)

    # ── Additional: Input validation edge cases ───────────────
    print("\n── Additional Validation Tests ──")
    _, err = validate_amount("abc")
    test("Amount 'abc' rejected", err is not None, err)

    _, err = validate_amount("")
    test("Empty amount rejected", err is not None, err)

    ok, msg = transfer(alice_id, "alice", "100", "1234")
    test("Self-transfer rejected", not ok, msg)

    # ── Summary ────────────────────────────────────────────────
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"  RESULTS:  {passed}/{total} passed,  {failed}/{total} failed")
    print("=" * 60 + "\n")

    # Clean up test database
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
