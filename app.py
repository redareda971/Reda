#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
R32 SHADOW – Premium Garena Account Management Bot
Version: 6.2 – CLEAN & FIXED
"""

import json
import os
import random
import string
import hashlib
import urllib.parse
import logging
import sys
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple

import requests
import urllib3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8977729299:AAFZ63ksEP_Mk71fDyqbUHsVGUhM1ZudRdA"
OWNER_ID = 7943260217
KEY_PREFIX = "R32-KEY"
MAX_DEVICES_DEFAULT = 5

KEYS_FILE = "keys.json"
USERS_FILE = "users.json"
SPAM_FILE = "spam_requests.json"
BOT_STATUS_FILE = "bot_status.json"

LANG_EN = "en"
LANG_AR = "ar"

# ============================================================
# LOGGING - SILENT
# ============================================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.ERROR)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ============================================================
# BRANDING
# ============================================================

FOOTER_EN = "\n\n---\n👨‍💻 **Developer:** R32 SHADOW\n👨‍💻 **Co-Developer:** ILYASS @XHR_M\n📱 **Telegram:** @r32pro\n📢 **Channel:** https://t.me/ShadowCodee"
FOOTER_AR = "\n\n---\n👨‍💻 **المطور:** R32 SHADOW\n👨‍💻 **المطور المساعد:** ILYASS @XHR_M\n📱 **تيليجرام:** @r32pro\n📢 **القناة:** https://t.me/ShadowCodee"

def get_footer(lang: str = LANG_EN) -> str:
    return FOOTER_AR if lang == LANG_AR else FOOTER_EN

def add_footer(text: str, lang: str = LANG_EN) -> str:
    return text + get_footer(lang)

def escape_markdown(text: str) -> str:
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def safe_markdown(text: str) -> str:
    parts = re.split(r'(`[^`]+`)', text)
    result = []
    for part in parts:
        if part.startswith('`') and part.endswith('`'):
            result.append(part)
        else:
            result.append(escape_markdown(part))
    return ''.join(result)

async def safe_reply_text(update: Update, text: str, parse_mode: str = "MarkdownV2", **kwargs):
    try:
        if update.message:
            return await update.message.reply_text(text=safe_markdown(text), parse_mode=parse_mode, **kwargs)
        elif update.callback_query and update.callback_query.message:
            return await update.callback_query.message.reply_text(text=safe_markdown(text), parse_mode=parse_mode, **kwargs)
        else:
            chat_id = update.effective_chat.id if update.effective_chat else None
            if chat_id:
                return await update.get_bot().send_message(chat_id=chat_id, text=safe_markdown(text), parse_mode=parse_mode, **kwargs)
            return None
    except Exception as e:
        logger.error(f"Markdown error: {e}")
        plain_text = re.sub(r'[`*_~#]', '', text)
        try:
            if update.message:
                return await update.message.reply_text(text=plain_text, parse_mode=None, **kwargs)
            elif update.callback_query and update.callback_query.message:
                return await update.callback_query.message.reply_text(text=plain_text, parse_mode=None, **kwargs)
            else:
                chat_id = update.effective_chat.id if update.effective_chat else None
                if chat_id:
                    return await update.get_bot().send_message(chat_id=chat_id, text=plain_text, parse_mode=None, **kwargs)
                return None
        except Exception as e2:
            logger.error(f"Fallback send error: {e2}")
            return None

# ============================================================
# DATA MANAGERS
# ============================================================

class BotStatusManager:
    @staticmethod
    def load_status() -> bool:
        try:
            if os.path.exists(BOT_STATUS_FILE):
                with open(BOT_STATUS_FILE, 'r') as f:
                    return json.load(f).get("running", True)
            return True
        except:
            return True
    
    @staticmethod
    def save_status(running: bool) -> bool:
        try:
            with open(BOT_STATUS_FILE, 'w') as f:
                json.dump({"running": running, "updated_at": datetime.now().isoformat()}, f, indent=4)
            return True
        except:
            return False
    
    @staticmethod
    def is_running() -> bool:
        return BotStatusManager.load_status()

class DataManager:
    @staticmethod
    def load(filename: str, default: Any = None) -> Any:
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
            return default or {}
        except Exception as e:
            logger.error(f"Load error {filename}: {e}")
            return default or {}
    
    @staticmethod
    def save(filename: str, data: Any) -> bool:
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Save error {filename}: {e}")
            return False
    
    @classmethod
    def get_keys(cls) -> Dict:
        return cls.load(KEYS_FILE, {})
    
    @classmethod
    def save_keys(cls, keys: Dict) -> bool:
        return cls.save(KEYS_FILE, keys)
    
    @classmethod
    def get_users(cls) -> Dict:
        return cls.load(USERS_FILE, {})
    
    @classmethod
    def save_users(cls, users: Dict) -> bool:
        return cls.save(USERS_FILE, users)
    
    @classmethod
    def get_spam_requests(cls) -> Dict:
        return cls.load(SPAM_FILE, {"requests": [], "active": {}})
    
    @classmethod
    def save_spam_requests(cls, data: Dict) -> bool:
        return cls.save(SPAM_FILE, data)
    
    @classmethod
    def ensure_user(cls, user_id: int, username: str = "", first_name: str = "") -> None:
        users = cls.get_users()
        uid = str(user_id)
        if uid not in users:
            users[uid] = {
                "id": user_id, "username": username, "first_name": first_name,
                "joined_at": datetime.now().isoformat(), "keys": [], "token_history": [],
                "language": LANG_EN, "spam_active": False, "spam_pending": False,
                "is_admin": (user_id == OWNER_ID)
            }
        else:
            if username and username != users[uid].get("username"):
                users[uid]["username"] = username
            if first_name and first_name != users[uid].get("first_name"):
                users[uid]["first_name"] = first_name
            if "language" not in users[uid]:
                users[uid]["language"] = LANG_EN
            if "spam_active" not in users[uid]:
                users[uid]["spam_active"] = False
            if "spam_pending" not in users[uid]:
                users[uid]["spam_pending"] = False
            if "is_admin" not in users[uid]:
                users[uid]["is_admin"] = (user_id == OWNER_ID)
        cls.save_users(users)
    
    @classmethod
    def get_user_lang(cls, user_id: int) -> str:
        users = cls.get_users()
        uid = str(user_id)
        return users.get(uid, {}).get("language", LANG_EN)
    
    @classmethod
    def set_user_lang(cls, user_id: int, lang: str) -> bool:
        users = cls.get_users()
        uid = str(user_id)
        if uid in users:
            users[uid]["language"] = lang
            return cls.save_users(users)
        return False
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        users = cls.get_users()
        uid = str(user_id)
        return users.get(uid, {}).get("is_admin", False) or user_id == OWNER_ID

class KeyManager:
    @staticmethod
    def generate() -> str:
        return f"{KEY_PREFIX}{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
    
    @staticmethod
    def create(duration: int, unit: str, max_devices: int, owner: int) -> Dict:
        now = datetime.now()
        expires = now + (timedelta(days=duration) if unit == "days" else timedelta(hours=duration))
        return {
            "key": KeyManager.generate(), "created_at": now.isoformat(), "expires_at": expires.isoformat(),
            "max_devices": max_devices, "users": [], "owner": owner, "active": True
        }
    
    @staticmethod
    def save(key_data: Dict) -> bool:
        keys = DataManager.get_keys()
        keys[key_data["key"]] = key_data
        return DataManager.save_keys(keys)
    
    @staticmethod
    def get(key: str) -> Optional[Dict]:
        return DataManager.get_keys().get(key)
    
    @staticmethod
    def get_all() -> Dict:
        return DataManager.get_keys()
    
    @staticmethod
    def disable(key: str) -> bool:
        keys = DataManager.get_keys()
        if key in keys:
            keys[key]["active"] = False
            return DataManager.save_keys(keys)
        return False
    
    @staticmethod
    def remove_user(key: str, user_id: int) -> bool:
        keys = DataManager.get_keys()
        if key not in keys or user_id not in keys[key].get("users", []):
            return False
        keys[key]["users"] = [u for u in keys[key]["users"] if u != user_id]
        users = DataManager.get_users()
        uid = str(user_id)
        if uid in users:
            users[uid]["keys"] = [k for k in users[uid]["keys"] if k != key]
        DataManager.save_users(users)
        return DataManager.save_keys(keys)
    
    @staticmethod
    def get_users(key: str) -> List[int]:
        data = KeyManager.get(key)
        return data.get("users", []) if data else []
    
    @staticmethod
    def cleanup() -> int:
        keys = DataManager.get_keys()
        now = datetime.now()
        count = 0
        for k, v in keys.items():
            if v.get("active", True):
                try:
                    if datetime.fromisoformat(v["expires_at"]) < now:
                        v["active"] = False
                        count += 1
                except:
                    pass
        if count:
            DataManager.save_keys(keys)
        return count

class SpamManager:
    @staticmethod
    def create_request(user_id: int, eat_token: str) -> Dict:
        return {
            "id": ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)),
            "user_id": user_id, "eat_token": eat_token, "status": "pending",
            "created_at": datetime.now().isoformat(), "approved_at": None
        }
    
    @staticmethod
    def save_request(request: Dict) -> bool:
        data = DataManager.get_spam_requests()
        data["requests"] = [r for r in data["requests"] if not (r["user_id"] == request["user_id"] and r["status"] == "pending")]
        data["requests"].append(request)
        users = DataManager.get_users()
        uid = str(request["user_id"])
        if uid in users:
            users[uid]["spam_pending"] = True
            DataManager.save_users(users)
        return DataManager.save_spam_requests(data)
    
    @staticmethod
    def get_pending_requests() -> List[Dict]:
        return [r for r in DataManager.get_spam_requests().get("requests", []) if r.get("status") == "pending"]
    
    @staticmethod
    def get_request(request_id: str) -> Optional[Dict]:
        for r in DataManager.get_spam_requests().get("requests", []):
            if r.get("id") == request_id:
                return r
        return None
    
    @staticmethod
    def approve_request(request_id: str) -> bool:
        data = DataManager.get_spam_requests()
        for r in data.get("requests", []):
            if r.get("id") == request_id and r.get("status") == "pending":
                r["status"] = "approved"
                r["approved_at"] = datetime.now().isoformat()
                users = DataManager.get_users()
                uid = str(r["user_id"])
                if uid in users:
                    users[uid]["spam_active"] = True
                    users[uid]["spam_pending"] = False
                    DataManager.save_users(users)
                return DataManager.save_spam_requests(data)
        return False
    
    @staticmethod
    def reject_request(request_id: str) -> bool:
        data = DataManager.get_spam_requests()
        for r in data.get("requests", []):
            if r.get("id") == request_id and r.get("status") == "pending":
                r["status"] = "rejected"
                users = DataManager.get_users()
                uid = str(r["user_id"])
                if uid in users:
                    users[uid]["spam_pending"] = False
                    DataManager.save_users(users)
                return DataManager.save_spam_requests(data)
        return False
    
    @staticmethod
    def deactivate_spam(user_id: int) -> bool:
        users = DataManager.get_users()
        uid = str(user_id)
        if uid in users:
            users[uid]["spam_active"] = False
            return DataManager.save_users(users)
        return False
    
    @staticmethod
    def is_spam_active(user_id: int) -> bool:
        users = DataManager.get_users()
        return users.get(str(user_id), {}).get("spam_active", False)
    
    @staticmethod
    def has_pending_request(user_id: int) -> bool:
        users = DataManager.get_users()
        return users.get(str(user_id), {}).get("spam_pending", False)

def check_user_key(user_id: int) -> bool:
    if DataManager.is_admin(user_id):
        return True
    keys = DataManager.get_keys()
    now = datetime.now()
    for key, data in keys.items():
        if not data.get("active", True) or user_id not in data.get("users", []):
            continue
        try:
            if datetime.fromisoformat(data["expires_at"]) > now:
                return True
            else:
                data["active"] = False
                DataManager.save_keys(keys)
        except:
            continue
    return False

def validate_key(key: str, user_id: int) -> Tuple[bool, str]:
    keys = DataManager.get_keys()
    if key not in keys:
        return False, "Invalid key"
    data = keys[key]
    if not data.get("active", True):
        return False, "Key disabled"
    try:
        if datetime.fromisoformat(data["expires_at"]) < datetime.now():
            data["active"] = False
            DataManager.save_keys(keys)
            return False, "Key expired"
    except:
        pass
    if len(data.get("users", [])) >= data.get("max_devices", 5):
        return False, "Device limit reached"
    if user_id not in data.get("users", []):
        data["users"].append(user_id)
        DataManager.save_keys(keys)
        users = DataManager.get_users()
        uid = str(user_id)
        if uid not in users:
            users[uid] = {"keys": []}
        if key not in users[uid]["keys"]:
            users[uid]["keys"].append(key)
        DataManager.save_users(users)
        return True, "Access granted!"
    return True, "Welcome back!"

# ============================================================
# GARENA API HELPERS - CLEAN VERSION LIKE APP.PY
# ============================================================

try:
    import MajoRLogin_pb2 as mLpB
    import MajorLoginRes_pb2 as mLrPb
except ImportError:
    logger.error("Protobuf files missing!")
    mLpB = None
    mLrPb = None

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

AeSkEy = b'Yg&tc%DEuh6%Zc^8'
AeSiV = b'6oyZDr22E3ychjM%'

def enc(d):
    return AES.new(AeSkEy, AES.MODE_CBC, AeSiV).encrypt(pad(d, 16))

def dec(d):
    return unpad(AES.new(AeSkEy, AES.MODE_CBC, AeSiV).decrypt(d), 16)

PLATFORM_MAP = {
    1: "Garena", 3: "Facebook", 4: "Guest", 5: "VK",
    6: "Huawei", 7: "Apple", 8: "Google", 10: "GameCenter",
    11: "X (Twitter)", 13: "Apple ID", 28: "Line", 35: "TikTok"
}

def convert_seconds(s: int) -> str:
    if s <= 0:
        return "0s"
    d, h = divmod(s, 86400)
    h, m = divmod(h, 3600)
    m, s = divmod(m, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"

def format_response_text(text: str, title: str = "API") -> str:
    try:
        data = json.loads(text)
        rc = data.get("result")
        if rc == 0:
            return f"✅ {title}: SUCCESS"
        elif rc is not None:
            error = data.get("error", "Unknown error")
            return f"❌ {title}: FAILED (Code: {rc} | {error})"
        return f"ℹ️ {title}: Done"
    except:
        if '"result":0' in text.replace(" ", ""):
            return f"✅ {title}: SUCCESS"
        return f"❌ {title}: Failed"

def mask_email(email: str) -> str:
    if not email or '@' not in email:
        return email
    local, domain = email.split('@')
    if len(local) <= 2:
        return email
    return f"{local[0]}{'*'*(len(local)-2)}{local[-1]}@{domain}"

# ---- API Functions (exactly like app.py) ----
def get_player_info(token: str) -> Tuple[str, str, str, bool]:
    try:
        r = requests.get(
            f"https://api-otrss.garena.com/support/callback/?access_token={token}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
            allow_redirects=True,
            verify=False
        )
        qp = urllib.parse.parse_qs(urllib.parse.urlparse(r.url).query)
        if 'access_token' in qp:
            return (
                qp.get('account_id', ['Unknown'])[0],
                urllib.parse.unquote(qp.get('nickname', ['Unknown'])[0]),
                qp.get('region', ['Unknown'])[0],
                True
            )
        return "Unknown", "Unknown", "Unknown", False
    except Exception as e:
        logger.error(f"get_player_info error: {e}")
        return "Unknown", "Unknown", "Unknown", False

def get_bind_info(token: str) -> Tuple[str, str, str, int, bool]:
    try:
        r = requests.get(
            "https://100067.connect.garena.com/game/account_security/bind:get_bind_info",
            params={"app_id": "100067", "access_token": token},
            headers={"User-Agent": "GarenaMSDK/4.0.19P9"},
            timeout=15,
            verify=False
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("email", ""), data.get("email_to_be", ""), convert_seconds(data.get("request_exec_countdown", 0)), data.get("result", -1), True
        return "", "", "", -1, False
    except Exception as e:
        logger.error(f"get_bind_info error: {e}")
        return "", "", "", -1, False

def get_bind_info_raw(token: str) -> Tuple[Dict, bool]:
    try:
        r = requests.get(
            "https://100067.connect.garena.com/game/account_security/bind:get_bind_info",
            params={"app_id": "100067", "access_token": token},
            headers={"User-Agent": "GarenaMSDK/4.0.19P9"},
            timeout=15,
            verify=False
        )
        if r.status_code == 200:
            return r.json(), True
        return {}, False
    except Exception as e:
        logger.error(f"get_bind_info_raw error: {e}")
        return {}, False

def send_otp(email: str, token: str) -> Tuple[bool, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"email": email, "locale": "en_PK", "region": "PK", "app_id": "100067", "access_token": token}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Send OTP")
    except Exception as e:
        return False, f"❌ Error: {e}"

def verify_otp(email: str, token: str, otp: str) -> Tuple[bool, str, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"app_id": "100067", "access_token": token, "email": email, "otp": otp, "type": "1"}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_otp", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Verify OTP"), r.json().get("verifier_token", "")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def create_bind_request(email: str, token: str, verifier: str, sec_code: str) -> Tuple[bool, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"email": email, "app_id": "100067", "access_token": token, "verifier_token": verifier, "secondary_password": sec_code}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:create_bind_request", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Bind Request")
    except Exception as e:
        return False, f"❌ Error: {e}"

def verify_identity_otp(email: str, token: str, otp: str) -> Tuple[bool, str, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"email": email, "app_id": "100067", "access_token": token, "otp": otp}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Verify Identity"), r.json().get("identity_token", "")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def verify_identity_sec(email: str, token: str, sec_code: str) -> Tuple[bool, str, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    hashed = hashlib.sha256(sec_code.encode('utf-8')).hexdigest()
    data = {"email": email, "app_id": "100067", "access_token": token, "secondary_password": hashed}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Verify Identity"), r.json().get("identity_token", "")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def create_unbind_request(token: str, identity: str) -> Tuple[bool, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"app_id": "100067", "access_token": token, "identity_token": identity}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:create_unbind_request", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Unbind Request")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def create_rebind_request(token: str, identity: str, email: str, verifier: str) -> Tuple[bool, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"identity_token": identity, "email": email, "app_id": "100067", "verifier_token": verifier, "access_token": token}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:create_rebind_request", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Rebind Request")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def cancel_bind_request(token: str) -> Tuple[bool, str]:
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"app_id": "100067", "access_token": token}
    try:
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:cancel_request", headers=headers, data=data, timeout=15, verify=False)
        return True, format_response_text(r.text, "Cancel Request")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def eat_to_token(eat: str) -> Tuple[str, Dict]:
    token = None
    if "http" in eat or "?" in eat:
        qp = urllib.parse.parse_qs(urllib.parse.urlparse(eat).query)
        token = qp.get('eat', [None])[0]
    else:
        token = eat.strip()
    if not token:
        return "❌ No EAT token found", {}
    try:
        r = requests.get(f"https://api-otrss.garena.com/support/callback/?access_token={token}", allow_redirects=True, timeout=15, verify=False)
        qp = urllib.parse.parse_qs(urllib.parse.urlparse(r.url).query)
        if 'access_token' in qp:
            return "", {
                "access_token": qp['access_token'][0],
                "nickname": urllib.parse.unquote(qp.get('nickname', ['Unknown'])[0]),
                "account_id": qp.get('account_id', ['Unknown'])[0],
                "region": qp.get('region', ['Unknown'])[0]
            }
        return "❌ Token expired or invalid", {}
    except Exception as e:
        return f"❌ Error: {e}", {}

def do_revoke(token: str) -> Tuple[str, Dict]:
    valid = False
    nickname = account_id = region = "Unknown"
    try:
        r = requests.get(f"https://api-otrss.garena.com/support/callback/?access_token={token}", headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True, timeout=15, verify=False)
        qp = urllib.parse.parse_qs(urllib.parse.urlparse(r.url).query)
        if 'access_token' in qp:
            valid = True
            nickname = urllib.parse.unquote(qp.get('nickname', ['Unknown'])[0])
            account_id = qp.get('account_id', ['Unknown'])[0]
            region = qp.get('region', ['Unknown'])[0]
    except:
        pass
    if not valid:
        return "❌ Token invalid or expired", {}
    try:
        r = requests.get(f"https://100067.connect.garena.com/oauth/logout?access_token={token}&refresh_token=1380dcb63ab3a077dc05bdf0b25ba4497c403a5b4eae96d7203010eafa6c83a8", timeout=15, verify=False)
        if r.status_code == 200 and "error" not in r.text.lower():
            return "", {"nickname": nickname, "account_id": account_id, "region": region, "status": "revoked"}
        return "❌ Failed to revoke token", {}
    except Exception as e:
        return f"❌ Error: {e}", {}

def check_bound(token: str) -> Tuple[bool, str, List, List]:
    try:
        r = requests.get("https://100067.connect.garena.com/bind/app/platform/info/get", params={"access_token": token}, headers={"User-Agent": "GarenaMSDK/4.0.19P9"}, timeout=10, verify=False)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}", [], []
        data = r.json()
        return True, "", data.get("bounded_accounts", []), data.get("available_platforms", [])
    except Exception as e:
        return False, f"Error: {e}", [], []

def access_to_jwt_api(token: str) -> Tuple[bool, str]:
    try:
        r = requests.get(f"https://acesstojwt-sigma.vercel.app/token?access_token={token}", timeout=15, verify=False)
        if r.status_code == 200:
            raw = r.text.strip()
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and "token" in data:
                    return True, data["token"]
            except:
                pass
            if raw.startswith("ey") and "." in raw:
                return True, raw
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"Error: {e}"

def ban_account_api(token: str) -> Tuple[bool, str]:
    try:
        r = requests.get(f"https://toji-api-jwt.vercel.app/ban?token={token}", timeout=20, verify=False)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, f"Error: {e}"

# ---- Login History (simplified) ----
def build_majorlogin(tok, open_id, p_type):
    if mLpB is None:
        return None
    m = mLpB.MajorLogin()
    m.event_time = str(datetime.now())[:-7]
    m.game_name = "free fire"
    m.platform_id = p_type
    m.client_version = "1.120.1"
    m.system_software = "Android OS 9 / API-28"
    m.system_hardware = "Handheld"
    m.telecom_operator = "Verizon"
    m.network_type = "WIFI"
    m.screen_width = 1920
    m.screen_height = 1080
    m.screen_dpi = "280"
    m.processor_details = "ARM64 FP ASIMD AES VMH | 2865 | 4"
    m.memory = 3003
    m.gpu_renderer = "Adreno (TM) 640"
    m.gpu_version = "OpenGL ES 3.1 v1.46"
    m.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
    m.client_ip = "223.191.51.89"
    m.language = "en"
    m.open_id = open_id
    m.open_id_type = str(p_type)
    m.device_type = "Handheld"
    m.access_token = tok
    m.platform_sdk_id = 1
    m.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    m.login_by = 3
    m.channel_type = 3
    m.cpu_type = 2
    m.cpu_architecture = "64"
    m.client_version_code = "2019118695"
    m.login_open_id_type = p_type
    m.origin_platform_type = str(p_type)
    m.primary_platform_type = str(p_type)
    return enc(m.SerializeToString())

def read_varint(data, offset):
    res, shift = 0, 0
    while True:
        if offset >= len(data): break
        b = data[offset]; offset += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return res, offset

def parse_record(data):
    rec, offset = {}, 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        wt, f = tag & 7, tag >> 3
        if wt == 0:
            val, offset = read_varint(data, offset)
            if f == 1: rec['ts'] = val
            elif f == 2: rec['ram'] = val
        elif wt == 2:
            length, offset = read_varint(data, offset)
            val = data[offset:offset+length]; offset += length
            if f == 3: rec['dev'] = val.decode(errors='ignore')
            elif f == 4: rec['arch'] = val.decode(errors='ignore')
        else: break
    return rec

def parse_history_protobuf(data):
    records, offset = [], 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        wt, f = tag & 7, tag >> 3
        if wt == 0:
            val, offset = read_varint(data, offset)
        elif wt == 2:
            length, offset = read_varint(data, offset)
            val = data[offset:offset+length]; offset += length
            if f == 1:
                records.append(parse_record(val))
        else: break
    return records

def get_login_history(token: str) -> Tuple[str, List[Dict]]:
    if mLpB is None or mLrPb is None:
        return "Protobuf libraries missing.", []
    jwt_token = None
    if token.startswith("ey") and "." in token:
        jwt_token = token
    else:
        oId = None
        try:
            r = requests.get(f"https://100067.connect.garena.com/oauth/token/inspect?token={token}", headers={"User-Agent": "Mozilla/5.0"}, timeout=5, verify=False)
            if r.status_code == 200:
                oId = r.json().get("open_id")
        except: pass
        if not oId:
            try:
                uid_res = requests.get("https://prod-api.reward.ff.garena.com/redemption/api/auth/inspect_token/", headers={"access-token": token, "user-agent": "Mozilla/5.0"}, verify=False, timeout=5)
                if uid_res.status_code == 200:
                    uid = uid_res.json().get("uid")
                    if uid:
                        openid_res = requests.post("https://topup.pk/api/auth/player_id_login", json={"app_id": 100067, "login_id": str(uid)}, verify=False, timeout=5)
                        if openid_res.status_code == 200:
                            oId = openid_res.json().get("open_id")
            except: pass
        if not oId:
            return "Failed to extract Open ID.", []
        platforms = [8, 3, 4, 6]
        for p_type in platforms:
            pl = build_majorlogin(token, oId, p_type)
            if pl is None: continue
            try:
                r = requests.post("https://loginbp.ggpolarbear.com/MajorLogin", 
                    headers={"User-Agent": "Dalvik/2.1.0", "Content-Type": "application/octet-stream", "X-GA": "v1 1", "X-Unity-Version": "2018.4.11f1", "ReleaseVersion": "OB54"},
                    data=pl, timeout=10, verify=False)
                if r.status_code == 200:
                    res = mLrPb.MajorLoginRes()
                    try: res.ParseFromString(dec(r.content))
                    except: res.ParseFromString(r.content)
                    if res.token:
                        jwt_token = res.token
                        break
            except: continue
        if not jwt_token:
            return "MajorLogin failed.", []
    try:
        r = requests.post("https://client.ind.freefiremobile.com/GetLoginHistory",
            headers={"Authorization": f"Bearer {jwt_token}", "X-Unity-Version": "2018.4.11f1", "X-GA": "v1 1", "ReleaseVersion": "OB54", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Dalvik/2.1.0"},
            data=enc(b""), timeout=15, verify=False)
        if r.status_code != 200:
            return f"HTTP {r.status_code}", []
        try: d = dec(r.content)
        except: d = r.content
        return "", parse_history_protobuf(d)
    except Exception as e:
        return f"Error: {e}", []

# ============================================================
# KEYBOARDS
# ============================================================

def get_user_keyboard(lang: str = LANG_EN) -> ReplyKeyboardMarkup:
    if lang == LANG_AR:
        buttons = [
            ["🟢 إضافة إيميل", "🔍 التحقق من الإيميل"],
            ["🌐 المنصات المرتبطة", "❌ إلغاء ربط الإيميل"],
            ["🔓 فك الربط", "🔄 تغيير الإيميل"],
            ["📋 تفاصيل التوكن", "🔗 تحويل EAT"],
            ["🔴 إلغاء التوكن", "📝 سجل الدخول"],
            ["🌍 تغيير اللغة", "🔄 طلب سبام"],
            ["🔑 تحويل إلى JWT", "🚫 حظر الحساب"],
            ["ℹ️ معلومات المطور", "❓ المساعدة"]
        ]
    else:
        buttons = [
            ["🟢 Add Recovery Email", "🔍 Check Recovery Email"],
            ["🌐 Check Platform", "❌ Cancel Recovery Email"],
            ["🔓 Unbind Email", "🔄 Change Bind Email"],
            ["📋 Get Token Details", "🔗 Eat Token Website"],
            ["🔴 Revoke Access Token", "📝 Login History"],
            ["🌍 Change Language", "🔄 Spam Login Request"],
            ["🔑 Access Token to JWT", "🚫 Ban Account"],
            ["ℹ️ Owner Details", "❓ Help"]
        ]
    return ReplyKeyboardMarkup([[KeyboardButton(b) for b in row] for row in buttons], resize_keyboard=True)

def get_admin_keyboard(lang: str = LANG_EN) -> ReplyKeyboardMarkup:
    if lang == LANG_AR:
        buttons = [
            ["🟢 إنشاء مفتاح", "🔴 تعطيل مفتاح"],
            ["👤 طرد مستخدم", "📊 إحصائيات"],
            ["📋 قائمة المفاتيح", "📢 رسالة جماعية"],
            ["📢 رسالة لمستخدم", "📋 طلبات السبام"],
            ["🔄 إعادة تعيين البوت", "🔴 إغلاق البوت"],
            ["🟢 تشغيل البوت", "❓ المساعدة"],
            ["ℹ️ معلومات المطور", "📋 عرض القائمة"]
        ]
    else:
        buttons = [
            ["🟢 Create Key", "🔴 Disable Key"],
            ["👤 Kick User", "📊 Statistics"],
            ["📋 List Keys", "📢 Broadcast Message"],
            ["📢 Send to User", "📋 Spam Requests"],
            ["🔄 Reset Bot", "🔴 Stop Bot"],
            ["🟢 Start Bot", "❓ Help"],
            ["ℹ️ Owner Details", "📋 Show Menu"]
        ]
    return ReplyKeyboardMarkup([[KeyboardButton(b) for b in row] for row in buttons], resize_keyboard=True)

def get_method_keyboard(lang: str = LANG_EN) -> ReplyKeyboardMarkup:
    if lang == LANG_AR:
        return ReplyKeyboardMarkup([["📩 كود التحقق", "🔐 كود الأمان"], ["↩️ العودة للقائمة"]], resize_keyboard=True)
    return ReplyKeyboardMarkup([["📩 OTP", "🔐 Security Code"], ["↩️ Back to Menu"]], resize_keyboard=True)

# ============================================================
# BOT HANDLERS - MAIN FUNCTIONS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    DataManager.ensure_user(user_id, user.username or "", user.first_name or "")
    is_admin = DataManager.is_admin(user_id)
    
    if check_user_key(user_id) or is_admin:
        lang = DataManager.get_user_lang(user_id)
        msg = f"👑 **Admin Panel**\n\n👤 ID: {user_id}" if is_admin else f"🚀 R32 SHADOW\n\n👤 User: {user_id}"
        await safe_reply_text(update, add_footer(msg, lang), reply_markup=get_admin_keyboard(lang) if is_admin else get_user_keyboard(lang))
        return
    
    context.user_data["state"] = "awaiting_key"
    await update.message.reply_text("🔐 R32 SHADOW\n\nPlease enter your activation key:\n\nR32-KEYXXXXXXXXXX", parse_mode=None)

async def show_menu(update: Update, user_id: int, context: ContextTypes.DEFAULT_TYPE = None):
    lang = DataManager.get_user_lang(user_id)
    is_admin = DataManager.is_admin(user_id)
    text = f"👑 **Admin Panel**\n\n👤 ID: {user_id}" if is_admin else f"🚀 R32 SHADOW\n\n👤 User: {user_id}"
    await safe_reply_text(update, add_footer(text, lang), reply_markup=get_admin_keyboard(lang) if is_admin else get_user_keyboard(lang))

async def owner_details(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = LANG_EN):
    await safe_reply_text(update, add_footer(f"""
