import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
API_BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000/api').rstrip('/')
REQUEST_TIMEOUT = float(os.getenv('API_REQUEST_TIMEOUT', '10.0'))
PAGE_SIZE = int(os.getenv('BOT_PAGE_SIZE', '3'))

# Admin Group and Public Channel IDs
_admin_group_raw = os.getenv('TELEGRAM_ADMIN_GROUP_ID', '').strip()
try:
    TELEGRAM_ADMIN_GROUP_ID = int(_admin_group_raw) if _admin_group_raw else None
except ValueError:
    TELEGRAM_ADMIN_GROUP_ID = _admin_group_raw or None

_channel_raw = os.getenv('TELEGRAM_PUBLIC_CHANNEL_ID', '').strip()
try:
    TELEGRAM_PUBLIC_CHANNEL_ID = int(_channel_raw) if _channel_raw and _channel_raw.startswith('-') else _channel_raw or None
except ValueError:
    TELEGRAM_PUBLIC_CHANNEL_ID = _channel_raw or None
