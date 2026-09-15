import os

from flask import Flask, render_template, request, session, redirect, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth


app = Flask(__name__, template_folder="templates")

app.secret_key = os.getenv(
    "SECRET_KEY",
    "online_poll_secret_key"
)


app.config["MYSQL_HOST"] = os.getenv(
    "MYSQLHOST",
    "localhost"
)

app.config["MYSQL_PORT"] = int(
    os.getenv("MYSQLPORT", "3306")
)

app.config["MYSQL_USER"] = os.getenv(
    "MYSQLUSER",
    "root"
)

app.config["MYSQL_PASSWORD"] = os.getenv(
    "MYSQLPASSWORD",
    ""
)

app.config["MYSQL_DB"] = os.getenv(
    "MYSQLDATABASE",
    "online_poll_db"
)


mysql = MySQL(app)


oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv(
        "GOOGLE_CLIENT_ID",
        "357512431894-9p5rgsve8khrtitknkl1ghlg8c4bu99r.apps.googleusercontent.com"
    ),
    client_secret=os.getenv(
        "GOOGLE_CLIENT_SECRET",
        ""
    ),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register")
def register():
    return redirect(url_for("google_login"))


@app.route("/user-login", methods=["GET", "POST"])
def user_login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email=%s AND role='user'
            """,
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()

        if user and user[3] and check_password_hash(
            user[3],
            password
        ):

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_role"] = "user"

            return redirect("/polls")

        return render_template(
            "user_login.html",
            error="Invalid user email or password. Please use Google Login."
        )

    return render_template("user_login.html")


@app.route("/auth/google")
def google_login():

    redirect_uri = url_for(
        "google_callback",
        _external=True
    )

    return google.authorize_redirect(
        redirect_uri
    )


@app.route("/auth/google/callback")
def google_callback():

    try:

        token = google.authorize_access_token()

        user_info = token.get("userinfo")

        if not user_info:
            user_info = google.userinfo()

        google_id = user_info.get("sub")
        email = user_info.get("email")
        name = user_info.get("name")

        email_verified = user_info.get(
            "email_verified",
            False
        )

        if not email or not email_verified:
            return render_template(
                "user_login.html",
                error="Google email could not be verified."
            )

        email = email.lower()

        if not email.endswith("@gmail.com"):
            return render_template(
                "user_login.html",
                error="Please use a Gmail account."
            )

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE google_id=%s
            """,
            (google_id,)
        )

        user = cursor.fetchone()

        if not user:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email=%s
                """,
                (email,)
            )

            user = cursor.fetchone()

        if user:

            cursor.execute(
                """
                UPDATE users
                SET google_id=%s
                WHERE id=%s
                """,
                (
                    google_id,
                    user[0]
                )
            )

            mysql.connection.commit()

        else:

            cursor.execute(
                """
                INSERT INTO users
                (name, email, password, role, google_id)
                VALUES (%s, %s, %s, 'user', %s)
                """,
                (
                    name,
                    email,
                    "",
                    google_id
                )
            )

            mysql.connection.commit()

            new_user_id = cursor.lastrowid

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE id=%s
                """,
                (new_user_id,)
            )

            user = cursor.fetchone()

        cursor.close()

        session["user_id"] = user[0]
        session["user_name"] = user[1]
        session["user_role"] = user[4]

        return redirect("/polls")

    except Exception:

        return render_template(
            "user_login.html",
            error="Google login failed. Please try again."
        )


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email=%s AND role='admin'
            """,
            (email,)
        )

        admin_user = cursor.fetchone()

        cursor.close()

        if admin_user and admin_user[3] and check_password_hash(
            admin_user[3],
            password
        ):

            session["user_id"] = admin_user[0]
            session["user_name"] = admin_user[1]
            session["user_role"] = "admin"

            return redirect("/admin")

        return render_template(
            "admin_login.html",
            error="Invalid admin email or password."
        )

    return render_template("admin_login.html")


@app.route("/login")
def login():
    return redirect("/user-login")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


@app.route("/polls")
def polls():

    if "user_id" not in session:
        return redirect("/user-login")

    if session["user_role"] == "admin":
        return redirect("/admin")

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT
            polls.id,
            polls.question,
            polls.description,
            polls.status,
            CASE
                WHEN votes.id IS NOT NULL THEN 1
                ELSE 0
            END AS already_voted
        FROM polls
        LEFT JOIN votes
        ON polls.id = votes.poll_id
        AND votes.user_id = %s
        WHERE polls.status='active'
        ORDER BY polls.id DESC
        """,
        (user_id,)
    )

    poll_list = cursor.fetchall()

    cursor.close()

    return render_template(
        "polls.html",
        polls=poll_list
    )


