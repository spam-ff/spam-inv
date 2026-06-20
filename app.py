import time
import threading
import json
import os
import re
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException
import uvicorn

# محاولة استيراد دوال التشفير الخاصة بك
try:
    from xH import gJwt, eID, enc, hdr
except ImportError:
    print("⚠️ [تحذير] ملف xH غير موجود، تأكد من إرفاقه.")

# الإعدادات
ADMIN_KEY = "SA9RIX"
ACCOUNTS_FILE = "acc.txt"
JWTS_FILE = "JWTS.json"
GRAVEYARD_FILE = "graveyard.json"
SAFE_FILE = "safe_uids.json"  # ملف لحفظ الآيديات المحمية

# تهيئة الـ API
app = FastAPI(title="FF Script API")

valid_jwts = []
active_spams = {}
safe_uids = set()
spam_lock = threading.Lock()

# ================= الدوال المساعدة ================= #
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
        except: return {}
    return {}

def save_to_graveyard(player_id):
    gy = load_graveyard()
    if str(player_id) not in gy:
        gy[str(player_id)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(GRAVEYARD_FILE, "w", encoding="utf-8") as f:
            json.dump(gy, f, ensure_ascii=False, indent=4)

def load_safe_uids():
    global safe_uids
    if os.path.exists(SAFE_FILE):
        try:
            with open(SAFE_FILE, "r") as f:
                safe_uids = set(json.load(f))
        except: safe_uids = set()

def save_safe_uids():
    with open(SAFE_FILE, "w") as f:
        json.dump(list(safe_uids), f)

def update_jwts_worker():
    global valid_jwts
    while True:
        print("🔄 [System] Start updating JWT tokens...")
        accounts = load_accounts()
        if accounts:
            new_jwts = []
            for uid, pwd in accounts:
                try:
                    jwt = gJwt(uid, pwd) 
                    if jwt: new_jwts.append(jwt)
                except: pass
            
            valid_jwts = new_jwts
            try:
                with open(JWTS_FILE, "w") as f: json.dump(valid_jwts, f)
            except: pass
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
    except: return False

def spam_logic(target_id, stop_event):
    request_count = 0
    errors_in_row = 0
    while not stop_event.is_set():
        current_jwts = list(valid_jwts)
        if not current_jwts:
            time.sleep(30)            
            continue
        
        for jwt in current_jwts:
            if stop_event.is_set(): break 
            success = send_add_request(target_id, jwt)
            if success:
                request_count += 1
                errors_in_row = 0
            else:
                errors_in_row += 1
            time.sleep(0.3) 
        time.sleep(1)
        if errors_in_row >= len(current_jwts) and len(current_jwts) > 0:
             time.sleep(10) 
             errors_in_row = 0

    with spam_lock: active_spams.pop(target_id, None)

@app.on_event("startup")
def startup_event():
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "w") as f: pass
    load_safe_uids()
    token_updater = threading.Thread(target=update_jwts_worker, daemon=True)
    token_updater.start()

@app.get("/spam")
def start_spam(uid: str):
    if not re.match(r'^\d+$', uid):
        return {"status": "error", "message": "الآيدي يجب أن يكون أرقام فقط"}
    
    if uid in safe_uids:
        return {"status": "error", "message": "❌ هذا الآيدي محمي (V.I.P) لا يمكن إرسال الطلبات إليه"}

    if not valid_jwts:
        return {"status": "error", "message": "لا توجد توكنات جاهزة حالياً"}

    with spam_lock:
        if uid in active_spams:
            return {"status": "error", "message": f"العملية جارية بالفعل على هذا الآيدي: {uid}"}

        save_to_graveyard(uid)
        stop_event = threading.Event()
        active_spams[uid] = stop_event
        
        thread = threading.Thread(target=spam_logic, args=(uid, stop_event), daemon=True)
        thread.start()
        
    return {"status": "success", "message": f"🔥 تم بدء الإرسال للآيدي: {uid}"}

@app.get("/stop_spam")
def stop_spam(uid: str = None):
    with spam_lock:
        if not uid:
            count = len(active_spams)
            for tid, event in active_spams.items():
                event.set()
            return {"status": "success", "message": f"🛑 تم إيقاف جميع العمليات ({count})"}
        else:
            if uid not in active_spams:
                return {"status": "error", "message": "الآيدي غير موجود في قائمة العمليات الحالية"}

            active_spams[uid].set()
            return {"status": "success", "message": f"🛑 تم إيقاف الإرسال للآيدي: {uid}"}

@app.get("/safe")
def protect_uid(uid: str, key: str):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="مفتاح الحماية غير صحيح")
    
    safe_uids.add(uid)
    save_safe_uids()
    
    # 
    with spam_lock:
        if uid in active_spams:
            active_spams[uid].set()
            
    return {"status": "success", "message": f"🛡️ تمت حماية الآيدي {uid} بنجاح"}

@app.get("/no_safe")
def unprotect_uid(uid: str, key: str):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="مفتاح الحماية غير صحيح")
    
    if uid in safe_uids:
        safe_uids.remove(uid)
        save_safe_uids()
        return {"status": "success", "message": f"🔓 تمت إزالة الحماية عن الآيدي {uid}"}
    
    return {"status": "error", "message": "الآيدي غير محمي مسبقاً"}

@app.get("/stats")
def get_stats():
    # 
    return {
        "active_spams_count": len(active_spams),
        "active_uids": list(active_spams.keys()),
        "protected_uids_count": len(safe_uids),
        "valid_jwts_count": len(valid_jwts)
    }

if __name__ == "__main__":
    # 
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    