👨‍💻 **Developer Information** (v6.2)

👨‍💻 **Developer:** R32 SHADOW
👨‍💻 **Co-Developer:** ILYASS @XHR_M
📱 **Telegram:** @r32pro
📢 **Channel:** https://t.me/ShadowCodee

All Garena APIs are now fully functional.
""", lang))

# ============================================================
# MAIN TEXT HANDLER
# ============================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    state = context.user_data.get("state")
    text = update.message.text.strip()
    lang = DataManager.get_user_lang(user_id)
    is_admin = DataManager.is_admin(user_id)
    
    # Check bot status
    if not BotStatusManager.is_running() and not is_admin:
        await update.message.reply_text("🔴 Bot is stopped." if lang == LANG_EN else "🔴 البوت متوقف.", parse_mode=None)
        return
    
    # Key input
    if state == "awaiting_key":
        if is_admin:
            context.user_data["state"] = None
            await update.message.reply_text("✅ Admin access granted!", parse_mode=None)
            await show_menu(update, user_id, context)
            return
        is_valid, msg = validate_key(text, user_id)
        if is_valid:
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ Access Granted!\n\n{msg}", parse_mode=None)
            await show_menu(update, user_id, context)
        else:
            await update.message.reply_text(f"❌ {msg}\n\nContact @r32pro", parse_mode=None)
        return
    
    if not check_user_key(user_id) and not is_admin:
        await update.message.reply_text("🔐 Use /start to login.", parse_mode=None)
        return
    
    # ============================================================
    # ADMIN COMMANDS
    # ============================================================
    if is_admin:
        if text in ["📋 Show Menu", "📋 عرض القائمة"]:
            await show_menu(update, user_id, context)
            return
        
        if text in ["ℹ️ Owner Details", "ℹ️ معلومات المطور"]:
            await owner_details(update, context, lang)
            return
        
        if text in ["🔴 Stop Bot", "🔴 إغلاق البوت"]:
            BotStatusManager.save_status(False)
            await update.message.reply_text("🔴 Bot stopped." if lang == LANG_EN else "🔴 تم إيقاف البوت.", reply_markup=get_admin_keyboard(lang), parse_mode=None)
            return
        
        if text in ["🟢 Start Bot", "🟢 تشغيل البوت"]:
            BotStatusManager.save_status(True)
            await update.message.reply_text("🟢 Bot started!" if lang == LANG_EN else "🟢 تم تشغيل البوت!", reply_markup=get_admin_keyboard(lang), parse_mode=None)
            return
        
        if text in ["🟢 Create Key", "🟢 إنشاء مفتاح"]:
            context.user_data["state"] = "create_duration"
            await update.message.reply_text("🟢 Create Key\n\nEnter duration (e.g., 24 hours or 7 days):" if lang == LANG_EN else "🟢 إنشاء مفتاح\n\nأدخل المدة:", parse_mode=None)
            return
        
        if state == "create_duration":
            try:
                parts = text.split()
                if len(parts) != 2: raise ValueError("Format: <number> <unit>")
                value, unit = int(parts[0]), parts[1].lower()
                if unit in ["hour", "hours", "hr", "h"]: unit = "hours"
                elif unit in ["day", "days", "d"]: unit = "days"
                else: raise ValueError("Use 'hours' or 'days'")
                context.user_data["duration"], context.user_data["unit"], context.user_data["state"] = value, unit, "create_devices"
                await update.message.reply_text(f"✅ {value} {unit}\n\nEnter max devices (default {MAX_DEVICES_DEFAULT}):" if lang == LANG_EN else f"✅ {value} {unit}\n\nأدخل عدد الأجهزة:", parse_mode=None)
            except Exception as e:
                await update.message.reply_text(f"❌ {e}\n\nUse: 24 hours or 7 days", parse_mode=None)
            return
        
        if state == "create_devices":
            try:
                max_dev = int(text) if text.strip() else MAX_DEVICES_DEFAULT
                duration, unit = context.user_data.get("duration", 24), context.user_data.get("unit", "hours")
                key_data = KeyManager.create(duration, unit, max_dev, user_id)
                KeyManager.save(key_data)
                context.user_data["state"] = None
                await update.message.reply_text(f"✅ Key Created!\n\n🔑 {key_data['key']}\n⏰ {duration} {unit}\n👥 {max_dev} devices", reply_markup=get_admin_keyboard(lang), parse_mode=None)
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}", parse_mode=None)
            return
        
        if text in ["🔴 Disable Key", "🔴 تعطيل مفتاح"]:
            context.user_data["state"] = "disable_key"
            await update.message.reply_text("🔴 Disable Key\n\nEnter key:" if lang == LANG_EN else "🔴 تعطيل مفتاح\n\nأدخل المفتاح:", parse_mode=None)
            return
        
        if state == "disable_key":
            if KeyManager.disable(text):
                await update.message.reply_text(f"✅ Key {text} disabled." if lang == LANG_EN else f"✅ تم تعطيل {text}.", reply_markup=get_admin_keyboard(lang), parse_mode=None)
            else:
                await update.message.reply_text("❌ Key not found." if lang == LANG_EN else "❌ غير موجود.", reply_markup=get_admin_keyboard(lang))
            context.user_data["state"] = None
            return
        
        if text in ["👤 Kick User", "👤 طرد مستخدم"]:
            context.user_data["state"] = "kick_key"
            await update.message.reply_text("👤 Kick User\n\nEnter key:" if lang == LANG_EN else "👤 طرد مستخدم\n\nأدخل المفتاح:", parse_mode=None)
            return
        
        if state == "kick_key":
            users = KeyManager.get_users(text)
            if not users:
                await update.message.reply_text(f"📭 No users for {text}", reply_markup=get_admin_keyboard(lang), parse_mode=None)
                context.user_data["state"] = None
                return
            context.user_data["kick_key"] = text
            context.user_data["state"] = "kick_user"
            await update.message.reply_text(f"👤 Kick User\n\n🔑 Key: {text}\n👥 Users: {', '.join(map(str, users))}\n\nEnter user ID:", parse_mode=None)
            return
        
        if state == "kick_user":
            try:
                uid = int(text)
                if KeyManager.remove_user(context.user_data.get("kick_key"), uid):
                    await update.message.reply_text(f"✅ User {uid} kicked.", reply_markup=get_admin_keyboard(lang), parse_mode=None)
                else:
                    await update.message.reply_text("❌ Failed.", reply_markup=get_admin_keyboard(lang))
            except ValueError:
                await update.message.reply_text("❌ Invalid ID.", reply_markup=get_admin_keyboard(lang))
            context.user_data["state"] = None
            return
        
        if text in ["📊 Statistics", "📊 إحصائيات"]:
            keys = DataManager.get_keys()
            users = DataManager.get_users()
            await update.message.reply_text(
                f"📊 Statistics\n\n🔑 Keys: {len(keys)}\n🟢 Active: {sum(1 for k in keys.values() if k.get('active', True))}\n👥 Users: {len(users)}\n📱 Devices: {sum(len(k.get('users', [])) for k in keys.values())}\n📋 Pending Spam: {len(SpamManager.get_pending_requests())}\n📌 Bot: {'🟢 Running' if BotStatusManager.is_running() else '🔴 Stopped'}",
                parse_mode=None
            )
            return
        
        if text in ["📋 List Keys", "📋 قائمة المفاتيح"]:
            keys = KeyManager.get_all()
            if not keys:
                await update.message.reply_text("📭 No keys.", parse_mode=None)
                return
            msg = "📋 Keys\n"
            for k, v in list(keys.items())[:20]:
                msg += f"• {k} ({len(v.get('users', []))}/{v.get('max_devices', 5)}) {'✅' if v.get('active') else '❌'}\n"
            await update.message.reply_text(msg, reply_markup=get_admin_keyboard(lang), parse_mode=None)
            return
        
        if text in ["📢 Broadcast Message", "📢 رسالة جماعية"]:
            context.user_data["state"] = "broadcast"
            await update.message.reply_text("📢 Broadcast\n\nSend message:", parse_mode=None)
            return
        
        if state == "broadcast":
            users = DataManager.get_users()
            sent = 0
            for uid in users:
                try:
                    await context.bot.send_message(chat_id=int(uid), text=f"📢 Announcement\n\n{text}\n\n— R32 SHADOW")
                    sent += 1
                    await asyncio.sleep(0.05)
                except: pass
            await update.message.reply_text(f"✅ Sent to {sent}/{len(users)} users.", reply_markup=get_admin_keyboard(lang), parse_mode=None)
            context.user_data["state"] = None
            return
        
        if text in ["📢 Send to User", "📢 رسالة لمستخدم"]:
            context.user_data["state"] = "send_to_user_id"
            await update.message.reply_text("📢 Send to User\n\nEnter user ID:", parse_mode=None)
            return
        
        if state == "send_to_user_id":
            try:
                context.user_data["send_target"] = int(text)
                context.user_data["state"] = "send_to_user_msg"
                await update.message.reply_text(f"Target: {text}\n\nEnter message:", parse_mode=None)
            except ValueError:
                await update.message.reply_text("❌ Invalid ID.", reply_markup=get_admin_keyboard(lang))
                context.user_data["state"] = None
            return
        
        if state == "send_to_user_msg":
            try:
                await context.bot.send_message(chat_id=context.user_data.get("send_target"), text=f"📢 Admin Message\n\n{text}")
                await update.message.reply_text("✅ Sent!", reply_markup=get_admin_keyboard(lang), parse_mode=None)
            except Exception as e:
                await update.message.reply_text(f"❌ Failed: {e}", reply_markup=get_admin_keyboard(lang))
            context.user_data["state"] = None
            return
        
        if text in ["📋 Spam Requests", "📋 طلبات السبام"]:
            pending = SpamManager.get_pending_requests()
            if not pending:
                await update.message.reply_text("📭 No pending requests.", reply_markup=get_admin_keyboard(lang), parse_mode=None)
                return
            keyboard = []
            for req in pending:
                keyboard.append([InlineKeyboardButton(f"✅ {req['user_id']}", callback_data=f"spam_approve_{req['id']}"), InlineKeyboardButton("❌ Reject", callback_data=f"spam_reject_{req['id']}")])
            await update.message.reply_text(f"📋 Pending: {len(pending)}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=None)
            return
        
        if text in ["🔄 Reset Bot", "🔄 إعادة تعيين البوت"]:
            keyboard = ReplyKeyboardMarkup([["✅ Yes", "❌ No"]], resize_keyboard=True)
            context.user_data["state"] = "reset_confirm"
            await update.message.reply_text("⚠️ Delete ALL data?\n\nAre you sure?", reply_markup=keyboard, parse_mode=None)
            return
        
        if state == "reset_confirm":
            if text == "✅ Yes":
                DataManager.save_keys({})
                DataManager.save_users({})
                DataManager.save_spam_requests({"requests": [], "active": {}})
                await update.message.reply_text("✅ Reset complete!", reply_markup=get_admin_keyboard(lang), parse_mode=None)
            else:
                await update.message.reply_text("❌ Cancelled.", reply_markup=get_admin_keyboard(lang))
            context.user_data["state"] = None
            return
        
        if text in ["❓ Help", "❓ المساعدة"]:
            await update.message.reply_text("""
