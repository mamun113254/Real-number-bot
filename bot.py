# ==================== UPDATE OTP BOT ====================
# Python version - converted from bot.js
# pip install python-telegram-bot pyotp aiohttp
# =========================================================

# Force system packages, bypass .venv
import sys
sys.path = [p for p in sys.path if ".venv" not in p]

import os, json, re, asyncio, logging, random, string, time
from datetime import datetime, timezone
from pathlib import Path
import aiohttp, pyotp
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ChatMemberHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── CONFIG ──
BOT_TOKEN       = "8657128372:AAFArlAPVAaCEnriPz_3Wn3xc1EQUjldLH8"
ADMIN_PASSWORD  = "mamun1132"
MAIN_CHANNEL    = "@updaterange"
MAIN_CHANNEL_ID = -1001893817371
CHAT_GROUP      = "https://t.me/updaterange1"
CHAT_GROUP_ID   = -1001522463424
OTP_GROUP       = "https://t.me/otpreceived1"
OTP_GROUP_ID    = -1001153782407
BACKUP_GROUP_ID = -1003732536424
BAILEYS_URL     = os.environ.get("BAILEYS_URL", "http://localhost:3000")

# ── PATHS ──
DATA_DIR = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)
NUMBERS_FILE        = DATA_DIR / "numbers.txt"
COUNTRIES_FILE      = DATA_DIR / "countries.json"
USERS_FILE          = DATA_DIR / "users.json"
SERVICES_FILE       = DATA_DIR / "services.json"
ACTIVE_NUMBERS_FILE = DATA_DIR / "active_numbers.json"
OTP_LOG_FILE        = DATA_DIR / "otp_log.json"
ADMINS_FILE         = DATA_DIR / "admins.json"
SETTINGS_FILE       = DATA_DIR / "settings.json"
TOTP_SECRETS_FILE   = DATA_DIR / "totp_secrets.json"
TEMP_MAILS_FILE     = DATA_DIR / "temp_mails.json"
EARNINGS_FILE       = DATA_DIR / "earnings.json"
WITHDRAW_FILE       = DATA_DIR / "withdrawals.json"
COUNTRY_PRICES_FILE = DATA_DIR / "country_prices.json"

# ── LOAD/SAVE ──
def load_json(path, default):
    try:
        if path.exists(): return json.loads(path.read_text("utf-8"))
    except Exception as e: logger.error(f"Load {path}: {e}")
    return default

def save_json(path, data):
    try: path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    except Exception as e: logger.error(f"Save {path}: {e}")

# ── GLOBAL DATA ──
settings       = load_json(SETTINGS_FILE, {"defaultNumberCount":10,"cooldownSeconds":5,"requireVerification":True,"minWithdraw":50,"defaultOtpPrice":0.25,"withdrawMethods":["bKash","Nagad"],"withdrawEnabled":True})
countries      = load_json(COUNTRIES_FILE, {"880":{"name":"Bangladesh","flag":"🇧🇩"},"91":{"name":"India","flag":"🇮🇳"},"92":{"name":"Pakistan","flag":"🇵🇰"},"1":{"name":"USA","flag":"🇺🇸"},"44":{"name":"UK","flag":"🇬🇧"},"977":{"name":"Nepal","flag":"🇳🇵"}})
services       = load_json(SERVICES_FILE, {"whatsapp":{"name":"WhatsApp","icon":"📱"},"telegram":{"name":"Telegram","icon":"✈️"},"facebook":{"name":"Facebook","icon":"📘"},"instagram":{"name":"Instagram","icon":"📸"},"google":{"name":"Google","icon":"🔍"},"verification":{"name":"Verification","icon":"✅"},"other":{"name":"Other","icon":"🔧"}})
users          = load_json(USERS_FILE, {})
active_numbers = load_json(ACTIVE_NUMBERS_FILE, {})
otp_log        = load_json(OTP_LOG_FILE, [])
admins         = load_json(ADMINS_FILE, [])
totp_secrets   = load_json(TOTP_SECRETS_FILE, {})
temp_mails     = load_json(TEMP_MAILS_FILE, {})
earnings       = load_json(EARNINGS_FILE, {})
withdrawals    = load_json(WITHDRAW_FILE, [])
country_prices = load_json(COUNTRY_PRICES_FILE, {})
sessions       = {}

