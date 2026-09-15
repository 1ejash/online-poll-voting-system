import os

MYSQL_HOST = os.getenv("MYSQLHOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQLPORT", "3306"))
MYSQL_USER = os.getenv("MYSQLUSER", "root")
MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD", "")
MYSQL_DB = os.getenv("MYSQLDATABASE", "online_poll_db")

GOOGLE_CLIENT_ID = "357512431894-9p5rgsve8khrtitknkl1ghlg8c4bu99r.apps.googleusercontent.com"

GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "online_poll_secret_key"
)