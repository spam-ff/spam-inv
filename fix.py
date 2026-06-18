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
    print("khata2")
    exit()

BOT_TOKEN = "8422711631:AAF7AlG1yA3pp6nLk-nhOWomBMtzEmf5rRE"
OWNER_ID = 2093600923
ACCOUNTS_FILE = "acc.txt"
JWTS_FILE = "JWTS.json"
GRAVEYARD_FILE = "graveyard.json"
AUTH_CHATS_FILE = "auth_chats.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

valid_jwts = []
active_spams = {}
authorized_chats = set()
spam_lock = threading.Lock()
auth_lock = threading.Lock()

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

def load_authorized_chats():
    global authorized_chats
    if os.path.exists(AUTH_CHATS_FILE):
        try:
            with open(AUTH_CHATS_FILE, "r") as f:
                data = json.load(f)
                authorized_chats = set(data)
                print(f"✅ [System] Loaded {len(authorized_chats)} authorized chats.")
        except Exception as e:
            print(f"❌ [System] Error loading auth chats: {e}")
            authorized_chats = set()
    else:
        authorized_chats = set()

def save_authorized_chat(chat_id):
    global authorized_chats
    with auth_lock:
        load_authorized_chats()
        authorized_chats.add(chat_id)
        try:
            with open(AUTH_CHATS_FILE, "w") as f:
                json.dump(list(authorized_chats), f)
            return True
        except Exception as e:
            print(f"❌ [System] Error saving auth chat: {e}")
            return False

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
            try:
                with open(JWTS_FILE, "w") as f:
                    json.dump(valid_jwts, f)
                print(f"✨ [System] Total valid tokens: {len(valid_jwts)}")
            except Exception as e:
                print(f"❌ [System] Error saving JWTS.json: {e}")
                
        time.sleep(7 * 3600)

def send_add_request(target_id, jwt):
    url = "https://clientbp.ggpolarbear.com/RequestAddingFriend"
    headers = hdr(jwt)
    try:
        encrypted_id_hex = eID(target_id)
        if not encrypted_id_hex: return False
        
        payload_hex = f"08a7c4839f1e10{encrypted_id_hex}1801"
        payload_bytes = bytes.fromhex(payload_hex)
        encrypted_payload = enc(payload_bytes)
        
        if not encrypted_payload: return False

        headers["Content-Length"] = str(len(encrypted_payload))
        response = requests.post(url, headers=headers, data=encrypted_payload, timeout=10, verify=False)
        return response.status_code == 200
    except Exception as e:
        return False

def spam_logic(target_id, stop_event):
    print(f"🚀 [Spam] Started on target: {target_id}")
    request_count = 0
    errors_in_row = 0

    while not stop_event.is_set():
        current_jwts = list(valid_jwts)
        
        if not current_jwts:
            print("⚠️ [Spam] No valid JWTs available. Waiting 30s...")
            time.sleep(30)            
            continue
        
        for jwt in current_jwts:
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
            
            time.sleep(0.3) 

        time.sleep(1)
        
        if errors_in_row >= len(current_jwts) and len(current_jwts) > 0:
             print(f"⚠️ [Spam] High failure rate on {target_id}. Pausing 10s.")
             time.sleep(10) 
             errors_in_row = 0

    print(f"🛑 [Spam] Stopped on target: {target_id}. Total sent: {request_count}")
    with spam_lock:
        active_spams.pop(target_id, None)

def is_owner(message):
    return message.from_user.id == OWNER_ID

def is_chat_authorized(message):
    chat_id = message.chat.id
    if message.chat.type == 'private' and message.from_user.id == OWNER_ID:
        return True
    if chat_id in authorized_chats:
        return True
    return False

def send_reply(message, text):
    try:
        bot.reply_to(message, f"<b>{text}</b>", parse_mode="HTML")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