📚 Admin Help

🟢 Create Key – generate new key
🔴 Disable Key – revoke key
👤 Kick User – remove user from key
📊 Statistics – view bot stats
📋 List Keys – see all keys
📢 Broadcast – send to all users
📢 Send to User – send to specific user
📋 Spam Requests – manage spam
🔄 Reset Bot – wipe all data
🔴 Stop Bot – stop bot
🟢 Start Bot – start bot
ℹ️ Owner Details – developer info
            """, parse_mode=None)
            return
    
    # ============================================================
    # USER COMMANDS
    # ============================================================
    
    if text in ["ℹ️ Owner Details", "ℹ️ معلومات المطور"]:
        await owner_details(update, context, lang)
        return
    
    if text in ["❓ Help", "❓ المساعدة"]:
        await update.message.reply_text("""
📚 R32 SHADOW Help

🟢 Add Recovery Email – bind email
🔍 Check Recovery Email – view status
🌐 Check Platform – view platforms
❌ Cancel Recovery Email – cancel pending
🔓 Unbind Email – remove email
🔄 Change Bind Email – change email
📋 Get Token Details – view token info
🔗 Eat Token Website – convert EAT
🔴 Revoke Access Token – invalidate token
📝 Login History – view history
🌍 Change Language – switch language
🔄 Spam Login Request – request spam
🔑 Access Token to JWT – convert to JWT
🚫 Ban Account – ban account
ℹ️ Owner Details – developer info
        """, parse_mode=None)
        return
    
    if text in ["🌍 Change Language", "🌍 تغيير اللغة"]:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")], [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")]])
        await update.message.reply_text("🌍 Select language:", reply_markup=keyboard, parse_mode=None)
        return
    
    # ---- Add Recovery Email ----
    if text in ["🟢 Add Recovery Email", "🟢 إضافة إيميل"]:
        context.user_data["action"] = "add_recovery"
        context.user_data["state"] = "add_recovery_token"
        await safe_reply_text(update, "🟢 Add Recovery Email\n\nStep 1/5: Enter Access Token" if lang == LANG_EN else "🟢 إضافة إيميل\n\nالخطوة 1/5: أدخل التوكن")
        return
    
    if state == "add_recovery_token" and context.user_data.get("action") == "add_recovery":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch info. Token may be invalid.")
            context.user_data["state"] = None
            return
        if email:
            await safe_reply_text(update, f"❌ Account already has email: {mask_email(email)}\n\nUse 'Change Bind Email' or 'Unbind Email'.")
            context.user_data["state"] = None
            return
        if pending:
            await safe_reply_text(update, f"ℹ️ Pending: {pending}\nCountdown: {countdown}\n\nPlease wait or cancel first.")
            context.user_data["state"] = None
            return
        context.user_data["add_token"] = token
        context.user_data["state"] = "add_recovery_email"
        await safe_reply_text(update, "Step 2/5: Enter email address:" if lang == LANG_EN else "الخطوة 2/5: أدخل الإيميل:")
        return
    
    if state == "add_recovery_email" and context.user_data.get("action") == "add_recovery":
        email = text
        if '@' not in email:
            await safe_reply_text(update, "❌ Invalid email.")
            return
        context.user_data["add_email"] = email
        token = context.user_data.get("add_token")
        context.user_data["state"] = "add_recovery_otp"
        success, result = send_otp(email, token)
        await safe_reply_text(update, f"Step 3/5: OTP sent to {email}\n\n{result}\n\nEnter OTP:" if lang == LANG_EN else f"الخطوة 3/5: تم إرسال الكود إلى {email}\n\n{result}\n\nأدخل الكود:")
        return
    
    if state == "add_recovery_otp" and context.user_data.get("action") == "add_recovery":
        otp = text
        email = context.user_data.get("add_email")
        token = context.user_data.get("add_token")
        success, result, verifier = verify_otp(email, token, otp)
        if not success or not verifier:
            await safe_reply_text(update, f"❌ OTP Failed!\n\n{result}")
            context.user_data["state"] = None
            return
        context.user_data["add_verifier"] = verifier
        context.user_data["state"] = "add_recovery_code"
        await safe_reply_text(update, f"✅ OTP Verified!\n\n{result}\n\nStep 4/5: Set 6-digit security code:" if lang == LANG_EN else f"✅ تم التحقق!\n\n{result}\n\nالخطوة 4/5: أدخل كود أمان 6 أرقام:")
        return
    
    if state == "add_recovery_code" and context.user_data.get("action") == "add_recovery":
        sec_code = text
        if len(sec_code) != 6 or not sec_code.isdigit():
            await safe_reply_text(update, "❌ Must be 6 digits.")
            return
        email = context.user_data.get("add_email")
        token = context.user_data.get("add_token")
        verifier = context.user_data.get("add_verifier")
        success, result = create_bind_request(email, token, verifier, sec_code)
        context.user_data["state"] = None
        await safe_reply_text(update, f"Step 5/5: {result}", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Check Recovery Email ----
    if text in ["🔍 Check Recovery Email", "🔍 التحقق من الإيميل"]:
        context.user_data["action"] = "check_recovery"
        context.user_data["state"] = "check_recovery_token"
        await safe_reply_text(update, "🔍 Check Recovery Email\n\nEnter Access Token:" if lang == LANG_EN else "🔍 التحقق من الإيميل\n\nأدخل التوكن:")
        return
    
    if state == "check_recovery_token" and context.user_data.get("action") == "check_recovery":
        token = text
        bind_data, success = get_bind_info_raw(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch info.")
            context.user_data["state"] = None
            return
        email = bind_data.get("email", "")
        pending = bind_data.get("email_to_be", "")
        countdown = convert_seconds(bind_data.get("request_exec_countdown", 0))
        account_id, nickname, region, valid = get_player_info(token)
        msg = f"""📋 **Account Info**

