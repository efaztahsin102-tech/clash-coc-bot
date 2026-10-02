import os
import json
import requests
import threading

from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
COC_API_KEY = os.getenv("COC_API_KEY")

# Render Environment Variable থেকে Admin ID নেবে
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except:
    ADMIN_ID = 8166144532

DB_FILE = "database.json"


# =========================================================
# DATABASE
# =========================================================

def default_db():
    return {
        "categories": {},
        "bases": [],
        "cwl": {}
    }


def load_db():

    if not os.path.exists(DB_FILE):
        return default_db()

    try:

        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)

        if "categories" not in db:
            db["categories"] = {}

        if "bases" not in db:
            db["bases"] = []

        if "cwl" not in db:
            db["cwl"] = {}

        return db

    except:

        return default_db()


def save_db(db):

    with open(
        DB_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            db,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(update):

    if not update.effective_user:
        return False

    return update.effective_user.id == ADMIN_ID


# =========================================================
# TELEGRAM MENU
# =========================================================

async def setup_menu(application):

    commands = [

        BotCommand(
            "start",
            "Open main menu"
        ),

        BotCommand(
            "base",
            "Base Library"
        ),

        BotCommand(
            "player",
            "Player Info"
        ),

        BotCommand(
            "clan",
            "Clan Info"
        ),

        BotCommand(
            "cwl",
            "CWL Tracker"
        ),

        BotCommand(
            "help",
            "Help"
        ),

        BotCommand(
            "ping",
            "Bot Status"
        ),

    ]

    await application.bot.set_my_commands(commands)


# =========================================================
# MAIN MENU
# =========================================================

def main_menu_keyboard(admin=False):

    keyboard = [

        [
            InlineKeyboardButton(
                "🏰 Base Library",
                callback_data="menu_base"
            ),

            InlineKeyboardButton(
                "👤 Player Info",
                callback_data="menu_player"
            ),
        ],

        [
            InlineKeyboardButton(
                "🏴 Clan Info",
                callback_data="menu_clan"
            ),

            InlineKeyboardButton(
                "🏆 CWL Tracker",
                callback_data="menu_cwl"
            ),
        ],

        [
            InlineKeyboardButton(
                "❓ Help",
                callback_data="menu_help"
            )
        ],

    ]

    if admin:

        keyboard.append(
            [
                InlineKeyboardButton(
                    "⚙️ Admin Panel",
                    callback_data="menu_admin"
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "🔥 CLASH COC MANAGER\n\n"
        "Welcome! 👋\n\n"
        "নিচের option নির্বাচন করুন:",

        reply_markup=main_menu_keyboard(
            is_admin(update)
        )
    )


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (

        "🤖 CLASH COC MANAGER\n\n"

        "🏰 /base\n"
        "Base Library খুলবে\n\n"

        "👤 /player #TAG\n"
        "Player information\n\n"

        "🏴 /clan #TAG\n"
        "Clan information\n\n"

        "🏆 /cwl\n"
        "CWL Tracker\n\n"

        "🏓 /ping\n"
        "Bot status\n\n"

        "⚙️ /admin\n"
        "Admin Panel"
    )

    await update.message.reply_text(text)


# =========================================================
# PING
# =========================================================

async def ping(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "🏓 Pong!\n\n"
        "🤖 Bot is online!"

    )


# =========================================================
# BASE LIBRARY
# =========================================================

async def base_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await show_base_th(
        update,
        context,
        edit=False
    )


async def show_base_th(
    update,
    context,
    edit=True
):

    keyboard = [

        [
            InlineKeyboardButton(
                "🏰 TH18",
                callback_data="base_th18"
            ),

            InlineKeyboardButton(
                "🏰 TH17",
                callback_data="base_th17"
            ),
        ],

        [
            InlineKeyboardButton(
                "🏰 TH16",
                callback_data="base_th16"
            ),

            InlineKeyboardButton(
                "🏰 TH15",
                callback_data="base_th15"
            ),
        ],

        [
            InlineKeyboardButton(
                "🏰 TH14",
                callback_data="base_th14"
            ),

            InlineKeyboardButton(
                "🏰 TH13",
                callback_data="base_th13"
            ),
        ],

        [
            InlineKeyboardButton(
                "🏰 TH12",
                callback_data="base_th12"
            ),

            InlineKeyboardButton(
                "🏰 TH11",
                callback_data="base_th11"
            ),
        ],

        [
            InlineKeyboardButton(
                "🏰 TH10",
                callback_data="base_th10"
            ),

            InlineKeyboardButton(
                "🏰 TH9",
                callback_data="base_th9"
            ),
        ],

        [
            InlineKeyboardButton(
                "🏰 TH8",
                callback_data="base_th8"
            ),
        ],

        [
            InlineKeyboardButton(
                "🔒 TH19 — UPCOMING",
                callback_data="th19_upcoming"
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="main_menu"
            )
        ]

    ]

    text = (
        "🏰 BASE LIBRARY\n\n"
        "Town Hall নির্বাচন করুন:"
    )

    markup = InlineKeyboardMarkup(keyboard)

    if edit:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=markup
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=markup
        )


# =========================================================
# BASE TYPE
# =========================================================

async def show_base_type(
    query,
    th
):

    keyboard = [

        [
            InlineKeyboardButton(
                "🆓 Normal",
                callback_data=f"basetype_normal_{th}"
            )
        ],

        [
            InlineKeyboardButton(
                "💎 Premium",
                callback_data=f"basetype_premium_{th}"
            )
        ],

        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_base"
            )
        ]

    ]

    await query.edit_message_text(

        f"🏰 {th} BASES\n\n"
        "Type নির্বাচন করুন:",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# CATEGORY LIST
# =========================================================

async def show_categories(
    query,
    th,
    base_type
):

    db = load_db()

    key = f"{th}_{base_type}"

    categories = db["categories"].get(
        key,
        []
    )

    keyboard = []

    for category in categories:

        keyboard.append(

            [
                InlineKeyboardButton(
                    f"📂 {category}",
                    callback_data=(
                        f"catview|"
                        f"{th}|"
                        f"{base_type}|"
                        f"{category}"
                    )
                )
            ]

        )

    if not categories:

        text = (

            f"📂 {th} "
            f"{base_type.upper()}\n\n"

            "❌ এখনো কোনো category নেই।"

        )

    else:

        text = (

            f"📂 {th} "
            f"{base_type.upper()}\n\n"

            "Category নির্বাচন করুন:"

        )

    keyboard.append(

        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data=(
                    f"base_th"
                    f"{th.replace('TH', '')}"
                )
            )
        ]

    )

    await query.edit_message_text(

        text,

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# SHOW BASES
# =========================================================

async def show_bases(
    query,
    th,
    base_type,
    category
):

    db = load_db()

    found = [

        b for b in db["bases"]

        if b.get("th") == th
        and b.get("type") == base_type
        and b.get("category") == category

    ]

    if not found:

        await query.edit_message_text(

            f"📂 {category}\n\n"
            "❌ এই category-তে কোনো base নেই।",

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data=(
                            f"basetype_"
                            f"{base_type}_"
                            f"{th}"
                        )
                    )
                ]

            ])

        )

        return

    await query.edit_message_text(

        f"📂 {category}\n\n"
        f"🏰 {th}\n"
        f"📦 মোট Base: {len(found)}"

    )

    for index, base in enumerate(found, 1):

        caption = (

            f"🏰 {base.get('th', 'N/A')}\n"

            f"📝 {base.get('name', 'N/A')}\n"

            f"📂 {base.get('category', 'N/A')}\n\n"

            f"🔗 {base.get('link', 'N/A')}"

        )

        photo = base.get(
            "photo",
            ""
        )

        if photo:

            try:

                await query.message.reply_photo(

                    photo=photo,
                    caption=(
                        f"🏠 Base #{index}\n\n"
                        + caption
                    )

                )

                continue

            except:

                pass

        await query.message.reply_text(

            f"🏠 Base #{index}\n\n"
            + caption

        )


