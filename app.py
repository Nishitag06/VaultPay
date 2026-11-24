"""
VaultPay — Secure Digital Wallet Simulator
===========================================
Main Streamlit application.
Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ── Project modules ───────────────────────────────────────────────
from database import init_db, get_connection
from auth import (
    register_user, login_user, admin_exists,
    generate_setup_key, create_admin,
)
from transactions import (
    get_wallet_summary, deposit, withdraw, transfer,
    get_transaction_history, get_recent_transactions,
)
from admin import (
    require_admin, get_all_users, get_all_wallets,
    get_all_transactions, get_audit_logs, get_failed_logins,
    get_dashboard_stats, unlock_user, lock_user,
)
from security import paise_to_rupees, rupees_float, log_audit

# Session timeout duration (minutes)
SESSION_TIMEOUT_MINUTES = 15

# ══════════════════════════════════════════════════════════════════
#  PAGE CONFIG & CUSTOM CSS
# ══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="VaultPay",
    page_icon="V",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Fintech-inspired theme: dark navy, white text, green accents
st.markdown("""
<style>
    /* ── Global ───────────────────────────────────────── */
    .stApp {
        background-color: #0a1628;
    }
    section[data-testid="stSidebar"] {
        background-color: #0d1f3c;
    }

    /* ── Metric / balance cards ───────────────────────── */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #0d1f3c 0%, #162d50 100%);
        border: 1px solid #1e3a5f;
        border-radius: 12px;
        padding: 16px 20px;
    }
    div[data-testid="stMetric"] label {
        color: #8899aa !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #00d09c !important;
        font-weight: 700;
    }

    /* ── Buttons ──────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, #00d09c 0%, #00b386 100%);
        color: #0a1628;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #00e6ac 0%, #00cc99 100%);
        transform: translateY(-1px);
    }

    /* ── Headings ─────────────────────────────────────── */
    h1, h2, h3 { color: #ffffff; }
    .brand-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00d09c, #00b386);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* ── Success / error banners ──────────────────────── */
    div[data-testid="stAlert"] {
        border-radius: 8px;
    }

    /* ── Tables / dataframes ──────────────────────────── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  DATABASE INITIALISATION
# ══════════════════════════════════════════════════════════════════

init_db()


# ══════════════════════════════════════════════════════════════════
#  SESSION HELPERS
# ══════════════════════════════════════════════════════════════════

def _init_session():
    """Set default session-state keys."""
    defaults = {
        "logged_in": False,
        "user": None,
        "page": "welcome",
        "last_activity": datetime.now(),
        "setup_key": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _check_timeout():
    """Log the user out after SESSION_TIMEOUT_MINUTES of inactivity."""
    if st.session_state.get("logged_in"):
        last = st.session_state.get("last_activity", datetime.now())
        if datetime.now() - last > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            user = st.session_state.get("user")
            if user:
                log_audit(user["user_id"], "SESSION_TIMEOUT",
                          f"Session timed out for: {user['username']}")
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.page = "welcome"
            st.warning("Session timed out due to inactivity. Please log in again.")


def _touch():
    """Update the last-activity timestamp (call on every interaction)."""
    st.session_state.last_activity = datetime.now()


_init_session()
_check_timeout()


# ══════════════════════════════════════════════════════════════════
#  NAVIGATION
# ══════════════════════════════════════════════════════════════════

def _nav(page):
    st.session_state.page = page
    _touch()


def _sidebar():
    """Render the sidebar navigation."""
    with st.sidebar:
        st.markdown('<p class="brand-title">VaultPay</p>',
                    unsafe_allow_html=True)
        st.caption("Secure Digital Wallet Simulator")
        st.divider()

        if not st.session_state.logged_in:
            if st.button("Welcome", use_container_width=True):
                _nav("welcome")
            if st.button("Register", use_container_width=True):
                _nav("register")
            if not admin_exists():
                if st.button("Admin Setup", use_container_width=True):
                    _nav("admin_setup")
        else:
            user = st.session_state.user
            st.success(f"{user['name']}")
            st.caption(f"@{user['username']}  •  {user['role'].upper()}")
            st.divider()

            if st.button("Dashboard", use_container_width=True):
                _nav("dashboard")
            if st.button("Deposit", use_container_width=True):
                _nav("deposit")
            if st.button("Withdraw", use_container_width=True):
                _nav("withdraw")
            if st.button("Transfer", use_container_width=True):
                _nav("transfer")
            if st.button("History", use_container_width=True):
                _nav("history")

            # Admin nav — only shown to admins
            if user["role"] == "admin":
                st.divider()
                st.caption("ADMIN")
                if st.button("Admin Panel", use_container_width=True):
                    _nav("admin")

            st.divider()
            if st.button("Logout", use_container_width=True):
                log_audit(user["user_id"], "LOGOUT",
                          f"User logged out: {user['username']}")
                st.session_state.logged_in = False
                st.session_state.user = None
                _nav("welcome")
                st.rerun()

_sidebar()


# ══════════════════════════════════════════════════════════════════
#  PAGE: WELCOME / LOGIN
# ══════════════════════════════════════════════════════════════════

def page_welcome():
    _touch()
    col1, col2 = st.columns([1.1, 1.1])

    with col1:
        st.markdown('<p class="brand-title">VaultPay</p>',
                    unsafe_allow_html=True)
        st.markdown("### Secure Digital Wallet Simulator")
        st.markdown(
            "A sandboxed digital wallet demonstrating **Secure Software "
            "Engineering (SSE)** principles:\n\n"
            "- **Authentication**: Multi-factor credentials & automated lockout\n"
            "- **Input Validation**: Strict amount & credential checks\n"
            "- **Role-Based Access Control (RBAC)**: Distinct User & Admin roles\n"
            "- **Data Integrity**: Atomic transactions & integer paise balance\n"
            "- **Audit Logging**: Tamper-evident activity logs without secrets"
        )
        st.info("Note: This is an academic simulation — no real banking APIs are involved.")

    with col2:
        tab_user, tab_admin, tab_register = st.tabs(["User Login", "Admin Login", "Register"])

        # ── Tab 1: Standard User Login ────────────────────────
        with tab_user:
            st.markdown("#### User Wallet Login")
            st.caption("Access your personal balance, deposits, withdrawals, and transfers.")
            with st.form("user_login_form"):
                username = st.text_input("Username", key="user_uname")
                password = st.text_input("Password", type="password", key="user_pwd")
                pin = st.text_input("Transaction PIN", type="password", key="user_pin")
                submitted = st.form_submit_button("Login as User", use_container_width=True)

                if submitted:
                    if not username or not password or not pin:
                        st.error("Please fill in all fields.")
                    else:
                        ok, msg, user_data = login_user(username, password, pin)
                        if ok:
                            st.session_state.logged_in = True
                            st.session_state.user = user_data
                            st.session_state.last_activity = datetime.now()
                            st.success(msg)
                            _nav("dashboard")
                            st.rerun()
                        else:
                            st.error(msg)

        # ── Tab 2: Admin Login ────────────────────────────────
        with tab_admin:
            st.markdown("#### Administrator Portal")
            st.caption("Restricted access for system administrators only (RBAC enforced).")

            if not admin_exists():
                st.info("**First-time setup:** No administrator exists yet. Complete the one-time admin setup below:")
                if not st.session_state.get("setup_key"):
                    key = generate_setup_key()
                    st.session_state.setup_key = key
                    print("\n" + "=" * 60)
                    print("  VAULTPAY — ADMIN SETUP KEY (use once, then discard)")
                    print(f"  {key}")
                    print("=" * 60 + "\n")
                
                with st.form("initial_admin_setup_form"):
                    setup_key = st.text_input("Setup Key (printed in your terminal)", help="Check the terminal where Streamlit is running")
                    name      = st.text_input("Admin Full Name", key="init_admin_name")
                    username  = st.text_input("Admin Username", key="init_admin_uname")
                    email     = st.text_input("Admin Email", key="init_admin_email")
                    password  = st.text_input("Password", type="password", key="init_admin_pwd")
                    pin       = st.text_input("Transaction PIN (4-6 digits)", type="password", key="init_admin_pin")
                    submitted = st.form_submit_button("Create Initial Admin Account", use_container_width=True)

                    if submitted:
                        ok, msg = create_admin(
                            name, username, email, password, pin,
                            setup_key, st.session_state.setup_key,
                        )
                        if ok:
                            st.success(msg + " You can now log in using the Admin tab.")
                            st.session_state.setup_key = None
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                with st.form("admin_login_form"):
                    admin_username = st.text_input("Admin Username", key="admin_uname")
                    admin_password = st.text_input("Password", type="password", key="admin_pwd")
                    admin_pin = st.text_input("Admin PIN", type="password", key="admin_pin")
                    admin_submitted = st.form_submit_button("Login as Admin", use_container_width=True)

                    if admin_submitted:
                        if not admin_username or not admin_password or not admin_pin:
                            st.error("Please fill in all fields.")
                        else:
                            ok, msg, user_data = login_user(admin_username, admin_password, admin_pin)
                            if ok:
                                # Strict RBAC check: reject standard users logging into the admin portal
                                if user_data["role"] != "admin":
                                    log_audit(user_data["user_id"], "ADMIN_LOGIN_REJECTED",
                                              f"Standard user '{admin_username}' attempted admin portal login")
                                    st.error("Access denied. This account does not possess administrator privileges.")
                                else:
                                    st.session_state.logged_in = True
                                    st.session_state.user = user_data
                                    st.session_state.last_activity = datetime.now()
                                    st.success(msg)
                                    _nav("admin")
                                    st.rerun()
                            else:
                                st.error(msg)

        # ── Tab 3: Register ───────────────────────────────────
        with tab_register:
            st.markdown("#### Create Standard Wallet Account")
            st.info(
                "**Security Requirements:**\n"
                "- **Password**: Minimum 8 characters with at least 1 uppercase letter, 1 lowercase letter, and 1 number.\n"
                "- **Transaction PIN**: 4 to 6 numeric digits."
            )
            with st.form("register_tab_form"):
                reg_name     = st.text_input("Full Name", key="reg_tab_name")
                reg_username = st.text_input("Username", key="reg_tab_uname")
                reg_email    = st.text_input("Email", key="reg_tab_email")
                reg_password = st.text_input("Password", type="password", key="reg_tab_pwd")
                reg_confirm  = st.text_input("Confirm Password", type="password", key="reg_tab_cpwd")
                reg_pin      = st.text_input("Transaction PIN (4–6 digits)", type="password", key="reg_tab_pin")
                reg_submitted = st.form_submit_button("Create Account", use_container_width=True)

                if reg_submitted:
                    if not all([reg_name, reg_username, reg_email, reg_password, reg_confirm, reg_pin]):
                        st.error("Please fill in all fields.")
                    elif reg_password != reg_confirm:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = register_user(reg_name, reg_username, reg_email, reg_password, reg_pin)
                        if ok:
                            st.success(msg + " Switch to 'User Login' to log in.")
                        else:
                            st.error(msg)


# ══════════════════════════════════════════════════════════════════
#  PAGE: REGISTRATION
# ══════════════════════════════════════════════════════════════════

def page_register():
    _touch()
    st.markdown("### Create Your Account")
    st.info(
        "**Security Requirements:**\n"
        "- **Password**: Minimum 8 characters with at least 1 uppercase letter, 1 lowercase letter, and 1 number.\n"
        "- **Transaction PIN**: 4 to 6 numeric digits."
    )

    with st.form("register_form"):
        name     = st.text_input("Full Name")
        username = st.text_input("Username")
        email    = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm  = st.text_input("Confirm Password", type="password")
        pin      = st.text_input("Transaction PIN (4–6 digits)", type="password")
        submitted = st.form_submit_button("Register", use_container_width=True)

        if submitted:
            if not all([name, username, email, password, confirm, pin]):
                st.error("Please fill in all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                ok, msg = register_user(name, username, email, password, pin)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


# ══════════════════════════════════════════════════════════════════
#  PAGE: ADMIN SETUP (first run only)
# ══════════════════════════════════════════════════════════════════

def page_admin_setup():
    _touch()
    if admin_exists():
        st.warning("An admin account already exists.")
        return

    st.markdown("###  Initial Admin Setup")
    st.info(
        "Create the first administrator account. "
        "Check the **terminal / console** where Streamlit is running "
        "to find the one-time **Setup Key**."
    )

    # Generate and persist the setup key in session
    if not st.session_state.get("setup_key"):
        key = generate_setup_key()
        st.session_state.setup_key = key
        # Print to server console so only the person running the server sees it
        print("\n" + "=" * 60)
        print("  VAULTPAY — ADMIN SETUP KEY (use once, then discard)")
        print(f"  {key}")
        print("=" * 60 + "\n")

    with st.form("admin_setup_form"):
        setup_key = st.text_input("Setup Key (from terminal)")
        name      = st.text_input("Admin Full Name")
        username  = st.text_input("Admin Username")
        email     = st.text_input("Admin Email")
        password  = st.text_input("Password", type="password")
        pin       = st.text_input("Transaction PIN", type="password")
        submitted = st.form_submit_button("Create Admin", use_container_width=True)

        if submitted:
            ok, msg = create_admin(
                name, username, email, password, pin,
                setup_key, st.session_state.setup_key,
            )
            if ok:
                st.success(msg + " You can now log in.")
                st.session_state.setup_key = None  # Invalidate the key
            else:
                st.error(msg)


# ══════════════════════════════════════════════════════════════════
#  PAGE: USER DASHBOARD
# ══════════════════════════════════════════════════════════════════

def page_dashboard():
    _touch()
    user = st.session_state.user
    st.markdown(f"### Welcome back, {user['name']}!")

    summary = get_wallet_summary(user["user_id"])

    # ── Balance cards ──────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Balance",          paise_to_rupees(summary["balance"]))
    c2.metric("Total Deposits",   paise_to_rupees(summary["total_deposits"]))
    c3.metric("Total Withdrawals", paise_to_rupees(summary["total_withdrawals"]))
    c4.metric("Total Transfers",  paise_to_rupees(summary["total_transfers"]))

    # ── Quick actions ──────────────────────────────────────────
    st.divider()
    st.markdown("#### Quick Actions")
    qa1, qa2, qa3, qa4 = st.columns(4)
    if qa1.button("Deposit",  use_container_width=True):
        _nav("deposit"); st.rerun()
    if qa2.button("Withdraw", use_container_width=True):
        _nav("withdraw"); st.rerun()
    if qa3.button("Transfer", use_container_width=True):
        _nav("transfer"); st.rerun()
    if qa4.button("History",  use_container_width=True):
        _nav("history"); st.rerun()

    # ── Recent transactions ───────────────────────────────────
    st.divider()
    st.markdown("#### Recent Transactions")
    recent = get_recent_transactions(user["user_id"], limit=5)
    if recent:
        df = _txn_dataframe(recent)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions yet. Start by making a deposit!")


# ══════════════════════════════════════════════════════════════════
#  PAGE: DEPOSIT
# ══════════════════════════════════════════════════════════════════

def page_deposit():
    _touch()
    user = st.session_state.user
    st.markdown("### Deposit Money")
    balance = get_wallet_summary(user["user_id"])["balance"]
    st.info(f"Current balance: **{paise_to_rupees(balance)}**")

    with st.form("deposit_form"):
        amount = st.text_input("Amount (₹)", placeholder="e.g. 1000")
        pin    = st.text_input("Transaction PIN", type="password")
        submitted = st.form_submit_button("Deposit", use_container_width=True)

        if submitted:
            if not amount or not pin:
                st.error("Please fill in all fields.")
            else:
                ok, msg = deposit(user["user_id"], amount, pin)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


# ══════════════════════════════════════════════════════════════════
#  PAGE: WITHDRAW
# ══════════════════════════════════════════════════════════════════

def page_withdraw():
    _touch()
    user = st.session_state.user
    st.markdown("### Withdraw Money")
    balance = get_wallet_summary(user["user_id"])["balance"]
    st.info(f"Current balance: **{paise_to_rupees(balance)}**")

    with st.form("withdraw_form"):
        amount = st.text_input("Amount (₹)", placeholder="e.g. 500")
        pin    = st.text_input("Transaction PIN", type="password")
        submitted = st.form_submit_button("Withdraw", use_container_width=True)

        if submitted:
            if not amount or not pin:
                st.error("Please fill in all fields.")
            else:
                ok, msg = withdraw(user["user_id"], amount, pin)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


# ══════════════════════════════════════════════════════════════════
#  PAGE: TRANSFER
# ══════════════════════════════════════════════════════════════════

def page_transfer():
    _touch()
    user = st.session_state.user
    st.markdown("### Transfer Money")
    balance = get_wallet_summary(user["user_id"])["balance"]
    st.info(f"Current balance: **{paise_to_rupees(balance)}**")

    with st.form("transfer_form"):
        receiver = st.text_input("Receiver Username")
        amount   = st.text_input("Amount (₹)", placeholder="e.g. 250")
        pin      = st.text_input("Transaction PIN", type="password")
        submitted = st.form_submit_button("Transfer", use_container_width=True)

        if submitted:
            if not receiver or not amount or not pin:
                st.error("Please fill in all fields.")
            else:
                ok, msg = transfer(user["user_id"], receiver, amount, pin)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


# ══════════════════════════════════════════════════════════════════
#  PAGE: TRANSACTION HISTORY
# ══════════════════════════════════════════════════════════════════

def page_history():
    _touch()
    user = st.session_state.user
    st.markdown("### Transaction History")

    txns = get_transaction_history(user["user_id"])
    if txns:
        df = _txn_dataframe(txns)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(txns)} transaction(s)")
    else:
        st.info("No transactions found.")


def _txn_dataframe(rows):
    """Convert raw transaction dicts to a nicely formatted DataFrame."""
    data = []
    for r in rows:
        data.append({
            "ID":       r["transaction_id"],
            "Type":     r["transaction_type"],
            "Amount":   paise_to_rupees(r["amount"]),
            "Sender":   r.get("sender_username") or "—",
            "Receiver": r.get("receiver_username") or "—",
            "Status":   r["status"],
            "Date/Time": r["timestamp"][:19].replace("T", "  "),
        })
    return pd.DataFrame(data)


# ══════════════════════════════════════════════════════════════════
#  PAGE: ADMIN PANEL  (RBAC-protected)
# ══════════════════════════════════════════════════════════════════

def page_admin():
    _touch()
    user = st.session_state.user

    # ── RBAC enforcement in code, not just UI ─────────────────
    ok, msg = require_admin(user)
    if not ok:
        st.error(msg)
        log_audit(
            user["user_id"] if user else None,
            "ADMIN_ACCESS_DENIED",
            f"Unauthorized admin access attempt by: {user['username'] if user else 'unknown'}",
        )
        return

    st.markdown("### Admin Dashboard")

    # ── Overview statistics ────────────────────────────────────
    stats = get_dashboard_stats()
    _conn = get_connection()
    try:
        total_balance_val = _conn.execute("SELECT COALESCE(SUM(balance), 0) FROM wallets").fetchone()[0]
    finally:
        _conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registered Users",    stats.get("total_users", 0))
    c2.metric("Locked Accounts",     stats.get("locked_accounts", 0))
    c3.metric("Total Transactions",  stats.get("total_txns", 0))
    c4.metric("Total Balance",       paise_to_rupees(total_balance_val))

    st.divider()

    # ── Tabs for different admin views ─────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        " Users", " Wallets", " Transactions",
        " Audit Logs", " Security",
    ])

    # ── Tab 1: All Users ──────────────────────────────────────
    with tab1:
        users = get_all_users()
        if users:
            df = pd.DataFrame(users)
            df.columns = ["ID", "Name", "Username", "Email", "Role",
                          "Failed Attempts", "Locked", "Created At"]
            df["Locked"] = df["Locked"].map({0: "No", 1: "Yes"})
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No users registered.")

    # ── Tab 2: All Wallets ────────────────────────────────────
    with tab2:
        wallets = get_all_wallets()
        if wallets:
            df = pd.DataFrame(wallets)
            df.columns = ["Username", "Name", "Balance (paise)"]
            df["Balance"] = df["Balance (paise)"].apply(paise_to_rupees)
            df = df[["Username", "Name", "Balance"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No wallets found.")

    # ── Tab 3: All Transactions ───────────────────────────────
    with tab3:
        txns = get_all_transactions()
        if txns:
            df = pd.DataFrame(txns)
            df.columns = ["ID", "Type", "Amount (paise)", "Status",
                          "Timestamp", "Sender", "Receiver"]
            df["Amount"] = df["Amount (paise)"].apply(paise_to_rupees)
            df = df[["ID", "Type", "Amount", "Sender", "Receiver",
                      "Status", "Timestamp"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No transactions recorded.")

    # ── Tab 4: Audit Logs ─────────────────────────────────────
    with tab4:
        logs = get_audit_logs()
        if logs:
            df = pd.DataFrame(logs)
            df.columns = ["Log ID", "Action", "Details", "Timestamp", "User"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No audit logs found.")

    # ── Tab 5: Security — failed logins & account management ──
    with tab5:
        st.markdown("#### Failed Logins & Locked Accounts")
        failed = get_failed_logins()
        if failed:
            df = pd.DataFrame(failed)
            df.columns = ["ID", "Username", "Name", "Failed Attempts", "Locked"]
            df["Locked"] = df["Locked"].map({0: "No", 1: "Yes"})
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.success("No failed login attempts or locked accounts.")

        st.divider()
        st.markdown("#### Manage Account Status")
        col_a, col_b = st.columns(2)

        with col_a:
            with st.form("unlock_form"):
                uname = st.text_input("Username to unlock")
                if st.form_submit_button("Unlock Account",
                                         use_container_width=True):
                    if uname:
                        ok, msg = unlock_user(user["user_id"], uname)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.error("Enter a username.")

        with col_b:
            with st.form("lock_form"):
                uname2 = st.text_input("Username to lock")
                if st.form_submit_button("Lock Account",
                                         use_container_width=True):
                    if uname2:
                        ok, msg = lock_user(user["user_id"], uname2)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.error("Enter a username.")


# ══════════════════════════════════════════════════════════════════
#  PAGE ROUTER
# ══════════════════════════════════════════════════════════════════

page = st.session_state.page

if not st.session_state.logged_in:
    # Unauthenticated pages
    if page == "register":
        page_register()
    elif page == "admin_setup":
        page_admin_setup()
    else:
        page_welcome()
else:
    # Authenticated pages
    pages = {
        "dashboard": page_dashboard,
        "deposit":   page_deposit,
        "withdraw":  page_withdraw,
        "transfer":  page_transfer,
        "history":   page_history,
        "admin":     page_admin,
    }
    pages.get(page, page_dashboard)()