👤 **Nickname:** {nickname}
🆔 **ID:** {account_id}
🌍 **Region:** {region}

🔐 **Email:**
• Current: {mask_email(email) if email else 'None'}
• Pending: {pending if pending else 'None'}
• Countdown: {countdown if pending else 'N/A'}
• Verified: {'✅' if bind_data.get('email_verified') == 1 else '❌' if email else 'N/A'}
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Check Platform ----
    if text in ["🌐 Check Platform", "🌐 المنصات المرتبطة"]:
        context.user_data["action"] = "check_platform"
        context.user_data["state"] = "check_platform_token"
        await safe_reply_text(update, "🌐 Check Platform\n\nEnter Access Token:" if lang == LANG_EN else "🌐 المنصات\n\nأدخل التوكن:")
        return
    
    if state == "check_platform_token" and context.user_data.get("action") == "check_platform":
        token = text
        success, error, bounded, available = check_bound(token)
        if not success:
            await safe_reply_text(update, f"❌ Failed: {error}")
            context.user_data["state"] = None
            return
        bounded_names = [PLATFORM_MAP.get(p, f"Unknown ({p})") for p in bounded]
        available_names = [PLATFORM_MAP.get(p, f"Unknown ({p})") for p in available]
        msg = f"""🌐 **Platforms**

🔗 **Bound:** {', '.join(bounded_names) if bounded_names else 'None'}

📋 **Available:** {', '.join(available_names) if available_names else 'None'}
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Cancel Recovery Email ----
    if text in ["❌ Cancel Recovery Email", "❌ إلغاء ربط الإيميل"]:
        context.user_data["action"] = "cancel_recovery"
        context.user_data["state"] = "cancel_recovery_token"
        await safe_reply_text(update, "❌ Cancel Recovery Email\n\nEnter Access Token:" if lang == LANG_EN else "❌ إلغاء ربط الإيميل\n\nأدخل التوكن:")
        return
    
    if state == "cancel_recovery_token" and context.user_data.get("action") == "cancel_recovery":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch info.")
            context.user_data["state"] = None
            return
        if not pending:
            await safe_reply_text(update, "ℹ️ No pending request to cancel.")
            context.user_data["state"] = None
            return
        success, result = cancel_bind_request(token)
        await safe_reply_text(update, f"❌ Cancel Request\n\n{result}")
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Unbind Email ----
    if text in ["🔓 Unbind Email", "🔓 فك الربط"]:
        context.user_data["action"] = "unbind"
        context.user_data["state"] = "unbind_token"
        await safe_reply_text(update, "🔓 Unbind Email\n\nStep 1/3: Enter Access Token:" if lang == LANG_EN else "🔓 فك الربط\n\nالخطوة 1/3: أدخل التوكن:")
        return
    
    if state == "unbind_token" and context.user_data.get("action") == "unbind":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch info.")
            context.user_data["state"] = None
            return
        if not email:
            await safe_reply_text(update, "❌ No email bound.")
            context.user_data["state"] = None
            return
        context.user_data["unbind_token"] = token
        context.user_data["unbind_email"] = email
        context.user_data["state"] = "unbind_method"
        await safe_reply_text(update, f"🔓 Unbind Email\n\nCurrent: {mask_email(email)}\n\nSelect method:", reply_markup=get_method_keyboard(lang))
        return
    
    if state == "unbind_method" and context.user_data.get("action") == "unbind":
        if text in ["📩 OTP", "📩 كود التحقق"]:
            context.user_data["unbind_method"] = "otp"
            context.user_data["state"] = "unbind_otp"
            email = context.user_data.get("unbind_email")
            token = context.user_data.get("unbind_token")
            success, result = send_otp(email, token)
            await safe_reply_text(update, f"Step 2/3: OTP sent\n\n{result}\n\nEnter OTP:")
        elif text in ["🔐 Security Code", "🔐 كود الأمان"]:
            context.user_data["unbind_method"] = "sec"
            context.user_data["state"] = "unbind_sec"
            await safe_reply_text(update, "Step 2/3: Enter 6-digit security code:" if lang == LANG_EN else "الخطوة 2/3: أدخل كود الأمان:")
        elif text in ["↩️ Back to Menu", "↩️ العودة للقائمة"]:
            context.user_data["state"] = None
            await show_menu(update, user_id, context)
        else:
            await safe_reply_text(update, "Please select a valid option.", reply_markup=get_method_keyboard(lang))
        return
    
    if state == "unbind_otp" and context.user_data.get("action") == "unbind":
        otp = text
        email = context.user_data.get("unbind_email")
        token = context.user_data.get("unbind_token")
        success, result, identity = verify_identity_otp(email, token, otp)
        if not success or not identity:
            await safe_reply_text(update, f"❌ Failed!\n\n{result}")
            context.user_data["state"] = None
            return
        success, result = create_unbind_request(token, identity)
        context.user_data["state"] = None
        await safe_reply_text(update, f"Step 3/3: {result}", reply_markup=get_user_keyboard(lang))
        return
    
    if state == "unbind_sec" and context.user_data.get("action") == "unbind":
        sec_code = text
        if len(sec_code) != 6 or not sec_code.isdigit():
            await safe_reply_text(update, "❌ Must be 6 digits.")
            return
        email = context.user_data.get("unbind_email")
        token = context.user_data.get("unbind_token")
        success, result, identity = verify_identity_sec(email, token, sec_code)
        if not success or not identity:
            await safe_reply_text(update, f"❌ Failed!\n\n{result}")
            context.user_data["state"] = None
            return
        success, result = create_unbind_request(token, identity)
        context.user_data["state"] = None
        await safe_reply_text(update, f"Step 3/3: {result}", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Change Bind Email ----
    if text in ["🔄 Change Bind Email", "🔄 تغيير الإيميل"]:
        context.user_data["action"] = "change"
        context.user_data["state"] = "change_token"
        await safe_reply_text(update, "🔄 Change Bind Email\n\nStep 1/5: Enter Access Token:" if lang == LANG_EN else "🔄 تغيير الإيميل\n\nالخطوة 1/5: أدخل التوكن:")
        return
    
    if state == "change_token" and context.user_data.get("action") == "change":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch info.")
            context.user_data["state"] = None
            return
        if not email:
            await safe_reply_text(update, "❌ No email bound. Use 'Add Recovery Email'.")
            context.user_data["state"] = None
            return
        context.user_data["change_token"] = token
        context.user_data["change_old_email"] = email
        context.user_data["state"] = "change_method"
        await safe_reply_text(update, f"🔄 Change Bind Email\n\nCurrent: {mask_email(email)}\n\nSelect method:", reply_markup=get_method_keyboard(lang))
        return
    
    if state == "change_method" and context.user_data.get("action") == "change":
        if text in ["📩 OTP", "📩 كود التحقق"]:
            context.user_data["change_method"] = "otp"
            context.user_data["state"] = "change_old_otp"
            email = context.user_data.get("change_old_email")
            token = context.user_data.get("change_token")
            success, result = send_otp(email, token)
            await safe_reply_text(update, f"Step 2/5: OTP sent\n\n{result}\n\nEnter OTP:")
        elif text in ["🔐 Security Code", "🔐 كود الأمان"]:
            context.user_data["change_method"] = "sec"
            context.user_data["state"] = "change_old_sec"
            await safe_reply_text(update, "Step 2/5: Enter 6-digit security code:" if lang == LANG_EN else "الخطوة 2/5: أدخل كود الأمان:")
        elif text in ["↩️ Back to Menu", "↩️ العودة للقائمة"]:
            context.user_data["state"] = None
            await show_menu(update, user_id, context)
        else:
            await safe_reply_text(update, "Please select a valid option.", reply_markup=get_method_keyboard(lang))
        return
    
    if state == "change_old_otp" and context.user_data.get("action") == "change":
        otp = text
        email = context.user_data.get("change_old_email")
        token = context.user_data.get("change_token")
        success, result, identity = verify_identity_otp(email, token, otp)
        if not success or not identity:
            await safe_reply_text(update, f"❌ Failed!\n\n{result}")
            context.user_data["state"] = None
            return
        context.user_data["change_identity"] = identity
        context.user_data["state"] = "change_new_email"
        await safe_reply_text(update, "Step 3/5: Enter new email:" if lang == LANG_EN else "الخطوة 3/5: أدخل الإيميل الجديد:")
        return
    
    if state == "change_old_sec" and context.user_data.get("action") == "change":
        sec_code = text
        if len(sec_code) != 6 or not sec_code.isdigit():
            await safe_reply_text(update, "❌ Must be 6 digits.")
            return
        email = context.user_data.get("change_old_email")
        token = context.user_data.get("change_token")
        success, result, identity = verify_identity_sec(email, token, sec_code)
        if not success or not identity:
            await safe_reply_text(update, f"❌ Failed!\n\n{result}")
            context.user_data["state"] = None
            return
        context.user_data["change_identity"] = identity
        context.user_data["state"] = "change_new_email"
        await safe_reply_text(update, "Step 3/5: Enter new email:" if lang == LANG_EN else "الخطوة 3/5: أدخل الإيميل الجديد:")
        return
    
    if state == "change_new_email" and context.user_data.get("action") == "change":
        new_email = text
        if '@' not in new_email:
            await safe_reply_text(update, "❌ Invalid email.")
            return
        context.user_data["change_new_email"] = new_email
        context.user_data["state"] = "change_new_otp"
        token = context.user_data.get("change_token")
        success, result = send_otp(new_email, token)
        await safe_reply_text(update, f"Step 4/5: OTP sent to {new_email}\n\n{result}\n\nEnter OTP:")
        return
    
    if state == "change_new_otp" and context.user_data.get("action") == "change":
        otp = text
        new_email = context.user_data.get("change_new_email")
        token = context.user_data.get("change_token")
        success, result, verifier = verify_otp(new_email, token, otp)
        if not success or not verifier:
            await safe_reply_text(update, f"❌ Failed!\n\n{result}")
            context.user_data["state"] = None
            return
        identity = context.user_data.get("change_identity")
        success, result = create_rebind_request(token, identity, new_email, verifier)
        context.user_data["state"] = None
        await safe_reply_text(update, f"Step 5/5: {result}", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Get Token Details ----
    if text in ["📋 Get Token Details", "📋 تفاصيل التوكن"]:
        context.user_data["action"] = "token_details"
        context.user_data["state"] = "token_details_input"
        await safe_reply_text(update, "📋 Get Token Details\n\nEnter Access Token:" if lang == LANG_EN else "📋 تفاصيل التوكن\n\nأدخل التوكن:")
        return
    
    if state == "token_details_input" and context.user_data.get("action") == "token_details":
        token = text
        account_id, nickname, region, valid = get_player_info(token)
        email, pending, countdown, rc, success = get_bind_info(token)
        bind_data, bind_success = get_bind_info_raw(token)
        email_verified = bind_data.get("email_verified", 0) if bind_success else 0
        msg = f"""📋 **Token Details**