# Load numbers
numbers_by_cs = {}
if NUMBERS_FILE.exists():
    for line in NUMBERS_FILE.read_text("utf-8").splitlines():
        line = line.strip()
        if not line: continue
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 3: number, cc, svc = parts[0].strip(), parts[1].strip(), parts[2].strip()
            elif len(parts) == 2: number, cc, svc = parts[0].strip(), parts[1].strip(), "other"
            else: continue
        else:
            number = line; cc = None; svc = "other"
            for l in [3,2,1]:
                if line[:l] in countries: cc = line[:l]; break
        if not re.match(r"^\d{10,15}$", number) or not cc: continue
        numbers_by_cs.setdefault(cc, {}).setdefault(svc, [])
        if number not in numbers_by_cs[cc][svc]: numbers_by_cs[cc][svc].append(number)

# ── SAVE HELPERS ──
def save_settings():    save_json(SETTINGS_FILE, settings)
def save_countries():   save_json(COUNTRIES_FILE, countries)
def save_users():       save_json(USERS_FILE, users)
def save_services():    save_json(SERVICES_FILE, services)
def save_active_numbers(): save_json(ACTIVE_NUMBERS_FILE, active_numbers)
def save_otp_log():     save_json(OTP_LOG_FILE, otp_log[-1000:])
def save_admins():      save_json(ADMINS_FILE, admins)
def save_totp_secrets():save_json(TOTP_SECRETS_FILE, totp_secrets)
def save_temp_mails():  save_json(TEMP_MAILS_FILE, temp_mails)
def save_earnings():    save_json(EARNINGS_FILE, earnings)
def save_withdrawals(): save_json(WITHDRAW_FILE, withdrawals)
def save_country_prices(): save_json(COUNTRY_PRICES_FILE, country_prices)
def save_numbers():
    lines = [f"{n}|{cc}|{s}" for cc in numbers_by_cs for s in numbers_by_cs[cc] for n in numbers_by_cs[cc][s]]
    NUMBERS_FILE.write_text("\n".join(lines), "utf-8")

# ── SESSION ──
def get_session(uid):
    uid = str(uid)
    if uid not in sessions:
        sessions[uid] = {"verified":False,"is_admin":False,"admin_state":None,"admin_data":None,"current_numbers":[],"current_service":None,"current_country":None,"last_number_time":0,"last_verification_check":0,"totp_state":None,"totp_data":None,"mail_state":None,"withdraw_state":None,"withdraw_data":None,"wa_state":None}
    return sessions[uid]

# ── EARNINGS ──
def get_user_earnings(uid):
    uid = str(uid)
    if uid not in earnings: earnings[uid] = {"balance":0,"totalEarned":0,"otpCount":0}
    return earnings[uid]

def get_otp_price(cc): return country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))

def add_earning(uid, cc):
    uid = str(uid); price = get_otp_price(cc); e = get_user_earnings(uid)
    e["balance"] = round(e["balance"]+price, 2); e["totalEarned"] = round(e["totalEarned"]+price, 2)
    e["otpCount"] = e.get("otpCount",0)+1; save_earnings(); return price

# ── HELPERS ──
def is_admin(uid): return str(uid) in admins

def get_country_code(number):
    s = str(number)
    for l in [3,2,1]:
        if s[:l] in countries: return s[:l]
    return None

def get_available_countries(svc):
    return [cc for cc in numbers_by_cs if svc in numbers_by_cs[cc] and numbers_by_cs[cc][svc] and cc in countries]

def get_numbers(cc, svc, uid, count):
    pool = numbers_by_cs.get(cc,{}).get(svc,[])
    if len(pool) < count: return []
    nums = []
    for _ in range(count):
        n = numbers_by_cs[cc][svc].pop(0); nums.append(n)
        active_numbers[n] = {"userId":str(uid),"countryCode":cc,"service":svc,"assignedAt":datetime.now(timezone.utc).isoformat(),"lastOTP":None,"otpCount":0}
    save_numbers(); save_active_numbers(); return nums

def extract_phone(text):
    if not text: return None
    m = re.search(r"\+?(\d{10,15})", text)
    return m.group(1) if m else None

def find_active_number(text):
    if not active_numbers: return None
    extracted = extract_phone(text)
    if extracted:
        if extracted in active_numbers: return extracted
        if extracted.lstrip("+") in active_numbers: return extracted.lstrip("+")
    for length in [0,8,6,4]:
        for num in active_numbers:
            if length == 0:
                if num in text: return num
            elif len(num) >= length and num[-length:] in text: return num
    return None

def extract_otp(text):
    if not text: return None
    for p in [r"(?:otp|code|pin|verification|verify|token)[^\d]{0,10}(\d{4,8})",r"(?:is|has|:)\s*(\d{4,8})\b",r"\b(\d{6})\b",r"\b(\d{4})\b"]:
        m = re.search(p, text, re.IGNORECASE)
        if m and 4 <= len(m.group(1)) <= 8: return m.group(1)
    return None