@app.route("/vote/<int:poll_id>", methods=["GET", "POST"])
def vote(poll_id):

    if "user_id" not in session:
        return redirect("/user-login")

    if session["user_role"] == "admin":
        return redirect("/admin")

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT id, question, description
        FROM polls
        WHERE id=%s AND status='active'
        """,
        (poll_id,)
    )

    poll = cursor.fetchone()

    if not poll:

        cursor.close()

        return "Poll not found or poll is closed!", 404

    cursor.execute(
        """
        SELECT id
        FROM votes
        WHERE user_id=%s AND poll_id=%s
        """,
        (
            user_id,
            poll_id
        )
    )

    existing_vote = cursor.fetchone()

    if existing_vote:

        cursor.close()

        return redirect(
            "/results/" + str(poll_id)
        )

    cursor.execute(
        """
        SELECT id, poll_id, option_text
        FROM poll_options
        WHERE poll_id=%s
        ORDER BY id
        """,
        (poll_id,)
    )

    options = cursor.fetchall()

    if request.method == "POST":

        option_id = request.form.get("option_id")

        if not option_id:

            cursor.close()

            return render_template(
                "vote.html",
                poll=poll,
                options=options,
                error="Please select an option before submitting your vote."
            )

        cursor.execute(
            """
            SELECT id
            FROM poll_options
            WHERE id=%s AND poll_id=%s
            """,
            (
                option_id,
                poll_id
            )
        )

        valid_option = cursor.fetchone()

        if not valid_option:

            cursor.close()

            return render_template(
                "vote.html",
                poll=poll,
                options=options,
                error="Invalid voting option."
            )

        try:

            cursor.execute(
                """
                INSERT INTO votes
                (user_id, poll_id, option_id)
                VALUES (%s, %s, %s)
                """,
                (
                    user_id,
                    poll_id,
                    option_id
                )
            )

            mysql.connection.commit()

        except Exception:

            mysql.connection.rollback()
            cursor.close()

            return redirect(
                "/results/" + str(poll_id)
            )

        cursor.close()

        return redirect(
            "/results/" + str(poll_id)
        )

    cursor.close()

    return render_template(
        "vote.html",
        poll=poll,
        options=options
    )


@app.route("/results/<int:poll_id>")
def results(poll_id):

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT id, question, description, status
        FROM polls
        WHERE id=%s
        """,
        (poll_id,)
    )

    poll = cur.fetchone()

    if not poll:

        cur.close()

        return "Poll not found", 404

    cur.execute(
        """
        SELECT
            poll_options.option_text,
            COUNT(votes.id)
        FROM poll_options
        LEFT JOIN votes
            ON poll_options.id = votes.option_id
        WHERE poll_options.poll_id=%s
        GROUP BY
            poll_options.id,
            poll_options.option_text
        ORDER BY poll_options.id
        """,
        (poll_id,)
    )

    results_data = cur.fetchall()

    cur.close()

    return render_template(
        "results.html",
        poll=poll,
        results=results_data
    )


@app.route("/admin")
def admin():

    if "user_id" not in session:
        return redirect("/admin-login")

    if session["user_role"] != "admin":
        return redirect("/polls")

    cursor = mysql.connection.cursor()

    cursor.execute(
        "SELECT * FROM polls ORDER BY id DESC"
    )

    poll_list = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE role='user'"
    )

    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM polls"
    )

    total_polls = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM votes"
    )

    total_votes = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM polls WHERE status='active'"
    )

    active_polls = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        "dashboard.html",
        polls=poll_list,
        total_users=total_users,
        total_polls=total_polls,
        total_votes=total_votes,
        active_polls=active_polls
    )


