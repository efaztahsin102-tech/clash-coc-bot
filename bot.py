import os
import json
import requests
from flask import Flask
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
COC_API_KEY = os.getenv("COC_API_KEY")

# তোমার Telegram User ID এখানে থাকবে
ADMIN_ID = 8166144532

DB_FILE = "database.json"


# =========================
# DATABASE
# =========================

def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "categories": {},
            "bases": [],
            "cwl": {}
        }

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
        return {
            "categories": {},
            "bases": [],
            "cwl": {}
        }


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def is_admin(update):
    return update.effective_user.id == ADMIN_ID


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
    ]

    if is_admin(update):
        keyboard.append([
            InlineKeyboardButton(
                "⚙️ Admin Panel",
                callback_data="menu_admin"
            )
        ])

    await update.message.reply_text(
        "🔥 CLASH COC MANAGER\n\n"
        "একটি option নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# HELP
# =========================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 COMMANDS\n\n"
        "/start — Main Menu\n"
        "/base — Base Library\n"
        "/player — Player Info\n"
        "/clan — Clan Info\n"
        "/cwl — CWL Tracker\n"
        "/admin — Admin Panel\n"
        "/ping — Bot Status"
    )


# =========================
# PING
# =========================

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🏓 Pong!\n\n"
        "🤖 Bot is online!"
    )


# =========================
# BASE LIBRARY
# =========================

async def base_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await show_base_th(update, context, edit=False)


async def show_base_th(update, context, edit=True):

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


# =========================
# NORMAL / PREMIUM
# =========================

async def show_base_type(query, th):

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
        ],
    ]

    await query.edit_message_text(
        f"🏰 {th} BASES\n\n"
        "Type নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# CATEGORY LIST
# =========================

async def show_categories(query, th, base_type):

    db = load_db()

    key = f"{th}_{base_type}"

    categories = db["categories"].get(key, [])

    keyboard = []

    for category in categories:

        keyboard.append([
            InlineKeyboardButton(
                f"📂 {category}",
                callback_data=f"catview|{th}|{base_type}|{category}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "⬅️ Back",
            callback_data=f"base_th{th.replace('TH', '').lower()}"
        )
    ])

    if not categories:

        text = (
            f"📂 {th} {base_type.upper()}\n\n"
            "এখনো কোনো category নেই।"
        )

    else:

        text = (
            f"📂 {th} {base_type.upper()}\n\n"
            "Category নির্বাচন করুন:"
        )

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# SHOW BASES
# =========================

async def show_bases(query, th, base_type, category):

    db = load_db()

    found = [
        b for b in db["bases"]
        if b["th"] == th
        and b["type"] == base_type
        and b["category"] == category
    ]

    if not found:

        await query.edit_message_text(
            f"📂 {category}\n\n"
            "❌ এই category-তে কোনো base নেই।"
        )

        return

    await query.edit_message_text(
        f"📂 {category}\n\n"
        f"মোট Base: {len(found)}"
    )

    for base in found:

        caption = (
            f"🏰 {base['th']}\n"
            f"📝 {base['name']}\n"
            f"📂 {base['category']}\n\n"
            f"🔗 {base['link']}"
        )

        try:

            await query.message.reply_photo(
                photo=base["photo"],
                caption=caption
            )

        except:

            await query.message.reply_text(
                caption
            )


# =========================
# PLAYER INFO
# =========================

async def player_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "👤 Player Info\n\n"
            "ব্যবহার:\n"
            "/player #PLAYER_TAG\n\n"
            "উদাহরণ:\n"
            "/player #ABC123"
        )

        return

    tag = context.args[0].replace("#", "")

    result = get_coc_data(
        f"players/%23{tag}"
    )

    if result.get("error"):

        await update.message.reply_text(
            "❌ Player Info পাওয়া যায়নি।\n\n"
            f"API Error:\n{result['error']}\n\n"
            "CoC API key/IP authorization check করুন।"
        )

        return

    text = (
        "👤 PLAYER INFO\n\n"
        f"📝 Name: {result.get('name', 'N/A')}\n"
        f"🏰 Town Hall: {result.get('townHallLevel', 'N/A')}\n"
        f"🏆 Trophies: {result.get('trophies', 'N/A')}\n"
        f"⭐ War Stars: {result.get('warStars', 'N/A')}\n"
        f"👥 Clan: "
        f"{result.get('clan', {}).get('name', 'No Clan')}\n"
    )

    await update.message.reply_text(text)