def time_ago(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z","+00:00")); secs = int((datetime.now(timezone.utc)-dt).total_seconds())
        for unit,div in [("year",31536000),("month",2592000),("day",86400),("hour",3600),("minute",60)]:
            v = secs//div
            if v >= 1: return f"{v} {unit}{'s' if v>1 else ''} ago"
        return f"{secs} seconds ago"
    except: return "unknown"

def rstr(n): return "".join(random.choices(string.ascii_lowercase+string.digits, k=n))
def rpwd():  return "".join(random.choices(string.ascii_letters+string.digits, k=16))

# ── MEMBERSHIP ──
async def check_membership(bot, user_id):
    results = {}
    for cid, key in [(MAIN_CHANNEL_ID,"main"),(CHAT_GROUP_ID,"chat"),(OTP_GROUP_ID,"otp")]:
        try: m = await bot.get_chat_member(cid, user_id); results[key] = m.status in ("member","administrator","creator")
        except: results[key] = False
    return {**results, "allJoined": all(results.values())}

def verify_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ 📢 Main Channel",   url="https://t.me/updaterange")],
        [InlineKeyboardButton("2️⃣ 🌐 Number Channel", url=CHAT_GROUP)],
        [InlineKeyboardButton("3️⃣ 📨 OTP Group",       url=OTP_GROUP)],
        [InlineKeyboardButton("✅ VERIFY MEMBERSHIP",   callback_data="verify_user")],
    ])

MAIN_KB = ReplyKeyboardMarkup([["☎️ Get Number","📧 Get Tempmail"],["🔐 2FA","💰 Balances"],["💸 Withdraw","💬 Support"],["📱 Connect WhatsApp","ℹ️ Help"]], resize_keyboard=True)

async def show_main_menu(update, context):
    await update.effective_message.reply_text("🏠 *Main Menu*\n\nChoose an option:", parse_mode="Markdown", reply_markup=MAIN_KB)

async def ensure_verified(update, context):
    user = update.effective_user
    if not user: return False
    uid = str(user.id); sess = get_session(uid)
    if sess.get("is_admin"): return True
    if not settings.get("requireVerification",True): sess["verified"]=True; return True
    now = time.time()
    if sess.get("verified") and (now - sess.get("last_verification_check",0)) < 7200: return True
    m = await check_membership(context.bot, user.id)
    if m["allJoined"]:
        sess["verified"]=True; sess["last_verification_check"]=now
        if uid in users: users[uid]["verified"]=True; save_users()
        return True
    missing = ("" if m.get("main") else "❌ 1️⃣ Main Channel\n") + ("" if m.get("chat") else "❌ 2️⃣ Number Channel\n") + ("" if m.get("otp") else "❌ 3️⃣ OTP Group\n")
    msg = f"⛔ *ACCESS BLOCKED*\n\nYou have not joined all required groups:\n\n{missing}\n🔐 *Please join ALL three groups and press VERIFY*\n\n👇 Click the buttons below to join:"
    sess["verified"]=False
    if uid in users: users[uid]["verified"]=False; save_users()
    if update.callback_query:
        await update.callback_query.answer("⛔ Please join all groups first!", show_alert=True)
        try: await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=verify_kb())
        except: pass
    else: await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=verify_kb())
    return False

# ══════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; uid = str(user.id); sess = get_session(uid)
    sess.update({"current_numbers":[],"current_service":None,"current_country":None,"last_number_time":0,"last_verification_check":0,"totp_state":None,"totp_data":None,"mail_state":None,"withdraw_state":None,"withdraw_data":None,"admin_state":None,"admin_data":None,"is_admin":is_admin(uid)})
    sess["verified"] = users.get(uid,{}).get("verified",False)
    if uid not in users:
        users[uid] = {"id":uid,"username":user.username or "no_username","first_name":user.first_name or "User","last_name":user.last_name or "","joined":datetime.now(timezone.utc).isoformat(),"last_active":datetime.now(timezone.utc).isoformat(),"verified":False}; save_users()
    if not settings.get("requireVerification",True): sess["verified"]=True; return await show_main_menu(update, context)
    await update.message.reply_text("🌹 *Wellcome to Update Otp Bot* 🌹\n\n🔐 *VERIFICATION REQUIRED - 3 GROUPS*\nTo use this bot, you MUST join ALL three groups first:\n\n👇 Click the buttons below to join:", parse_mode="Markdown", disable_web_page_preview=True, reply_markup=verify_kb())

