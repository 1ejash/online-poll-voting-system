import os
from flask import Flask, render_template, request, session, redirect
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="templates")

app.secret_key = os.getenv("SECRET_KEY", "online_poll_secret_key")

app.config["MYSQL_HOST"] = os.getenv("MYSQLHOST", "localhost")
app.config["MYSQL_PORT"] = int(os.getenv("MYSQLPORT", "3306"))
app.config["MYSQL_USER"] = os.getenv("MYSQLUSER", "root")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQLPASSWORD", "")
app.config["MYSQL_DB"] = os.getenv("MYSQLDATABASE", "online_poll_db")

mysql = MySQL(app)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template(
                "register.html",
                error="All fields are required."
            )

        cursor = mysql.connection.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email=%s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()

            return render_template(
                "register.html",
                error="Email already registered."
            )

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users
            (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, hashed_password, "user")
        )

        mysql.connection.commit()
        cursor.close()

        return redirect("/user-login")

    return render_template("register.html")


@app.route("/user-login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email=%s
            AND role='user'
            """,
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_role"] = "user"

            return redirect("/polls")

        return render_template(
            "user_login.html",
            error="Invalid email or password."
        )

    return render_template("user_login.html")


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email=%s
            AND role='admin'
            """,
            (email,)
        )

        admin_user = cursor.fetchone()

        cursor.close()

        if admin_user and check_password_hash(
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

    if session.get("user_role") == "admin":
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
        WHERE polls.status = 'active'
        ORDER BY polls.id DESC
        """,
        (user_id,)
    )

    polls_data = cursor.fetchall()

    cursor.close()

    return render_template(
        "polls.html",
        polls=polls_data
    )


@app.route("/vote/<int:poll_id>", methods=["GET", "POST"])
def vote(poll_id):
    if "user_id" not in session:
        return redirect("/user-login")

    if session.get("user_role") == "admin":
        return redirect("/admin")

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM polls
        WHERE id=%s
        AND status='active'
        """,
        (poll_id,)
    )

    poll = cursor.fetchone()

    if not poll:
        cursor.close()

        return redirect("/polls")

    cursor.execute(
        """
        SELECT id
        FROM votes
        WHERE user_id=%s
        AND poll_id=%s
        """,
        (user_id, poll_id)
    )

    existing_vote = cursor.fetchone()

    if request.method == "GET" and existing_vote:
        cursor.close()

        return redirect(f"/results/{poll_id}")

    cursor.execute(
        """
        SELECT
            id,
            poll_id,
            option_text
        FROM poll_options
        WHERE poll_id=%s
        ORDER BY id
        """,
        (poll_id,)
    )

    options = cursor.fetchall()

    if request.method == "POST":
        option_id = request.form.get("option_id")

        if existing_vote:
            cursor.close()

            return redirect(f"/results/{poll_id}")

        if not option_id:
            cursor.close()

            return render_template(
                "vote.html",
                poll=poll,
                options=options,
                error="Please select an option."
            )

        cursor.execute(
            """
            SELECT id
            FROM poll_options
            WHERE id=%s
            AND poll_id=%s
            """,
            (option_id, poll_id)
        )

        valid_option = cursor.fetchone()

        if not valid_option:
            cursor.close()

            return render_template(
                "vote.html",
                poll=poll,
                options=options,
                error="Invalid option selected."
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

            return redirect(f"/results/{poll_id}")

        cursor.close()

        return redirect(f"/results/{poll_id}")

    cursor.close()

    return render_template(
        "vote.html",
        poll=poll,
        options=options
    )


@app.route("/results/<int:poll_id>")
def results(poll_id):
    if "user_id" not in session:
        return redirect("/user-login")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT
            poll_options.option_text,
            COUNT(votes.id) AS vote_count
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

    results_data = cursor.fetchall()

    cursor.execute(
        """
        SELECT *
        FROM polls
        WHERE id=%s
        """,
        (poll_id,)
    )

    poll = cursor.fetchone()

    cursor.close()

    if not poll:
        return redirect("/polls")

    return render_template(
        "results.html",
        poll=poll,
        results=results_data
    )


@app.route("/admin")
def admin():
    if "user_id" not in session:
        return redirect("/admin-login")

    if session.get("user_role") != "admin":
        return redirect("/polls")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM polls
        ORDER BY id DESC
        """
    )

    polls_data = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE role='user'
        """
    )

    total_users = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM polls
        """
    )

    total_polls = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM votes
        """
    )

    total_votes = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM polls
        WHERE status='active'
        """
    )

    active_polls = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        "dashboard.html",
        polls=polls_data,
        total_users=total_users,
        total_polls=total_polls,
        total_votes=total_votes,
        active_polls=active_polls
    )


@app.route("/admin/voters")
def voters():
    if "user_id" not in session:
        return redirect("/admin-login")

    if session.get("user_role") != "admin":
        return redirect("/polls")

    search = request.args.get(
        "search",
        ""
    ).strip()

    cursor = mysql.connection.cursor()

    if search:
        search_value = "%" + search + "%"

        cursor.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                polls.question,
                poll_options.option_text,
                votes.voted_at
            FROM votes

            INNER JOIN users
                ON votes.user_id = users.id

            INNER JOIN polls
                ON votes.poll_id = polls.id

            INNER JOIN poll_options
                ON votes.option_id = poll_options.id

            WHERE users.role='user'
            AND (
                users.name LIKE %s
                OR users.email LIKE %s
            )

            ORDER BY votes.voted_at DESC
            """,
            (
                search_value,
                search_value
            )
        )

    else:
        cursor.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                polls.question,
                poll_options.option_text,
                votes.voted_at
            FROM votes

            INNER JOIN users
                ON votes.user_id = users.id

            INNER JOIN polls
                ON votes.poll_id = polls.id

            INNER JOIN poll_options
                ON votes.option_id = poll_options.id

            WHERE users.role='user'

            ORDER BY votes.voted_at DESC
            """
        )

    voters_data = cursor.fetchall()

    cursor.close()

    return render_template(
        "voters.html",
        voters=voters_data,
        search=search
    )


@app.route(
    "/admin/create-poll",
    methods=["GET", "POST"]
)
def create_poll():
    if "user_id" not in session:
        return redirect("/admin-login")

    if session.get("user_role") != "admin":
        return redirect("/polls")

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        option1 = request.form.get(
            "option1",
            ""
        ).strip()

        option2 = request.form.get(
            "option2",
            ""
        ).strip()

        option3 = request.form.get(
            "option3",
            ""
        ).strip()

        option4 = request.form.get(
            "option4",
            ""
        ).strip()

        if not question:
            return render_template(
                "create_poll.html",
                error="Poll question is required."
            )

        options = [
            option1,
            option2,
            option3,
            option4
        ]

        if any(not option for option in options):
            return render_template(
                "create_poll.html",
                error="All four options are required."
            )

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            INSERT INTO polls
            (question, description, status)
            VALUES (%s, %s, %s)
            """,
            (
                question,
                description,
                "active"
            )
        )

        poll_id = cursor.lastrowid

        for option in options:

            cursor.execute(
                """
                INSERT INTO poll_options
                (poll_id, option_text)
                VALUES (%s, %s)
                """,
                (
                    poll_id,
                    option
                )
            )

        mysql.connection.commit()

        cursor.close()

        return redirect("/admin")

    return render_template("create_poll.html")