# =========================================================
# PLAYER INFO
# =========================================================

async def player_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(

            "👤 PLAYER INFO\n\n"

            "ব্যবহার:\n"
            "/player #PLAYER_TAG\n\n"

            "উদাহরণ:\n"
            "/player #ABC123"

        )

        return

    tag = context.args[0].replace(
        "#",
        ""
    )

    result = get_coc_data(
        f"players/%23{tag}"
    )

    if result.get("error"):

        await update.message.reply_text(

            "❌ Player Info পাওয়া যায়নি।\n\n"

            f"API Error:\n"
            f"{result['error']}"

        )

        return

    clan = result.get(
        "clan",
        {}
    )

    text = (

        "👤 PLAYER INFO\n\n"

        f"📝 Name: "
        f"{result.get('name', 'N/A')}\n"

        f"🏰 Town Hall: "
        f"{result.get('townHallLevel', 'N/A')}\n"

        f"🏆 Trophies: "
        f"{result.get('trophies', 'N/A')}\n"

        f"⭐ War Stars: "
        f"{result.get('warStars', 'N/A')}\n"

        f"👥 Clan: "
        f"{clan.get('name', 'No Clan')}\n"

    )

    await update.message.reply_text(text)


# =========================================================
# CLAN INFO
# =========================================================

