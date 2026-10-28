import os
import sqlite3
from typing import Any, Optional, Union
from werkzeug.security import generate_password_hash

                       
try:
    import MySQLdb
    from MySQLdb.cursors import DictCursor
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    DictCursor = None

class DatabaseManager:
    """
    Robust Database Manager providing seamless interaction with MySQL
    and automated SQLite fallback for testing environments.
    """
    def __init__(self, app=None):
        self.app = app
        self.engine = "mysql"
        if app:
            self.init_app(app)

    def init_app(self, app):
                                                               
        old_engine = getattr(self, "engine", None)
        old_conn = getattr(self, "_memory_conn", None)
        self.app = app
        self.engine = app.config.get("DB_ENGINE", "mysql").lower()
        if self.engine == "sqlite" and app.config.get("SQLITE_PATH") == ":memory:":
            if old_conn is not None:
                try:
                    old_conn.close()
                except Exception:
                    pass
            self._memory_conn = None
        if self.engine == "mysql" and not MYSQL_AVAILABLE:
            app.logger.warning("MySQLdb driver not found, falling back to SQLite.")
            self.engine = "sqlite"

        self.ensure_schema()

    def get_connection(self):
        """Get an active database connection."""
        if self.engine == "sqlite":
            db_path = self.app.config.get("SQLITE_PATH", "online_poll.sqlite3")
            if db_path == ":memory:":
                if not hasattr(self, "_memory_conn") or self._memory_conn is None:
                    self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                    self._memory_conn.row_factory = sqlite3.Row
                    self._memory_conn.execute("PRAGMA foreign_keys = ON")
                return self._memory_conn
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        else:
            cfg = self.app.config
            return MySQLdb.connect(
                host=cfg.get("MYSQL_HOST", "localhost"),
                port=int(cfg.get("MYSQL_PORT", 3306)),
                user=cfg.get("MYSQL_USER", "root"),
                passwd=cfg.get("MYSQL_PASSWORD", ""),
                db=cfg.get("MYSQL_DB", "online_poll_db"),
                charset="utf8mb4"
            )

    def _convert_query(self, query: str) -> str:
        """Convert MySQL %s placeholder to SQLite ? placeholder if in SQLite mode."""
        if self.engine == "sqlite":
            return query.replace("%s", "?")
        return query

    def _release_connection(self, conn):
        """Close connection unless it is a persistent in-memory SQLite connection."""
        if self.engine == "sqlite" and conn is getattr(self, "_memory_conn", None):
            return
        try:
            conn.close()
        except Exception:
            pass

    def fetchall(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute SELECT query and return rows as list of dicts."""
        conn = self.get_connection()
        try:
            sql = self._convert_query(query)
            if self.engine == "sqlite":
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                cursor.close()
                return result
            else:
                cursor = conn.cursor(DictCursor)
                cursor.execute(sql, params)
                result = list(cursor.fetchall())
                cursor.close()
                return result
        finally:
            self._release_connection(conn)

    def fetchone(self, query: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        """Execute SELECT query and return a single row as dict, or None."""
        rows = self.fetchall(query, params)
        return rows[0] if rows else None

    def execute(self, query: str, params: tuple = ()) -> int:
        """Execute INSERT/UPDATE/DELETE query and return lastrowid (or rows affected)."""
        conn = self.get_connection()
        try:
            sql = self._convert_query(query)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            last_id = cursor.lastrowid or cursor.rowcount
            cursor.close()
            return last_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self._release_connection(conn)

    def execute_many(self, query: str, seq_of_params: list[tuple]) -> int:
        """Execute parameterized query with multiple sets of parameters."""
        conn = self.get_connection()
        try:
            sql = self._convert_query(query)
            cursor = conn.cursor()
            cursor.executemany(sql, seq_of_params)
            conn.commit()
            count = cursor.rowcount
            cursor.close()
            return count
        except Exception:
            conn.rollback()
            raise
        finally:
            self._release_connection(conn)

    def ensure_schema(self):
        """Self-heal schema by ensuring all required tables and columns exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if self.engine == "sqlite":
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    google_id TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS polls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    poll_type TEXT NOT NULL DEFAULT 'multiple_choice',
                    expires_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS poll_options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poll_id INTEGER NOT NULL,
                    option_text TEXT NOT NULL,
                    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    poll_id INTEGER NOT NULL,
                    option_id INTEGER NOT NULL,
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, poll_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
                    FOREIGN KEY (option_id) REFERENCES poll_options(id) ON DELETE CASCADE
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS poll_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    poll_id INTEGER NOT NULL,
                    selected_option_ids TEXT,
                    answer_text TEXT,
                    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, poll_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at INTEGER NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """)
                user_cols = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
                if "google_id" not in user_cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
                if "created_at" not in user_cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                poll_cols = [row[1] for row in cursor.execute("PRAGMA table_info(polls)").fetchall()]
                if "created_at" not in poll_cols:
                    cursor.execute("ALTER TABLE polls ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                if "expires_at" not in poll_cols:
                    cursor.execute("ALTER TABLE polls ADD COLUMN expires_at TIMESTAMP NULL")
                if "poll_type" not in poll_cols:
                    cursor.execute("ALTER TABLE polls ADD COLUMN poll_type TEXT NOT NULL DEFAULT 'multiple_choice'")
                conn.commit()
            else:
                                     
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'user',
                    google_id VARCHAR(255) DEFAULT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS polls (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    question VARCHAR(255) NOT NULL,
                    description TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    poll_type VARCHAR(30) NOT NULL DEFAULT 'multiple_choice',
                    expires_at DATETIME NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS poll_options (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    poll_id INT NOT NULL,
                    option_text VARCHAR(255) NOT NULL,
                    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    poll_id INT NOT NULL,
                    option_id INT NOT NULL,
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_poll (user_id, poll_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
                    FOREIGN KEY (option_id) REFERENCES poll_options(id) ON DELETE CASCADE
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS poll_answers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    poll_id INT NOT NULL,
                    selected_option_ids TEXT NULL,
                    answer_text TEXT NULL,
                    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_poll_answer (user_id, poll_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
                )
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    token_hash CHAR(64) NOT NULL UNIQUE,
                    expires_at BIGINT NOT NULL,
                    used TINYINT(1) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """)
                conn.commit()

                                                                          
                cursor.execute("DESCRIBE users")
                cols = [row[0] for row in cursor.fetchall()]
                if "google_id" not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN google_id VARCHAR(255) DEFAULT NULL UNIQUE")
                    conn.commit()
                if "created_at" not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    conn.commit()

                cursor.execute("DESCRIBE polls")
                poll_cols = [row[0] for row in cursor.fetchall()]
                if "created_at" not in poll_cols:
                    cursor.execute("ALTER TABLE polls ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    conn.commit()
                if "expires_at" not in poll_cols:
                    cursor.execute("ALTER TABLE polls ADD COLUMN expires_at DATETIME NULL")
                    conn.commit()
                if "poll_type" not in poll_cols:
                    cursor.execute("ALTER TABLE polls ADD COLUMN poll_type VARCHAR(30) NOT NULL DEFAULT 'multiple_choice'")
                    conn.commit()

                                                                              
                                                                             
            admin_email = (self.app.config.get("ADMIN_EMAIL") or "").strip().lower()
            admin_password = self.app.config.get("ADMIN_PASSWORD") or ""
            if admin_email and admin_password:
                admin_check_sql = self._convert_query("SELECT id FROM users WHERE email = %s")
                cursor.execute(admin_check_sql, (admin_email,))
                admin_user = cursor.fetchone()
                if not admin_user:
                    admin_pw_hash = generate_password_hash(admin_password)
                    insert_admin_sql = self._convert_query(
                        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)"
                    )
                    cursor.execute(insert_admin_sql, ("Administrator", admin_email, admin_pw_hash, "admin"))
                    conn.commit()
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error ensuring database schema: {e}")
        finally:
            cursor.close()
            self._release_connection(conn)

db = DatabaseManager()
