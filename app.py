import os
import sys
import time
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime
from flask import (
    Flask, render_template, request, session, redirect,
    url_for, flash, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from urllib.parse import urlparse

from config import Config, TestConfig
from db import db
from auth_utils import (
    is_valid_gmail, validate_password, get_csrf_token,
    validate_csrf_token, login_required, admin_required
)


def safe_next_url(target):
    """Accept only relative URLs on this host to prevent open redirects."""
    if not target:
        return None
    ref = urlparse(request.host_url)
    test = urlparse(target)
    if test.scheme and test.scheme not in ("http", "https"):
        return None
    if test.netloc and (test.netloc != ref.netloc):
        return None
    if target.startswith("//"):
        return None
    return target if target.startswith("/") else None



def send_password_reset_email(app, recipient_email, reset_url):
    """Send a password reset link using the configured SMTP account."""
    cfg = app.config
    required = [cfg.get("SMTP_HOST"), cfg.get("SMTP_USERNAME"), cfg.get("SMTP_PASSWORD"), cfg.get("SMTP_FROM_EMAIL")]
    if not all(required):
        app.logger.warning("Password reset requested, but SMTP is not configured.")
        return False

    message = EmailMessage()
    message["Subject"] = "Reset your Axion account password"
    message["From"] = cfg["SMTP_FROM_EMAIL"]
    message["To"] = recipient_email
    message.set_content(
        "We received a request to reset your Axion account password.\n\n"
        f"Use this one-time link within {max(1, int(cfg.get('PASSWORD_RESET_MAX_AGE', 1800)) // 60)} minutes:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], int(cfg.get("SMTP_PORT", 587)), timeout=15) as server:
            if cfg.get("SMTP_USE_TLS", True):
                server.starttls()
            server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            server.send_message(message)
        return True
    except Exception:
        app.logger.exception("Could not send password reset email")
        return False


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

                                                                             
                                                               
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

                         
    db.init_app(app)

                             
    oauth = OAuth(app)
    google = oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID", ""),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET", ""),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"}
    )

                        
    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": get_csrf_token,
            "current_year": datetime.now().year,
            "active_path": request.path
        }

                                          
    @app.before_request
    def check_csrf():
                                                                                                    
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if app.config.get("WTF_CSRF_ENABLED", True):
                token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
                                                            
                if not request.path.startswith("/auth/google/callback"):
                    if not token or not validate_csrf_token(token):
                        flash("Security verification failed. Please try submitting again.", "danger")
                        return redirect(request.referrer or url_for("home"))

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

                                                                   
                             
                                                                   
    @app.route("/")
    def home():
                                                      
        try:
            total_polls_row = db.fetchone("SELECT COUNT(*) AS count FROM polls")
            total_votes_row = db.fetchone("SELECT COUNT(*) AS count FROM votes")
            total_voters_row = db.fetchone("SELECT COUNT(*) AS count FROM users WHERE role = 'user'")
            
                                                     
            featured_polls = db.fetchall(
                "SELECT id, question, description FROM polls WHERE status = 'active' AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP) ORDER BY id DESC LIMIT 3"
            )
            stats = {
                "polls": total_polls_row["count"] if total_polls_row else 0,
                "votes": total_votes_row["count"] if total_votes_row else 0,
                "voters": total_voters_row["count"] if total_voters_row else 0
            }
        except Exception:
            stats = {"polls": 0, "votes": 0, "voters": 0}
            featured_polls = []

        return render_template("index.html", stats=stats, featured_polls=featured_polls)

                                                                   
                                          
                                                                   
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if session.get("user_id"):
            return redirect(url_for("admin") if session.get("user_role") == "admin" else url_for("polls"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not name:
                flash("Please provide your full name.", "danger")
                return render_template("register.html", name=name, email=email)

                                     
            valid_gmail, err_msg = is_valid_gmail(email)
            if not valid_gmail:
                flash(err_msg, "danger")
                return render_template("register.html", name=name, email=email)

                                 
            if password != confirm_password:
                flash("Passwords do not match. Please re-enter.", "danger")
                return render_template("register.html", name=name, email=email)

            valid_pw, pw_err = validate_password(password)
            if not valid_pw:
                flash(pw_err, "danger")
                return render_template("register.html", name=name, email=email)

                                          
            existing_user = db.fetchone("SELECT id FROM users WHERE email = %s", (email,))
            if existing_user:
                flash("An account with this Gmail address already exists. Please log in.", "warning")
                return redirect(url_for("user_login"))

                                           
            pw_hash = generate_password_hash(password)
            try:
                user_id = db.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'user')",
                    (name, email, pw_hash)
                )
                session["user_id"] = user_id
                session["user_name"] = name
                session["user_role"] = "user"
                session["user_email"] = email

                flash(f"Account created successfully! Welcome, {name}.", "success")
                return redirect(url_for("polls"))
            except Exception as e:
                app.logger.error(f"Registration failure: {e}")
                flash("Registration failed due to a server error. Please try again.", "danger")
                return render_template("register.html", name=name, email=email)

        return render_template("register.html")

    @app.route("/user-login", methods=["GET", "POST"])
    def user_login():
        if session.get("user_id"):
            return redirect(url_for("admin") if session.get("user_role") == "admin" else url_for("polls"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

                                         
            valid_gmail, err_msg = is_valid_gmail(email)
            if not valid_gmail:
                flash("Only authorized @gmail.com accounts are permitted to log in.", "danger")
                return render_template("user_login.html", email=email)

            user = db.fetchone(
                "SELECT id, name, email, password, role FROM users WHERE email = %s AND role = 'user'",
                (email,)
            )

            if user and user.get("password") and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                session["user_role"] = "user"
                session["user_email"] = user["email"]

                flash(f"Logged in successfully. Welcome back, {user['name']}!", "success")
                next_url = safe_next_url(request.args.get("next"))
                return redirect(next_url or url_for("polls"))

            flash(
                "Invalid email or password. If you originally signed up with Google, please click 'Continue with Google'.",
                "danger"
            )
            return render_template("user_login.html", email=email)

        return render_template("user_login.html")

    @app.route("/admin-login", methods=["GET", "POST"])
    def admin_login():
        if session.get("user_id") and session.get("user_role") == "admin":
            return redirect(url_for("admin"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            admin_user = db.fetchone(
                "SELECT id, name, email, password, role FROM users WHERE email = %s AND role = 'admin'",
                (email,)
            )

            if admin_user and admin_user.get("password") and check_password_hash(admin_user["password"], password):
                session["user_id"] = admin_user["id"]
                session["user_name"] = admin_user["name"]
                session["user_role"] = "admin"
                session["user_email"] = admin_user["email"]

                flash(f"Administrator access granted. Welcome, {admin_user['name']}!", "success")
                next_url = safe_next_url(request.args.get("next"))
                return redirect(next_url or url_for("admin"))

            flash("Invalid admin credentials. Access denied.", "danger")
            return render_template("admin_login.html", email=email)

        return render_template("admin_login.html")

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            valid_gmail, _ = is_valid_gmail(email)
                                                                                               
            if valid_gmail:
                user = db.fetchone("SELECT id, email FROM users WHERE email = %s", (email,))
                if user:
                    raw_token = secrets.token_urlsafe(32)
                    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                    expires_at = int(time.time()) + int(app.config.get("PASSWORD_RESET_MAX_AGE", 1800))
                    try:
                        db.execute(
                            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used) VALUES (%s, %s, %s, 0)",
                            (user["id"], token_hash, expires_at)
                        )
                        reset_url = url_for("reset_password", token=raw_token, _external=True)
                        if not send_password_reset_email(app, user["email"], reset_url):
                                                                               
                            db.execute("UPDATE password_reset_tokens SET used = 1 WHERE token_hash = %s", (token_hash,))
                            flash("If that Gmail address belongs to an account, a reset email will be sent shortly. If no email arrives, contact the administrator to check email delivery settings.", "info")
                            return redirect(url_for("forgot_password"))
                    except Exception:
                        app.logger.exception("Password reset request failed")
                        flash("Password reset is temporarily unavailable. Please try again later.", "danger")
                        return render_template("forgot_password.html", email=email)
            flash("If that Gmail address belongs to an account, a password-reset link will be sent shortly.", "info")
            return redirect(url_for("forgot_password"))
        return render_template("forgot_password.html")

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        reset_record = db.fetchone(
            "SELECT id, user_id, expires_at, used FROM password_reset_tokens WHERE token_hash = %s",
            (token_hash,)
        )
        if not reset_record or reset_record.get("used") or int(reset_record.get("expires_at", 0)) < int(time.time()):
            flash("This password-reset link is invalid, expired, or already used. Request a new one.", "danger")
            return redirect(url_for("forgot_password"))

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return render_template("reset_password.html", token=token)
            valid_pw, pw_err = validate_password(password)
            if not valid_pw:
                flash(pw_err, "danger")
                return render_template("reset_password.html", token=token)
            db.execute("UPDATE users SET password = %s WHERE id = %s", (generate_password_hash(password), reset_record["user_id"]))
            db.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = %s", (reset_record["id"],))
                                                                            
            db.execute("UPDATE password_reset_tokens SET used = 1 WHERE user_id = %s", (reset_record["user_id"],))
            flash("Password updated successfully. You can now sign in with your new password.", "success")
            return redirect(url_for("admin_login") if db.fetchone("SELECT role FROM users WHERE id = %s", (reset_record["user_id"],)).get("role") == "admin" else url_for("user_login"))
        return render_template("reset_password.html", token=token)

    @app.route("/admin/create-admin", methods=["GET", "POST"])
    @admin_required
    def create_admin():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not name:
                flash("Please enter the administrator's name.", "danger")
            else:
                valid_gmail, gmail_error = is_valid_gmail(email)
                valid_pw, pw_error = validate_password(password)
                if not valid_gmail:
                    flash(gmail_error, "danger")
                elif password != confirm_password:
                    flash("Passwords do not match.", "danger")
                elif not valid_pw:
                    flash(pw_error, "danger")
                elif db.fetchone("SELECT id FROM users WHERE email = %s", (email,)):
                    flash("An account with that Gmail already exists.", "warning")
                else:
                    try:
                        db.execute(
                            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'admin')",
                            (name, email, generate_password_hash(password))
                        )
                        flash("Administrator account created successfully. They can now sign in through Admin Portal.", "success")
                        return redirect(url_for("admin"))
                    except Exception:
                        app.logger.exception("Admin account creation failed")
                        flash("Could not create the administrator account. Please try again.", "danger")
        return render_template("create_admin.html")

    @app.route("/login")
    def login():
        """Universal login selector."""
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been securely signed out.", "info")
        return redirect(url_for("home"))

                                                                   
                                 
                                                                   
    @app.route("/auth/google")
    @app.route("/login/google")
    def google_login():
                                                                                     
        if not app.config.get("GOOGLE_CLIENT_SECRET"):
            flash(
                "Google OAuth client secret is not configured in environment. Please use email & password login or set GOOGLE_CLIENT_SECRET.",
                "warning"
            )
            return redirect(url_for("user_login"))

                                                                             
                                                                               
        redirect_uri = app.config.get("GOOGLE_REDIRECT_URI") or url_for(
            "google_callback",
            _external=True,
            _scheme="https" if (request.is_secure or os.getenv("RAILWAY_ENVIRONMENT")) else None
        )
        return google.authorize_redirect(redirect_uri)

    @app.route("/auth/google/callback")
    def google_callback():
        try:
            token = google.authorize_access_token()
            user_info = token.get("userinfo") or google.userinfo()

            google_id = user_info.get("sub")
            email = user_info.get("email", "").strip().lower()
            name = user_info.get("name", "Google User")
            email_verified = user_info.get("email_verified", False)

            if not email or not email_verified:
                flash("Google email could not be verified by Google.", "danger")
                return redirect(url_for("user_login"))

                                      
            valid_gmail, err_msg = is_valid_gmail(email)
            if not valid_gmail:
                flash(f"Access Denied: {err_msg}", "danger")
                return redirect(url_for("user_login"))

                                                                           
                                                                             
                                                
            user = db.fetchone(
                "SELECT id, name, email, password, role, google_id FROM users WHERE google_id = %s",
                (google_id,)
            )

            if not user:
                email_user = db.fetchone(
                    "SELECT id, name, email, password, role, google_id FROM users WHERE email = %s",
                    (email,)
                )
                if email_user and email_user.get("role") != "user":
                    flash("This Google account cannot be used for administrator sign-in. Use Admin Login.", "danger")
                    return redirect(url_for("user_login"))

                if email_user:
                                                                              
                    if email_user.get("google_id") and email_user["google_id"] != google_id:
                        flash("This email is already linked to a different Google account.", "danger")
                        return redirect(url_for("user_login"))
                    if not email_user.get("google_id"):
                        db.execute(
                            "UPDATE users SET google_id = %s WHERE id = %s AND role = 'user'",
                            (google_id, email_user["id"])
                        )
                    user = db.fetchone(
                        "SELECT id, name, email, role, google_id FROM users WHERE id = %s AND role = 'user'",
                        (email_user["id"],)
                    )
                else:
                    new_id = db.execute(
                        "INSERT INTO users (name, email, password, role, google_id) VALUES (%s, %s, %s, 'user', %s)",
                        (name, email, "", google_id)
                    )
                    user = db.fetchone(
                        "SELECT id, name, email, role, google_id FROM users WHERE id = %s AND role = 'user'",
                        (new_id,)
                    )

            if not user or user.get("role") != "user":
                flash("Google sign-in is available for voter accounts only.", "danger")
                return redirect(url_for("user_login"))

                                                              
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = "user"
            session["user_email"] = user["email"]

            flash(f"Successfully authenticated with Google as {email}!", "success")
            return redirect(url_for("polls"))

        except Exception as e:
            app.logger.error(f"Google OAuth Exception: {e}")
            flash("Google authentication failed or was cancelled. Please try again.", "danger")
            return redirect(url_for("user_login"))

                                                                   
                            
                                                                   
    @app.route("/polls")
    @login_required
    def polls():
        if session.get("user_role") == "admin":
            return redirect(url_for("admin"))

        user_id = session["user_id"]

                                                                                   
        query = """
        SELECT
            p.id,
            p.question,
            p.description,
            p.status,
            p.created_at,
            p.expires_at,
            ((SELECT COUNT(*) FROM votes v WHERE v.poll_id = p.id) +
             (SELECT COUNT(*) FROM poll_answers pa WHERE pa.poll_id = p.id)) AS total_votes,
            CASE WHEN EXISTS (
                SELECT 1 FROM votes v WHERE v.poll_id = p.id AND v.user_id = %s
            ) OR EXISTS (
                SELECT 1 FROM poll_answers pa WHERE pa.poll_id = p.id AND pa.user_id = %s
            ) THEN 1 ELSE 0 END AS already_voted
        FROM polls p
        WHERE p.status = 'active' AND (p.expires_at IS NULL OR p.expires_at > CURRENT_TIMESTAMP)
        ORDER BY p.id DESC
        """
        poll_list = db.fetchall(query, (user_id, user_id))
        return render_template("polls.html", polls=poll_list)

    @app.route("/vote/<int:poll_id>", methods=["GET", "POST"])
    @login_required
    def vote(poll_id):
        if session.get("user_role") == "admin":
            flash("Administrators cannot cast votes. Please log in as a registered voter.", "info")
            return redirect(url_for("admin"))

        user_id = session["user_id"]

                                          
        poll = db.fetchone("SELECT id, question, description, status, poll_type, expires_at FROM polls WHERE id = %s", (poll_id,))
        if not poll:
            flash("The requested poll does not exist.", "warning")
            return redirect(url_for("polls"))

        if poll["status"] != "active":
            flash("This poll is closed and no longer accepting votes.", "warning")
            return redirect(url_for("results", poll_id=poll_id))
        if poll.get("expires_at"):
            expiry = poll["expires_at"]
            if isinstance(expiry, str):
                try:
                    expiry = datetime.fromisoformat(expiry)
                except ValueError:
                    expiry = None
            if expiry and expiry <= datetime.now():
                flash("Voting time has expired for this poll.", "warning")
                return redirect(url_for("results", poll_id=poll_id))

                                
        existing_vote = db.fetchone(
            "SELECT id FROM votes WHERE user_id = %s AND poll_id = %s",
            (user_id, poll_id)
        ) or db.fetchone(
            "SELECT id FROM poll_answers WHERE user_id = %s AND poll_id = %s",
            (user_id, poll_id)
        )
        if existing_vote:
            flash("You have already cast your vote in this poll. Here are the latest results.", "info")
            return redirect(url_for("results", poll_id=poll_id))

                            
        options = db.fetchall(
            "SELECT id, poll_id, option_text FROM poll_options WHERE poll_id = %s ORDER BY id",
            (poll_id,)
        )

        if request.method == "POST":
            poll_type = poll.get("poll_type", "multiple_choice")
            if poll_type in {"short_answer", "paragraph"}:
                answer_text = request.form.get("answer_text", "").strip()
                max_length = 500 if poll_type == "short_answer" else 5000
                if not answer_text or len(answer_text) > max_length:
                    flash("Please enter a valid answer within the allowed length.", "danger")
                    return render_template("vote.html", poll=poll, options=options)
                db.execute("INSERT INTO poll_answers (user_id, poll_id, answer_text) VALUES (%s, %s, %s)", (user_id, poll_id, answer_text))
            elif poll_type == "checkboxes":
                # HTML checkboxes submit repeated option_ids fields. Read every value,
                # normalize IDs, validate them against this poll, and store the full set.
                submitted_ids = request.form.getlist("option_ids")
                if not submitted_ids:
                    flash("Please select at least one option.", "danger")
                    return render_template("vote.html", poll=poll, options=options)
                if any(not str(value).strip().isdigit() for value in submitted_ids):
                    flash("One or more selected options are invalid.", "danger")
                    return render_template("vote.html", poll=poll, options=options)
                selected_ids = list(dict.fromkeys(int(value) for value in submitted_ids))
                placeholders = ",".join(["%s"] * len(selected_ids))
                valid = db.fetchall(
                    f"SELECT id FROM poll_options WHERE poll_id = %s AND id IN ({placeholders})",
                    tuple([poll_id] + selected_ids)
                )
                valid_ids = sorted({int(row["id"]) for row in valid})
                if len(valid_ids) != len(selected_ids):
                    flash("One or more selected options do not belong to this poll.", "danger")
                    return render_template("vote.html", poll=poll, options=options)
                stored_ids = "," + ",".join(str(option_id) for option_id in valid_ids) + ","
                db.execute(
                    "INSERT INTO poll_answers (user_id, poll_id, selected_option_ids) VALUES (%s, %s, %s)",
                    (user_id, poll_id, stored_ids)
                )
            elif poll_type == "dropdown":
                # Dropdown submits one option_id, just like single-choice voting.
                option_id = request.form.get("option_id", "").strip()
                valid_option = db.fetchone(
                    "SELECT id FROM poll_options WHERE id = %s AND poll_id = %s",
                    (option_id, poll_id)
                ) if option_id.isdigit() else None
                if not valid_option:
                    flash("Please choose a valid option from the dropdown.", "danger")
                    return render_template("vote.html", poll=poll, options=options)
                db.execute("INSERT INTO votes (user_id, poll_id, option_id) VALUES (%s, %s, %s)", (user_id, poll_id, option_id))
            else:
                option_id = request.form.get("option_id")
                valid_option = db.fetchone("SELECT id FROM poll_options WHERE id = %s AND poll_id = %s", (option_id, poll_id)) if option_id else None
                if not valid_option:
                    flash("Please select a valid option before submitting your vote.", "danger")
                    return render_template("vote.html", poll=poll, options=options)
                db.execute("INSERT INTO votes (user_id, poll_id, option_id) VALUES (%s, %s, %s)", (user_id, poll_id, option_id))
            flash("Your response has been securely recorded! Thank you for participating.", "success")
            return redirect(url_for("results", poll_id=poll_id))

        return render_template("vote.html", poll=poll, options=options)

    @app.route("/results/<int:poll_id>")
    def results(poll_id):
        poll = db.fetchone("SELECT id, question, description, status, poll_type, created_at FROM polls WHERE id = %s", (poll_id,))
        if not poll:
            flash("Poll not found.", "warning")
            return redirect(url_for("polls" if session.get("user_id") else "home"))

                                            
        query = """
        SELECT
            po.id,
            po.option_text,
            COUNT(v.id) AS vote_count
        FROM poll_options po
        LEFT JOIN votes v ON po.id = v.option_id
        WHERE po.poll_id = %s
        GROUP BY po.id, po.option_text
        ORDER BY po.id
        """
        raw_results = db.fetchall(query, (poll_id,))

        poll_type = poll.get("poll_type", "multiple_choice")
        text_answers = []
        if poll_type == "checkboxes":
            answer_rows = db.fetchall("SELECT selected_option_ids FROM poll_answers WHERE poll_id = %s AND selected_option_ids IS NOT NULL", (poll_id,))
            counts = {str(item["id"]): 0 for item in raw_results}
            for answer in answer_rows:
                selected_ids = {part for part in (answer.get("selected_option_ids") or "").split(",") if part}
                for selected_id in selected_ids:
                    if selected_id in counts:
                        counts[selected_id] += 1
            for item in raw_results:
                item["vote_count"] = counts.get(str(item["id"]), 0)
        elif poll_type in {"short_answer", "paragraph"}:
            text_answers = db.fetchall("SELECT answer_text, answered_at FROM poll_answers WHERE poll_id = %s AND answer_text IS NOT NULL ORDER BY id DESC", (poll_id,))

        total_votes = sum(item["vote_count"] for item in raw_results)
        max_votes = max((item["vote_count"] for item in raw_results), default=0)

                                 
        results_data = []
        for item in raw_results:
            pct = round((item["vote_count"] / total_votes * 100), 1) if total_votes > 0 else 0
            results_data.append({
                "id": item["id"],
                "option_text": item["option_text"],
                "vote_count": item["vote_count"],
                "percentage": pct,
                "is_leading": (item["vote_count"] == max_votes and max_votes > 0)
            })

        return render_template(
            "results.html",
            poll=poll,
            results=results_data,
            total_votes=total_votes,
            max_votes=max_votes,
            text_answers=text_answers,
            response_count=(len(text_answers) if poll_type in {"short_answer", "paragraph"} else (len(answer_rows) if poll_type == "checkboxes" else total_votes)),
            poll_type=poll_type
        )

                                                                   
                             
                                                                   
    @app.route("/admin")
    @admin_required
    def admin():
                     
        total_users_row = db.fetchone("SELECT COUNT(*) AS count FROM users WHERE role = 'user'")
        total_polls_row = db.fetchone("SELECT COUNT(*) AS count FROM polls")
        total_votes_row = db.fetchone("SELECT COUNT(*) AS count FROM votes")
        active_polls_row = db.fetchone("SELECT COUNT(*) AS count FROM polls WHERE status = 'active'")

                                                           
        query = """
        SELECT
            p.id,
            p.question,
            p.description,
            p.status,
            p.created_at,
            p.expires_at,
            (SELECT COUNT(*) FROM votes v WHERE v.poll_id = p.id) AS vote_count,
            (SELECT COUNT(*) FROM poll_options po WHERE po.poll_id = p.id) AS options_count
        FROM polls p
        ORDER BY p.id DESC
        """
        polls_list = db.fetchall(query)

        return render_template(
            "dashboard.html",
            polls=polls_list,
            total_users=total_users_row["count"] if total_users_row else 0,
            total_polls=total_polls_row["count"] if total_polls_row else 0,
            total_votes=total_votes_row["count"] if total_votes_row else 0,
            active_polls=active_polls_row["count"] if active_polls_row else 0
        )

    @app.route("/admin/create-poll", methods=["GET", "POST"])
    @admin_required
    def create_poll():
        if request.method == "POST":
            question = request.form.get("question", "").strip()
            description = request.form.get("description", "").strip()
            poll_type = request.form.get("poll_type", "multiple_choice").strip().lower()
            if poll_type not in {"multiple_choice", "checkboxes", "dropdown", "short_answer", "paragraph"}:
                poll_type = "multiple_choice"
            expiry_input = request.form.get("expires_at", "").strip()
            expires_at = None
            if expiry_input:
                try:
                    expires_at = datetime.strptime(expiry_input, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    try:
                        expires_at = datetime.strptime(expiry_input, "%Y-%m-%dT%H:%M")
                    except ValueError:
                        flash("Please enter a valid voting expiry date and time.", "danger")
                        return render_template("create_poll.html", question=question, description=description)
                if expires_at <= datetime.now():
                    flash("Voting expiry must be in the future.", "danger")
                    return render_template("create_poll.html", question=question, description=description)

                                                                             
            options = []
            for i in range(1, 10):
                opt = request.form.get(f"option{i}", "").strip()
                if opt:
                    options.append(opt)

            if not question:
                flash("Poll question is required.", "danger")
                return render_template("create_poll.html", question=question, description=description)

            if poll_type not in {"short_answer", "paragraph"} and len(options) < 2:
                flash("A poll must contain at least 2 distinct voting options.", "danger")
                return render_template("create_poll.html", question=question, description=description)
            if poll_type not in {"short_answer", "paragraph"} and len(options) > app.config.get("MAX_POLL_OPTIONS", 6):
                flash(f"A poll can have at most {app.config.get('MAX_POLL_OPTIONS', 6)} options.", "danger")
                return render_template("create_poll.html", question=question, description=description)
            if poll_type not in {"short_answer", "paragraph"} and len({opt.casefold() for opt in options}) != len(options):
                flash("Each poll option must be unique.", "danger")
                return render_template("create_poll.html", question=question, description=description)

            try:
                poll_id = db.execute(
                    "INSERT INTO polls (question, description, status, poll_type, expires_at) VALUES (%s, %s, 'active', %s, %s)",
                    (question, description, poll_type, expires_at)
                )

                option_records = [(poll_id, opt) for opt in options]
                db.execute_many(
                    "INSERT INTO poll_options (poll_id, option_text) VALUES (%s, %s)",
                    option_records
                )

                flash("New poll has been successfully published!", "success")
                return redirect(url_for("admin"))
            except Exception as e:
                app.logger.error(f"Error creating poll: {e}")
                flash("Failed to create poll. Please try again.", "danger")

        return render_template("create_poll.html")

    @app.route("/admin/edit-poll/<int:poll_id>", methods=["GET", "POST"])
    @admin_required
    def edit_poll(poll_id):
        poll = db.fetchone("SELECT id, question, description, status, poll_type, expires_at FROM polls WHERE id = %s", (poll_id,))
        if not poll:
            flash("Poll not found.", "warning")
            return redirect(url_for("admin"))

        options = db.fetchall(
            "SELECT id, option_text FROM poll_options WHERE poll_id = %s ORDER BY id",
            (poll_id,)
        )

        if request.method == "POST":
            question = request.form.get("question", "").strip()
            description = request.form.get("description", "").strip()
            poll_type = request.form.get("poll_type", poll.get("poll_type", "multiple_choice")).strip().lower()
            if poll_type not in {"multiple_choice", "checkboxes", "dropdown", "short_answer", "paragraph"}:
                poll_type = "multiple_choice"
            status = request.form.get("status", "active").strip().lower()
            expiry_input = request.form.get("expires_at", "").strip()
            expires_at = None
            if expiry_input:
                try:
                    expires_at = datetime.strptime(expiry_input, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    try:
                        expires_at = datetime.strptime(expiry_input, "%Y-%m-%dT%H:%M")
                    except ValueError:
                        flash("Please enter a valid voting expiry date and time.", "danger")
                        return render_template("edit_poll.html", poll=poll, options=options)
                if expires_at <= datetime.now():
                    flash("Voting expiry must be in the future.", "danger")
                    return render_template("edit_poll.html", poll=poll, options=options)
            if status not in {"active", "closed"}:
                flash("Invalid poll status.", "danger")
                return render_template("edit_poll.html", poll=poll, options=options)

            submitted_options = []
            for i in range(1, 10):
                opt = request.form.get(f"option{i}", "").strip()
                if opt:
                    submitted_options.append(opt)

            if not question:
                flash("Poll question cannot be empty.", "danger")
                return render_template("edit_poll.html", poll=poll, options=options)

            if poll_type not in {"short_answer", "paragraph"} and len(submitted_options) < 2:
                flash("At least 2 options are required.", "danger")
                return render_template("edit_poll.html", poll=poll, options=options)
            if poll_type not in {"short_answer", "paragraph"} and len(submitted_options) > app.config.get("MAX_POLL_OPTIONS", 6):
                flash(f"A poll can have at most {app.config.get('MAX_POLL_OPTIONS', 6)} options.", "danger")
                return render_template("edit_poll.html", poll=poll, options=options)
            if poll_type not in {"short_answer", "paragraph"} and len({opt.casefold() for opt in submitted_options}) != len(submitted_options):
                flash("Each poll option must be unique.", "danger")
                return render_template("edit_poll.html", poll=poll, options=options)

                                                                                   
                                                   
            vote_count = db.fetchone("SELECT COUNT(*) AS count FROM votes WHERE poll_id = %s", (poll_id,))
            answer_count = db.fetchone("SELECT COUNT(*) AS count FROM poll_answers WHERE poll_id = %s", (poll_id,))
            has_responses = ((vote_count and vote_count["count"] > 0) or (answer_count and answer_count["count"] > 0))
            if has_responses and poll_type != poll.get("poll_type", "multiple_choice"):
                flash("Question type cannot be changed after the first response. Close this poll and create a new one instead.", "danger")
                return render_template("edit_poll.html", poll=poll, options=options)
            if has_responses:
                existing_texts = [o["option_text"] for o in options]
                if submitted_options != existing_texts:
                    flash("Voting options cannot be changed after the first vote. Close this poll and create a new one instead.", "danger")
                    return render_template("edit_poll.html", poll=poll, options=options)

            try:
                db.execute(
                    "UPDATE polls SET question = %s, description = %s, status = %s, poll_type = %s, expires_at = %s WHERE id = %s",
                    (question, description, status, poll_type, expires_at, poll_id)
                )

                                                            
                if poll_type in {"short_answer", "paragraph"}:
                    submitted_options = [o["option_text"] for o in options]
                for idx, opt_text in enumerate(submitted_options):
                    if idx < len(options):
                        db.execute(
                            "UPDATE poll_options SET option_text = %s WHERE id = %s AND poll_id = %s",
                            (opt_text, options[idx]["id"], poll_id)
                        )
                    else:
                        db.execute(
                            "INSERT INTO poll_options (poll_id, option_text) VALUES (%s, %s)",
                            (poll_id, opt_text)
                        )

                                                                   
                if len(options) > len(submitted_options):
                    for extra_opt in options[len(submitted_options):]:
                        db.execute("DELETE FROM poll_options WHERE id = %s", (extra_opt["id"],))

                flash("Poll details and options have been updated successfully.", "success")
                return redirect(url_for("admin"))
            except Exception as e:
                app.logger.error(f"Error editing poll: {e}")
                flash("Failed to update poll. Please try again.", "danger")

        return render_template("edit_poll.html", poll=poll, options=options)

    @app.route("/admin/toggle-poll/<int:poll_id>", methods=["POST"])
    @admin_required
    def toggle_poll(poll_id):
        poll = db.fetchone("SELECT id, status FROM polls WHERE id = %s", (poll_id,))
        if not poll:
            flash("Poll not found.", "warning")
            return redirect(url_for("admin"))

        new_status = "closed" if poll["status"] == "active" else "active"
        db.execute("UPDATE polls SET status = %s WHERE id = %s", (new_status, poll_id))
        flash(f"Poll has been marked as {new_status.upper()}.", "success")
        return redirect(url_for("admin"))

    @app.route("/admin/delete-poll/<int:poll_id>", methods=["POST"])
    @admin_required
    def delete_poll(poll_id):
                                                                             
        try:
            db.execute("DELETE FROM votes WHERE poll_id = %s", (poll_id,))
            db.execute("DELETE FROM poll_options WHERE poll_id = %s", (poll_id,))
            db.execute("DELETE FROM polls WHERE id = %s", (poll_id,))
            flash("Poll and all its associated votes have been permanently deleted.", "success")
        except Exception as e:
            app.logger.error(f"Error deleting poll: {e}")
            flash("Error deleting poll.", "danger")

        return redirect(url_for("admin"))

    @app.route("/admin/voters")
    @admin_required
    def voters():
        """Audit log of registered Gmail voters and participation history."""
        query = """
        SELECT
            u.id,
            u.name,
            u.email,
            u.role,
            u.google_id,
            u.created_at,
            COUNT(v.id) AS total_votes_cast,
            MAX(v.voted_at) AS last_voted_at
        FROM users u
        LEFT JOIN votes v ON u.id = v.user_id
        WHERE u.role = 'user'
        GROUP BY u.id, u.name, u.email, u.role, u.google_id, u.created_at
        ORDER BY u.id DESC
        """
        voter_records = db.fetchall(query)
        return render_template("voters.html", voters=voter_records)

                                                                   
                            
                                                                   
    @app.route("/health")
    @app.route("/test-db")
    def health():
        try:
            res = db.fetchone("SELECT 1 AS ok")
            return jsonify({
                "status": "healthy",
                "database": "connected" if res and res.get("ok") == 1 else "unexpected_result",
                "engine": db.engine,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            return jsonify({
                "status": "unhealthy",
                "database_error": str(e),
                "engine": db.engine
            }), 500

                                                                   
                        
                                                                   
    @app.errorhandler(400)
    def bad_request(e):
        return render_template("404.html", error_code=400, message="Bad Request"), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("404.html", error_code=403, message="Access Forbidden"), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html", error_code=404, message="Page Not Found"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("404.html", error_code=500, message="Internal Server Error"), 500

    return app


                                     
app = create_app(Config)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)