async def clan_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(

            "🏴 CLAN INFO\n\n"

            "ব্যবহার:\n"
            "/clan #CLAN_TAG\n\n"

            "উদাহরণ:\n"
            "/clan #ABC123"

        )

        return

    tag = context.args[0].replace(
        "#",
        ""
    )

    result = get_coc_data(
        f"clans/%23{tag}"
    )

    if result.get("error"):

        await update.message.reply_text(

            "❌ Clan Info পাওয়া যায়নি।\n\n"

            f"API Error:\n"
            f"{result['error']}"

        )

        return

    text = (

        "🏴 CLAN INFO\n\n"

        f"📝 Name: "
        f"{result.get('name', 'N/A')}\n"

        f"🏷️ Tag: "
        f"{result.get('tag', 'N/A')}\n"

        f"⭐ Level: "
        f"{result.get('clanLevel', 'N/A')}\n"

        f"👥 Members: "
        f"{result.get('members', 'N/A')}\n"

        f"🏆 Points: "
        f"{result.get('clanPoints', 'N/A')}\n"

        f"🏆 Capital Points: "
        f"{result.get('clanCapitalPoints', 'N/A')}"

    )

    await update.message.reply_text(text)


# =========================================================
# COC API
# =========================================================

def get_coc_data(endpoint):

    if not COC_API_KEY:

        return {
            "error":
            "COC_API_KEY environment variable পাওয়া যায়নি।"
        }

    url = (
        "https://api.clashofclans.com/v1/"
        + endpoint
    )

    headers = {

        "Authorization":
        f"Bearer {COC_API_KEY}",

        "Accept":
        "application/json"

    }

    try:

        response = requests.get(

            url,
            headers=headers,
            timeout=15

        )

        if response.status_code == 200:

            return response.json()

        try:

            data = response.json()

            return {

                "error":
                data.get(
                    "message",
                    f"HTTP {response.status_code}"
                )

            }

        except:

            return {
                "error":
                f"HTTP {response.status_code}"
            }

    except Exception as e:

        return {
            "error": str(e)
        }


# =========================================================
# CWL
# =========================================================

async def cwl_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [

        [
            InlineKeyboardButton(
                "➕ Add Player",
                callback_data="cwl_add"
            )
        ],

        [
            InlineKeyboardButton(
                "📊 View Tracker",
                callback_data="cwl_view"
            )
        ],

        [
            InlineKeyboardButton(
                "🗑️ Reset CWL",
                callback_data="cwl_reset"
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="main_menu"
            )
        ]

    ]

    await update.message.reply_text(

        "🏆 CWL TRACKER\n\n"
        "Option নির্বাচন করুন:",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# ADMIN PANEL
# =========================================================

def admin_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "➕ Add Category",
                callback_data="admin_addcat"
            )
        ],

        [
            InlineKeyboardButton(
                "🗑️ Delete Category",
                callback_data="admin_delcat"
            )
        ],

        [
            InlineKeyboardButton(
                "➕ Add Base",
                callback_data="admin_addbase"
            )
        ],

        [
            InlineKeyboardButton(
                "🗑️ Delete Base",
                callback_data="admin_delbase"
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="main_menu"
            )
        ]

    ])