@app.route("/admin/create-poll", methods=["GET", "POST"])
def create_poll():

    if "user_id" not in session:
        return redirect("/admin-login")

    if session["user_role"] != "admin":
        return redirect("/polls")

    if request.method == "POST":

        question = request.form["question"].strip()

        description = request.form[
            "description"
        ].strip()

        options = [
            request.form["option1"].strip(),
            request.form["option2"].strip(),
            request.form["option3"].strip(),
            request.form["option4"].strip()
        ]

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            INSERT INTO polls
            (question, description, status)
            VALUES (%s, %s, 'active')
            """,
            (
                question,
                description
            )
        )

        poll_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO poll_options
            (poll_id, option_text)
            VALUES
            (%s, %s),
            (%s, %s),
            (%s, %s),
            (%s, %s)
            """,
            (
                poll_id,
                options[0],
                poll_id,
                options[1],
                poll_id,
                options[2],
                poll_id,
                options[3]
            )
        )

        mysql.connection.commit()

        cursor.close()

        return redirect("/admin")

    return render_template(
        "create_poll.html"
    )


@app.route(
    "/admin/edit-poll/<int:poll_id>",
    methods=["GET", "POST"]
)
def edit_poll(poll_id):

    if "user_id" not in session:
        return redirect("/admin-login")

    if session["user_role"] != "admin":
        return redirect("/polls")

    cursor = mysql.connection.cursor()

    cursor.execute(
        "SELECT * FROM polls WHERE id=%s",
        (poll_id,)
    )

    poll = cursor.fetchone()

    if not poll:

        cursor.close()

        return "Poll not found!", 404

    cursor.execute(
        """
        SELECT id, option_text
        FROM poll_options
        WHERE poll_id=%s
        ORDER BY id
        """,
        (poll_id,)
    )

    options = cursor.fetchall()

    if request.method == "POST":

        question = request.form[
            "question"
        ].strip()

        description = request.form[
            "description"
        ].strip()

        status = request.form[
            "status"
        ]

        option_values = [
            request.form["option1"].strip(),
            request.form["option2"].strip(),
            request.form["option3"].strip(),
            request.form["option4"].strip()
        ]

        cursor.execute(
            """
            UPDATE polls
            SET
                question=%s,
                description=%s,
                status=%s
            WHERE id=%s
            """,
            (
                question,
                description,
                status,
                poll_id
            )
        )

        for index in range(4):

            cursor.execute(
                """
                UPDATE poll_options
                SET option_text=%s
                WHERE id=%s AND poll_id=%s
                """,
                (
                    option_values[index],
                    options[index][0],
                    poll_id
                )
            )

        mysql.connection.commit()

        cursor.close()

        return redirect("/admin")

    cursor.close()

    return render_template(
        "edit_poll.html",
        poll=poll,
        options=options
    )


@app.route("/admin/delete-poll/<int:poll_id>")
def delete_poll(poll_id):

    if "user_id" not in session:
        return redirect("/admin-login")

    if session["user_role"] != "admin":
        return redirect("/polls")

    cursor = mysql.connection.cursor()

    cursor.execute(
        "DELETE FROM votes WHERE poll_id=%s",
        (poll_id,)
    )

    cursor.execute(
        "DELETE FROM poll_options WHERE poll_id=%s",
        (poll_id,)
    )

    cursor.execute(
        "DELETE FROM polls WHERE id=%s",
        (poll_id,)
    )

    mysql.connection.commit()

    cursor.close()

    return redirect("/admin")


@app.route("/test-db")
def test_db():

    try:

        cursor = mysql.connection.cursor()

        cursor.execute("SELECT 1")

        result = cursor.fetchone()

        cursor.close()

        return (
            "Database connected successfully! "
            "Result: " + str(result[0])
        )

    except Exception as e:

        return (
            "Database connection failed: "
            + str(e)
        )


if __name__ == "__main__":

    app.run(
        debug=True
    )