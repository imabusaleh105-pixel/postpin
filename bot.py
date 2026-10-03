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
    CopyTextButton,
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
db.execute("PRAGMA journal_mode=WAL")

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    active INTEGER NOT NULL DEFAULT 1
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    owner_id INTEGER NOT NULL
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

    return row is not None and row[0] == 1


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

def save_group(chat_id: int, title: str, owner_id: int):
    db.execute(
        """
        INSERT INTO groups(chat_id, title, owner_id)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET title = excluded.title,
                      owner_id = excluded.owner_id
        """,
        (chat_id, title, owner_id)
    )
    db.commit()


def get_group_owner(chat_id: int):
    row = db.execute(
        "SELECT owner_id FROM groups WHERE chat_id = ?",
        (chat_id,)
    ).fetchone()

    return row[0] if row else None


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

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

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
        "⚡ Pin Cycle\n\n"
        "Select an option below:",
        reply_markup=main_menu()
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id

    if not has_access(user_id):

        await query.edit_message_text(
            "❌ You don't have access to use Pin Cycle.\n\n"
            "Please contact the owner."
        )

        return

    # -----------------------------------------------------
    # ADD GROUP
    # -----------------------------------------------------

    if query.data == "add_group":

        select_button = KeyboardButton(
            "➕ Select Group",
            request_chat={
                "request_id": 1001,
                "chat_is_channel": False,
                "chat_is_forum": False,
                "bot_is_member": True,
            }
        )

        keyboard = ReplyKeyboardMarkup(
            [[select_button]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await query.message.reply_text(
            "Select the group where you want to use Pin Cycle.",
            reply_markup=keyboard
        )

        return

    # -----------------------------------------------------
    # USEFUL COMMANDS
    # -----------------------------------------------------

    if query.data == "useful_commands":

        keyboard = [
            [
                InlineKeyboardButton(
                    "📋 /pin 4h",
                    copy_text=CopyTextButton(
                        text="/pin 4h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 /pin 8h",
                    copy_text=CopyTextButton(
                        text="/pin 8h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 /pin 12h",
                    copy_text=CopyTextButton(
                        text="/pin 12h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 /pin 24h",
                    copy_text=CopyTextButton(
                        text="/pin 24h"
                    )
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
            "Use these commands in your group.\n\n"
            "Tap any command to copy it.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # -----------------------------------------------------
    # BACK
    # -----------------------------------------------------

    if query.data == "back_start":

        await query.edit_message_text(
            "⚡ Pin Cycle\n\n"
            "Select an option below:",
            reply_markup=main_menu()
        )

        return


# =========================================================
# GROUP SELECTED
# =========================================================

async def group_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    shared = message.chat_shared

    if not shared:
        return

    if not has_access(user.id):
        return

    chat_id = shared.chat_id

    try:

        # -------------------------------------------------
        # GET GROUP
        # -------------------------------------------------

        chat = await context.bot.get_chat(chat_id)

        if chat.type not in (
            ChatType.GROUP,
            ChatType.SUPERGROUP,
        ):

            await message.reply_text(
                "❌ Please select a group.",
                reply_markup=ReplyKeyboardRemove()
            )

            return

        # -------------------------------------------------
        # CHECK BOT
        # -------------------------------------------------

        me = await context.bot.get_me()

        bot_member = await context.bot.get_chat_member(
            chat_id,
            me.id
        )

        if bot_member.status != "administrator":

            await message.reply_text(
                "❌ Pin Cycle must be an administrator "
                "in this group.\n\n"
                "Please make the bot an admin and give it "
                "the permission to pin messages.",
                reply_markup=ReplyKeyboardRemove()
            )

            return

        # -------------------------------------------------
        # SAVE GROUP
        # -------------------------------------------------

        save_group(
            chat_id=chat_id,
            title=chat.title or "Unnamed Group",
            owner_id=user.id
        )

        await message.reply_text(
            f"✅ Group added successfully.\n\n"
            f"Group: {chat.title}\n\n"
            "Now use one of these commands in the group:\n\n"
            "/pin 4h\n"
            "/pin 8h\n"
            "/pin 12h\n"
            "/pin 24h",
            reply_markup=ReplyKeyboardRemove()
        )

    except Exception as e:

        print("GROUP SELECT ERROR:", repr(e))

        await message.reply_text(
            "❌ Couldn't add this group.\n\n"
            "Make sure Pin Cycle is added as an administrator "
            "and has permission to pin messages.",
            reply_markup=ReplyKeyboardRemove()
        )


# =========================================================
# /PIN COMMAND
# =========================================================

async def pin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    # -----------------------------------------------------
    # GROUP ONLY
    # -----------------------------------------------------

    if chat.type not in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ):
        return

    # -----------------------------------------------------
    # ACCESS
    # -----------------------------------------------------

    if not has_access(user.id):
        return

    # -----------------------------------------------------
    # GROUP OWNER
    # -----------------------------------------------------

    group_owner = get_group_owner(chat.id)

    if group_owner != user.id:
        return

    # -----------------------------------------------------
    # ARGUMENT
    # -----------------------------------------------------

    if not context.args:

        try:
            await message.delete()
        except Exception:
            pass

        return

    value = context.args[0].lower().strip()

    durations = {
        "4h": 4 * 60 * 60,
        "8h": 8 * 60 * 60,
        "12h": 12 * 60 * 60,
        "24h": 24 * 60 * 60,
    }

    if value not in durations:

        try:
            await message.delete()
        except Exception:
            pass

        return

    duration = durations[value]

    # -----------------------------------------------------
    # GET GROUP STATE
    # -----------------------------------------------------

    data = context.application.chat_data.setdefault(
        chat.id,
        {}
    )

    # -----------------------------------------------------
    # CANCEL OLD TIMER
    # -----------------------------------------------------

    old_task = data.get("pin_task")

    if old_task:

        if not old_task.done():
            old_task.cancel()

        data.pop("pin_task", None)

    # -----------------------------------------------------
    # SAVE NEW SETTINGS
    # -----------------------------------------------------

    data["waiting"] = True
    data["duration"] = duration

    # -----------------------------------------------------
    # DELETE COMMAND
    # -----------------------------------------------------

    try:
        await message.delete()
    except Exception as e:
        print("COMMAND DELETE ERROR:", repr(e))

    # -----------------------------------------------------
    # STATUS MESSAGE
    # -----------------------------------------------------

    hours = value.replace("h", "")

    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            "✅ Pin Cycle is ready.\n\n"
            f"The next member message will be pinned "
            f"for {hours} hours, except admins."
        )
    )


# =========================================================
# MEMBER MESSAGE HANDLER
# =========================================================

async def member_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # -----------------------------------------------------
    # GROUP ONLY
    # -----------------------------------------------------

    if chat.type not in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ):
        return

    # -----------------------------------------------------
    # GET STATE
    # -----------------------------------------------------

    data = context.application.chat_data.get(chat.id)

    if not data:
        return

    if not data.get("waiting"):
        return

    # -----------------------------------------------------
    # USER
    # -----------------------------------------------------

    user = message.from_user

    if not user:
        return

    # Ignore bots
    if user.is_bot:
        return

    # -----------------------------------------------------
    # CHECK ADMIN
    # -----------------------------------------------------

    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        if member.status in (
            "administrator",
            "creator",
        ):
            return

    except Exception as e:

        print("ADMIN CHECK ERROR:", repr(e))
        return

    # -----------------------------------------------------
    # DURATION
    # -----------------------------------------------------

    duration = data.get("duration")

    if not duration:
        return

    # -----------------------------------------------------
    # LOCK IMMEDIATELY
    # -----------------------------------------------------

    data["waiting"] = False

    # -----------------------------------------------------
    # PIN MESSAGE
    # -----------------------------------------------------

    try:

        await context.bot.pin_chat_message(
            chat_id=chat.id,
            message_id=message.message_id,
            disable_notification=True
        )

    except Exception as e:

        print("PIN ERROR:", repr(e))

        data["waiting"] = True

        return

    # -----------------------------------------------------
    # CREATE UNPIN TASK
    # -----------------------------------------------------

    task = asyncio.create_task(
        unpin_after(
            context=context,
            chat_id=chat.id,
            message_id=message.message_id,
            duration=duration
        )
    )

    data["pin_task"] = task


# =========================================================
# AUTO UNPIN
# =========================================================

async def unpin_after(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    duration: int
):

    try:

        await asyncio.sleep(duration)

        # -------------------------------------------------
        # UNPIN
        # -------------------------------------------------

        try:

            await context.bot.unpin_chat_message(
                chat_id=chat_id,
                message_id=message_id
            )

        except Exception as e:

            print("UNPIN ERROR:", repr(e))

        # -------------------------------------------------
        # RESET STATE
        # -------------------------------------------------

        data = context.application.chat_data.get(chat_id)

        if data:

            data["waiting"] = False
            data.pop("pin_task", None)

    except asyncio.CancelledError:

        print(
            f"PIN TIMER CANCELLED: "
            f"{chat_id} / {message_id}"
        )

    except Exception as e:

        print("UNPIN TASK ERROR:", repr(e))


# =========================================================
# OWNER: /ACCESS
# =========================================================

async def access_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user or user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n\n"
            "/access USER_ID"
        )

        return

    try:

        user_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Telegram user ID."
        )

        return

    grant_access(user_id)

    await update.message.reply_text(
        "✅ Access granted successfully.\n\n"
        f"User ID: {user_id}"
    )


# =========================================================
# OWNER: /REMOVE
# =========================================================

async def remove_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user or user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n\n"
            "/remove USER_ID"
        )

        return

    try:

        user_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Telegram user ID."
        )

        return

    if user_id == OWNER_ID:

        await update.message.reply_text(
            "❌ You cannot remove the owner."
        )

        return

    remove_access(user_id)

    await update.message.reply_text(
        "✅ Access removed successfully.\n\n"
        f"User ID: {user_id}"
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT ERROR:",
        repr(context.error)
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing. "
            "Please add BOT_TOKEN to your environment variables."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("pin", pin_command)
    )

    application.add_handler(
        CommandHandler("access", access_command)
    )

    application.add_handler(
        CommandHandler("remove", remove_command)
    )

    # -----------------------------------------------------
    # CALLBACK BUTTONS
    # ---------------------