async def cmd_adminlogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id); sess = get_session(uid)
    if context.args and context.args[0] == ADMIN_PASSWORD:
        if uid not in admins: admins.append(uid); save_admins()
        sess["is_admin"] = True
        await update.message.reply_text("✅ *Admin access granted!*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    else: await update.message.reply_text("❌ Wrong password.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; uid = str(user.id); sess = get_session(uid); text = update.message.text.strip()
    if uid in users: users[uid]["last_active"] = datetime.now(timezone.utc).isoformat()

    # Admin broadcast
    if sess.get("is_admin") and sess.get("admin_state") == "waiting_broadcast":
        sent = failed = 0
        for tuid in list(users.keys()):
            try: await context.bot.send_message(int(tuid), text, parse_mode="Markdown"); sent += 1
            except: failed += 1
            await asyncio.sleep(0.05)
        sess["admin_state"] = None
        return await update.message.reply_text(f"📢 *Broadcast Done!*\n\n✅ Sent: {sent}\n❌ Failed: {failed}", parse_mode="Markdown")

    # TOTP state
    if sess.get("totp_state"):
        state = sess["totp_state"]
        if state == "waiting_name":
            sess["totp_data"] = {"name": text}; sess["totp_state"] = "waiting_secret"
            return await update.message.reply_text(f"➕ Name: *{text}*\n\nNow send the TOTP secret key:", parse_mode="Markdown")
        elif state == "waiting_secret":
            name = (sess.get("totp_data") or {}).get("name","Unknown")
            try:
                pyotp.TOTP(text).now()
                totp_secrets.setdefault(uid, {})[name] = text; save_totp_secrets()
                sess["totp_state"] = None; sess["totp_data"] = None
                return await update.message.reply_text(f"✅ *Secret Saved!*\n\n📌 {name}: `{pyotp.TOTP(text).now()}`", parse_mode="Markdown")
            except: return await update.message.reply_text("❌ Invalid TOTP secret. Try again.")

    # Withdraw state
    if sess.get("withdraw_state"):
        state = sess["withdraw_state"]
        if state == "waiting_number":
            phone = re.sub(r"\D","",text)
            if len(phone) < 10: return await update.message.reply_text("❌ Invalid phone number. Try again:")
            sess["withdraw_data"]["phone"] = text; sess["withdraw_state"] = "waiting_amount"
            e = get_user_earnings(uid)
            return await update.message.reply_text(f"💸 Phone: *{text}*\n\nBalance: *{e['balance']:.2f} taka*\n\nHow much to withdraw?", parse_mode="Markdown")
        elif state == "waiting_amount":
            try:
                amount = float(text); min_w = settings.get("minWithdraw",50); e = get_user_earnings(uid)
                if amount < min_w: return await update.message.reply_text(f"❌ Minimum is {min_w} taka.")
                if amount > e["balance"]: return await update.message.reply_text(f"❌ Insufficient balance: {e['balance']:.2f} taka.")
                w = {"userId":uid,"method":sess["withdraw_data"]["method"],"phone":sess["withdraw_data"]["phone"],"amount":amount,"status":"pending","timestamp":datetime.now(timezone.utc).isoformat()}
                withdrawals.append(w); save_withdrawals()
                e["balance"] = round(e["balance"]-amount,2); save_earnings()
                sess["withdraw_state"] = None; sess["withdraw_data"] = None
                return await update.message.reply_text(f"✅ *Withdrawal Requested!*\n\n💳 Method: {w['method']}\n📱 Phone: {w['phone']}\n💵 Amount: {amount:.2f} taka\n\n⏳ Will be processed within 24 hours.", parse_mode="Markdown")
            except ValueError: return await update.message.reply_text("❌ Invalid amount. Send a number:")

    # WA state
    if sess.get("wa_state") == "waiting_phone":
        phone = re.sub(r"\D","",text)
        if len(phone) < 10: return await update.message.reply_text("❌ Invalid number. Try again:")
        await update.message.reply_text("⏳ Getting pairing code...")
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{BAILEYS_URL}/pair", json={"phone":phone,"userId":uid}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
            if data.get("connected"): await update.message.reply_text("✅ Already connected!")
            elif data.get("code"): await update.message.reply_text(f"🔑 *Pairing Code:*\n\n`{data['code']}`\n\nEnter this in WhatsApp → Linked Devices → Link a Device → Link with phone number", parse_mode="Markdown")
            else: await update.message.reply_text(f"❌ Error: {data.get('error','Unknown error')}")
        except Exception as e: await update.message.reply_text(f"❌ Connection failed: {e}")
        sess["wa_state"] = None; return

    # Menu buttons
    actions = {
        "☎️ Get Number": handle_get_number, "📧 Get Tempmail": handle_tempmail,
        "🔐 2FA": handle_2fa, "💰 Balances": handle_balance,
        "💸 Withdraw": handle_withdraw, "💬 Support": handle_support,
        "📱 Connect WhatsApp": handle_whatsapp, "ℹ️ Help": handle_help,
    }
    if text in actions: return await actions[text](update, context)

async def handle_get_number(update, context):
    if not await ensure_verified(update, context): return
    keyboard = [[InlineKeyboardButton(f"{s['icon']} {s['name']}", callback_data=f"select_service:{sid}")] for sid,s in services.items() if get_available_countries(sid)]
    if not keyboard: return await update.effective_message.reply_text("❌ No numbers available right now.")
    await update.effective_message.reply_text("📱 *Select a Service:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_balance(update, context):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id); e = get_user_earnings(uid)
    await update.message.reply_text(f"💰 *Your Earnings*\n\n💵 Balance: *{e['balance']:.2f} taka*\n📈 Total Earned: *{e['totalEarned']:.2f} taka*\n📨 OTPs: *{e.get('otpCount',0)}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💸 Withdraw", callback_data="start_withdraw")]]))

