import os
import sqlite3
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 8762217575
OWNER_USERNAME = "wabillah"

DB_FILE = "pincycle.db"


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set.")


# =========================
# DATABASE
# =========================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.row_factory = sqlite3.Row

db.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        access INTEGER DEFAULT 0
    )
    """
)

db.execute(
    """
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        added_at TEXT NOT NULL
    )
    """
)

db.execute(
    """
    CREATE TABLE IF NOT EXISTS pending (
        chat_id INTEGER PRIMARY KEY,
        hours INTEGER NOT NULL
    )
    """
)

db.commit()


# =========================
# BASIC FUNCTIONS
# =========================

def now():
    return datetime.now(timezone.utc).isoformat()


def save_user(user):
    username = (user.username or "").lower()

    db.execute(
        """
        INSERT INTO users (user_id, username)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET username = excluded.username
        """,
        (user.id, username),
    )

    db.commit()


def has_access(user_id):
    if user_id == OWNER_ID:
        return True

    row = db.execute(
        "SELECT access FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    return row is not None and row["access"] == 1


def find
