import os
import sqlite3
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 8762217575
OWNER_USERNAME = "wabillah"

DB_FILE = "pincycle.db"


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 1
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    owner_id INTEGER,
    active INTEGER DEFAULT 1,
    duration INTEGER DEFAULT 0,
    waiting INTEGER DEFAULT 0
)
""")

db.commit()


# =========================================================
# ACCESS
# =========================================================

def has_access(user_id: int) -> bool:

    if user_id == OWNER_ID:
        return True

    row = db.execute(
        "SELECT active FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    return bool(row and row[0] == 1)


def grant_access(user_id: int):

    db.execute(
        """
        INSERT INTO users(user_id, active)
        VALUES (?, 1)
        ON CONFLICT(user_id)
        DO UPDATE SET active = 1
        """,
        (user_id,)
    )

    db.commit()


def remove_access(user_id: int):

    db.execute(
        "UPDATE users SET active = 0 WHERE user_id = ?",
        (user_id,)
    )

    db.commit()


# =========================================================
# GROUP DATABASE
# =========================================================

def save_group(chat_id, title, owner_id):

    db.execute(
        """
        INSERT INTO groups(
            chat_id,
            title,
            owner_id,
            active,
            duration,
            waiting
        )
        VALUES (?, ?, ?, 1, 0, 0)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            title = excluded.title,
            owner_id = excluded.owner_id,
            active = 1
        """,
        (chat_id, title, owner_id)
    )

    db.commit()


def get_group(chat_id):

    return db.execute(
        """
        SELECT chat_id, title, owner_id, active, duration, waiting
        FROM groups
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()


def update_group(chat_id, duration=None, waiting=None):

    if duration is not None:

        db.execute(
            """
            UPDATE groups
            SET duration = ?
            WHERE chat_id = ?
            """,
            (duration, chat_id)
        )

    if waiting is not None:

        db.execute(
            """
            UPDATE groups
            SET waiting = ?
            WHERE chat_id = ?
            """,
            (1 if waiting else 0, chat_id)
        )

    db.commit()


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Group",
                callback_data="add_group"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Useful Commands",
                callback_data="useful_commands"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Contact Owner",
                url=f"https://t.me/{OWNER_USERNAME}"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not has_access(user.id):

        keyboard = [
            [
                InlineKeyboardButton(
                    "👤 Contact Owner",
                    url=f"https://t.me/{OWNER_USERNAME}"
                )
            ]
        ]

        await update.message.reply_text(
            "❌ You don't have access to use Pin Cycle.\n\n"
            "Please contact the owner to request access.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    await update.message.reply_text(
        "📌 Pin Cycle\n\n"
        "Select an option below:",
        reply_markup=main_menu()
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if not has_access(user_id):

        await query.edit_message_text(
            "❌ You don't have access to use Pin Cycle."
        )

        return

    # =====================================================
    # ADD GROUP
    # =====================================================

    if query.data == "add_group":

        button = KeyboardButton(
            "➕ Select Group",
            request_chat={
                "request_id": 1001,
                "chat_is_channel": False,
                "chat_is_forum": False,
                "bot_is_member": True,
            }
        )

        keyboard = ReplyKeyboardMarkup(
            [[button]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await query.message.reply_text(
            "Select the group where you want to use Pin Cycle.",
            reply_markup=keyboard
        )

        return

    # =====================================================
    # USEFUL COMMANDS
    # =====================================================

    if query.data == "useful_commands":

        keyboard = [
            [
                InlineKeyboardButton(
                    "📌 /pin 4h",
                    callback_data="cmd_4"
                )
            ],
            [
                InlineKeyboardButton(
                    "📌 /pin 8h",
                    callback_data="cmd_8"
                )
            ],
            [
                InlineKeyboardButton(
                    "📌 /pin 12h",
                    callback_data="cmd_12"
                )
            ],
            [
                InlineKeyboardButton(
                    "📌 /pin 24h",
                    callback_data="cmd_24"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="back_start"
                )
            ],
        ]

        await query.edit_message_text(
            "📋 Useful Commands\n\n"
            "Use one of these commands in your group.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # =====================================================
    # COMMAND COPY
    # =====================================================

    if query.data.startswith("cmd_"):

        hours = query.data.replace("cmd_", "")

        await query.answer(
            f"/pin {hours}h",
            show_alert=True
        )

        return

    # =====================================================
    # BACK
    # =====================================================

    if query.data == "back_start":

        await query.edit_message_text(
            "📌 Pin Cycle\n\n"
            "Select an option below:",
            reply_markup=main_menu()
        )


# =========================================================
# GROUP SELECTED
# =========================================================

async def group_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):

   