async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update):

        await update.message.reply_text(
            "❌ Admin only."
        )

        return

    await update.message.reply_text(

        "⚙️ ADMIN PANEL\n\n"
        "Management option নির্বাচন করুন:",

        reply_markup=admin_keyboard()

    )


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data


    # =====================================================
    # MAIN MENU
    # =====================================================

    if data == "main_menu":

        await query.edit_message_text(

            "🔥 CLASH COC MANAGER\n\n"
            "Option নির্বাচন করুন:",

            reply_markup=main_menu_keyboard(
                is_admin(update)
            )

        )

        return


    # =====================================================
    # MENU BASE
    # =====================================================

    if data == "menu_base":

        await show_base_th(
            update,
            context,
            edit=True
        )

        return


    # =====================================================
    # MENU PLAYER
    # =====================================================

    if data == "menu_player":

        await query.edit_message_text(

            "👤 PLAYER INFO\n\n"

            "ব্যবহার:\n"
            "/player #PLAYER_TAG\n\n"

            "উদাহরণ:\n"
            "/player #ABC123",

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="main_menu"
                    )
                ]

            ])

        )

        return


    # =====================================================
    # MENU CLAN
    # =====================================================

    if data == "menu_clan":

        await query.edit_message_text(

            "🏴 CLAN INFO\n\n"

            "ব্যবহার:\n"
            "/clan #CLAN_TAG\n\n"

            "উদাহরণ:\n"
            "/clan #ABC123",

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="main_menu"
                    )
                ]

            ])

        )

        return


    # =====================================================
    # MENU CWL
    # =====================================================

    if data == "menu_cwl":

        keyboard = [

            [
                InlineKeyboardButton(
                    "➕ Add Player",
                    callback_data="cwl_add"
                )
            ],

            [
                InlineKeyboardButton(
                    "📊 View Tracker",
                    callback_data="cwl_view"
                )
            ],

            [
                InlineKeyboardButton(
                    "🗑️ Reset CWL",
                    callback_data="cwl_reset"
                )
            ],

            [
                InlineKeyboardButton(
                    "🏠 Main Menu",
                    callback_data="main_menu"
                )
            ]

        ]

        await query.edit_message_text(

            "🏆 CWL TRACKER\n\n"
            "Option নির্বাচন করুন:",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return


    # =====================================================
    # MENU HELP
    # =====================================================

    if data == "menu_help":

        await query.edit_message_text(

            "❓ HELP\n\n"

            "🏰 Base Library\n"
            "Town Hall অনুযায়ী base দেখুন।\n\n"

            "👤 Player Info\n"
            "/player #TAG\n\n"

            "🏴 Clan Info\n"
            "/clan #TAG\n\n"

            "🏆 CWL Tracker\n"
            "CWL player tracking system।\n\n"

            "🏓 /ping\n"
            "Bot online কিনা দেখুন।",

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="main_menu"
                    )
                ]

            ])

        )

        return


    # =====================================================
    # ADMIN MENU
    # =====================================================

    if data == "menu_admin":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        await query.edit_message_text(

            "⚙️ ADMIN PANEL\n\n"
            "Management option নির্বাচন করুন:",

            reply_markup=admin_keyboard()

        )

        return


    # =====================================================
    # TH19
    # =====================================================

    if data == "th19_upcoming":

        await query.edit_message_text(

            "🔒 TH19\n\n"

            "🚧 UPCOMING\n\n"

            "TH19 Base Library এখনো available নয়।",

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="back_base"
                    )
                ]

            ])

        )

        return


    # =====================================================
    # TH BUTTON
    # =====================================================

    if data.startswith("base_th"):

        number = data.replace(
            "base_th",
            ""
        )

        th = f"TH{number}"

        await show_base_type(
            query,
            th
        )

        return


    # =====================================================
    # NORMAL / PREMIUM
    # =====================================================

    if data.startswith("basetype_"):

        parts = data.split("_")

        base_type = parts[1]

        th = parts[2].upper()

        await show_categories(

            query,
            th,
            base_type

        )

        return


    # =====================================================
    # CATEGORY VIEW
    # =====================================================

    if data.startswith("catview|"):

        _, th, base_type, category = data.split(
            "|",
            3
        )

        await show_bases(

            query,
            th,
            base_type,
            category

        )

        return


    # =====================================================
    # BACK BASE
    # =====================================================

    if data == "back_base":

        await show_base_th(
            update,
            context,
            edit=True
        )

        return


    # =====================================================
    # ADMIN ADD CATEGORY
    # =====================================================

    if data == "admin_addcat":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        context.user_data[
            "admin_action"
        ] = "add_category"

        await query.edit_message_text(

            "➕ ADD CATEGORY\n\n"

            "Format:\n"
            "TH18 Normal Anti 3 Star\n\n"

            "উদাহরণ:\n"
            "TH18 Normal Anti 3 Star"

        )

        return


    # =====================================================
    # ADMIN DELETE CATEGORY
    # =====================================================

    if data == "admin_delcat":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        context.user_data[
            "admin_action"
        ] = "delete_category"

        await query.edit_message_text(

            "🗑️ DELETE CATEGORY\n\n"

            "Format:\n"
            "TH18 Normal Anti 3 Star"

        )

        return


    # =====================================================
    # ADMIN ADD BASE
    # =====================================================

    if data == "admin_addbase":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        context.user_data[
            "admin_action"
        ] = "add_base"

        await query.edit_message_text(

            "➕ ADD BASE\n\n"

            "Format:\n"
            "TH18 Normal Anti 3 Star https://link\n\n"

            "উদাহরণ:\n"
            "TH18 Normal Anti 3 Star https://link.com/base\n\n"

            "⚠️ Link অবশ্যই শেষে দিতে হবে।"

        )

        return


    # =====================================================
    # ADMIN DELETE BASE
    # =====================================================

    if data == "admin_delbase":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        context.user_data[
            "admin_action"
        ] = "delete_base"

        await query.edit_message_text(

            "🗑️ DELETE BASE\n\n"

            "Format:\n"
            "TH18 Normal Anti 3 Star https://link\n\n"

            "যে base-এর link delete করতে চান,"
            "সেই link দিন।"

        )

        return


    # =====================================================
    # CWL ADD
    # =====================================================

    if data == "cwl_add":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        context.user_data[
            "admin_action"
        ] = "cwl_add"

        await query.edit_message_text(

            "➕ CWL PLAYER\n\n"

            "Player name লিখুন।"

        )

        return


    # =====================================================
    # CWL VIEW
    # =====================================================

    if data == "cwl_view":

        db = load_db()

        if not db["cwl"]:

            await query.edit_message_text(

                "🏆 CWL TRACKER\n\n"
                "❌ Tracker এখনো empty।",

                reply_markup=InlineKeyboardMarkup([

                    [
                        InlineKeyboardButton(
                            "⬅️ Back",
                            callback_data="menu_cwl"
                        )
                    ]

                ])

            )

            return

        text = "🏆 CWL TRACKER\n\n"

        for name, info in db["cwl"].items():

            text += (

                f"👤 {name}\n"

                f"⚔️ Attacks: "
                f"{info.get('attacks', 0)}\n"

                f"⭐ Stars: "
                f"{info.get('stars', 0)}\n"

                f"💯 Destruction: "
                f"{info.get('destruction', 0)}%\n\n"

            )

        await query.edit_message_text(

            text,

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="menu_cwl"
                    )
                ]

            ])

        )

        return


    # =====================================================
    # CWL RESET
    # =====================================================

    if data == "cwl_reset":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        db = load_db()

        db["cwl"] = {}

        save_db(db)

        await query.edit_message_text(

            "🗑️ CWL Tracker reset হয়েছে।",

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="main_menu"
                    )
                ]

            ])

        )

        return


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update):

        return

    action = context.user_data.get(
        "admin_action"
    )

    text = update.message.text.strip()


    # =====================================================
    # ADD BASE
    # =====================================================

    if action == "add_base":

        parts = text.split()

        if len(parts) < 5:

            await update.message.reply_text(

                "❌ Format ভুল।\n\n"

                "সঠিক format:\n"
                "TH18 Normal Anti 3 Star https://link"

            )

            return

        th = parts[0].upper()

        base_type = parts[1].lower()

        link = parts[-1]

        category = " ".join(
            parts[2:-1]
        )


        if base_type not in [
            "normal",
            "premium"
        ]:

            await update.message.reply_text(

                "❌ Type শুধু Normal অথবা Premium হবে।"

            )

            return


        # TH CHECK

        try:

            th_number = int(
                th.replace(
                    "TH",
                    ""
                )
            )

            if th_number < 8 or th_number > 18:

                await update.message.reply_text(

                    "❌ শুধু TH8 থেকে TH18 পর্যন্ত "
                    "base add করা যাবে।"

                )

                return

        except:

            await update.message.reply_text(

                "❌ Town Hall format ভুল।\n\n"
                "উদাহরণ: TH18"

            )

            return


        # LINK CHECK

        if not (
            link.startswith("http://")
            or
            link.startswith("https://")
        ):

            await update.message.reply_text(

                "❌ Link ভুল।\n\n"
                "শেষে একটি http/https link দিতে হবে।"

            )

            return


        db = load_db()

        key = f"{th}_{base_type}"


        # CATEGORY AUTO CREATE

        if key not in db["categories"]:

            db["categories"][key] = []


        if category not in db["categories"][key]:

            db["categories"][key].append(
                category
            )


        # BASE SAVE

        db["bases"].append({

            "th": th,

            "type": base_type,

            "category": category,

            "name": category,

            "link": link,

            "photo": ""

        })


        save_db(db)

        context.user_data.clear()


        await update.message.reply_text(

            "✅ BASE SUCCESSFULLY ADDED!\n\n"

            f"🏰 TH: {th}\n"

            f"📂 Type: "
            f"{base_type.upper()}\n"

            f"📝 Category: "
            f"{category}\n"

            f"🔗 Link:\n"
            f"{link}"

        )

        return


    # =====================================================
    # ADD CATEGORY
    # =====================================================

    if action == "add_category":

        parts = text.split(
            " ",
            2
        )

        if len(parts) < 3:

            await update.message.reply_text(

                "❌ Format ভুল।\n\n"

                "উদাহরণ:\n"
                "TH18 Normal Anti 3 Star"

            )

            return


        th = parts[0].upper()

        base_type = parts[1].lower()

        category = parts[2].strip()


        if base_type not in [
            "normal",
            "premium"
        ]:

            await update.message.reply_text(

                "❌ Type শুধু Normal অথবা Premium হবে।"

            )

            return


        try:

            th_number = int(
                th.replace(
                    "TH",
                    ""
                )
            )

            if th_number < 8 or th_number > 18:

                await update.message.reply_text(

                    "❌ শুধু TH8 থেকে TH18 পর্যন্ত "
                    "category তৈরি করা যাবে।"

                )

                return

        except:

            await update.message.reply_text(
                "❌ Town Hall format ভুল।"
            )

            return


        db = load_db()

        key = f"{th}_{base_type}"


        if key not in db["categories"]:

            db["categories"][key] = []


        if category in db["categories"][key]:

            await update.message.reply_text(

                "⚠️ এই category আগে থেকেই আছে।"

            )

            context.user_data.clear()

            return


        db["categories"][key].append(
            category
        )

        save_db(db)

        context.user_data.clear()


        await update.message.reply_text(

            "✅ CATEGORY ADDED!\n\n"

            f"🏰 {th}\n"
            f"📂 {base_type.upper()}\n"
            f"📝 {category}"

        )

        return


    # =====================================================
    # DELETE CATEGORY
    # =====================================================

    if action == "delete_category":

        parts = text.split(
            " ",
            2
        )

        if len(parts) < 3:

            await update.message.reply_text(

                "❌ Format ভুল।\n\n"

                "উদাহরণ:\n"
                "TH18 Normal Anti 3 Star"

            )

            return


        th = parts[0].upper()

        base_type = parts[1].lower()

        category = parts[2].strip()


        db = load_db()

        key = f"{th}_{base_type}"


        if (
            key not in db["categories"]
            or
            category not in db["categories"][key]
        ):

            await update.message.reply_text(

                "❌ Category পাওয়া যায়নি।"

            )

            context.user_data.clear()

            return


        db["categories"][key].remove(
            category
        )


        # Category-এর সব base delete

        db["bases"] = [

            b for b in db["bases"]

            if not (

                b.get("th") == th
                and
                b.get("type") == base_type
                and
                b.get("category") == category

            )

        ]


        save_db(db)

        context.user_data.clear()


        await update.message.reply_text(

            "✅ CATEGORY DELETED!\n\n"

            f"🏰 {th}\n"
            f"📂 {base_type.upper()}\n"
            f"📝 {category}\n\n"

            "Category এবং এর সব base delete হয়েছে।"

        )

        return


    # =====================================================
    # DELETE BASE
    # =====================================================

    if action == "delete_base":

        parts = text.split()

        if len(parts) < 5:

            await update.message.reply_text(

                "❌ Format ভুল।\n\n"

                "উদাহরণ:\n"
                "TH18 Normal Anti 3 Star https://link"

            )

            return


        th = parts[0].upper()

        base_type = parts[1].lower()

        link = parts[-1]

        category = " ".join(
            parts[2:-1]
        )


        db = load_db()


        old_count = len(
            db["bases"]
        )


        db["bases"] = [

            b for b in db["bases"]

            if not (

                b.get("th") == th
                and
                b.get("type") == base_type
                and
                b.get("category") == category
                and
                b.get("link") == link

            )

        ]


        new_count = len(
            db["bases"]
        )


        if old_count == new_count:

            await update.message.reply_text(

                "❌ এই base পাওয়া যায়নি।"

            )

            context.user_data.clear()

            return


        save_db(db)

        context.user_data.clear()


        await update.message.reply_text(

            "✅ BASE DELETED!\n\n"

            f"🏰 {th}\n"
            f"📂 {base_type.upper()}\n"
            f"📝 {category}\n"
            f"🔗 {link}"

        )

        return


    # =====================================================
    # CWL ADD
    # =====================================================

    if action == "cwl_add":

        name = text

        if not name:

            return


        db = load_db()


        db["cwl"][name] = {

            "attacks": 0,

            "stars": 0,

            "destruction": 0

        }


        save_db(db)

        context.user_data.clear()


        await update.message.reply_text(

            f"✅ {name}\n\n"
            "CWL Tracker-এ যোগ হয়েছে।"

        )

        return