🔐 **Status:** {'✅ Valid' if valid else '❌ Invalid'}

👤 **Nickname:** {nickname}
🆔 **ID:** {account_id}
🌍 **Region:** {region}

🔐 **Email:**
• Current: {mask_email(email) if email else 'None'}
• Pending: {pending if pending else 'None'}
• Verified: {'✅' if email_verified == 1 else '❌' if email else 'N/A'}

🔑 **Token:** `{token}`
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Eat Token Website ----
    if text in ["🔗 Eat Token Website", "🔗 تحويل EAT"]:
        context.user_data["action"] = "eat_token"
        context.user_data["state"] = "eat_token_input"
        await safe_reply_text(update, "🔗 Eat Token to Access Token\n\nEnter EAT Token or URL:" if lang == LANG_EN else "🔗 تحويل EAT\n\nأدخل توكن EAT أو الرابط:")
        return
    
    if state == "eat_token_input" and context.user_data.get("action") == "eat_token":
        error, result = eat_to_token(text)
        if error:
            await safe_reply_text(update, f"❌ {error}")
            context.user_data["state"] = None
            return
        msg = f"""🔗 **EAT to Access Token**

✅ Success!

👤 **Nickname:** {result.get('nickname')}
🆔 **ID:** {result.get('account_id')}
🌍 **Region:** {result.get('region')}

🔑 **Token:** `{result.get('access_token')}`
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Revoke Access Token ----
    if text in ["🔴 Revoke Access Token", "🔴 إلغاء التوكن"]:
        context.user_data["action"] = "revoke_token"
        context.user_data["state"] = "revoke_token_input"
        await safe_reply_text(update, "🔴 Revoke Access Token\n\nEnter Token:" if lang == LANG_EN else "🔴 إلغاء التوكن\n\nأدخل التوكن:")
        return
    
    if state == "revoke_token_input" and context.user_data.get("action") == "revoke_token":
        error, result = do_revoke(text)
        if error:
            await safe_reply_text(update, f"❌ {error}")
            context.user_data["state"] = None
            return
        msg = f"""🔴 **Token Revoked!**

