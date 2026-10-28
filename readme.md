# Axion and Voting System with Strict Gmail Verification

A modernized, high-integrity online polling and voting web application built using Python Flask, MySQL/SQLite, Chart.js, and modern Vanilla CSS.

---

## 🌟 Key Features & Enhancements

### 🛡️ 1. Real Gmail-Only Authentication & Security
- **Strict `@gmail.com` Domain Enforcement**: Only authentic Google Gmail accounts (`^[a-zA-Z0-9.]+@gmail\.com$`) are permitted to register and vote. Non-gmail domains (e.g. Yahoo, Outlook, Proton, disposable temporary emails) are strictly rejected.
- **RFC-Compliant Gmail Username Rules**: Enforces 6–30 character length, disallows consecutive periods (`..`), and rejects special characters.
- **Google OAuth 2.0 Integration**: Authenticate with official Google Sign-In with verified email claims.
- **Cryptographic Password Hashing**: Passwords stored using Werkzeug secure password hashes (scrypt/PBKDF2).
- **One Voter, One Vote Guarantee**: Database-level unique constraints and session checks prevent duplicate voting on the same poll.

### 🎨 2. Premium Modern UI / UX Design System
- **Google Typography**: `Outfit` for bold display headings + `Inter` for clean body typography.
- **Glassmorphism & Micro-Interactions**: Soft elevation shadows, floating focus rings, hover lift states, and glowing status pills.
- **Live Client-Side Feedback**: Real-time visual Gmail validator indicator as users type.
- **Interactive Vote Cards**: Radio option cards with option letters (A, B, C, D...) and animated selection glows.
- **Dynamic Graphical Visualizer**: Chart.js graphs supporting instant toggle between **Horizontal Bar Chart** and **Doughnut Chart**.
- **Responsive Layout**: Full mobile responsiveness with toggleable slide-down navigation menu.

### ⚙️ 3. Architecture & Robust Framework Structure
- **Database Abstraction Layer (`db.py`)**: Seamless support for MySQL in production/local development, with automatic SQLite fallback for zero-dependency test environments.
- **Automatic Schema Migration**: Checks and adds required columns (`google_id`, `created_at`) automatically on startup.
- **Role-Based Access Control (RBAC)**: Enforced via `@login_required` and `@admin_required` decorators.
- **CSRF Protection & HTTP Security Headers**: Automatic CSRF token verification and standard security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`).
- **Dynamic Poll Options**: Supports 2 to 6 options flexibly with real-time add/remove buttons.
- **Admin Management & Voter Audit**: Dashboard with participation metrics, status toggling, and dedicated `/admin/voters` audit log.

### 🧪 4. Software Testing Framework
- **Automated Test Suite (`tests/test_poll_system.py`)**:
  - automated test cases covering Gmail domain validation, duplicate registration rejection, RBAC security, voting integrity, dynamic option lifecycle, and HTTP security headers.
  - Can be executed using Python's standard `unittest` or `pytest`.

---

## 🚀 Getting Started

### 1. Requirements
- Python 3.10+
- MySQL (via XAMPP, Docker, or native service)

### 2. Installation
```bash
# Clone or navigate to the directory
cd online_poll_voting_system

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup
Start MySQL (for example, XAMPP → MySQL → Start). The app initializes missing tables when the configured database is reachable. You can also import `database/database.sql` through phpMyAdmin or run:
```bash
mysql -u root -p < database/database.sql
```

If you see `Can't connect to server on 'localhost' (10061)`, MySQL is not accepting connections: start it in XAMPP and verify that the configured host/port are correct. The local database and Railway database are separate; changing one does not change the other.

### 4. Running the Application
```bash
python app.py
```
Open your browser at: **`http://localhost:5000/`**

---

## 🧹 Reset old demo data (no demo records are inserted)

If you only used demo data and want a clean database, start MySQL and run `database/reset_demo_data.sql` in phpMyAdmin (select the `online_poll_db` database first) or import that SQL file. **This permanently deletes all rows from users, polls, poll_options, votes, and password_reset_tokens** but keeps the table structure. It does not add any sample polls or users.

After resetting, configure `ADMIN_EMAIL` and `ADMIN_PASSWORD` in your private `.env` before starting the app. On startup, the app creates that first administrator if the account does not already exist. After login, administrators can use **Create Admin** to add more admins. Admins create all polls manually.