# =========================================================
# FLASK SERVER FOR RENDER
# =========================================================

app_web = Flask(__name__)


@app_web.route("/")
def home():

    return "Clash COC Bot is running!"


def run_web():

    app_web.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                10000
            )
        )

    )


# =========================================================
# MAIN
# =========================================================

def main():

    # Render web server
    threading.Thread(
        target=run_web,
        daemon=True
    ).start()


    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN পাওয়া যায়নি।"
        )

        return


    app = (

        Application
        .builder()
        .token(BOT_TOKEN)
        .post_init(setup_menu)
        .build()

    )


    # COMMANDS

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )


    app.add_handler(
        CommandHandler(
            "ping",
            ping
        )
    )


    app.add_handler(
        CommandHandler(
            "base",
            base_command
        )
    )


    app.add_handler(
        CommandHandler(
            "player",
            player_command
        )
    )


    app.add_handler(
        CommandHandler(
            "clan",
            clan_command
        )
    )


    app.add_handler(
        CommandHandler(
            "cwl",
            cwl_command
        )
    )


    app.add_handler(
        CommandHandler(
            "admin",
            admin_command
        )
    )


    # BUTTONS

    app.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )


    # TEXT

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )


    print(
        "Bot is running..."
    )

    print(
        f"Admin ID configured: "
        f"{ADMIN_ID != 0}"
    )


    app.run_polling()


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":

    main()