👤 **Nickname:** {result.get('nickname')}
🆔 **ID:** {result.get('account_id')}
🌍 **Region:** {result.get('region')}
📌 **Status:** {result.get('status')}
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Login History ----
    if text in ["📝 Login History", "📝 سجل الدخول"]:
        context.user_data["action"] = "login_history"
        context.user_data["state"] = "login_history_token"
        await safe_reply_text(update, "📝 Login History\n\nEnter Access Token or JWT:" if lang == LANG_EN else "📝 سجل الدخول\n\nأدخل التوكن:")
        return
    
    if state == "login_history_token" and context.user_data.get("action") == "login_history":
        await update.message.reply_text("🔄 Fetching history...", parse_mode=None)
        error, records = get_login_history(text)
        if error:
            await safe_reply_text(update, f"❌ {error}")
            context.user_data["state"] = None
            return
        if not records:
            await safe_reply_text(update, "📭 No records found.")
            context.user_data["state"] = None
            return
        account_id, nickname, region, valid = get_player_info(text)
        msg = f"""📝 **Login History**

👤 **Nickname:** {nickname}
🆔 **ID:** {account_id}
📊 **Records:** {len(records)}

"""
        for i, rec in enumerate(records[:10], 1):
            try:
                date_str = datetime.fromtimestamp(rec.get('ts', 0)).strftime('%Y-%m-%d %H:%M:%S')
            except:
                date_str = "Invalid"
            msg += f"**#{i}** {date_str}\n📱 {rec.get('dev', 'Unknown')}\n💾 {rec.get('ram', 0)} MB\n\n"
        if len(records) > 10:
            msg += f"... +{len(records)-10} more"
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Access Token to JWT ----
    if text in ["🔑 Access Token to JWT", "🔑 تحويل إلى JWT"]:
        context.user_data["action"] = "access_to_jwt"
        context.user_data["state"] = "access_to_jwt_input"
        await safe_reply_text(update, "🔑 Access Token to JWT\n\nEnter Access Token:" if lang == LANG_EN else "🔑 تحويل إلى JWT\n\nأدخل التوكن:")
        return
    
    if state == "access_to_jwt_input" and context.user_data.get("action") == "access_to_jwt":
        await update.message.reply_text("🔄 Converting...", parse_mode=None)
        success, result = access_to_jwt_api(text)
        if not success:
            await safe_reply_text(update, f"❌ Failed: {result}")
            context.user_data["state"] = None
            return
        account_id, nickname, region, valid = get_player_info(text)
        msg = f"""🔑 **Token to JWT**

✅ Success!

👤 **Nickname:** {nickname}
🆔 **ID:** {account_id}

🔑 **JWT:** `{result}`
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Ban Account ----
    if text in ["🚫 Ban Account", "🚫 حظر الحساب"]:
        context.user_data["action"] = "ban_account"
        context.user_data["state"] = "ban_account_input"
        await safe_reply_text(update, "🚫 Ban Account\n\n⚠️ WARNING: This will attempt to ban!\n\nEnter Access Token:" if lang == LANG_EN else "🚫 حظر الحساب\n\n⚠️ تحذير: سيتم محاولة الحظر!\n\nأدخل التوكن:")
        return
    
    if state == "ban_account_input" and context.user_data.get("action") == "ban_account":
        await update.message.reply_text("🔄 Sending ban request...", parse_mode=None)
        success, result = ban_account_api(text)
        if success:
            try:
                parsed = json.loads(result)
                msg = f"🚫 **Ban Response**\n\n✅ Request sent!\n\n```json\n{json.dumps(parsed, indent=4)}```"
            except:
                msg = f"🚫 **Ban Response**\n\n✅ Request sent!\n\n{result}"
        else:
            msg = f"🚫 **Ban Response**\n\n❌ Failed!\n\n{result}"
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Spam Login Request ----
    if text in ["🔄 Spam Login Request", "🔄 طلب سبام"]:
        if SpamManager.has_pending_request(user_id):
            await safe_reply_text(update, "⏳ You already have a pending request." if lang == LANG_EN else "⏳ لديك طلب معلق.")
            return
        if SpamManager.is_spam_active(user_id):
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Spam", callback_data="spam_cancel")]])
            await safe_reply_text(update, "🔄 Spam is Active!\n\nPress Cancel to disable." if lang == LANG_EN else "🔄 السبام مفعل!\n\nاضغط إلغاء.", reply_markup=keyboard)
            return
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ YES", callback_data="spam_warning_yes")], [InlineKeyboardButton("❌ NO", callback_data="spam_warning_no")]])
        await safe_reply_text(update, "⚠️ WARNING: This may get your account BANNED!\n\nProceed?" if lang == LANG_EN else "⚠️ تحذير: قد يتسبب في حظر حسابك!\n\nهل تريد الاستمرار؟", reply_markup=keyboard)
        return
    
    if state == "spam_eat_input" and context.user_data.get("action") == "spam_request":
        error, result = eat_to_token(text)
        if error:
            await safe_reply_text(update, f"❌ {error}")
            context.user_data["state"] = None
            return
        request = SpamManager.create_request(user_id, text)
        SpamManager.save_request(request)
        await safe_reply_text(update, "✅ Request sent to admin for approval." if lang == LANG_EN else "✅ تم إرسال الطلب للمشرف.")
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=f"📋 New Spam Request\n\n👤 User: {user_id}\n📌 ID: {request['id']}")
        except: pass
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button.", reply_markup=get_user_keyboard(lang))
        return
    
    # ---- Language Switch (Callback) ----
    if text in ["↩️ Back to Menu", "↩️ العودة للقائمة"]:
        context.user_data.clear()
        await show_menu(update, user_id, context)
        return
    
    await safe_reply_text(update, "Please use menu buttons." if lang == LANG_EN else "استخدم أزرار القائمة.", reply_markup=get_user_keyboard(lang))

# ============================================================
# CALLBACK HANDLER
# ============================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    lang = DataManager.get_user_lang(user_id)
    is_admin = DataManager.is_admin(user_id)

    if data == "lang_en":
        DataManager.set_user_lang(user_id, LANG_EN)
        await query.edit_message_text("🌍 Language set to English ✅")
        await show_menu(update, user_id, context)
        return

    if data == "lang_ar":
        DataManager.set_user_lang(user_id, LANG_AR)
        await query.edit_message_text("🌍 تم ضبط اللغة إلى العربية ✅")
        await show_menu(update, user_id, context)
        return

    if data == "spam_warning_yes":
        context.user_data["state"] = "spam_eat_input"
        context.user_data["action"] = "spam_request"
        await query.edit_message_text("🔄 Spam Request\n\nSend EAT Token or URL:" if lang == LANG_EN else "🔄 طلب سبام\n\nأرسل توكن EAT أو الرابط:")
        return

    if data == "spam_warning_no":
        await query.edit_message_text("❌ Cancelled." if lang == LANG_EN else "❌ تم الإلغاء.")
        return

    if data == "spam_cancel":
        SpamManager.deactivate_spam(user_id)
        await query.edit_message_text("❌ Spam disabled." if lang == LANG_EN else "❌ تم إلغاء السبام.")
        return

    if is_admin:
        if data.startswith("spam_approve_"):
            request_id = data.replace("spam_approve_", "")
            if SpamManager.approve_request(request_id):
                req = SpamManager.get_request(request_id)
                if req:
                    try:
                        await context.bot.send_message(chat_id=req["user_id"], text="✅ Spam approved! You can now use spam mode.")
                    except: pass
                await query.edit_message_text(f"✅ Approved {request_id}")
            else:
                await query.edit_message_text(f"❌ Failed")
            return

        if data.startswith("spam_reject_"):
            request_id = data.replace("spam_reject_", "")
            if SpamManager.reject_request(request_id):
                req = SpamManager.get_request(request_id)
                if req:
                    try:
                        await context.bot.send_message(chat_id=req["user_id"], text="❌ Spam request rejected.")
                    except: pass
                await query.edit_message_text(f"✅ Rejected {request_id}")
            else:
                await query.edit_message_text(f"❌ Failed")
            return

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("""
🚀 R32 SHADOW BOT v6.2 (CLEAN & FIXED)
👨‍💻 Developer: @r32pro
👨‍💻 Co-Developer: @XHR_M
📢 https://t.me/ShadowCodee
📋 All APIs working like app.py!
    """)
    
    KeyManager.cleanup()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("🟢 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)