# =========================
# CLAN INFO
# =========================

async def clan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "🏴 Clan Info\n\n"
            "ব্যবহার:\n"
            "/clan #CLAN_TAG\n\n"
            "উদাহরণ:\n"
            "/clan #ABC123"
        )

        return

    tag = context.args[0].replace("#", "")

    result = get_coc_data(
        f"clans/%23{tag}"
    )

    if result.get("error"):

        await update.message.reply_text(
            "❌ Clan Info পাওয়া যায়নি।\n\n"
            f"API Error:\n{result['error']}"
        )

        return

    text = (
        "🏴 CLAN INFO\n\n"
        f"📝 Name: {result.get('name', 'N/A')}\n"
        f"🏷️ Tag: {result.get('tag', 'N/A')}\n"
        f"⭐ Level: {result.get('clanLevel', 'N/A')}\n"
        f"👥 Members: {result.get('members', 'N/A')}\n"
        f"🏆 Points: {result.get('clanPoints', 'N/A')}\n"
        f"🏆 Capital Points: "
        f"{result.get('clanCapitalPoints', 'N/A')}"
    )

    await update.message.reply_text(text)


# =========================
# COC API
# =========================

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


# =========================
# CWL
# =========================

async def cwl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
    ]

    await update.message.reply_text(
        "🏆 CWL TRACKER\n\n"
        "Option নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ADMIN PANEL
# =========================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update):

        await update.message.reply_text(
            "❌ Admin only."
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Category",
                callback_data="admin_addcat"
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ Edit Category",
                callback_data="admin_editcat"
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
    ]

    await update.message.reply_text(
        "⚙️ ADMIN PANEL",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# CALLBACK HANDLER
# =========================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    # MAIN MENU
    if data == "menu_base":

        await show_base_th(
            update,
            context
        )

        return

    if data == "menu_player":

        await query.edit_message_text(
            "👤 PLAYER INFO\n\n"
            "ব্যবহার:\n"
            "/player #PLAYER_TAG"
        )

        return

    if data == "menu_clan":

        await query.edit_message_text(
            "🏴 CLAN INFO\n\n"
            "ব্যবহার:\n"
            "/clan #CLAN_TAG"
        )

        return

    if data == "menu_cwl":

        await query.edit_message_text(
            "🏆 CWL TRACKER\n\n"
            "ব্যবহার /cwl"
        )

        return

    if data == "menu_admin":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        await query.edit_message_text(
            "⚙️ ADMIN PANEL\n\n"
            "/admin দিয়ে management options ব্যবহার করুন।"
        )

        return

    # TH19
    if data == "th19_upcoming":

        await query.edit_message_text(
            "🔒 TH19\n\n"
            "🚧 UPCOMING\n\n"
            "TH19 Base Library এখনো available নয়.",
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

    # TH BUTTON
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

    # NORMAL / PREMIUM
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

    # CATEGORY VIEW
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

    # BACK
    if data == "back_base":

        await show_base_th(
            update,
            context,
            edit=True
        )

        return

    # ADD CATEGORY
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
            "Format:\n\n"
            "TH18 Normal Anti 3 Star\n\n"
            "এভাবে category name লিখুন."
        )

        return

    # EDIT CATEGORY
    if data == "admin_editcat":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        await query.edit_message_text(
            "✏️ EDIT CATEGORY\n\n"
            "Category edit system পরের ধাপে activate করা যাবে."
        )

        return

    # DELETE CATEGORY
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
            "Format:\n\n"
            "TH18 Normal Anti 3 Star"
        )

        return

    # ADD BASE
    if data == "admin_addbase":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        await query.edit_message_text(
            "➕ ADD BASE\n\n"
            "Base Add system পরের ধাপে activate করা হবে."
        )

        return

    # DELETE BASE
    if data == "admin_delbase":

        if not is_admin(update):

            await query.edit_message_text(
                "❌ Admin only."
            )

            return

        await query.edit_message_text(
            "🗑️ DELETE BASE\n\n"
            "Base Delete system পরের ধাপে activate করা হবে."
        )

        return

    # CWL ADD
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
            "Player name লিখুন."
        )

        return

    # CWL VIEW
    if data == "cwl_view":

        db = load_db()

        if not db["cwl"]:

            await query.edit_message_text(
                "🏆 CWL Tracker empty."
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
            text
        )

        return

    # CWL RESET
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
            "🗑️ CWL Tracker reset হয়েছে."
        )

        return


