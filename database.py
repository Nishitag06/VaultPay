"""
VaultPay - Database Module
==========================
Handles SQLite database initialization and connection management.
Enables foreign key constraints for referential integrity.
"""

import sqlite3
import os

# Database file lives next to the application files
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vaultpay.db")


def get_connection():
    """
    Create and return a database connection.
    - Foreign keys are enabled for referential integrity.
    - Row factory is set so rows behave like dictionaries.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # Enforce foreign key constraints
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    """
    Initialize the database with the four required tables:
    users, wallets, transactions, audit_logs.
    Uses CREATE TABLE IF NOT EXISTS so it is safe to call repeatedly.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ── Users table ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            username        TEXT    UNIQUE NOT NULL,
            email           TEXT    NOT NULL,
            password_hash   TEXT    NOT NULL,
            pin_hash        TEXT    NOT NULL,
            role            TEXT    NOT NULL DEFAULT 'user',
            failed_attempts INTEGER DEFAULT 0,
            is_locked       INTEGER DEFAULT 0,
            created_at      TEXT    NOT NULL
        )
    """)

    # ── Wallets table ────────────────────────────────────────────
    # Balance is stored in INTEGER paise (1 rupee = 100 paise)
    # to avoid floating-point precision problems.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL UNIQUE,
            balance   INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # ── Transactions table ───────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id        INTEGER,
            receiver_id      INTEGER,
            transaction_type TEXT    NOT NULL,
            amount           INTEGER NOT NULL,
            status           TEXT    NOT NULL,
            timestamp        TEXT    NOT NULL,
            FOREIGN KEY (sender_id)   REFERENCES users(user_id),
            FOREIGN KEY (receiver_id) REFERENCES users(user_id)
        )
    """)

    # ── Audit logs table ─────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            action    TEXT NOT NULL,
            details   TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    conn.close()
