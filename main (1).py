import telebot
import time
import threading
import json
import os
import re
from datetime import datetime
import requests

try:
    from xH import gJwt, eID, enc, hdr
except ImportError:
    print("kyn khata2 taekd a w9")
    exit()

BOT_TOKEN = "8422711631:AAF7AlG1yA3pp6nLk-nhOWomBMtzEmf5rRE"
OWNER_ID = 2093600923
ACCOUNTS_FILE = "acc.txt"
JWTS_FILE = "JWTS.json"
GRAVEYARD_FILE = "graveyard.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

valid_jwts = []
active_spams = {}  # Dictionary to hold multiple active targets: {target_id: stop_event}
spam_lock = threading.Lock()

def load_accounts():
    accs = []
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) == 2:
                    accs.append((parts[0], parts[1]))
    return accs

def load_graveyard():
    if os.path.exists(GRAVEYARD_FILE):
        try:
            with open(GRAVEYARD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_to_graveyard(player_id):
    gy = load_graveyard()

    if str(player_id) not in gy:
        gy[str(player_id)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(GRAVEYARD_FILE, "w", encoding="utf-8") as f:
            json.dump(gy, f, ensure_ascii=False, indent=4)

def update_jwts_worker():
    global valid_jwts
    while True:
        print("🔄 [System] Start updating JWT tokens...")
        accounts = load_accounts()
        if not accounts:
            print("⚠️ [System] No accounts found in acc.txt")
            valid_jwts = []
        else:
            new_jwts = []
            for uid, pwd in accounts:
                try:
                    jwt = gJwt(uid, pwd)
                    if jwt:
                        new_jwts.append(jwt)
                        print(f"✅ [Token] Fetched for UID: {uid}")
                except Exception as e:
                    print(f"❌ [Token] Failed for UID: {uid}. Error: {e}")
            valid_jwts = new_jwts
            with open(JWTS_FILE, "w") as f:
                json.dump(valid_jwts, f)
            print(f"✨ [System] Total valid tokens: {len(valid_jwts)}")
        time.sleep(7 * 3600)

def send_add_request(target_id, jwt):
    url = "https://clientbp.ggpolarbear.com/RequestAddingFriend"
    headers = hdr(jwt)
    try:
        encrypted_id_hex = eID(target_id)
        payload_hex = f"08a7c4839f1e10{encrypted_id_hex}1801"
        payload_bytes = bytes.fromhex(payload_hex)
        encrypted_payload = enc(payload_bytes)
        headers["Content-Length"] = str(len(encrypted_payload))
        response = requests.post(url, headers=headers, data=encrypted_payload, timeout=10, verify=False)
        return response.status_code == 200
    except:
        return False

def spam_logic(target_id, stop_event):
    print(f"🚀 [Spam] Started on target: {target_id}")
    request_count = 0
    errors_in_row = 0

    while not stop_event.is_set():
        if not valid_jwts:
            print("️ [Spam] No valid JWTs available. Waiting...")
            time.sleep(30)            
            continue

        tokens_to_use = list(valid_jwts)
        
        for jwt in tokens_to_use:
            if stop_event.is_set(): 
                break 

            success = send_add_request(target_id, jwt)
            
            if success:
                request_count += 1
                errors_in_row = 0
                if request_count % 10 == 0:
                    print(f"🛰️ [Spam] Sent {request_count} requests to {target_id}...")
            else:
                errors_in_row += 1
            
            time.sleep(0.5) 

        time.sleep(2)
        
        if errors_in_row >= len(tokens_to_use) and len(tokens_to_use) > 0:
             print("⚠️ [Spam] Too many failures. Possible token expiry or bad ID.")
             time.sleep(10) 

    print(f"🛑 [Spam] Stopped on target: {target_id}. Total sent: {request_count}")
    with spam_lock:
        active_spams.pop(target_id, None)

def is_owner(message):
    return message.from_user.id == OWNER_ID

def send_reply(message, text):
    bot.reply_to(message, f"<b>{text}</b>")

@bot.message_handler(func=lambda msg: msg.from_user.id != OWNER_ID)
def block_others(message):
    pass

@bot.message_handler(commands=['start'])
def send_welcome(message):
    help_text = (
        "💀 نظام القبر - المالك فقط\n"
        "---------------------------\n"
        "/7wih \n"
        "/w9f \n"
        "/lm7wiyin \n"
        "---------------------------"
    )
    send_reply(message, help_text)

@bot.message_handler(commands=['7wih'])
def start_spam_cmd(message):
    parts = message.text.split()
    if len(parts) < 2:
        send_reply(message, "Maxi huka nn Dir => \n/7wih 123456789")
        return
    
    target_id = parts[1]
    
    if not re.match(r'^\d+$', target_id):
        send_reply(message, "Wa w9 Id 4alat Just numérique")
        return

    if not valid_jwts:
        send_reply(message, "Toknat ba9in a w9 att")
        return

    with spam_lock:
        if target_id in active_spams:
            send_reply(message, f"Rah khdam deja 3la hada => {target_id}")
            return

        # حفظ الـ ID فوراً في القائمة
        save_to_graveyard(target_id)
        
        stop_event = threading.Event()
        active_spams[target_id] = stop_event
        
        thread = threading.Thread(target=spam_logic, args=(target_id, stop_event), daemon=True)
        thread.start()
        
    send_reply(message, f"Sf ra bdit kn 7wi fih =>\nkonto {target_id}")

@bot.message_handler(commands=['w9f'])
def stop_spam_cmd(message):
    parts = message.text.split()
    with spam_lock:
        if len(parts) < 2:
            # إيقاف جميع الـ IDs
            if not active_spams:
                send_reply(message, "mkyn ta spam")
                return
            for tid, event in active_spams.items():
                event.set()
            send_reply(message, "Wa zb att ani anw9f kolchi... Att")
        else:
            # إيقاف ID محدد
            target_id = parts[1]

        if target_id not in active_spams:
            send_reply(message, f"Hada makaynch f list => {target_id}")
            return

        active_spams[target_id].set()
        send_reply(message, f"Wa zb att ani anw9f had => {target_id}... Att")
                
            

@bot.message_handler(commands=['lm7wiyin'])
def list_graveyard_cmd(message):
    gy = load_graveyard()
    if not gy:
        send_reply(message, "Ba9i m7wit ta 7ad")
        return
    txt = "Xof x7al 7xit hhhhhh \n\n"
    count = 1
    for fid, gtime in gy.items():
        txt += f"{count}. <code>{fid}</code> - {gtime}\n"
        count += 1
        if count > 50: 
            txt += "... و المزيد"
            break
    send_reply(message, txt)

if __name__ == "__main__":
    print("🔥 Bot is starting...")
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "w") as f:
            pass
        print(f"⚠️ [Setup] Created empty {ACCOUNTS_FILE}. Please add UID:PASSWORD.")

    token_updater = threading.Thread(target=update_jwts_worker, daemon=True)
    token_updater.start()

    print("🤖 Bot is polling...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"❌ [Bot Error] {e}")
            time.sleep(5)