async def handle_withdraw(update, context):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id); e = get_user_earnings(uid); min_w = settings.get("minWithdraw",50)
    if not settings.get("withdrawEnabled",True): return await update.effective_message.reply_text("❌ Withdrawals are currently disabled.")
    if e["balance"] < min_w: return await update.effective_message.reply_text(f"❌ Minimum withdraw is *{min_w} taka*.\nYour balance: *{e['balance']:.2f} taka*", parse_mode="Markdown")
    methods = settings.get("withdrawMethods",["bKash","Nagad"])
    await update.effective_message.reply_text(f"💸 *Withdraw*\n\nBalance: *{e['balance']:.2f} taka*\n\nSelect payment method:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(m, callback_data=f"withdraw_method:{m}")] for m in methods]))

async def handle_2fa(update, context):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id); user_secrets = totp_secrets.get(uid,{})
    if not user_secrets:
        return await update.message.reply_text("🔐 *2FA Manager*\n\nNo secrets saved yet.\n\nSend me a TOTP secret key to add it:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add Secret", callback_data="totp_add")]]))
    lines = ["🔐 *Your 2FA Codes:*\n"]
    for name, secret in user_secrets.items():
        try: lines.append(f"📌 *{name}*: `{pyotp.TOTP(secret).now()}`")
        except: lines.append(f"📌 *{name}*: ❌ Invalid")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add New",callback_data="totp_add"),InlineKeyboardButton("🔄 Refresh",callback_data="totp_refresh")]]))

async def handle_tempmail(update, context):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    if uid in temp_mails:
        mail = temp_mails[uid]
        await update.message.reply_text(f"📧 *Your Temp Email:*\n\n`{mail['address']}`\n\nCreated: {time_ago(mail['createdAt'])}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Check Inbox",callback_data="mail_inbox"),InlineKeyboardButton("🔄 New Email",callback_data="mail_new")]]))
    else:
        await update.message.reply_text("📧 *Temp Email*\n\nCreate a temporary email address:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✉️ Create Email",callback_data="mail_create")]]))

async def handle_whatsapp(update, context):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{BAILEYS_URL}/status?userId={uid}", timeout=aiohttp.ClientTimeout(total=5)) as r:
                connected = (await r.json()).get("connected",False)
    except: connected = False
    if connected:
        await update.message.reply_text("✅ *WhatsApp Connected!*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔴 Disconnect",callback_data="wa_disconnect")]]))
    else:
        await update.message.reply_text("📱 *Connect WhatsApp*\n\nSend your phone number to get a pairing code:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 Connect",callback_data="wa_connect")]]))

async def handle_support(update, context):
    await update.effective_message.reply_text(f"💬 *Support*\n\n📢 Main Channel: @updaterange\n🌐 Number Group: {CHAT_GROUP}", parse_mode="Markdown")

async def handle_help(update, context):
    await update.message.reply_text("ℹ️ *How to use UPDATE Otp Bot*\n\n1️⃣ Join all 3 required groups\n2️⃣ Press ☎️ Get Number\n3️⃣ Select service & country\n4️⃣ Use number to receive OTP\n5️⃣ Earn taka per OTP received\n6️⃣ Withdraw via bKash/Nagad\n\n💡 Connect WhatsApp to check numbers!", parse_mode="Markdown")