# =========================
# TEXT HANDLER
# =========================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update):
        return

    action = context.user_data.get(
        "admin_action"
    )

    # ADD CATEGORY
    if action == "add_category":

        parts = update.message.text.split(
            " ",
            2
        )

        if len(parts) < 3:

            await update.message.reply_text(
                "❌ Format ভুল.\n\n"
                "উদাহরণ:\n"
                "TH18 Normal Anti 3 Star"
            )

            return

        th = parts[0].upper()

        base_type = parts[1].lower()

        category = parts[2]

        if base_type not in [
            "normal",
            "premium"
        ]:

            await update.message.reply_text(
                "❌ Type শুধু Normal অথবা Premium হবে."
            )

            return

        # TH8-TH18 only
        try:

            th_number = int(
                th.replace("TH", "")
            )

            if th_number < 8 or th_number > 18:

                await update.message.reply_text(
                    "❌ শুধু TH8 থেকে TH18 পর্যন্ত category তৈরি করা যাবে."
                )

                return

        except:

            await update.message.reply_text(
                "❌ Town Hall format ভুল."
            )

            return

        db = load_db()

        key = f"{th}_{base_type}"

        if key not in db["categories"]:

            db["categories"][key] = []

        if category not in db["categories"][key]:

            db["categories"][key].append(
                category
            )

        save_db(db)

        context.user_data.clear()

        await update.message.reply_text(
            "✅ Category added!\n\n"
            f"🏰 {th}\n"
            f"📂 {base_type}\n"
            f"📝 {category}"
        )

        return

    # DELETE CATEGORY
    if action == "delete_category":

        parts = update.message.text.split(
            " ",
            2
        )

        if len(parts) < 3:

            await update.message.reply_text(
                "❌ Format ভুল."
            )

            return

        th = parts[0].upper()

        base_type = parts[1].lower()

        category = parts[2]

        db = load_db()

        key = f"{th}_{base_type}"

        if key in db["categories"]:

            if category in db["categories"][key]:

                db["categories"][key].remove(
                    category
                )

                # Category-এর সব base delete
                db["bases"] = [
                    b for b in db["bases"]
                    if not (
                        b["th"] == th
                        and b["type"] == base_type
                        and b["category"] == category
                    )
                ]

                save_db(db)

                await update.message.reply_text(
                    "✅ Category deleted!"
                )

            else:

                await update.message.reply_text(
                    "❌ Category পাওয়া যায়নি."
                )

        else:

            await update.message.reply_text(
                "❌ Category পাওয়া যায়নি."
            )

        context.user_data.clear()

        return

    # CWL ADD
    if action == "cwl_add":

        name = update.message.text.strip()

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
            f"✅ {name} CWL Tracker-এ যোগ হয়েছে."
        )

        return

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Clash COC Bot is running!"

def run_web():
    app_web.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
    
# =========================
# MAIN
# =========================

def main():
    threading.Thread(target=run_web, daemon=True).start()
    
    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN পাওয়া যায়নি."
        )

        return

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

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

    app.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    print("Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
