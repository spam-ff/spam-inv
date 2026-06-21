import telebot
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
import my_pb2
import output_pb2
import jwt

TOKEN = "7834904283:AAEM9mcGlrVJ3KX_PqcMNghUCQHg3HJ8lH4"  # ضع توكن البوت هنا
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

def encrypt_message(plaintext):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    padded_message = pad(plaintext, AES.block_size)
    return cipher.encrypt(padded_message)

def fetch_open_id(access_token):
    try:
        uid_url = "https://prod-api.reward.ff.garena.com/redemption/api/auth/inspect_token/"
        uid_headers = {"access-token": access_token}
        uid_res = requests.get(uid_url, headers=uid_headers)
        uid_data = uid_res.json()
        uid = uid_data.get("uid")
        if not uid:
            return None, "Failed to extract UID"

        openid_url = "https://shop2game.com/api/auth/player_id_login"
        openid_headers = {"Content-Type": "application/json"}
        payload = {"app_id": 100067, "login_id": str(uid)}
        openid_res = requests.post(openid_url, headers=openid_headers, json=payload)
        openid_data = openid_res.json()
        open_id = openid_data.get("open_id")
        if not open_id:
            return None, "Failed to extract open_id"
        return open_id, None
    except Exception as e:
        return None, f"Exception: {str(e)}"

def get_majorlogin_jwt(access_token, provided_open_id=None):
    open_id = provided_open_id
    if not open_id:
        open_id, error = fetch_open_id(access_token)
        if error:
            return None, error

    platforms = [8, 3, 4, 6]
    for platform_type in platforms:
        game_data = my_pb2.GameData()
        game_data.timestamp = "2024-12-05 18:15:32"
        game_data.game_name = "free fire"
        game_data.game_version = 1
        game_data.version_code = "1.108.3"
        game_data.os_info = "Android OS 9 / API-28"
        game_data.device_type = "Handheld"
        game_data.network_provider = "Verizon Wireless"
        game_data.connection_type = "WIFI"
        game_data.screen_width = 1280
        game_data.screen_height = 960
        game_data.dpi = "240"
        game_data.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
        game_data.total_ram = 5951
        game_data.gpu_name = "Adreno (TM) 640"
        game_data.gpu_version = "OpenGL ES 3.0"
        game_data.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
        game_data.ip_address = "172.190.111.97"
        game_data.language = "en"
        game_data.open_id = open_id
        game_data.access_token = access_token
        game_data.platform_type = platform_type
        game_data.field_99 = str(platform_type)
        game_data.field_100 = str(platform_type)

        serialized_data = game_data.SerializeToString()
        encrypted_data = encrypt_message(serialized_data)
        edata = bytes.fromhex(binascii.hexlify(encrypted_data).decode())

        try:
            response = requests.post(
                "https://loginbp.ggblueshark.com/MajorLogin",
                data=edata,
                headers={
                    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "Content-Type": "application/octet-stream"
                },
                timeout=5
            )
            if response.status_code == 200:
                try:
                    example_msg = output_pb2.Garena_420()
                    example_msg.ParseFromString(response.content)
                    data_dict = {field.name: getattr(example_msg, field.name)
                                 for field in example_msg.DESCRIPTOR.fields
                                 if field.name not in ["binary", "binary_data", "Garena420"]}
                except Exception:
                    try:
                        data_dict = response.json()
                    except ValueError:
                        continue

                if data_dict and "token" in data_dict:
                    token_value = data_dict["token"]
                    try:
                        decoded_token = jwt.decode(token_value, options={"verify_signature": False})
                    except Exception:
                        decoded_token = {}
                    return {
                        "account_id": decoded_token.get("account_id"),
                        "account_name": decoded_token.get("nickname"),
                        "open_id": open_id,
                        "access_token": access_token,
                        "platform": decoded_token.get("external_type"),
                        "region": decoded_token.get("lock_region"),
                        "status": "success",
                        "token": token_value
                    }, None
        except requests.RequestException:
            continue
    return None, "No valid platform found"

# ======= بوت تيليجرام =======
@bot.message_handler(commands=['start'])
def start_msg(message):
    text = """✨ اهلا بيك في بوت CTX TEAM ✨
⚡ استخدم /jwt <access_token> <open_id> لجلب بيانات حسابك."""
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['jwt'])
def jwt_command(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ استخدم: /jwt <access_token> [open_id]")
            return
        access_token = parts[1]
        open_id = parts[2] if len(parts) >= 3 else None
        result, error = get_majorlogin_jwt(access_token, open_id)
        if error:
            bot.send_message(message.chat.id, f"```lol```\nDEV BY ⚙️ @UXD_0\n{error}", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"✅ تم جلب البيانات:\n<pre>{result}</pre>\nDEV BY ⚙️ @UXD_0", parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f"```3spa```\nDEV BY ⚙️ @UXD_0\n{str(e)}", parse_mode='Markdown')

bot.infinity_polling()