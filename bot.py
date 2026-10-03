import os
import sqlite3
from datetime import datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 8762217575
OWNER_USERNAME = "wabillah"

DB_FILE = "pincycle.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False,
)

db.row_factory = sqlite3.Row

db.execute("PRAGMA journal_mode=WAL")

db.executescript(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        access INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        added_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS pending_pin (
        chat_id INTEGER PRIMARY KEY,
        hours INTEGER NOT NULL
    );
    """
)

db.commit()


# =========================================================
# HELPERS
# =========================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_user(user):
    username = user.username or ""

    db.execute(
        """
        INSERT INTO users(user_id, username)
        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET username = excluded.username
        """,
        (
            user.id,
            username.lower(),
        ),
    )

    db.commit()


def has_access(user_id):

    if user_id == OWNER_ID:
        return True

    row = db.execute(
        """
        SELECT access
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    return bool(row and row["access"] == 1)


def get_user_by_username(username):

    username = username.lstrip("@").lower()

    return db.execute(
        """
        SELECT user_id
        FROM users
        WHERE LOWER(username) = ?
        """,
        (username,),
    ).fetchone()


def give_access(username):

    row = get_user_by_username(username)

    if not row:
        return None

    db.execute(
        """
        UPDATE users
        SET access = 1
        WHERE user_id = ?
        """,
        (row["user_id"],),
    )

    db.commit()

    return row["user_id"]


def remove_access(username):

    row = get_user_by_username(username)

    if not row:
        return None

    if row["user_id"] == OWNER_ID:
        return row["user_id"]

    db.execute(
        """
        UPDATE users
        SET access = 0
        WHERE user_id = ?
        """,
        (row["user_id"],),
    )

    db.commit()

    return row["user_id"]


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
            added_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            title = excluded.title,
            owner_id = excluded.owner_id
        """,
        (
            chat_id,
            title,
            owner_id,
            utc_now(),
        ),
    )

    db.commit()


def get_groups(owner_id):

    return db.execute(
        """
        SELECT chat_id, title
        FROM groups
        WHERE owner_id = ?
        ORDER BY title
        """,
        (owner_id,),
    ).fetchall()


def get_group(chat_id, owner_id):

    return db.execute(
        """
        SELECT chat_id, title
        FROM groups
        WHERE chat_id = ?
        AND owner_id = ?
        """,
        (
            chat_id,
            owner_id,
        ),
    ).fetchone()


def delete_group(chat_id, owner_id):

    db.execute(
        """
        DELETE FROM groups
        WHERE chat_id = ?
        AND owner_id = ?
        """,
        (
            chat_id,
            owner_id,
        ),
    )

    db.execute(
        """
        DELETE FROM pending_pin
        WHERE chat_id = ?
        """,
        (chat_id,),
    )

    db.commit()


# =========================================================
# KEYBOARDS
# =========================================================

def main_menu():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Add Group",
                    callback_data="add_group",
                ),
                InlineKeyboardButton(
                    "📂 My Group",
                    callback_data="my_group",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📋 Useful Commands",
                    callback_data="commands",
                ),
                InlineKeyboardButton(
                    "👤 Contact Owner",
                    url=f"https://t.me/{OWNER_USERNAME}",
                ),
            ],
        ]
    )


def back(callback):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=callback,
                )
            ]
        ]
    )


def denied_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👤 Contact Owner",
                    url=f"https://t.me/{OWNER_USERNAME}",
                )
            ]
        ]
    )


# =========================================================
# ACCESS DENIED
# =========================================================

def denied_text():

    return (
        "❌ You don't have access to use Pin Cycle.\n\n"
        "Please contact the owner to request access."
    )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    save_user(user)

    if not has_access(user.id):

        await update.message.reply_text(
            denied_text(),
            reply_markup=denied_keyboard(),
        )

        return

    await update.message.reply_text(
        "📌 Pin Cycle",
        reply_markup=main_menu(),
    )


# =========================================================
# ACCESS COMMAND
# =========================================================

async def access_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    save_user(user)

    if user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/access @username"
        )

        return

    username = context.args[0]

    target = give_access(username)

    if target is None:

        await update.message.reply_text(
            "❌ User not found.\n\n"
            "Ask the user to open PinCycleBOT with /start first."
        )

        return

    await update.message.reply_text(
        f"✅ Access granted to {username}."
    )


# =========================================================
# REMOVE ACCESS
# =========================================================

async def removeaccess_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    save_user(user)

    if user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/removeaccess @username"
        )

        return

    username = context.args[0]

    target = remove_access(username)

    if target is None:

        await update.message.reply_text(
            "❌ User not found."
        )

        return

    await update.message.reply_text(
        f"✅ Access removed from {username}."
    )


# =========================================================
# INLINE BUTTON HANDLER
# =========================================================

async def buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user = query.from_user

    save_user(user)

    if not has_access(user.id):

        await query.edit_message_text(
            denied_text(),
            reply_markup=denied_keyboard(),
        )

        return

    data = query.data

    # -----------------------------------------------------
    # HOME
    # -----------------------------------------------------

    if data == "home":

        await query.edit_message_text(
            "📌 Pin Cycle",
            reply_markup=main_menu(),
        )

        return

    # -----------------------------------------------------
    # ADD GROUP
    # -----------------------------------------------------

    if data == "add_group":

        groups = get_groups(user.id)

        if not groups:

            await query.edit_message_text(
                "➕ Add Group\n\n"
                "No group is available yet.\n\n"
                "Add PinCycleBOT to your group as an admin "
                "with permission to pin messages.",
                reply_markup=back("home"),
            )

            return

        keyboard = []

        for group in groups:

            keyboard.append(
                [
                    InlineKeyboardButton(
                        group["title"][:50],
                        callback_data=(
                            f"select_group:{group['chat_id']}"
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="home",
                )
            ]
        )

        await query.edit_message_text(
            "➕ Select Group",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    # -----------------------------------------------------
    # SELECT GROUP
    # -----------------------------------------------------

    if data.startswith("select_group:"):

        chat_id = int(
            data.split(":")[1]
        )

        group = get_group(
            chat_id,
            user.id,
        )

        if not group:

            await query.edit_message_text(
                "❌ Group not found.",
                reply_markup=back("add_group"),
            )

            return

        await query.edit_message_text(
            f"✅ {group['title']} is ready.\n\n"
            "Use in the group:\n\n"
            "`/pin 4h`\n"
            "`/pin 8h`\n"
            "`/pin 12h`\n"
            "`/pin 24h`",
            parse_mode="Markdown",
            reply_markup=back("home"),
        )

        return

    # -----------------------------------------------------
    # MY GROUP
    # -----------------------------------------------------

    if data == "my_group":

        groups = get_groups(user.id)

        if not groups:

            await query.edit_message_text(
                "📂 My Group\n\n"
                "No groups added yet.",
                reply_markup=back("home"),
            )

            return

        keyboard = []

        for group in groups:

            keyboard.append(
                [
                    InlineKeyboardButton(
                        group["title"][:50],
                        callback_data=(
                            f"group:{group['chat_id']}"
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑 Remove Group",
                    callback_data="remove_group",
                )
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="home",
                )
            ]
        )

        await query.edit_message_text(
            "📂 My Group",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    # -----------------------------------------------------
    # GROUP DETAILS
    # -----------------------------------------------------

    if data.startswith("group:"):

        chat_id = int(
            data.split(":")[1]
        )

        group = get_group(
            chat_id,
            user.id,
        )

        if not group:

            await query.edit_message_text(
                "❌ Group not found.",
                reply_markup=back("my_group"),
            )

            return

        await query.edit_message_text(
            f"📂 {group['title']}\n\n"
            "Available commands:\n\n"
            "`/pin 4h`\n"
            "`/pin 8h`\n"
            "`/pin 12h`\n"
            "`/pin 24h`",
            parse_mode="Markdown",
            reply_markup=back("my_group"),
        )

        return

    # -----------------------------------------------------
    # REMOVE GROUP
    # -----------------------------------------------------

    if data == "remove_group":

        groups = get_groups(user.id)

        if not groups:

            await query.edit_message_text(
                "🗑 No groups available.",
                reply_markup=back("my_group"),
            )

            return

        keyboard = []

        for group in groups:

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🗑 {group['title'][:45]}",
                        callback_data=(
                            f"delete:{group['chat_id']}"
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="my_group",
                )
            ]
        )

        await query.edit_message_text(
            "🗑 Select a group to remove:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    # -----------------------------------------------------
    # DELETE GROUP
    # -----------------------------------------------------

    if data.startswith("delete:"):

        chat_id = int(
            data.split(":")[1]
        )

        delete_group(
            chat_id,
            user.id,
        )

        await query.edit_message_text(
            "✅ Group removed.",
            reply_markup=back("my_group"),
        )

        return

    # -----------------------------------------------------
    # USEFUL COMMANDS
    # -----------------------------------------------------

    if data == "commands":

        text = (
            "📋 Useful Commands\n\n"
            "`/pin 4h`\n"
            "`/pin 8h`\n"
            "`/pin 12h`\n"
            "`/pin 24h`"
        )

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=back("home"),
        )

        return


# =========================================================
# BOT ADDED TO GROUP
# =========================================================

async def bot_status_changed(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    info = update.my_chat_member

    if not info:
        return

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    status = info.new_chat_member.status

    if status not in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
    ):
        return

    user = info.from_user

    if not user:
        return

    save_user(user)

    # Only users with access can register a group.
    if not has_access(user.id):
        return

    # Make sure bot is administrator.
    try:

        bot_member = await context.bot.get_chat_member(
            chat.id,
            context.bot.id,
        )

        if bot_member.status == ChatMemberStatus.ADMINISTRATOR:

            if not bot_member.can_pin_messages:

                return

    except Exception:

        pass

    save_group(
        chat.id,
        chat.title or "Unnamed Group",
        user.id,
    )


# =========================================================
# /PIN COMMAND
# =========================================================

async def pin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    save_user(user)

    if not has_access(user.id):
        return

    # Check if this group belongs to the user.
    group = get_group(
        chat.id,
        user.id,
    )

    if not group:

        await message.reply_text(
            "❌ This group is not added to your Pin Cycle."
        )

        return

    if not context.args:

        await message.reply_text(
            "Usage:\n\n"
            "/pin 4h\n"
            "/pin 8h\n"
            "/pin 12h\n"
            "/pin 24h"
        )

        return

    duration = context.args[0].lower()

    durations = {
        "4h": 4,
        "8h": 8,
        "12h": 12,
        "24h": 24,
    }

    if duration not in durations:

        await message.reply_text(
            "❌ Invalid duration.\n\n"
            "Available:\n"
            "/pin 4h\n"
            "/pin 8h\n"
            "/pin 12h\n"
            "/pin 24h"
        )

        return

    hours = durations[duration]

    # Save pending pin.
    db.execute(
        """
        INSERT INTO pending_pin(
            chat_id,
            hours
        )
        VALUES (?, ?)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            hours = excluded.hours
        """,
        (
            chat.id,
            hours,
        ),
    )

    db.commit()

    await message.reply_text(
        f"✅ Pin Cycle is ready. "
        f"The next post will be pinned for {hours} hours, "
        f"except admins."
    )


# =========================================================
# NEXT MEMBER MESSAGE
# =========================================================

async def member_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    # Check pending pin.
    pending = db.execute(
        """
        SELECT hours
        FROM pending_pin
        WHERE chat_id = ?
        """,
        (chat.id,),
    ).fetchone()

    if not pending:
        return

    # Ignore commands.
    if message.text and message.text.startswith("/"):
        return

    sender = message.from_user

    if not sender:
        return

    # Check sender status.
    try:

        member = await context.bot.get_chat_member(
            chat.id,
            sender.id,
        )

        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return

    except Exception:

        return

    hours = pending["hours"]

    # Consume pending pin.
    db.execute(
        """
        DELETE FROM pend