# ── CALLBACKS ──
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; d = q.data; uid = str(update.effective_user.id); sess = get_session(uid)

    if d == "verify_user":
        await q.answer("🔍 Checking all 3 groups...")
        m = await check_membership(context.bot, update.effective_user.id)
        if m["allJoined"]:
            sess["verified"]=True; sess["last_verification_check"]=time.time()
            if uid in users: users[uid]["verified"]=True; save_users()
            await q.edit_message_text("✅ *VERIFICATION SUCCESSFUL!*\n\n🎉 You have joined all 3 required groups.\n\nYou can now use all bot features.\n\n👇 Press the button below to continue:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Go to Main Menu",callback_data="goto_main_menu")]]))
        else:
            missing = ("" if m.get("main") else "❌ 1️⃣ Main Channel\n") + ("" if m.get("chat") else "❌ 2️⃣ Number Channel\n") + ("" if m.get("otp") else "❌ 3️⃣ OTP Group\n")
            await q.edit_message_text(f"❌ *VERIFICATION FAILED*\n\nYou haven't joined:\n\n{missing}\nPlease join them and try again:", parse_mode="Markdown", reply_markup=verify_kb())

    elif d == "goto_main_menu": await q.answer(); await show_main_menu(update, context)
    elif d == "back_to_services": await q.answer(); await handle_get_number(update, context)
    elif d == "start_withdraw": await q.answer(); await handle_withdraw(update, context)
    elif d == "wa_connect": await q.answer(); sess["wa_state"]="waiting_phone"; await q.edit_message_text("📲 *Connect WhatsApp*\n\nSend your phone number with country code:\n\nExample: `8801XXXXXXXXX`", parse_mode="Markdown")
    elif d == "wa_disconnect":
        await q.answer("🔴 Disconnecting...")
        try:
            async with aiohttp.ClientSession() as s: await s.post(f"{BAILEYS_URL}/disconnect", json={"userId":uid})
        except: pass
        await q.edit_message_text("🔴 *WhatsApp Disconnected.*", parse_mode="Markdown")
    elif d == "totp_add": await q.answer(); sess["totp_state"]="waiting_name"; await q.edit_message_text("➕ *Add 2FA Secret*\n\nSend the name for this account (e.g. Google, Facebook):", parse_mode="Markdown")
    elif d == "totp_refresh":
        await q.answer("🔄 Refreshed!")
        user_secrets = totp_secrets.get(uid,{}); lines = ["🔐 *Your 2FA Codes:*\n"]
        for name,secret in user_secrets.items():
            try: lines.append(f"📌 *{name}*: `{pyotp.TOTP(secret).now()}`")
            except: lines.append(f"📌 *{name}*: ❌ Invalid")
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add New",callback_data="totp_add"),InlineKeyboardButton("🔄 Refresh",callback_data="totp_refresh")]]))
    elif d == "mail_create" or d == "mail_new":
        await q.answer("⏳ Creating email...")
        mail = await create_email()
        if not mail: return await q.edit_message_text("❌ Failed to create email. Try again.")
        temp_mails[uid]=mail; save_temp_mails()
        await q.edit_message_text(f"✅ *Email Created!*\n\n`{mail['address']}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Check Inbox",callback_data="mail_inbox")]]))
    elif d == "mail_inbox":
        await q.answer("📥 Checking inbox...")
        mail = temp_mails.get(uid)
        if not mail: return await q.edit_message_text("❌ No email found. Create one first.")
        msgs = await get_email_inbox(mail)
        if not msgs:
            return await q.edit_message_text(f"📭 *Inbox Empty*\n\n`{mail['address']}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh",callback_data="mail_inbox")]]))
        lines = [f"📧 *Inbox ({len(msgs)} messages):*\n"]
        for msg in msgs[:5]: lines.append(f"📨 From: {msg.get('from',{}).get('address','unknown')}\n📌 {msg.get('subject','No subject')}\n")
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh",callback_data="mail_inbox")]]))
    elif d.startswith("select_service:"):
        await q.answer(); svc_id = d.split(":")[1]; sess["current_service"]=svc_id
        available = get_available_countries(svc_id)
        if not available: return await q.edit_message_text("❌ No numbers available for this service.")
        keyboard = [[InlineKeyboardButton(f"{countries[cc]['flag']} {countries[cc]['name']} ({len(numbers_by_cs.get(cc,{}).get(svc_id,[]))})", callback_data=f"select_country:{cc}")] for cc in available]
        keyboard.append([InlineKeyboardButton("🔙 Back",callback_data="back_to_services")])
        await q.edit_message_text("🌍 *Select a Country:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif d.startswith("select_country:"):
        await q.answer(); cc = d.split(":")[1]; sess["current_country"]=cc; svc_id = sess.get("current_service","other")
        count = len(numbers_by_cs.get(cc,{}).get(svc_id,[])); price = get_otp_price(cc)
        c = countries.get(cc,{"flag":"🌍","name":cc}); svc = services.get(svc_id,{"icon":"📱","name":svc_id})
        await q.edit_message_text(f"{c['flag']} *{c['name']}* — {svc['icon']} {svc['name']}\n\n📊 Available: *{count}* numbers\n💵 Price per OTP: *{price} taka*\n\nHow many numbers do you want?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("1️⃣ 1",callback_data="get_numbers:1"),InlineKeyboardButton("5️⃣ 5",callback_data="get_numbers:5"),InlineKeyboardButton("🔟 10",callback_data="get_numbers:10")],[InlineKeyboardButton("🔙 Back",callback_data=f"select_service:{svc_id}")]]))
    elif d.startswith("get_numbers:"):
        await q.answer(); count = int(d.split(":")[1]); now = time.time()
        if now - sess.get("last_number_time",0) < settings.get("cooldownSeconds",5): return await q.answer(f"⏳ Please wait {settings.get('cooldownSeconds',5)} seconds.", show_alert=True)
        cc = sess.get("current_country"); svc_id = sess.get("current_service","other")
        if not cc: return await q.edit_message_text("❌ Session expired. Please start again.")
        nums = get_numbers(cc, svc_id, uid, count)
        if not nums: return await q.edit_message_text("❌ Not enough numbers available.")
        sess["current_numbers"]=nums; sess["last_number_time"]=now
        c = countries.get(cc,{"flag":"🌍","name":cc}); svc = services.get(svc_id,{"icon":"📱","name":svc_id})
        numbers_text = "\n".join([f"`+{n}`" for n in nums])
        await q.edit_message_text(f"✅ *Numbers Assigned!*\n\n{svc['icon']} Service: *{svc['name']}*\n{c['flag']} Country: *{c['name']}*\n\n📞 *Your Numbers:*\n{numbers_text}\n\n⏳ Waiting for OTP...", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu",callback_data="goto_main_menu")]]))
    elif d.startswith("withdraw_method:"):
        await q.answer(); method = d.split(":")[1]; sess["withdraw_state"]="waiting_number"; sess["withdraw_data"]={"method":method}
        await q.edit_message_text(f"💸 *Withdraw via {method}*\n\nPlease send your {method} number:", parse_mode="Markdown")
    elif d == "admin_panel": await cb_admin_panel(update, context)
    elif d == "admin_stats": await cb_admin_stats(update, context)
    elif d == "admin_settings": await cb_admin_settings(update, context)
    elif d == "admin_toggle_verify": settings["requireVerification"]=not settings.get("requireVerification",True); save_settings(); await cb_admin_settings(update, context)
    elif d == "admin_toggle_withdraw": settings["withdrawEnabled"]=not settings.get("withdrawEnabled",True); save_settings(); await cb_admin_settings(update, context)
    elif d == "admin_broadcast": sess["admin_state"]="waiting_broadcast"; await q.edit_message_text("📢 *Broadcast Message*\n\nSend the message to broadcast to all users:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel",callback_data="admin_panel")]]))
    else: await q.answer("Unknown action")

