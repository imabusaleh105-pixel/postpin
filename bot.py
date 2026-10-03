import os
import sqlite3
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

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 8762217575
OWNER = "wabillah"

DB = sqlite3.connect("pincycle.db", check_same_thread=False)
DB.row_factory = sqlite3.Row

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

DB.execute(
    "CREATE TABLE IF NOT EXISTS users "
    "(id INTEGER PRIMARY KEY, username TEXT, access INTEGER DEFAULT 0)"
)

DB.execute(
    "CREATE TABLE IF NOT EXISTS groups "
    "(chat_id INTEGER PRIMARY KEY, title TEXT, owner_id INTEGER)"
)

DB.execute(
    "CREATE TABLE IF NOT EXISTS pending "
    "(chat_id INTEGER PRIMARY KEY, hours INTEGER)"
)

DB.commit()


def save_user(user):
    DB.execute(
        "INSERT INTO users (id, username) VALUES (?, ?) "
        "ON CONFLICT(id) DO UPDATE SET username=excluded.username",
        (user.id, (user.username or "").lower()),
    )
    DB.commit()


def allowed(uid):
    if uid == OWNER_ID:
        return True

    row = DB.execute(
        "SELECT access FROM users WHERE id=?",
        (uid,),
    ).fetchone()

    return bool(row and row["access"])


def