@app.route(
    "/admin/edit-poll/<int:poll_id>",
    methods=["GET", "POST"]
)
def edit_poll(poll_id):
    if "user_id" not in session:
        return redirect("/admin-login")

    if session.get("user_role") != "admin":
        return redirect("/polls")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM polls
        WHERE id=%s
        """,
        (poll_id,)
    )

    poll = cursor.fetchone()

    if not poll:
        cursor.close()

        return redirect("/admin")

    cursor.execute(
        """
        SELECT
            id,
            option_text
        FROM poll_options
        WHERE poll_id=%s
        ORDER BY id
        """,
        (poll_id,)
    )

    options = cursor.fetchall()

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        status = request.form.get(
            "status",
            "active"
        ).strip()

        option1 = request.form.get(
            "option1",
            ""
        ).strip()

        option2 = request.form.get(
            "option2",
            ""
        ).strip()

        option3 = request.form.get(
            "option3",
            ""
        ).strip()

        option4 = request.form.get(
            "option4",
            ""
        ).strip()

        new_options = [
            option1,
            option2,
            option3,
            option4
        ]

        if not question:

            cursor.close()

            return render_template(
                "edit_poll.html",
                poll=poll,
                options=options,
                error="Poll question is required."
            )

        if any(not option for option in new_options):

            cursor.close()

            return render_template(
                "edit_poll.html",
                poll=poll,
                options=options,
                error="All four options are required."
            )

        cursor.execute(
            """
            UPDATE polls
            SET question=%s,
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

        for index, option in enumerate(new_options):

            if index < len(options):

                option_id = options[index][0]

                cursor.execute(
                    """
                    UPDATE poll_options
                    SET option_text=%s
                    WHERE id=%s
                    """,
                    (
                        option,
                        option_id
                    )
                )

            else:

                cursor.execute(
                    """
                    INSERT INTO poll_options
                    (poll_id, option_text)
                    VALUES (%s, %s)
                    """,
                    (
                        poll_id,
                        option
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


@app.route(
    "/admin/delete-poll/<int:poll_id>"
)
def delete_poll(poll_id):
    if "user_id" not in session:
        return redirect("/admin-login")

    if session.get("user_role") != "admin":
        return redirect("/polls")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        DELETE FROM votes
        WHERE poll_id=%s
        """,
        (poll_id,)
    )

    cursor.execute(
        """
        DELETE FROM poll_options
        WHERE poll_id=%s
        """,
        (poll_id,)
    )

    cursor.execute(
        """
        DELETE FROM polls
        WHERE id=%s
        """,
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

        if result:
            return "Database connection successful."

        return "Database connection failed."

    except Exception as e:

        return f"Database connection failed: {e}"


if __name__ == "__main__":
    app.run(debug=True)