async def cb_admin_panel(update, context):
    q = update.callback_query; await q.answer(); uid = str(update.effective_user.id)
    if not is_admin(uid): return await q.answer("❌ No access.", show_alert=True)
    await q.edit_message_text("⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats",callback_data="admin_stats"),InlineKeyboardButton("⚙️ Settings",callback_data="admin_settings")],
        [InlineKeyboardButton("💰 Earnings",callback_data="admin_earnings"),InlineKeyboardButton("💸 Withdrawals",callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📢 Broadcast",callback_data="admin_broadcast")],
    ]))

async def cb_admin_stats(update, context):
    await update.callback_query.answer()
    total = len(users); verified = sum(1 for u in users.values() if u.get("verified"))
    total_nums = sum(len(numbers_by_cs[cc][s]) for cc in numbers_by_cs for s in numbers_by_cs[cc])
    total_earn = sum(e.get("totalEarned",0) for e in earnings.values())
    await update.callback_query.edit_message_text(f"📊 *Bot Statistics*\n\n👥 Total Users: *{total}*\n✅ Verified: *{verified}*\n📱 Available Numbers: *{total_nums}*\n🔄 Active Numbers: *{len(active_numbers)}*\n💵 Total Paid: *{total_earn:.2f} taka*\n📨 OTP Logs: *{len(otp_log)}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]))

async def cb_admin_settings(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(f"⚙️ *Settings*\n\n🔢 Default Numbers: *{settings.get('defaultNumberCount',10)}*\n⏳ Cooldown: *{settings.get('cooldownSeconds',5)}s*\n🔐 Verification: *{'ON' if settings.get('requireVerification') else 'OFF'}*\n💸 Min Withdraw: *{settings.get('minWithdraw',50)} taka*\n💵 OTP Price: *{settings.get('defaultOtpPrice',0.25)} taka*\n💳 Withdraw: *{'ON' if settings.get('withdrawEnabled') else 'OFF'}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔐 Toggle Verification",callback_data="admin_toggle_verify")],[InlineKeyboardButton("💸 Toggle Withdraw",callback_data="admin_toggle_withdraw")],[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]))

