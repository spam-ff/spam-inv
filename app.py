from flask import Flask, request, jsonify
import threading
import json
import os
import re
import time
from datetime import datetime
import requests

try:
    from xH import gJwt, eID, enc, hdr
    print("OK IMPORT")
except Exception as e:
    print("IMPORT ERROR:", repr(e))
    raise
app = Flask(__name__)

# ============ إعدادات ============
API_KEY = "FADAI"  # مفتاح الحماية للـ API
OWNER_TOKEN = "8422711631:AAF7AlG1yA3pp6nLk-nhOWomBMtzEmf5rRE"  # اختياري
ACCOUNTS_FILE = "acc.txt"
JWTS_FILE = "JWTS.json"
GRAVEYARD_FILE = "graveyard.json"

# ============ متغيرات عامة ============
valid_jwts = []
active_spams = {}  # {target_id: stop_event}
spam_lock = threading.Lock()

# ============ دوال مساعدة ============

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
            print("⚠️ [Spam] No valid JWTs available. Waiting...")
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

# ============ Middleware للتحقق من المفتاح ============

def check_api_key():
    key = request.args.get("key") or request.headers.get("X-API-Key")
    if not key or key != API_KEY:
        return jsonify({"error": "مفتاح API غير صحيح"}), 403
    return None

# ============ Endpoints ============

@app.route("/")
def index():
    return jsonify({
        "service": "FF Friend Sender API",
        "version": "1.0",
        "endpoints": {            "/start_spam": "POST/GET - ?key=FADAI&uid=123456 (بدء سبام)",
            "/stop_spam": "POST/GET - ?key=FADAI&uid=123456 (إيقاف سبام)",
            "/stop_all": "POST/GET - ?key=FADAI (إيقاف الكل)",
            "/list_targets": "GET - ?key=FADAI (عرض القائمة)",
            "/status": "GET - ?key=FADAI (حالة النظام)",
            "/update_tokens": "POST - ?key=FADAI (تحديث التوكنات يدوياً)"
        }
    })

@app.route("/start_spam", methods=["GET", "POST"])
def start_spam():
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    uid = request.args.get("uid") or (request.json.get("uid") if request.is_json else None)

    if not uid:
        return jsonify({"error": "يجب إدخال uid"}), 400

    if not re.match(r'^\d+$', str(uid)):
        return jsonify({"error": "UID يجب أن يكون أرقام فقط"}), 400

    if not valid_jwts:
        return jsonify({"error": "لا توجد توكنات صالحة. انتظر حتى يتم التحديث"}), 503

    uid = str(uid)

    with spam_lock:
        if uid in active_spams:
            return jsonify({"message": f"السبام نشط بالفعل على هذا الـ UID: {uid}"}), 200

        # حفظ فوري في القائمة
        save_to_graveyard(uid)

        stop_event = threading.Event()
        active_spams[uid] = stop_event

        thread = threading.Thread(target=spam_logic, args=(uid, stop_event), daemon=True)
        thread.start()

    return jsonify({
        "message": "تم بدء السبام بنجاح",
        "uid": uid,
        "active_spams": len(active_spams)
    })

@app.route("/stop_spam", methods=["GET", "POST"])
def stop_spam():
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    uid = request.args.get("uid") or (request.json.get("uid") if request.is_json else None)

    if not uid:
        return jsonify({"error": "يجب إدخال uid"}), 400

    uid = str(uid)

    with spam_lock:
        if uid not in active_spams:
            return jsonify({"error": f"لا يوجد سبام نشط للـ UID: {uid}"}), 404

        active_spams[uid].set()

    return jsonify({"message": f"تم إيقاف السبام للـ UID: {uid}"})

@app.route("/stop_all", methods=["GET", "POST"])
def stop_all():
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    with spam_lock:
        if not active_spams:
            return jsonify({"message": "لا توجد مهام سبام نشطة"}), 200

        for uid, event in active_spams.items():
            event.set()

        stopped_count = len(active_spams)
        active_spams.clear()

    return jsonify({
        "message": "تم إيقاف جميع مهام السبام",
        "stopped_count": stopped_count
    })

@app.route("/list_targets", methods=["GET"])
def list_targets():
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    gy = load_graveyard()

    if not gy:
        return jsonify({"message": "القائمة فارغة", "targets": []})
    targets = []
    for fid, gtime in gy.items():
        is_active = fid in active_spams
        targets.append({
            "uid": fid,
            "added_at": gtime,
            "active": is_active
        })

    return jsonify({
        "total": len(targets),
        "active_count": len(active_spams),
        "targets": targets
    })

@app.route("/status", methods=["GET"])
def status():
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    return jsonify({
        "valid_tokens": len(valid_jwts),
        "active_spams": len(active_spams),
        "active_uids": list(active_spams.keys()),
        "total_targets": len(load_graveyard())
    })

@app.route("/update_tokens", methods=["POST", "GET"])
def update_tokens():
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    # تشغيل التحديث في خلفية
    threading.Thread(target=update_jwts_worker, daemon=True).start()

    return jsonify({"message": "تم بدء تحديث التوكنات في الخلفية"})

# ============ تشغيل ============

if __name__ == "__main__":
    print("🔥 API is starting...")

    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "w") as f:
            pass
        print(f"️ [Setup] Created empty {ACCOUNTS_FILE}. Please add UID:PASSWORD.")

# تحميل التوكنات عند البدء
token_updater = threading.Thread(target=update_jwts_worker, daemon=True)
token_updater.start()

print("🌐 API is running on http://0.0.0.0:26080")
app.run(host="0.0.0.0", port=26080, threaded=True)