When creating or editing a poll, use **Voting Expiry** to set a deadline; leave it blank for no time limit. The server rejects votes after the deadline. Poll numbers shown in lists are display numbers that re-order after deletion; database IDs stay unchanged so vote relationships remain valid.

## 🧪 Running Automated Tests

Run the full automated test suite anytime using:
```bash
python -m unittest discover tests
```
Tests run against an isolated in-memory SQLite database and do not connect to the production database. Review test output before deploying; automated tests are useful but do not replace a full security review.

---

## 🔐 Administrator and environment setup

For security, the application no longer creates a predictable production administrator password automatically. Configure these environment variables before the first launch:

- `ADMIN_EMAIL` — administrator email
- `ADMIN_PASSWORD` — a strong administrator password (the app stores a password hash)
- `SECRET_KEY` — a long, random secret used to sign sessions
- `GOOGLE_CLIENT_ID` — OAuth Web Client ID
- `GOOGLE_CLIENT_SECRET` — OAuth Web Client Secret
- `GOOGLE_REDIRECT_URI` — exact callback URI registered in Google Cloud

For the Railway deployment, set `GOOGLE_REDIRECT_URI` to:
`https://YOUR-RAILWAY-DOMAIN/auth/google/callback`

Replace `YOUR-RAILWAY-DOMAIN` with the exact public Railway hostname. Add the same exact URI under Google Cloud Console → Google Auth Platform → Clients → your Web client → Authorized redirect URIs. Never commit secrets to GitHub or paste them into chat.

For local development, copy `.env.example` to `.env`, replace the placeholders with your own values, and start MySQL/XAMPP. Keep `.env` private and never commit it. The app loads `.env` when `python-dotenv` is installed. For tests, `TestConfig` provides isolated SQLite and test-only admin credentials.

---

## 📁 Project Structure

```
online_poll_voting_system/
├── app.py                     # Main Flask application with routes & handlers
├── config.py                  # Environment & security configuration
├── auth_utils.py              # Gmail regex validator, CSRF, and RBAC decorators
├── db.py                      # Multi-engine database manager (MySQL + SQLite)
├── requirements.txt           # Python package dependencies
├── database/
│   └── database.sql           # Database schema & default admin seed
├── static/
│   ├── css/
│   │   └── style.css          # Modern design system stylesheet
│   └── js/
│       ├── main.js            # Client-side dynamic validation, options & UI logic
│       └── charts.js          # Chart.js helper scripts
├── templates/
│   ├── base.html              # Responsive base layout with nav & footer
│   ├── index.html             # Landing page with hero & live stats
│   ├── user_login.html        # Voter sign in with Gmail validator
│   ├── register.html          # Voter registration with strict Gmail validation
│   ├── admin_login.html       # Administrator portal login
│   ├── polls.html             # Available polls with live search & filter
│   ├── vote.html              # Interactive voting booth
│   ├── results.html           # Graphical results with Chart.js toggles
│   ├── dashboard.html         # Admin management dashboard
│   ├── voters.html            # Voter audit log
│   ├── create_poll.html       # Dynamic poll creator
│   ├── edit_poll.html         # Poll editor
│   ├── login.html             # Universal login selector
│   └── 404.html               # Custom error page
└── tests/
    ├── __init__.py
    └── test_poll_system.py    # 26 automated unit & integration test cases
```


### Password reset email setup
The Forgot Password page works for both voter and administrator accounts. To deliver reset links, configure these variables in `.env` (or your deployment environment): `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL`. For Gmail, enable 2-Step Verification and create a Google App Password; do not use your regular Gmail password. The reset link expires after 30 minutes and is one-time use. Without SMTP settings, reset emails cannot be delivered.

### Creating administrator accounts
The first administrator must be seeded through `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`. After signing in to the Admin Portal, use **Create Admin** from the dashboard or navigation to create additional administrator accounts. Public voter registration cannot create administrator roles.

## Question types

Polls support multiple choice (one answer), checkboxes (multiple answers), dropdown (one answer), short answer, and paragraph responses. Text answers and checkbox selections are stored in the `poll_answers` table, which is created automatically at application startup. For deployments that manage schema manually, review `database/migration_question_types.sql` before applying it. Copy `.env.example` to `.env` and configure your own secrets/database credentials; do not share real `.env` files.
