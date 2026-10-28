"""Small SQLite helper for the Groq chat app.

Two tables:
    conversations(id, title, created_at)
    messages(id, conversation_id, role, content, created_at)

The database is a single file (chat.db) created next to this script.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Path of the database file, next to this script.
DB_PATH = Path(__file__).parent / "chat.db"


@contextmanager
def get_connection():
    """Open the database, give it to the caller, then save and close it.

    Usage:
        with get_connection() as conn:
            conn.execute("...")
    """
    conn = sqlite3.connect(DB_PATH)
    # Lets us read columns by name (row["title"]) instead of by position.
    conn.row_factory = sqlite3.Row
    # SQLite ignores links between tables unless we turn this on.
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()  # save the changes if everything went well
    finally:
        conn.close()   # always close, even if there was an error


def init_db() -> None:
    """Create the tables if they don't exist yet (safe to call every run)."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL
                    REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_conversation(title: str = "New chat") -> int:
    """Insert a new conversation and return its id."""
    with get_connection() as conn:
        # The "?" is a placeholder: sqlite fills it safely with our value.
        cursor = conn.execute(
            "INSERT INTO conversations (title) VALUES (?)", (title,)
        )
        return cursor.lastrowid  # id given to the new row


def list_conversations() -> list[dict]:
    """Return all conversations, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def add_message(conversation_id: int, role: str, content: str) -> None:
    """Save one message ('user' or 'assistant') in a conversation."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) "
            "VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )


def get_messages(conversation_id: int) -> list[dict]:
    """Return a conversation's messages in order, as [{'role':..., 'content':...}].

    This is the same format as st.session_state.messages, so we can send
    it directly to the Groq API.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages "
            "WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def rename_conversation(conversation_id: int, title: str) -> None:
    """Change the title of a conversation."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )


def delete_conversation(conversation_id: int) -> None:
    """Delete a conversation and all its messages (ON DELETE CASCADE)."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )