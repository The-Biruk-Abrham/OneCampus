# OneCampus — University Events Hub 🎓📢

A centralized event aggregation, discovery, and broadcast system for ASTU (Adama Science and Technology University). OneCampus pairs a robust Django REST API backend with an interactive Telegram bot interface and automated channel broadcasting.

---

## ✨ Features

- **🏛️ Club Submissions & Moderation Flow**:
  - Direct submissions via guided bot conversation (`/submit`).
  - Supports forwarded announcements, text posts, photos, and videos.
  - Interactive Admin Approval Queue in private moderation group (`[✅ Approve]`, `[❌ Reject]`, `[✏️ Edit Fields]`).
  - Single-field inline editing without restarting the submission flow.
  - Automatic channel broadcast upon approval with zero modifications to original captions.
- **📅 Smart Event Discovery**:
  - `/today` — Paginated list of events happening today.
  - `/week` — Grouped view of all events for the upcoming 7 days.
  - `/events` — Category-filtered event browsing.
  - Strict date/time parsing and validation (`DD/MM/YYYY HH:MM`).
- **🛡️ Custom Categories & Clubs ("➕ Other")**:
  - Safe free-text custom entry for unlisted organizers or event categories.
  - Admin notification explicitly flags unverified club claims to protect community trust.
- **⚡ Reliable Architecture**:
  - Django REST Framework API with PostgreSQL & SQLite support.
  - Single-instance bot locking to prevent polling loops.
  - Inactivity conversation timeouts (20 min) and universal `/cancel` / `/help` commands.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12+, Django 5.x, Django REST Framework
- **Bot Engine**: `python-telegram-bot` (v21.x async)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **HTTP Client**: `httpx` (async)

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12 or higher
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Installation & Setup

```bash
# Clone the repository
git clone https://github.com/The-Biruk-Abrham/OneCampus.git
cd OneCampus

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate   # On Windows
# source .venv/bin/activate # On Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

### 3. Configure `.env`
Update `.env` with your credentials:
```env
SECRET_KEY=your-django-secret-key
DEBUG=True
USE_SQLITE=True

TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
API_BASE_URL=http://127.0.0.1:8000/api
TELEGRAM_ADMIN_GROUP_ID=-100xxxxxxxxxx
TELEGRAM_PUBLIC_CHANNEL_ID=@your_events_channel
```

### 4. Database Setup & Seed Data
```bash
# Run migrations
python manage.py migrate

# Seed sample categories, clubs, and initial events
python manage.py seed_data

# Register an admin user
python manage.py add_admin <YOUR_TELEGRAM_ID> --role superadmin --name "Your Name"
```

### 5. Running the Application

Open **two** terminal windows:

**Terminal 1 (Django REST API Server):**
```bash
python manage.py runserver
```

**Terminal 2 (Telegram Bot):**
```bash
python run_bot.py
```

---

## 🧪 Testing

Run the full automated test suite:
```bash
python manage.py test
```

---

## 📜 License
MIT License. Created for ASTU University Community.