@bot.message_handler(commands=['x'])
def activate_chat_cmd(message):
    if not is_owner(message):
        return

    if message.chat.type == 'private':
        send_reply(message, "❌ هاد الأمر خدام غير ف لڭروبات أ و9.")
        return

    chat_id = message.chat.id
    chat_title = message.chat.title

    if chat_id in authorized_chats:
        send_reply(message, f"Hbs y7wa jad group => ({chat_title}) Khdam 9bl")
        return

    if save_authorized_chat(chat_id):
        send_reply(message, f"Sf khdmt mkyk a l7wa: {chat_title}\n.")
        print(f"➕ [Auth] Chat activated: {chat_title} ({chat_id})")
    else:
        send_reply(message, "Error a w9")

@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith('/') and not is_chat_authorized(msg))
def block_unauthorized_chats(message):
    if message.chat.type != 'private':
        send_reply(message, "Wa admin pas /x bx nkhdm")
    else:
        send_reply(message, "❌ خاص بالمالك فقط.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    help_text = (
        "---------------------------\n"
        "== Dispo ==:\n"
        "/7wih [ID] -> 7wya pro maw\n"
        "/w9f [ID] -> Baraka 3lih\n"
        "/w9f -> Stop all\n"
        "/lm7wiyin -> Rak 3rf\n"
        "---------------------------"
    )
    if is_owner(message) and message.chat.type != 'private':
        help_text += "\n<b>SIR TKWA<b>"
        
    send_reply(message, help_text)

@bot.message_handler(commands=['7wih'])
def start_spam_cmd(message):
    parts = message.text.split()
    if len(parts) < 2:
        send_reply(message, "Rakaz dir haka => \n/7wih 123456789")
        return
    
    target_id = parts[1]
    
    if not re.match(r'^\d+$', target_id):
        send_reply(message, "Id 4ir ar9am xarb lma7ya la ?.")
        return

    if not valid_jwts:
        send_reply(message, "Sb nxarji toknat")
        return

    with spam_lock:
        if target_id in active_spams:
            send_reply(message, f"Ra deja kn7wi fih => {target_id}")
            return

        save_to_graveyard(target_id)
        
        stop_event = threading.Event()
        active_spams[target_id] = stop_event
        
        thread = threading.Thread(target=spam_logic, args=(target_id, stop_event), daemon=True)
        thread.start()
        
    send_reply(message, f"Sf bdit kn7wih 😁 konto => {target_id}")

@bot.message_handler(commands=['w9f'])
def stop_spam_cmd(message):
    parts = message.text.split()
    with spam_lock:
        if len(parts) < 2:
            if not active_spams:
                send_reply(message, "Mkyn mn 7wi")
                return
            
            count = len(active_spams)
            for tid, event in active_spams.items():
                event.set()
            send_reply(message, f"Att n7bs => {count} .....")
        else:
            target_id = parts[1]

            if target_id not in active_spams:
                send_reply(message, f"Mkynx => ({target_id}) Fi lm7wiyin")
                return

            active_spams[target_id].set()
            send_reply(message, f"Sbr nw9f => {target_id}... att.")

@bot.message_handler(commands=['lm7wiyin'])
def list_graveyard_cmd(message):
    gy = load_graveyard()
    if not gy:
        send_reply(message, "Mkyn walo Ayayayyyy")
        return
    
    txt = f"💀 <b>lm7wiyin => {len(gy)})</b>\n\n"
    count = 1
    sorted_gy = sorted(gy.items(), key=lambda x: x[1], reverse=True)
    
    for fid, gtime in sorted_gy:
        txt += f"{count}. <code>{fid}</code> - {gtime}\n"
        count += 1
        if count > 50: 
            txt += "... و المزيد"
            break
    send_reply(message, txt)

if __name__ == "__main__":
    print("🔥 Bot is starting...")
    
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "w") as f: pass
        print(f"⚠️ [Setup] Created empty {ACCOUNTS_FILE}. Add UID:PASSWORD.")
    
    load_authorized_chats()

    token_updater = threading.Thread(target=update_jwts_worker, daemon=True)
    token_updater.start()

    print("🤖 Bot is polling...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ [Bot Error] {e}")
            time.sleep(5)
            