import os
import json
import hashlib
import re
import time
import threading
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import requests
from flask import Flask

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, PreCheckoutQueryHandler, ConversationHandler, filters,
)

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
COC_API_KEY = os.getenv("COC_API_KEY", "").strip()
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0").strip())
except Exception:
    ADMIN_ID = 0

DB_FILE = Path(os.getenv("DB_FILE", "database.json"))
PORT = int(os.getenv("PORT", "10000"))

TH_LEVELS = list(range(18, 7, -1))
DEFAULT_CATEGORIES = ["Anti 3 Star", "Anti 2 Star", "War Base", "Farming"]

# Conversation states
(
    ADD_CAT_TH, ADD_CAT_TYPE, ADD_CAT_NAME,
    EDIT_CAT_TH, EDIT_CAT_TYPE, EDIT_CAT_OLD, EDIT_CAT_NEW,
    DEL_CAT_TH, DEL_CAT_TYPE, DEL_CAT_NAME,
    ADD_BASE_TH, ADD_BASE_TYPE, ADD_BASE_CAT, ADD_BASE_NAME,
    ADD_BASE_LINK, ADD_BASE_PRICE, ADD_BASE_PHOTO,
    EDIT_BASE_ID, EDIT_BASE_FIELD, EDIT_BASE_VALUE,
    DEL_BASE_ID,
    PRICE_TYPE, PRICE_VALUE,
    SET_CLAN_TAG,
    REQUEST_TEXT,
    BROADCAST_TEXT,
) = range(26)

DB_LOCK = threading.Lock()

# ============================================================
# DATABASE
# ============================================================
DEFAULT_DB = {
    "users": {},
    "bases": [],
    "categories": {},
    "purchases": [],
    "requests": [],
    "settings": {
        "clan_tag": "",
        "premium_base_price": 5,
        "premium_cwl_price": 5,
    },
    "notifications": [],
}


def load_db():
    if not DB_FILE.exists():
        save_db(DEFAULT_DB)
        return json.loads(json.dumps(DEFAULT_DB))
    try:
        data = json.loads(DB_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = json.loads(json.dumps(DEFAULT_DB))
    for k, v in DEFAULT_DB.items():
        if k not in data:
            data[k] = json.loads(json.dumps(v))
    return data


def save_db(data):
    tmp = DB_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DB_FILE)


def with_db(fn):
    with DB_LOCK:
        db = load_db()
        result = fn(db)
        save_db(db)
        return result


# ============================================================
# HELPERS
# ============================================================
def now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def is_admin(user_id):
    return ADMIN_ID != 0 and user_id == ADMIN_ID