# ── OTP GROUP MONITOR ──
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if str(update.effective_chat.id) != str(OTP_GROUP_ID): return
        text = update.message.text or update.message.caption or ""
        if not text: return
        matched = find_active_number(text)
        if not matched: return
        data = active_numbers[matched]; user_id = data["userId"]; cc = data.get("countryCode",""); msg_id = update.message.message_id
        if data.get("lastOTP") == msg_id: return
        data["lastOTP"]=msg_id; data["otpCount"]=data.get("otpCount",0)+1; save_active_numbers()
        otp_code = extract_otp(text); earned = add_earning(user_id, cc); balance = get_user_earnings(user_id)["balance"]
        svc = services.get(data.get("service","other"),{"icon":"📱","name":"other"}); country = countries.get(cc,{"flag":"🌍","name":cc})
        notify = f"📨 *OTP Received!*\n\n{svc['icon']} *Service:* {svc['name']}\n{country['flag']} *Country:* {country['name']}\n📞 *Number:* `+{matched}`\n"
        if otp_code: notify += f"\n🔑 *OTP Code:* `{otp_code}`\n"
        notify += f"\n💵 *+{earned:.2f} taka earned!*\n💰 *Balance: {balance:.2f} taka*"
        await context.bot.send_message(int(user_id), notify, parse_mode="Markdown")
        await context.bot.forward_message(int(user_id), OTP_GROUP_ID, msg_id)
        otp_log.append({"phoneNumber":matched,"userId":user_id,"countryCode":cc,"service":data.get("service"),"otpCode":otp_code,"earned":earned,"messageId":msg_id,"delivered":True,"timestamp":datetime.now(timezone.utc).isoformat()}); save_otp_log()
    except Exception as e: logger.error(f"OTP monitor error: {e}")

async def handle_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = update.chat_member
        if not member: return
        chat_id = str(update.effective_chat.id); user_id = str(member.new_chat_member.user.id)
        if chat_id not in [str(MAIN_CHANNEL_ID),str(CHAT_GROUP_ID),str(OTP_GROUP_ID)]: return
        if member.old_chat_member.status in ("member","administrator","creator") and member.new_chat_member.status in ("left","kicked","restricted"):
            if user_id in users: users[user_id]["verified"]=False; save_users()
            if user_id in sessions: sessions[user_id]["verified"]=False
    except Exception as e: logger.error(f"chat_member error: {e}")

# ── MAIL ──
async def create_email():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.mail.tm/domains?page=1") as r: data = await r.json()
            domains = data if isinstance(data,list) else data.get("hydra:member",[])
            if not domains: return None
            domain=domains[0]["domain"]; username=rstr(12); password=rpwd(); address=f"{username}@{domain}"; acc=None
            for _ in range(3):
                async with s.post("https://api.mail.tm/accounts",json={"address":address,"password":password}) as r: acc=await r.json()
                if acc.get("id"): break
                await asyncio.sleep(2)
            if not acc or not acc.get("id"): return None
            async with s.post("https://api.mail.tm/token",json={"address":address,"password":password}) as r: tok=await r.json()
            if not tok.get("token"): return None
            return {"address":address,"sidToken":tok["token"],"provider":"mailtm","createdAt":datetime.now(timezone.utc).isoformat()}
    except Exception as e: logger.error(f"Mail.tm error: {e}"); return None

async def get_email_inbox(mail):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.mail.tm/messages?page=1",headers={"Authorization":f"Bearer {mail['sidToken']}"}) as r: data=await r.json()
        return data if isinstance(data,list) else data.get("hydra:member",[])
    except: return []

# ── MAIN ──
def main():
    logger.info("="*40); logger.info("🚀 Starting UPDATE Otp Bot (Python)"); logger.info("="*40)
    save_settings(); save_countries(); save_services()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("adminlogin", cmd_adminlogin))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(OTP_GROUP_ID), handle_group_message))
    app.add_handler(ChatMemberHandler(handle_chat_member))
    logger.info("✅ Bot started successfully!")
    app.run_polling(allowed_updates=["message","callback_query","chat_member","my_chat_member"])

if __name__ == "__main__":
    main()
