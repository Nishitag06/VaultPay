# VaultPay – Secure Digital Wallet Simulator

VaultPay is a simulated digital wallet application developed using Python, Streamlit, and SQLite. It allows registered users to manage virtual money through deposits, withdrawals, and peer-to-peer transfers.

The project is designed for academic learning and demonstrates how Secure Software Engineering (SSE) principles can be applied to a small application. 

## Features

- User registration and login
- Password and transaction PIN verification
- Account lockout after 5 consecutive incorrect password attempts
- Admin-controlled unlocking of locked accounts
- Wallet dashboard with balance information
- Simulated deposits and withdrawals
- Peer-to-peer transfers between registered users
- Transaction history
- Admin dashboard and role-based access
- Audit logs for important security and account activities
- Input validation and transaction limits

## Security Concepts Demonstrated

1. **Authentication:** Passwords and transaction PINs are stored as hashes. Repeated incorrect password attempts trigger account lockout.
2. **Input Validation:** Invalid amounts, unsupported operations, and invalid recipients are rejected.
3. **Role-Based Access Control (RBAC):** Standard users and administrators have different permissions.
4. **Transaction Integrity:** SQLite transactions help ensure that a transfer is processed as one operation rather than leaving a partial update.
5. **Audit Logging:** Important events are recorded for monitoring and accountability. Passwords and PINs should never be written to logs.

## Technology Stack

- **Language:** Python
- **Frontend:** Streamlit
- **Database:** SQLite
- **Password/PIN hashing:** bcrypt
- **Version control:** Git and GitHub

## Project Structure

```text
VaultPay/
├── app.py
├── database.py
├── auth.py
├── security.py
├── transactions.py
├── admin.py
├── requirements.txt
├── .gitignore
└── vaultpay.db       # Created automatically when the app runs
```

The exact structure may change as the project develops.

## Getting Started

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd VaultPay
```

### 2. Create and activate a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
streamlit run app.py
```

Streamlit will display a local URL in the terminal. Open that URL in your browser.

## Account Lockout

VaultPay locks an account after **5 consecutive incorrect password attempts**. A locked account cannot log in, even if the correct password is entered. In this project version, an administrator must unlock the account. Failed login attempts and lockout events are recorded in the audit log.

## Important Notes

- VaultPay is an educational simulation, not a real banking or payment application.
- No real money is deposited, withdrawn, or transferred.
- Do not use real banking credentials or sensitive personal information.
- Keep database files and secrets out of public repositories where appropriate.
- Configure the initial administrator account securely; do not expose default credentials in the source code.

## Testing

The application should be tested for normal and invalid scenarios, including:

- Registration and duplicate usernames
- Successful login and incorrect passwords
- Account lockout and administrator unlock
- Negative or zero transaction amounts
- Withdrawals exceeding the available balance
- Transfers to invalid recipients
- Transfers above the transaction limit
- Unauthorized attempts to access admin functions
- Transaction rollback when a transfer fails

Only tests that have actually been run should be reported as passed.

## Project Purpose

This project was created as part of **Secure Software Engineering** coursework to understand and demonstrate practical security principles while building a simple, functional digital wallet simulator.