def admin_only(fn):
    @wraps(fn)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not is_admin(user.id):
            if update.callback_query:
                await update.callback_query.answer("Admin only.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text("⛔ Admin only.")
            return
        return await fn(update, context)
    return wrapper


def user_touch(user):
    if not user:
        return
    uid = str(user.id)
    with DB_LOCK:
        db = load_db()
        old = db["users"].get(uid, {})
        db["users"][uid] = {
            "id": user.id,
            "name": user.full_name or "Unknown",
            "username": user.username or "",
            "first_seen": old.get("first_seen", now_str()),
            "last_active": now_str(),
            "premium": old.get("premium", False),
        }
        save_db(db)


def ensure_categories(db):
    for th in TH_LEVELS:
        key = str(th)
        db["categories"].setdefault(key, {"normal": [], "premium": []})
        for mode in ("normal", "premium"):
            if not db["categories"][key].get(mode):
                db["categories"][key][mode] = list(DEFAULT_CATEGORIES)


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def valid_coctag(tag):
    return bool(re.fullmatch(r"#[A-Z0-9]{5,12}", tag.strip().upper()))


def normalize_tag(tag):
    return tag.strip().upper()


def get_categories(th, mode):
    def read(db):
        ensure_categories(db)
        return list(db["categories"].get(str(th), {}).get(mode, []))
    return with_db(read)


def base_by_id(base_id):
    def read(db):
        return next((b for b in db["bases"] if b["id"] == base_id), None)
    return with_db(read)


def has_purchase(user_id, base_id):
    def read(db):
        return any(p.get("user_id") == user_id and p.get("base_id") == base_id for p in db["purchases"])
    return with_db(read)


def price_for_base(base):
    return int(base.get("price", 0) or 0)


def available_api():
    return bool(COC_API_KEY)


def coc_get(path):
    if not COC_API_KEY:
        return None, "API unavailable"
    url = "https://cocproxy.royaleapi.dev/v1" + path
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json(), None
        return None, f"HTTP {r.status_code}"
    except Exception as e:
        return None, str(e)


def coc_api(path):
    # Prefer the official API. If the Render IP is not allowed for the key,
    # try the RoyaleAPI proxy as a fallback. Never expose the API key in logs.
    if not COC_API_KEY:
        return None, "API unavailable"
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    official_url = "https://api.clashofclans.com/v1" + path
    try:
        r = requests.get(official_url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json(), None
        official_err = f"HTTP {r.status_code}"
    except Exception as e:
        official_err = type(e).__name__

    # Render's outbound IP can differ from the IP allowlisted on a CoC API key.
    # The proxy fallback avoids treating that as a generic 'API unavailable'.
    proxy_url = "https://cocproxy.royaleapi.dev/v1" + path
    try:
        r = requests.get(proxy_url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json(), None
        return None, f"Official {official_err}; proxy HTTP {r.status_code}"
    except Exception as e:
        return None, f"Official {official_err}; proxy {type(e).__name__}"


def api_unavailable_text():
    return "🔒 <b>Currently Unavailable</b>\nCoC API connected হলে এই information automatically available হবে।"


# ============================================================
# UI
# ============================================================
def main_keyboard(user_id):
    rows = [
        [InlineKeyboardButton("🏰 Base Library", callback_data="base")],
        [InlineKeyboardButton("🏆 CWL Tracker", callback_data="cwl")],
        [InlineKeyboardButton("👤 Player Info", callback_data="player")],
        [InlineKeyboardButton("🏴 Clan Info", callback_data="clan")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    if is_admin(user_id):
        rows.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def back_home_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Home", callback_data="home")]])


def th_keyboard(prefix):
    rows = []
    for i in range(0, len(TH_LEVELS), 2):
        row = []
        for th in TH_LEVELS[i:i+2]:
            row.append(InlineKeyboardButton(f"🏰 TH{th}", callback_data=f"{prefix}:th:{th}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Home", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def mode_keyboard(th):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 NORMAL", callback_data=f"base:mode:{th}:normal")],
        [InlineKeyboardButton("⭐ PREMIUM", callback_data=f"base:mode:{th}:premium")],
        [InlineKeyboardButton("⬅️ TH List", callback_data="base")],
    ])


def category_keyboard(th, mode, admin=False):
    cats = get_categories(th, mode)
    rows = [[InlineKeyboardButton(f"📂 {c}", callback_data=f"base:cat:{th}:{mode}:{i}")] for i, c in enumerate(cats)]
    if mode == "premium":
        rows.append([InlineKeyboardButton("🏷️ Name Base", callback_data=f"base:names:{th}")])
        rows.append([InlineKeyboardButton("📩 Request", callback_data=f"request:{th}")])
    if admin:
        rows.append([
            InlineKeyboardButton("➕ Add Category", callback_data=f"admin:addcat:{th}:{mode}"),
            InlineKeyboardButton("✏️ Edit Category", callback_data=f"admin:editcat:{th}:{mode}"),
        ])
        rows.append([InlineKeyboardButton("🗑️ Delete Category", callback_data=f"admin:delcat:{th}:{mode}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"base:th:{th}")])
    return InlineKeyboardMarkup(rows)


def base_open_markup(base, admin=False, unlocked=False):
    rows = []
    if unlocked:
        rows.append([InlineKeyboardButton("🔗 OPEN", url=base["link"])])
    else:
        price = price_for_base(base)
        rows.append([InlineKeyboardButton(f"🔒 UNLOCK — ⭐ {price}", callback_data=f"buy:{base['id']}")])
    if admin:
        rows.append([InlineKeyboardButton("🗑️ DELETE", callback_data=f"admin:delbase:{base['id']}")])
    return InlineKeyboardMarkup(rows)


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Category", callback_data="admin:addcat")],
        [InlineKeyboardButton("✏️ Edit Category", callback_data="admin:editcat")],
        [InlineKeyboardButton("🗑️ Delete Category", callback_data="admin:delcat")],
        [InlineKeyboardButton("➕ Add Base", callback_data="admin:addbase")],
        [InlineKeyboardButton("✏️ Edit Base", callback_data="admin:editbase")],
        [InlineKeyboardButton("🗑️ Delete Base", callback_data="admin:delbase")],
        [InlineKeyboardButton("💰 Edit Premium Price", callback_data="admin:price")],
        [InlineKeyboardButton("📊 User Statistics", callback_data="admin:stats")],
        [InlineKeyboardButton("📩 Request Inbox", callback_data="admin:requests")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("🏷️ Set Clan Tag", callback_data="admin:clantag")],
        [InlineKeyboardButton("💾 Database Backup", callback_data="admin:backup")],
        [InlineKeyboardButton("⬅️ Home", callback_data="home")],
    ])


# ============================================================
# COMMANDS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_touch(update.effective_user)
    text = (
        "🏰 <b>Clash Bot</b>\n\n"
        "Base Library, CWL Tracker, Player Info, Clan Info এবং Premium features এক জায়গায়।"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard(update.effective_user.id))


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_touch(update.effective_user)
    await update.message.reply_text("🏠 <b>Main Menu</b>", parse_mode=ParseMode.HTML, reply_markup=main_keyboard(update.effective_user.id))


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_touch(q.from_user)
    data = q.data

    if data == "home":
        await q.edit_message_text("🏠 <b>Main Menu</b>", parse_mode=ParseMode.HTML, reply_markup=main_keyboard(q.from_user.id))
        return

    if data == "base":
        await q.edit_message_text("🏰 <b>BASE LIBRARY</b>", parse_mode=ParseMode.HTML, reply_markup=th_keyboard("base"))
        return

    if data.startswith("base:th:"):
        th = int(data.split(":")[2])
        await q.edit_message_text(f"🏰 <b>TH{th}</b>", parse_mode=ParseMode.HTML, reply_markup=mode_keyboard(th))
        return

    if data.startswith("base:mode:"):
        _, _, th, mode = data.split(":")
        label = "🆓 NORMAL" if mode == "normal" else "⭐ PREMIUM"
        await q.edit_message_text(f"{label} <b>TH{th}</b>", parse_mode=ParseMode.HTML,
                                   reply_markup=category_keyboard(int(th), mode, is_admin(q.from_user.id)))
        return

    if data.startswith("base:cat:"):
        _, _, th, mode, idx = data.split(":")
        th = int(th)
        cats = get_categories(th, mode)
        idx = int(idx)
        if idx >= len(cats):
            await q.answer("Category not found", show_alert=True)
            return
        cat = cats[idx]
        def read(db):
            return [b for b in db["bases"] if b["th"] == th and b["mode"] == mode and b["category"] == cat]
        bases = with_db(read)
        if not bases:
            await q.edit_message_text(f"📂 <b>{esc(cat)}</b>\n\nNo bases added yet.", parse_mode=ParseMode.HTML,
                                       reply_markup=category_keyboard(th, mode, is_admin(q.from_user.id)))
            return
        for n, base in enumerate(bases):
            unlocked = mode == "normal" or has_purchase(q.from_user.id, base["id"])
            caption = f"📌 <b>{esc(base['name'])}</b>\n🏰 TH{th}\n📂 {esc(cat)}"
            if mode == "premium" and not unlocked:
                caption += "\n🔒 Premium"
            if n == 0:
                await q.edit_message_text(caption, parse_mode=ParseMode.HTML,
                                           reply_markup=base_open_markup(base, is_admin(q.from_user.id), unlocked))
            else:
                try:
                    await context.bot.send_message(q.from_user.id, caption, parse_mode=ParseMode.HTML,
                                                   reply_markup=base_open_markup(base, is_admin(q.from_user.id), unlocked))
                except Exception:
                    pass
        return

    if data.startswith("base:names:"):
        th = int(data.split(":")[2])
        def read(db):
            return sorted([b for b in db["bases"] if b["th"] == th and b["mode"] == "premium"], key=lambda x: x["name"].lower())
        bases = with_db(read)
        rows = []
        for b in bases:
            rows.append([InlineKeyboardButton(f"🔹 {b['name']}", callback_data=f"base:view:{b['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"base:th:{th}")])
        await q.edit_message_text(f"🏷️ <b>NAME BASE — TH{th}</b>", parse_mode=ParseMode.HTML,
                                   reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("base:view:"):
        bid = data.split(":")[2]
        base = base_by_id(bid)
        if not base:
            await q.answer("Base not found", show_alert=True)
            return
        unlocked = base["mode"] == "normal" or has_purchase(q.from_user.id, bid)
        caption = f"📌 <b>{esc(base['name'])}</b>\n🏰 TH{base['th']}\n📂 {esc(base['category'])}"
        await q.edit_message_text(caption, parse_mode=ParseMode.HTML,
                                   reply_markup=base_open_markup(base, is_admin(q.from_user.id), unlocked))
        return

    if data == "cwl":
        await show_cwl_menu(q)
        return

    if data == "cwl:normal":
        await show_cwl(q, context)
        return

    if data == "cwl:premium":
        await cwl_premium(q, context)
        return

    if data == "player":
        await q.edit_message_text(
            "👤 <b>Player Info</b>\n\nPlayer Tag পাঠাও, যেমন: <code>#ABC123</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        context.user_data["awaiting"] = "player"
        return

    if data == "clan":
        await q.edit_message_text(
            "🏴 <b>Clan Info</b>\n\nClan Tag পাঠাও, যেমন: <code>#ABC123</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        context.user_data["awaiting"] = "clan"
        return

    if data == "help":
        await q.edit_message_text(
            "❓ <b>Help</b>\n\n"
            "🏰 Base Library — TH8–TH18 bases\n"
            "🏆 CWL Tracker — CWL opponents\n"
            "👤 Player Info — player tag দিয়ে তথ্য\n"
            "🏴 Clan Info — clan tag দিয়ে তথ্য\n"
            "⭐ Premium — Stars দিয়ে premium unlock\n\n"
            "Contact Admin:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ℹ️ About Bot", callback_data="about")],
                [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/efaz_tahsin42")],
                [InlineKeyboardButton("⬅️ Home", callback_data="home")],
            ]))
        return

    if data == "about":
        await q.edit_message_text(
            "ℹ️ <b>About Bot</b>\n\n"
            "এই bot Clash of Clans base browsing, premium base unlock, CWL tracking এবং API-based player/clan information-এর জন্য তৈরি।",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Help", callback_data="help")]]))
        return

    if data == "admin":
        if not is_admin(q.from_user.id):
            await q.answer("Admin only", show_alert=True)
            return
        await q.edit_message_text("⚙️ <b>Admin Panel</b>", parse_mode=ParseMode.HTML, reply_markup=admin_keyboard())
        return

    if data.startswith("buy:"):
        bid = data.split(":", 1)[1]
        base = base_by_id(bid)
        if not base or base["mode"] != "premium":
            await q.answer("Base not found", show_alert=True)
            return
        if has_purchase(q.from_user.id, bid):
            await q.edit_message_text("✅ Already unlocked.", reply_markup=base_open_markup(base, is_admin(q.from_user.id), True))
            return
        price = price_for_base(base)
        if price <= 0:
            await q.answer("Invalid price", show_alert=True)
            return
        payload = f"premium_base:{bid}:{q.from_user.id}"
        await context.bot.send_invoice(
            chat_id=q.from_user.id,
            title=f"Premium Base — {base['name']}",
            description=f"Unlock {base['name']} for TH{base['th']}",
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice("Premium Base", price)],
            provider_token="",
        )
        return

    if data.startswith("request:"):
        th = data.split(":")[1]
        context.user_data["request_th"] = th
        context.user_data["awaiting"] = "request"
        await q.edit_message_text(
            f"📩 <b>Request — TH{th}</b>\n\nতোমার request লিখে পাঠাও।",
            parse_mode=ParseMode.HTML,
            reply_markup=back_home_markup())
        return

    # Admin callback actions
    if data.startswith("admin:"):
        await admin_callback(q, context, data)
        return


# ============================================================
# CWL
# ============================================================
async def show_cwl_menu(q):
    await q.edit_message_text(
        "🏆 <b>CWL TRACKER</b>\n\nChoose a mode:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🆓 NORMAL", callback_data="cwl:normal")],
            [InlineKeyboardButton("⭐ PREMIUM", callback_data="cwl:premium")],
            [InlineKeyboardButton("⬅️ Home", callback_data="home")],
        ]),
    )


async def show_cwl(q, context):
    clan_tag = with_db(lambda db: db["settings"].get("clan_tag", ""))
    if not clan_tag:
        text = "🏆 <b>CWL TRACKER</b>\n\n" + api_unavailable_text() + "\n\nAdmin এখনও Clan Tag set করেনি।"
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        return
    data, err = coc_api(f"/clans/{clan_tag}/currentwar/leaguegroup")
    if err or not data:
        await q.edit_message_text("🏆 <b>CWL TRACKER</b>\n\n" + api_unavailable_text(),
                                  parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        return
    clans = {c.get("tag"): c for c in data.get("clans", [])}
    rounds = data.get("rounds", [])
    lines = ["🏆 <b>CWL Opponents</b>"]
    for i, rnd in enumerate(rounds, 1):
        war_tags = rnd.get("warTags", [])
        opponent = None
        for wt in war_tags:
            if wt == "#0":
                continue
            war, e = coc_api(f"/clanwarleagues/wars/{wt[1:]}")
            if e or not war:
                continue
            c1 = war.get("clan", {})
            c2 = war.get("opponent", {})
            if c1.get("tag") == clan_tag:
                opponent = c2
            elif c2.get("tag") == clan_tag:
                opponent = c1
            if opponent:
                break
        lines.append(f"\n⚔️ <b>Round {i}</b>")
        if opponent:
            lines.append(f"🏴 {esc(opponent.get('name','Unknown'))}\n🏷️ <code>{esc(opponent.get('tag',''))}</code>")
        else:
            lines.append("🔒 Currently Unavailable")
    lines.append("\n⭐ Premium-এ opponent player list, TH distribution এবং আরও তথ্য থাকবে।")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ PREMIUM CWL", callback_data="cwl:premium")],
        [InlineKeyboardButton("⬅️ Home", callback_data="home")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


async def cwl_premium(q, context):
    # One global premium CWL purchase per user.
    def read(db):
        return any(p.get("user_id") == q.from_user.id and p.get("type") == "premium_cwl" for p in db["purchases"])
    unlocked = with_db(read)
    if not unlocked:
        price = with_db(lambda db: int(db["settings"].get("premium_cwl_price", 5)))
        await q.edit_message_text(
            f"🏆 <b>Premium CWL Tracker</b>\n\n🔒 Unlock for ⭐ {price}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"⭐ UNLOCK — {price}", callback_data="buycwl")],
                [InlineKeyboardButton("⬅️ Back", callback_data="cwl")],
            ]))
        return
    await show_cwl_premium(q, context)


async def show_cwl_premium(q, context):
    clan_tag = with_db(lambda db: db["settings"].get("clan_tag", ""))
    if not clan_tag or not COC_API_KEY:
        await q.edit_message_text("🏆 <b>Premium CWL Tracker</b>\n\n" + api_unavailable_text(),
                                  parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        return
    data, err = coc_api(f"/clans/{clan_tag}/currentwar/leaguegroup")
    if err or not data:
        await q.edit_message_text("🏆 <b>Premium CWL Tracker</b>\n\n" + api_unavailable_text(),
                                  parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        return
    lines = ["🏆 <b>Premium CWL Tracker</b>"]
    for i, rnd in enumerate(data.get("rounds", []), 1):
        opponent = None
        for wt in rnd.get("warTags", []):
            if wt == "#0":
                continue
            war, e = coc_api(f"/clanwarleagues/wars/{wt[1:]}")
            if e or not war:
                continue
            a, b = war.get("clan", {}), war.get("opponent", {})
            if a.get("tag") == clan_tag:
                opponent = b
            elif b.get("tag") == clan_tag:
                opponent = a
            if opponent:
                break
        lines.append(f"\n⚔️ <b>Round {i}</b>")
        if not opponent:
            lines.append("🔒 Currently Unavailable")
            continue
        members = opponent.get("members", [])
        lines.append(f"🏴 {esc(opponent.get('name','Unknown'))}\n🏷️ <code>{esc(opponent.get('tag',''))}</code>")
        lines.append(f"👥 Players: {len(members)}")
        counts = {}
        for m in members:
            th = m.get("townhallLevel", "?")
            counts[str(th)] = counts.get(str(th), 0) + 1
        if counts:
            lines.append("📊 TH: " + ", ".join(f"TH{k} {v}" for k, v in sorted(counts.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999, reverse=True)))
        for m in members:
            lines.append(f"• {esc(m.get('name','Unknown'))} — TH{m.get('townhallLevel','?')}")
    await q.edit_message_text("\n".join(lines)[:4000], parse_mode=ParseMode.HTML, reply_markup=back_home_markup())


# ============================================================
# PLAYER / CLAN SEARCH
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_touch(update.effective_user)
    text = (update.message.text or "").strip()
    awaiting = context.user_data.get("awaiting")

    if awaiting == "player":
        context.user_data.pop("awaiting", None)
        tag = normalize_tag(text)
        if not valid_coctag(tag):
            await update.message.reply_text("❌ Valid Player Tag দাও, যেমন <code>#ABC123</code>", parse_mode=ParseMode.HTML)
            return
        data, err = coc_api(f"/players/{tag[1:]}")
        if err or not data:
            await update.message.reply_text("👤 <b>Player Info</b>\n\n" + api_unavailable_text(), parse_mode=ParseMode.HTML,
                                            reply_markup=back_home_markup())
            return
        lines = [
            "👤 <b>Player Info</b>",
            f"Name: <b>{esc(data.get('name',''))}</b>",
            f"Tag: <code>{esc(data.get('tag',''))}</code>",
            f"Town Hall: TH{data.get('townHallLevel','?')}",
            f"Trophies: {data.get('trophies','?')}",
            f"War Stars: {data.get('warStars','?')}",
            f"Clan: {esc((data.get('clan') or {}).get('name','No Clan'))}",
        ]
        heroes = data.get("heroes", [])
        if heroes:
            lines.append("Heroes: " + ", ".join(f"{esc(h.get('name',''))} Lv{h.get('level','?')}" for h in heroes))
        pets = data.get("heroEquipment", [])
        if not pets:
            pets = data.get("pets", [])
        if pets:
            lines.append("Pets/Equipment: " + ", ".join(esc(p.get('name','')) for p in pets[:10]))
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        return

    if awaiting == "clan":
        context.user_data.pop("awaiting", None)
        tag = normalize_tag(text)
        if not valid_coctag(tag):
            await update.message.reply_text("❌ Valid Clan Tag দাও, যেমন <code>#ABC123</code>", parse_mode=ParseMode.HTML)
            return
        data, err = coc_api(f"/clans/{tag[1:]}")
        if err or not data:
            await update.message.reply_text("🏴 <b>Clan Info</b>\n\n" + api_unavailable_text(), parse_mode=ParseMode.HTML,
                                            reply_markup=back_home_markup())
            return
        war = data.get("warLeague", {}).get("name", "?")
        cwl = data.get("warLeague", {}).get("name", "?")
        lines = [
            "🏴 <b>Clan Info</b>",
            f"Name: <b>{esc(data.get('name',''))}</b>",
            f"Tag: <code>{esc(data.get('tag',''))}</code>",
            f"Level: {data.get('clanLevel','?')}",
            f"Members: {data.get('members','?')}",
            f"Trophies: {data.get('clanPoints','?')}",
            f"CWL/War League: {esc(cwl)}",
            f"War Status: {esc(data.get('warFrequency','?'))}",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup([
                                            [InlineKeyboardButton("👥 View Members", callback_data=f"clanmembers:{tag}")],
                                            [InlineKeyboardButton("⬅️ Home", callback_data="home")]
                                        ]))
        return

    if awaiting == "request":
        th = context.user_data.get("request_th", "?")
        context.user_data.pop("awaiting", None)
        context.user_data.pop("request_th", None)
        req_id = str(int(time.time() * 1000))
        req = {"id": req_id, "user_id": update.effective_user.id, "name": update.effective_user.full_name,
               "th": th, "text": text, "time": now_str(), "status": "open"}
        with_db(lambda db: db["requests"].append(req))
        await update.message.reply_text("✅ Request Admin-এর কাছে পাঠানো হয়েছে।", reply_markup=back_home_markup())
        if ADMIN_ID:
            try:
                await context.bot.send_message(ADMIN_ID, f"📩 <b>New Request</b>\n👤 {esc(req['name'])} ({req['user_id']})\n🏰 TH{th}\n📝 {esc(text)}",
                                               parse_mode=ParseMode.HTML)
            except Exception:
                pass
        return

    # Admin conversation states
    state = context.user_data.get("admin_state")
    if state:
        await handle_admin_state(update, context, text, state)
        return

    await update.message.reply_text("🏠 Main Menu", reply_markup=main_keyboard(update.effective_user.id))


# ============================================================
# PAYMENTS
# ============================================================
async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    payload = query.invoice_payload
    if payload.startswith("premium_base:") or payload.startswith("premium_cwl:"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Unknown purchase.")


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    user_id = update.effective_user.id
    if payload.startswith("premium_base:"):
        bid = payload.split(":")[1]
        def write(db):
            if not any(p.get("user_id") == user_id and p.get("base_id") == bid for p in db["purchases"]):
                db["purchases"].append({"type": "premium_base", "user_id": user_id, "base_id": bid,
                                        "stars": payment.total_amount, "time": now_str(),
                                        "telegram_payment_charge_id": payment.telegram_payment_charge_id})
        with_db(write)
        await update.message.reply_text("✅ <b>Premium Base Unlocked!</b>\nBase Library থেকে এখন OPEN করতে পারবে।",
                                        parse_mode=ParseMode.HTML, reply_markup=main_keyboard(user_id))
    elif payload == "premium_cwl":
        with_db(lambda db: db["purchases"].append({"type": "premium_cwl", "user_id": user_id,
                                                    "stars": payment.total_amount, "time": now_str(),
                                                    "telegram_payment_charge_id": payment.telegram_payment_charge_id}))
        await update.message.reply_text("✅ <b>Premium CWL Tracker Unlocked!</b>", parse_mode=ParseMode.HTML,
                                        reply_markup=main_keyboard(user_id))


# ============================================================
# ADMIN
# ============================================================
async def admin_callback(q, context, data):
    if not is_admin(q.from_user.id):
        await q.answer("Admin only", show_alert=True)
        return
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if data == "admin:stats":
        def stats(db):
            users = list(db["users"].values())
            prem = {p.get("user_id") for p in db["purchases"]}
            active_cut = time.time() - 30 * 86400
            # approximate active count from timestamp string
            active = 0
            for u in users:
                try:
                    dt = datetime.strptime(u["last_active"], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                    if dt.timestamp() >= active_cut:
                        active += 1
                except Exception:
                    pass
            return len(users), active, len(prem)
        total, active, prem = with_db(stats)
        await q.edit_message_text(f"📊 <b>User Statistics</b>\n\n👥 Total: {total}\n🟢 Active (30d): {active}\n⭐ Premium Buyers: {prem}",
                                  parse_mode=ParseMode.HTML, reply_markup=admin_keyboard())
        return

    if data == "admin:requests":
        def read(db):
            return [r for r in db["requests"] if r.get("status") == "open"]
        reqs = with_db(read)
        if not reqs:
            text = "📩 <b>Request Inbox</b>\n\nNo open requests."
            kb = admin_keyboard()
        else:
            text = "📩 <b>Request Inbox</b>\n\n" + "\n".join(
                f"#{r['id']} — 👤 {esc(r['name'])}\n🏰 TH{r['th']}\n📝 {esc(r['text'])}\n🕐 {r['time']}" for r in reqs[:8])
            rows = [[InlineKeyboardButton(f"✅ Done #{r['id']}", callback_data=f"admin:reqdone:{r['id']}")] for r in reqs[:8]]
            rows.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin")])
            kb = InlineKeyboardMarkup(rows)
        await q.edit_message_text(text[:4000], parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    if action == "reqdone":
        rid = parts[2]
        with_db(lambda db: [r.update({"status": "done"}) for r in db["requests"] if r["id"] == rid])
        await q.edit_message_text("✅ Request marked Done.", reply_markup=admin_keyboard())
        return

    if data == "admin:backup":
        try:
            await context.bot.send_document(q.from_user.id, document=str(DB_FILE), caption="💾 Database backup")
        except Exception as e:
            await q.answer(f"Backup error: {str(e)[:100]}", show_alert=True)
        return

    if data == "admin:broadcast":
        context.user_data["admin_state"] = "broadcast"
        await q.edit_message_text("📢 Broadcast message লিখে পাঠাও।", reply_markup=back_home_markup())
        return

    if data == "admin:clantag":
        context.user_data["admin_state"] = "clantag"
        current = with_db(lambda db: db["settings"].get("clan_tag", "") or "Not set")
        await q.edit_message_text(f"🏷️ Current Clan Tag: <code>{esc(current)}</code>\n\nনতুন Clan Tag পাঠাও।",
                                  parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        return

    if data == "admin:price":
        context.user_data["admin_state"] = "price_menu"
        await q.edit_message_text("💰 কোন price edit করবে?\n\n1 = Premium Base\n2 = Premium CWL\n\n<code>1</code> বা <code>2</code> পাঠাও।",
                                  parse_mode=ParseMode.HTML, reply_markup=back_home_markup())
        return

    # Generic admin actions that start guided conversations
    if action in ("addcat", "editcat", "delcat") and len(parts) == 2:
        context.user_data["admin_state"] = action
        await q.edit_message_text("🏰 TH number পাঠাও (8–18)।", reply_markup=back_home_markup())
        return
    if action in ("addbase", "editbase", "delbase") and len(parts) == 2:
        context.user_data["admin_state"] = action
        await q.edit_message_text("🏰 Base-এর TH পাঠাও (8–18)।", reply_markup=back_home_markup())
        return

    # Category shortcuts from a TH mode page
    if action in ("addcat", "editcat", "delcat") and len(parts) == 4:
        th, mode = parts[2], parts[3]
        context.user_data.update({"admin_state": action, "admin_th": th, "admin_mode": mode})
        if action == "addcat":
            await q.edit_message_text(f"➕ Add Category — TH{th} {mode}\n\nCategory name পাঠাও.", reply_markup=back_home_markup())
        elif action == "editcat":
            await q.edit_message_text(f"✏️ Edit Category — TH{th} {mode}\n\nপুরোনো category name পাঠাও.", reply_markup=back_home_markup())
        else:
            await q.edit_message_text(f"🗑️ Delete Category — TH{th} {mode}\n\nCategory name পাঠাও.", reply_markup=back_home_markup())
        return

    if action == "delbase" and len(parts) == 3:
        bid = parts[2]
        def delete(db):
            before = len(db["bases"])
            db["bases"] = [b for b in db["bases"] if b["id"] != bid]
            return len(db["bases"]) < before
        ok = with_db(delete)
        await q.answer("Deleted" if ok else "Not found", show_alert=True)
        await q.edit_message_text("⚙️ <b>Admin Panel</b>", parse_mode=ParseMode.HTML, reply_markup=admin_keyboard())
        return


async def handle_admin_state(update, context, text, state):
    if not is_admin(update.effective_user.id):
        context.user_data.pop("admin_state", None)
        return

    if state == "clantag":
        tag = normalize_tag(text)
        if not valid_coctag(tag):
            await update.message.reply_text("❌ Invalid Clan Tag. আবার পাঠাও, যেমন #ABC123")
            return
        with_db(lambda db: db["settings"].update({"clan_tag": tag}))
        context.user_data.pop("admin_state", None)
        await update.message.reply_text(f"✅ Clan Tag set: {tag}", reply_markup=admin_keyboard())
        return

    if state == "broadcast":
        context.user_data.pop("admin_state", None)
        users = with_db(lambda db: list(db["users"].keys()))
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(int(uid), text)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"📢 Broadcast complete. Sent: {sent}", reply_markup=admin_keyboard())
        return

    if state == "price_menu":
        if text not in ("1", "2"):
            await update.message.reply_text("1 বা 2 পাঠাও।")
            return
        context.user_data["price_type"] = text
        context.user_data["admin_state"] = "price_value"
        await update.message.reply_text("⭐ New Stars price পাঠাও, যেমন 5")
        return

    if state == "price_value":
        try:
            price = int(text)
            if price < 1:
                raise ValueError
        except Exception:
            await update.message.reply_text("❌ Positive Stars number দাও।")
            return
        ptype = context.user_data.pop("price_type", "1")
        key = "premium_base_price" if ptype == "1" else "premium_cwl_price"
        with_db(lambda db: db["settings"].update({key: price}))
        context.user_data.pop("admin_state", None)
        await update.message.reply_text("✅ Price updated.", reply_markup=admin_keyboard())
        return

    if state in ("addcat", "editcat", "delcat"):
        if "admin_th" not in context.user_data:
            try:
                th = int(text)
                if th not in TH_LEVELS:
                    raise ValueError
            except Exception:
                await update.message.reply_text("8–18 এর মধ্যে TH দাও।")
                return
            context.user_data["admin_th"] = str(th)
            if state == "addcat":
                await update.message.reply_text("normal না premium? পাঠাও: normal / premium")
            elif state == "editcat":
                await update.message.reply_text("normal না premium? পাঠাও: normal / premium")
            else:
                await update.message.reply_text("normal না premium? পাঠাও: normal / premium")
            context.user_data["admin_cat_step"] = "mode"
            return
        if context.user_data.get("admin_cat_step") == "mode":
            mode = text.lower()
            if mode not in ("normal", "premium"):
                await update.message.reply_text("শুধু normal বা premium")
                return
            context.user_data["admin_mode"] = mode
            context.user_data["admin_cat_step"] = "name"
            if state == "editcat":
                await update.message.reply_text("পুরোনো category name পাঠাও।")
            else:
                await update.message.reply_text("Category name পাঠাও।")
            return
        th = int(context.user_data["admin_th"]); mode = context.user_data["admin_mode"]
        if state == "addcat":
            with_db(lambda db: (ensure_categories(db), db["categories"][str(th)][mode].append(text) if text not in db["categories"][str(th)][mode] else None))
            msg = "✅ Category added."
        elif state == "delcat":
            def delete_cat(db):
                ensure_categories(db)
                if text in db["categories"][str(th)][mode]:
                    db["categories"][str(th)][mode].remove(text)
                    return True
                return False
            msg = "✅ Category deleted." if with_db(delete_cat) else "❌ Category not found."
        else:
            context.user_data["admin_oldcat"] = text
            context.user_data["admin_state"] = "editcat_new"
            await update.message.reply_text("নতুন category name পাঠাও।")
            return
        for k in ("admin_state", "admin_th", "admin_mode", "admin_cat_step", "admin_oldcat"):
            context.user_data.pop(k, None)
        await update.message.reply_text(msg, reply_markup=admin_keyboard())
        return

    if state == "editcat_new":
        th = int(context.user_data["admin_th"]); mode = context.user_data["admin_mode"]; old = context.user_data["admin_oldcat"]
        def edit_cat(db):
            ensure_categories(db)
            arr = db["categories"][str(th)][mode]
            if old not in arr:
                return False
            arr[arr.index(old)] = text
            for b in db["bases"]:
                if b["th"] == th and b["mode"] == mode and b["category"] == old:
                    b["category"] = text
            return True
        ok = with_db(edit_cat)
        for k in ("admin_state", "admin_th", "admin_mode", "admin_cat_step", "admin_oldcat"):
            context.user_data.pop(k, None)
        await update.message.reply_text("✅ Category updated." if ok else "❌ Category not found.", reply_markup=admin_keyboard())
        return

    if state == "addbase":
        # Wizard: TH -> mode -> category -> name -> link -> price if premium -> photo optional
        step = context.user_data.get("base_step")
        if not step:
            try:
                th = int(text)
                if th not in TH_LEVELS: raise ValueError
            except Exception:
                await update.message.reply_text("8–18 এর মধ্যে TH দাও।")
                return
            context.user_data["base_th"] = th
            context.user_data["base_step"] = "mode"
            await update.message.reply_text("normal না premium? পাঠাও: normal / premium")
            return
        if step == "mode":
            mode = text.lower()
            if mode not in ("normal", "premium"):
                await update.message.reply_text("normal বা premium")
                return
            context.user_data["base_mode"] = mode
            context.user_data["base_step"] = "category"
            cats = get_categories(context.user_data["base_th"], mode)
            await update.message.reply_text("Category name পাঠাও:\n" + "\n".join(cats))
            return
        if step == "category":
            th = context.user_data["base_th"]; mode = context.user_data["base_mode"]
            if text not in get_categories(th, mode):
                await update.message.reply_text("এই category নেই। উপরের list থেকে একটি নাম পাঠাও।")
                return
            context.user_data["base_category"] = text
            context.user_data["base_step"] = "name"
            await update.message.reply_text("Base Name পাঠাও।")
            return
        if step == "name":
            context.user_data["base_name"] = text
            context.user_data["base_step"] = "link"
            await update.message.reply_text("Clash of Clans base link পাঠাও।")
            return
        if step == "link":
            if not (text.startswith("http://") or text.startswith("https://")):
                await update.message.reply_text("Valid http/https link পাঠাও।")
                return
            context.user_data["base_link"] = text
            if context.user_data["base_mode"] == "premium":
                context.user_data["base_step"] = "price"
                await update.message.reply_text("Premium price in Stars পাঠাও, যেমন 5")
            else:
                context.user_data["base_step"] = "photo"
                await update.message.reply_text("Base photo থাকলে এখন photo পাঠাও; না থাকলে <code>skip</code> লিখো।", parse_mode=ParseMode.HTML)
            return
        if step == "price":
            try:
                price = int(text)
                if price < 1: raise ValueError
            except Exception:
                await update.message.reply_text("Positive Stars price দাও।")
                return
            context.user_data["base_price"] = price
            context.user_data["base_step"] = "photo"
            await update.message.reply_text("Base photo পাঠাও; না থাকলে <code>skip</code> লিখো।", parse_mode=ParseMode.HTML)
            return
        if step == "photo":
            # Text handler only; actual photo handled by photo handler below.
            if text.lower() != "skip":
                await update.message.reply_text("Photo পাঠাও অথবা skip লিখো।")
                return
            await finish_add_base(update, context, None)
            return

    if state == "delbase":
        # TH first, then base id/name
        step = context.user_data.get("delbase_step")
        if not step:
            try:
                th = int(text)
                if th not in TH_LEVELS: raise ValueError
            except Exception:
                await update.message.reply_text("8–18 এর মধ্যে TH দাও।")
                return
            context.user_data["delbase_th"] = th
            context.user_data["delbase_step"] = "id"
            bases = with_db(lambda db: [b for b in db["bases"] if b["th"] == th])
            if not bases:
                await update.message.reply_text("এই TH-তে কোনো base নেই।", reply_markup=admin_keyboard())
                context.user_data.pop("admin_state", None)
                return
            await update.message.reply_text("Delete করতে Base ID পাঠাও:\n" + "\n".join(f"{b['id']} — {b['name']}" for b in bases))
            return
        bid = text
        ok = with_db(lambda db: _delete_base(db, bid))
        context.user_data.pop("admin_state", None); context.user_data.pop("delbase_step", None); context.user_data.pop("delbase_th", None)
        await update.message.reply_text("✅ Base deleted." if ok else "❌ Base ID not found.", reply_markup=admin_keyboard())
        return

    if state == "editbase":
        step = context.user_data.get("editbase_step")
        if not step:
            try:
                th = int(text)
                if th not in TH_LEVELS: raise ValueError
            except Exception:
                await update.message.reply_text("8–18 এর মধ্যে TH দাও।")
                return
            bases = with_db(lambda db: [b for b in db["bases"] if b["th"] == th])
            if not bases:
                await update.message.reply_text("এই TH-তে কোনো base নেই।")
                return
            context.user_data["editbase_step"] = "id"
            await update.message.reply_text("Base ID পাঠাও:\n" + "\n".join(f"{b['id']} — {b['name']}" for b in bases))
            return
        if step == "id":
            if not base_by_id(text):
                await update.message.reply_text("Base ID not found.")
                return
            context.user_data["editbase_id"] = text
            context.user_data["editbase_step"] = "field"
            await update.message.reply_text("কি edit করবে?\nname / link / price / category")
            return
        if step == "field":
            field = text.lower()
            if field not in ("name", "link", "price", "category"):
                await update.message.reply_text("name / link / price / category")
                return
            context.user_data["editbase_field"] = field
            context.user_data["editbase_step"] = "value"
            await update.message.reply_text("নতুন value পাঠাও।")
            return
        field = context.user_data["editbase_field"]; bid = context.user_data["editbase_id"]
        ok = _edit_base_value(bid, field, text)
        for k in ("admin_state", "editbase_step", "editbase_id", "editbase_field"):
            context.user_data.pop(k, None)
        await update.message.reply_text("✅ Base updated." if ok else "❌ Update failed.", reply_markup=admin_keyboard())
        return


async def finish_add_base(update, context, photo_file_id):
    th = context.user_data["base_th"]; mode = context.user_data["base_mode"]; category = context.user_data["base_category"]
    name = context.user_data["base_name"]; link = context.user_data["base_link"]
    price = context.user_data.get("base_price", 0)
    bid = str(int(time.time() * 1000))
    base = {"id": bid, "th": th, "mode": mode, "category": category, "name": name,
            "link": link, "price": price, "photo_file_id": photo_file_id or "", "created_at": now_str()}
    with_db(lambda db: db["bases"].append(base))
    for k in list(context.user_data.keys()):
        if k.startswith("base_"):
            context.user_data.pop(k, None)
    context.user_data.pop("admin_state", None)
    await update.message.reply_text("✅ Base added successfully!", reply_markup=admin_keyboard())


def _delete_base(db, bid):
    before = len(db["bases"])
    db["bases"] = [b for b in db["bases"] if b["id"] != bid]
    return len(db["bases"]) < before


def _edit_base_value(bid, field, value):
    def edit(db):
        b = next((x for x in db["bases"] if x["id"] == bid), None)
        if not b: return False
        if field == "price":
            try:
                v = int(value)
                if v < 0: return False
            except Exception:
                return False
            b[field] = v
        elif field == "link":
            if not value.startswith(("http://", "https://")): return False
            b[field] = value
        elif field == "category":
            if value not in db["categories"].get(str(b["th"]), {}).get(b["mode"], []): return False
            b[field] = value
        else:
            b[field] = value
        return True
    return with_db(edit)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_touch(update.effective_user)
    if not is_admin(update.effective_user.id):
        return
    if context.user_data.get("admin_state") == "addbase" and context.user_data.get("base_step") == "photo":
        photo = update.message.photo[-1]
        await finish_add_base(update, context, photo.file_id)


# ============================================================
# STARTUP / WEB HEALTH
# ============================================================
app_flask = Flask(__name__)

@app_flask.get("/")
def health():
    return "Clash Bot is running", 200


def run_health_server():
    app_flask.run(host="0.0.0.0", port=PORT)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Do not leak secrets or full API headers into logs.
    print("Bot error:", repr(context.error))


# ============================================================
# MAIN
# ============================================================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")
    ensure_categories_in_db()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_cmd))
    application.add_handler(PreCheckoutQueryHandler(precheckout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)

    base_url = os.getenv("RENDER_EXTERNAL_URL", "https://clash-coc-bot.onrender.com").rstrip("/")
    secret_token = hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()[:32]
    print("Bot is running in webhook mode...")
    print("Admin ID configured:", bool(ADMIN_ID))
    print("CoC API configured:", bool(COC_API_KEY))
    print("Webhook URL configured:", base_url + "/telegram")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="telegram",
        webhook_url=base_url + "/telegram",
        secret_token=secret_token,
        drop_pending_updates=True,
    )


def ensure_categories_in_db():
    with DB_LOCK:
        db = load_db()
        ensure_categories(db)
        save_db(db)


if __name__ == "__main__":
    main()
