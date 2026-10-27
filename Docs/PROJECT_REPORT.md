# University Events Hub — Comprehensive Technical Report

**Document Status:** Current Codebase Baseline Report  
**Workspace:** `c:\Users\hp\Documents\Events`  
**Analysis Date:** October 2026  
**Audience:** Core Engineers, Architects, and Project Maintainers  

---

## 1. Project Overview

### 1.1 Purpose and Objectives
The **University Events Hub** (ASTU Events Hub) is a specialized backend and Telegram automation platform built for university campuses (specifically deployed and styled for Adama Science and Technology University - ASTU). It aggregates student club activities, academic workshops, sports tournaments, hackathons, guest lectures, and student initiatives into a single, verified, and always-current source of truth.

The platform eliminates fragmented campus communication across arbitrary Telegram channels and group chats by introducing:
1. A **curated public broadcast channel** where approved event announcements are posted directly or forwarded with original media intact.
2. An **interactive Telegram bot (`@AASTUeventsbot`)** for students to query upcoming schedules (`/today`, `/week`, `/events`), browse by categories, and paginate through listings.
3. A **moderated submission pipeline** where verified student club officers submit events (via forwarded posts or guided prompts), which enter an approval queue for the administration team.
4. A **Django REST Framework (DRF) backend API** that manages relational state, permissions, audit timestamps, and structured queries while maintaining separation between raw forwarded media/captions and structured queryable metadata.

### 1.2 User Roles & Target Personas
- **General Students / Public Viewers:** Anyone with Telegram. They can view the broadcast channel, execute read-only queries (`/start`, `/today`, `/week`, `/events`), filter by category, and navigate pagination menus. No login or verification required.
- **Club Representatives / Verified Officers:** Authorized club leaders whose Telegram user IDs are linked to a registered `Club`. They can access the `/submit` wizard (or inline `[📝 Submit Post]`) to submit event announcements.
- **Moderators & Bot Admins:** Users registered in the `Admin` database table (with levels `moderator`, `admin`, or `superadmin`) or Django superusers. They review incoming submissions in a dedicated private Telegram Admin Group via interactive inline buttons (`Approve`, `Reject`, `Edit Fields`).
- **Bot Owner:** The primary platform administrator configured via `TELEGRAM_OWNER_ID` in `.env`. Possesses elevated privileges across all clubs: can register new clubs (`/add_club`), grant representative status (`/add_club_admin`), revoke representative status (`/remove_club_admin`), and bypass club-specific restrictions during submissions.

### 1.3 Implementation Status by Phase (Planned vs. Actual)
- **Phase 1: Core Data & Admin (COMPLETE)**  
  - Relational models ([`Category`](file:///c:/Users/hp/Documents/Events/events/models.py#L5-L20), [`Club`](file:///c:/Users/hp/Documents/Events/events/models.py#L22-L49), [`Event`](file:///c:/Users/hp/Documents/Events/events/models.py#L58-L181), [`Admin`](file:///c:/Users/hp/Documents/Events/events/models.py#L189-L215)) are fully implemented.
  - Django Admin site ([`events/admin.py`](file:///c:/Users/hp/Documents/Events/events/admin.py)) registered with color-coded status badges, filters, search, and bulk moderation actions.
  - Seeding command ([`events/management/commands/seed_data.py`](file:///c:/Users/hp/Documents/Events/events/management/commands/seed_data.py)) and admin creation command ([`events/management/commands/add_admin.py`](file:///c:/Users/hp/Documents/Events/events/management/commands/add_admin.py)) are implemented.
- **Phase 2: REST API with DRF (COMPLETE)**  
  - Full endpoint suite for `/api/events/`, `/api/events/<id>/`, `/api/events/<id>/status/`, `/api/clubs/`, `/api/clubs/<id>/officers/`, and `/api/categories/`.
  - Custom header-based authentication ([`IsTelegramAdminUser`](file:///c:/Users/hp/Documents/Events/events/permissions.py#L45-L58)) using `X-Telegram-User-Id`.
  - Comprehensive API test suite ([`events/tests.py`](file:///c:/Users/hp/Documents/Events/events/tests.py)).
- **Phase 3: Telegram Bot v1 - Viewing & Navigation (COMPLETE)**  
  - Commands implemented: `/start`, `/help`, `/today`, `/week`, `/events`, `/cancel`.
  - Interactive category picker and grid pagination with `[◀️ Prev]`, `[Next ▶️]`, `[🔙 Categories]`, and `[🏠 Main Menu]`.
  - Dedicated formatting engines with Markdown V1 safe character escaping.
- **Phase 4: Telegram Bot v2 - Submissions & Moderation (COMPLETE)**  
  - 10-state `ConversationHandler` for submission handling forwarded media (photos, videos, animations, documents, audio, voice, polls, text).
  - Admin Group notification card with media and `[✅ Approve]`, `[❌ Reject]`, `[✏️ Edit Fields]`.
  - Auto-broadcasting to public channel upon approval.
  - Real-time in-place editing of channel posts via `channel_message_id`.
  - Owner management flows for clubs and officers ([`bot/handlers/officers.py`](file:///c:/Users/hp/Documents/Events/bot/handlers/officers.py)).
- **Phase 5: Engagement, Subscriptions & Reminders (NOT STARTED)**  
  - `Subscription` model, `/subscribe`, `/unsubscribe`, push notifications for new events, weekly digest cron/Celery jobs, and event reminder alarms are **not yet implemented**.
- **Phase 6: Public Web Frontend (NOT STARTED)**  
  - Web UI deferred as per SDD plan.

---

## 2. Tech Stack and Versions

### 2.1 Dependencies & Runtime Environment
Verified against active virtual environment (`.venv`) and [`requirements.txt`](file:///c:/Users/hp/Documents/Events/requirements.txt):

| Component | Specified in `requirements.txt` | Active Installed Version | Purpose |
|---|---|---|---|
| **Python** | `>=3.11` (implicit) | `3.14.6` (Windows x64) | Core Language Runtime |
| **Django** | `>=5.1,<6.0` | `5.2.17` | Web framework, ORM, Admin portal |
| **Django REST Framework** | `>=3.15.0` | `3.18.0` | Serializers, API views, permissions |
| **python-telegram-bot** | `>=21.0` | `22.8` | Async Telegram Bot API wrapper |
| **httpx** | `>=0.27.0` | `0.28.1` | Async HTTP client for bot-to-API calls |
| **psycopg / psycopg-binary** | `>=3.2.0` | `3.3.4` | PostgreSQL 3 database adapter |
| **python-dotenv** | `>=1.0.1` | `1.2.3` | Environment variable loader |
| **dj-database-url** | `>=2.3.0` | `3.1.2` | 12-factor database URL parser |

### 2.2 Database Configuration: SQLite vs. PostgreSQL
- **Actual Database in Active Use:** **SQLite** (`db.sqlite3`, file size ~224 KB).
- **Configuration Logic in [`events_hub/settings.py`](file:///c:/Users/hp/Documents/Events/events_hub/settings.py#L100-L128):**
  - Checked via `USE_SQLITE = os.getenv('USE_SQLITE', 'True').lower() in ('true', '1', 't')`.
  - Default `.env` has `USE_SQLITE=True`.
  - If `USE_SQLITE=False` and `DATABASE_URL` is set, `dj_database_url` connects to PostgreSQL with connection pooling (`conn_max_age=600`, `conn_health_checks=True`).
  - If `USE_SQLITE=False` and discrete parameters (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) are provided, Django connects via `django.db.backends.postgresql`.
  - Otherwise, falls back to `BASE_DIR / 'db.sqlite3'`.

### 2.3 Scheduler and Queue Systems
- **Currently Configured:** **None**.
- There is **no Celery, Redis, django-q, or APScheduler** installed or running in the codebase. Asynchronous operations within the bot rely on Python's built-in `asyncio` event loop.

---

## 3. Project Structure

```
c:\Users\hp\Documents\Events
├── .env                              # Active environment config (credentials, tokens, IDs)
├── .env.example                      # Template config defining all required env variable names
├── .gitignore                        # Git exclusion rules
├── db.sqlite3                        # Active local development database
├── manage.py                         # Django administrative management entry point
├── requirements.txt                  # Python package dependencies
├── run_bot.py                        # Single-instance locked bot execution script
│
├── Docs/                             # Architectural and planning specifications
│   ├── SDD.md                        # Software Design Document (system specification)
│   ├── task-checklist.md             # Checklist tracking implementation milestones
│   └── agent-prompts.md              # Historical development prompts
│
├── events_hub/                       # Django Project Configuration Package
│   ├── __init__.py
│   ├── asgi.py                       # ASGI configuration for async web servers
│   ├── settings.py                   # Django settings, database routing, middleware, apps
│   ├── urls.py                       # Root URL routing: /admin/ and /api/
│   └── wsgi.py                       # WSGI entry point for standard web deployment
│
├── events/                           # Core Django App: Models, REST API, Moderation
│   ├── __init__.py
│   ├── admin.py                      # Django Admin site customization with actions and badges
│   ├── apps.py                       # App configuration (EventsConfig)
│   ├── models.py                     # Category, Club, Event, Admin, EventStatus, PermissionLevel
│   ├── permissions.py                # IsTelegramAdminUser and header-based ID authentication
│   ├── serializers.py                # DRF serializers (read, create, status, field updates)
│   ├── urls.py                       # API URL routing (/events/, /clubs/, /categories/)
│   ├── views.py                      # ListCreate, RetrieveUpdate, StatusUpdate, Officers views
│   ├── tests.py                      # Django test suite (models, admin actions, DRF API)
│   ├── management/
│   │   └── commands/
│   │       ├── add_admin.py          # CLI command: python manage.py add_admin <tg_id> --level
│   │       └── seed_data.py          # CLI command: python manage.py seed_data [--clear]
│   └── migrations/
│       ├── 0001_initial.py           # Initial database schema migration
│       └── 0002_event_custom_category_event_custom_club.py # Support for unlisted clubs/categories
│
└── bot/                              # Asynchronous Telegram Bot Subsystem
    ├── __init__.py
    ├── api_client.py                 # EventsApiClient: async httpx REST wrapper for Django API
    ├── config.py                     # Env parsing (tokens, channel IDs, timeouts, owner checks)
    ├── formatters.py                 # Markdown formatters for today, week, channel posts, cards
    ├── pagination.py                 # Inline keyboard builders (pagination, menus, confirmations)
    ├── main.py                       # Bot application builder, router registration, polling loop
    ├── handlers/
    │   ├── __init__.py
    │   ├── start.py                  # /start and /help command handler with role-tailored menus
    │   ├── today.py                  # /today command with paginated output
    │   ├── week.py                   # /week command with day-grouped output
    │   ├── events.py                 # /events command with interactive category grid & navigation
    │   ├── submit.py                 # 10-state ConversationHandler for event submissions
    │   ├── admin.py                  # Moderation: approve, reject, in-place edit, channel broadcast
    │   ├── officers.py               # Owner portal: add/remove club officers, create clubs
    │   └── callbacks.py              # Central callback_query router for pagination and menus
    └── tests/
        ├── __init__.py
        ├── test_bot.py               # Unit tests for formatters, pagination, and API client
        └── test_submission_and_admin.py # Unit tests for submission, admin, and officer flows
```

---

## 4. Data Models

Defined in [`events/models.py`](file:///c:/Users/hp/Documents/Events/events/models.py).

### 4.1 `Category`
Represents an event classification category (e.g., Club Social, Sports, Academic, Entertainment, Career/Workshop, Religious, Other).
- **`id`**: `BigAutoField`, Primary Key.
- **`name`**: `CharField(max_length=100, unique=True)`. Name of the category.
- **`description`**: `TextField(blank=True)`. Optional description.
- **`created_at`**: `DateTimeField(auto_now_add=True)`.
- **Ordering**: `['name']`.

### 4.2 `Club`
Represents a student club, chapter, or university organization.
- **`id`**: `BigAutoField`, Primary Key.
- **`name`**: `CharField(max_length=200, unique=True)`. Official club name.
- **`category_type`**: `CharField(max_length=100, blank=True)`. Genre/type (e.g. Technology, Engineering, Sports).
- **`verified_officers`**: `JSONField(default=list, blank=True)`. Python list storing Telegram user IDs (integers or strings) authorized to submit events for this club.
- **`contact_info`**: `TextField(blank=True)`. Email, phone, or Telegram handle.
- **`created_at`**: `DateTimeField(auto_now_add=True)`.
- **`updated_at`**: `DateTimeField(auto_now=True)`.
- **Method `is_officer(telegram_id: int | str) -> bool`**: Compares stringified user ID against elements of `verified_officers`.

### 4.3 `EventStatus` (TextChoices)
Enum defining event moderation states:
- `PENDING = 'pending', 'Pending'`
- `APPROVED = 'approved', 'Approved'`
- `REJECTED = 'rejected', 'Rejected'`
- `CANCELLED = 'cancelled', 'Cancelled'`

### 4.4 `Event`
The central entity. It strictly isolates queryable structured fields from unmodified raw content.
- **Structured Fields (Queryable & Filterable):**
  - **`id`**: `BigAutoField`, Primary Key.
  - **`title`**: `CharField(max_length=255)`. Short, clean event title.
  - **`club`**: `ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')`. Host organization. Nullable if `custom_club` is entered.
  - **`custom_club`**: `CharField(max_length=100, blank=True, default='')`. Custom unlisted host club name entered via the "Other" option.
  - **`category`**: `ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')`. Nullable if `custom_category` is entered.
  - **`custom_category`**: `CharField(max_length=100, blank=True, default='')`. Custom unlisted category entered via the "Other" option.
  - **`start_datetime`**: `DateTimeField(db_index=True)`. Event commencement timestamp (indexed for range queries).
  - **`end_datetime`**: `DateTimeField(null=True, blank=True)`. Optional conclusion timestamp.
  - **`location`**: `CharField(max_length=255)`. Venue or location description.
- **Raw Content (Original Media & Caption):**
  - **`raw_content`**: `JSONField(default=dict, blank=True)`. Stores the unmodified payload:
    ```json
    {
      "media_type": "photo | video | document | animation | audio | voice | poll | text",
      "file_ids": ["AgACAgIAAxkBAAIC..."],
      "caption": "🚀 Original announcement text as forwarded from Telegram...",
      "is_forwarded": true,
      "submitter_telegram_id": 123456789,
      "submitter_username": "student_leader",
      "forward_info": {
        "origin_type": "channel",
        "chat_title": "ASTU Tech News",
        "chat_username": "astutechnews"
      }
    }
    ```
  - **Distinction from Structured Fields:** Structured fields (`title`, `start_datetime`, `location`, `club`, `category`) allow database filtering, calendar calculations (`/today`, `/week`), and admin editing. `raw_content` preserves Telegram `file_id` strings and original text verbatim so that forwarded channel broadcasts can be displayed without mangling or lost formatting.
- **Moderation & Channel Publishing:**
  - **`status`**: `CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.PENDING, db_index=True)`.
  - **`recurring`**: `BooleanField(default=False)`.
  - **`recurrence_pattern`**: `CharField(max_length=100, null=True, blank=True)`. Recurrence description (e.g. "Every Wednesday 5 PM").
  - **`channel_message_id`**: `BigIntegerField(null=True, blank=True)`. Stores the Telegram message ID once broadcast to the public channel, enabling in-place message updates.
  - **`submitted_at`**: `DateTimeField(auto_now_add=True)`.
  - **`approved_at`**: `DateTimeField(null=True, blank=True)`.
  - **`approved_by`**: `CharField(max_length=100, null=True, blank=True)`. Admin name or Telegram ID.
- **Indexes:**
  - Index on `start_datetime` (field-level).
  - Composite index `event_status_start_idx` on `['status', 'start_datetime']`.
- **Helper Methods:**
  - `approve(approver_identifier, channel_msg_id)`
  - `reject(approver_identifier)`
  - `cancel()`

### 4.5 `PermissionLevel` & `Admin`
- **`PermissionLevel` (TextChoices):** `SUPERADMIN = 'superadmin'`, `ADMIN = 'admin'`, `MODERATOR = 'moderator'`.
- **`Admin`:**
  - **`id`**: `BigAutoField`, Primary Key.
  - **`telegram_id`**: `BigIntegerField(unique=True, db_index=True)`. Telegram user ID of authorized bot admin.
  - **`name`**: `CharField(max_length=150, blank=True)`. Display handle.
  - **`permission_level`**: `CharField(max_length=50, choices=PermissionLevel.choices, default=PermissionLevel.MODERATOR)`.
  - **`is_active`**: `BooleanField(default=True)`.
  - **`created_at`**: `DateTimeField(auto_now_add=True)`.

---

## 5. REST API Specification

Base URL: `/api/` (Default local: `http://127.0.0.1:8000/api`)

### 5.1 Authentication & Permissions
Authentication is handled via [`events/permissions.py`](file:///c:/Users/hp/Documents/Events/events/permissions.py):
1. **Django Superuser/Staff:** If `request.user.is_authenticated` and `request.user.is_staff` or `is_superuser`, access is granted.
2. **Telegram Admin Identification:** Inspects headers `X-Telegram-User-Id`, `X-Telegram-Admin-Id`, or query parameter `telegram_admin_id`.
3. **Owner Check:** If the ID matches `TELEGRAM_OWNER_ID` from the environment, access is granted with synthetic `superadmin` level.
4. **Database Admin Check:** Queries `Admin.objects.filter(telegram_id=id, is_active=True).first()`. If found, attaches `request.telegram_admin` and permits execution.
5. **Unauthenticated Endpoints:** Public reads (`GET /api/events/`, `GET /api/categories/`, `GET /api/clubs/`, `GET /api/clubs/<id>/`) and public submissions (`POST /api/events/`) do not require admin headers.

### 5.2 Endpoints Table

| Method | URL | Purpose | Query Params | Request Body | Response Shape / Code | Permission Class |
|---|---|---|---|---|---|---|
| **GET** | `/api/events/` | List approved events (or all if admin) | `range` (`today`\|`week`), `category` (id\|name), `club` (id\|name), `status` | None | `200 OK`: Array of [`EventSerializer`](file:///c:/Users/hp/Documents/Events/events/serializers.py#L33-L86) objects | `AllowAny` (Defaults to `status=approved` for non-admins) |
| **POST** | `/api/events/` | Submit new event | None | `EventCreateSerializer` (title, start_datetime, location, club, custom_club, category, custom_category, raw_content) | `201 Created`: Created event details (forced `status="pending"`) | `AllowAny` (Club officers verified at bot level) |
| **GET** | `/api/events/<pk>/` | Retrieve event detail | None | None | `200 OK`: Single `EventSerializer` object | `AllowAny` |
| **PATCH / PUT** | `/api/events/<pk>/` | Edit event structured fields | None | `EventStructuredFieldsUpdateSerializer` (title, start_datetime, end_datetime, location, club, custom_club, category, custom_category, recurring, recurrence_pattern) | `200 OK`: Updated `EventSerializer` object | `IsTelegramAdminUser` (403 if unauthorized) |
| **PATCH** | `/api/events/<pk>/status/` | Transition status (approve, reject, cancel) | None | `EventStatusUpdateSerializer`: `{"status": "approved"\|"rejected"\|"cancelled", "channel_message_id": 1234}` | `200 OK`: Updated `EventSerializer` object | `IsTelegramAdminUser` (403 if unauthorized) |
| **GET** | `/api/clubs/` | List all registered clubs | None | None | `200 OK`: Array of `ClubSerializer` objects | `AllowAny` |
| **POST** | `/api/clubs/` | Register a new club | None | `ClubSerializer`: `{"name": "...", "category_type": "...", "contact_info": "..."}` | `201 Created`: Created `ClubSerializer` object | `IsTelegramAdminUser` (Admin / Owner only) |
| **GET** | `/api/clubs/<pk>/` | Retrieve specific club | None | None | `200 OK`: Single `ClubSerializer` object | `AllowAny` |
| **POST** | `/api/clubs/<pk>/officers/` | Add verified officer | None | `OfficerManagementSerializer`: `{"telegram_id": 123456789}` | `200 OK`: Updated `ClubSerializer` object | `IsTelegramAdminUser` (Admin / Owner only) |
| **DELETE** | `/api/clubs/<pk>/officers/` | Remove verified officer | None | `OfficerManagementSerializer`: `{"telegram_id": 123456789}` | `200 OK`: Updated `ClubSerializer` object | `IsTelegramAdminUser` (Admin / Owner only) |
| **GET** | `/api/categories/` | List all categories | None | None | `200 OK`: Array of `CategorySerializer` objects | `AllowAny` |

---

## 6. Telegram Bot: Commands and Menus

### 6.1 Commands Reference

| Command | Accessible By | Handler | Purpose & Behavior |
|---|---|---|---|
| `/start`, `/help` | All Users | [`start_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/start.py#L8-L56) | Welcomes the user and dynamically renders the quick action keyboard based on role (Viewer, Officer, Owner). |
| `/today` | All Users | [`today_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/today.py#L13-L33) | Fetches events happening today (`range=today`), paginated 3 per page with `[◀️ Prev]`, `[Next ▶️]`, and `[🏠 Main Menu]`. |
| `/week` | All Users | [`week_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/week.py#L12-L28) | Fetches events for the upcoming 7 days (`range=week`), grouped by weekday (e.g. `📅 Monday, Sep 15`). |
| `/events` | All Users | [`events_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/events.py#L59-L73) | If called as `/events <name>`, filters directly. If called with no arguments, renders a 2-column interactive category picker. |
| `/submit` | Verified Officers & Owner | [`start_submission`](file:///c:/Users/hp/Documents/Events/bot/handlers/submit.py#L217-L262) | Initiates the 10-state event submission wizard. Rejects unverified students with an authorization notice. |
| `/cancel` | All Users | [`cancel_submission`](file:///c:/Users/hp/Documents/Events/bot/handlers/submit.py#L899-L919) / [`start_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/start.py#L8-L56) | Cancels active submission, officer management, or edit session and returns to Main Menu. |
| `/pending` | Admins & Owner | [`pending_events_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/admin.py#L29-L57) | Lists all events currently in `status=pending` with inline approval keyboards. |
| `/check_config` | Admins & Owner | [`check_config_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/admin.py#L59-L103) | Diagnostics command: tests connectivity and permissions by pinging Admin Group and Public Channel. |
| `/add_club` | Bot Owner | [`add_club_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/officers.py#L686-L712) | Interactive wizard or CLI syntax `/add_club <name>` to register a new university club. |
| `/add_club_admin` | Bot Owner | [`add_officer_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/officers.py#L469-L505) | Interactive wizard or CLI syntax `/add_club_admin <club_id> <tg_id>` to add a verified representative. |
| `/remove_club_admin`| Bot Owner | [`remove_officer_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/officers.py#L507-L543) | Interactive wizard or CLI syntax `/remove_club_admin <club_id> <tg_id>` to remove a verified representative. |
| `/officers` | Bot Owner & Admins | [`list_officers_command`](file:///c:/Users/hp/Documents/Events/bot/handlers/officers.py#L714-L740) | Lists all clubs and their verified Telegram officer IDs. |

### 6.2 Interactive Callbacks and Menu Navigation

```
[Main Menu /start]
  ├── [☀️ Today's Events]        ──► Calls /today (page 1) ──► [◀️ Prev] [1/3] [Next ▶️] [🏠 Main Menu]
  ├── [🗓️ This Week]             ──► Calls /week (7-day grouped schedule) ──► [🏠 Main Menu]
  ├── [🏷️ Browse by Category]    ──► 2-Column Grid of Categories ──► [🔙 Back to Main Menu]
  │                                    └── Tap Category ──► Paginated Events ──► [🔙 Categories] [🏠 Main Menu]
  ├── [📝 Submit Post]           ──► (Officers only) Starts /submit wizard
  ├── [➕ Add Club Admin]        ──► (Owner only) Club Picker ──► Forward Msg / Type ID ──► Verified
  ├── [➖ Remove Club Admin]     ──► (Owner only) Club Picker ──► [🗑️ Remove ID: X] ──► Confirmed
  └── [🏛️ Register New Club]    ──► (Owner only) Name Prompt ──► Genre Picker ──► Created
```

- **Callback Prefixes:**
  - `btn:today`, `btn:week`, `btn:categories`, `btn:main_menu`, `btn:submit`
  - `page:today:<page_number>`: Today pagination.
  - `page:cat:<cat_id>:<page_number>`: Category pagination.
  - `cat:select:<cat_id>`: Category selection.
  - `submit:club:<id|other>`, `submit:cat:<id|other>`, `submit:confirm`, `submit:cancel`, `submit:edit:<field>`
  - `admin:approve:<id>`, `admin:reject:<id>`, `admin:edit:<id>`, `admin:editfield:<field>:<id>`
  - `owner:add_admin`, `owner:remove_admin`, `owner:create_club`, `owner:club_add:<id>`, `owner:club_rm:<id>`, `owner:rm_officer:<club_id>:<off_id>`, `owner:genre:<genre>`, `owner:cancel`

---

## 7. Conversation Flows (Step-by-Step)

### 7.1 Event Submission Flow ([`bot/handlers/submit.py`](file:///c:/Users/hp/Documents/Events/bot/handlers/submit.py))
1. **Entry & Authorization Gate:** User sends `/submit` or clicks `[📝 Submit Post]`.
   - The bot queries `get_user_verified_clubs(user_id)`.
   - If the user is neither an officer of at least one club nor the bot owner, access is rejected immediately with a friendly explanation.
2. **State 0 (`STATE_CONTENT`): Media / Forward Capture:**
   - Submitter forwards a post (with photo, video, document, animation, audio, voice, or text) from their channel, or sends content directly.
   - [`extract_raw_content()`](file:///c:/Users/hp/Documents/Events/bot/handlers/submit.py#L44-L133) preserves media `file_ids`, media types, origin metadata, and original caption text unmodified.
3. **State 1 (`STATE_TITLE`): Title Input:**
   - Prompt: "Please enter a short Title for this event:".
   - Submitter types title.
4. **State 2 (`STATE_CLUB` / `STATE_CUSTOM_CLUB`): Host Club Resolution:**
   - **Auto-Fill Optimization:** If the officer is verified for **exactly 1 club**, the club is auto-selected without displaying a picker, jumping directly to Category selection.
   - If verified for multiple clubs (or owner), an inline picker is displayed.
   - If "➕ Other (Type Custom Club)" is selected, enters `STATE_CUSTOM_CLUB` (validated max 50 characters).
5. **State 3 (`STATE_CATEGORY` / `STATE_CUSTOM_CATEGORY`): Category Selection:**
   - Displays 2-column inline category buttons fetched dynamically from `/api/categories/` plus `➕ Other`.
   - If "➕ Other" is selected, enters `STATE_CUSTOM_CATEGORY` (validated max 50 characters).
6. **State 4 (`STATE_DATETIME`): Date & Time Validation:**
   - Prompt: "Enter start date and time in `DD/MM/YYYY HH:MM` (24-hour clock): _Example: 15/09/2026 14:30_".
   - Validated via [`parse_event_datetime()`](file:///c:/Users/hp/Documents/Events/bot/handlers/submit.py#L135-L146) against `%d/%m/%Y %H:%M` and `%d/%m/%y %H:%M`. If invalid, re-prompts with format instructions.
7. **State 5 (`STATE_LOCATION`): Venue Input:**
   - Prompt: "Enter event venue or location description:".
   - Submitter types location.
8. **State 6 (`STATE_CONFIRM`): Structured Preview & Field Editing:**
   - Displays full structured summary with attached media info.
   - Buttons: `[✅ Confirm & Submit]`, `[✏️ Title]`, `[🏛️ Club]`, `[🏷️ Category]`, `[📅 Date & Time]`, `[📍 Location]`, `[❌ Cancel Submission]`.
   - Tapping any edit button allows single-field modification and returns directly to the confirmation screen.
9. **Final Submission & Admin Alert:**
   - Calls `POST /api/events/`. Backend sets `status='pending'`.
   - The bot notifies the designated Telegram Admin Group (`TELEGRAM_ADMIN_GROUP_ID`) with media and structured review card.
10. **Timeout & Cancel Behavior:**
    - Conversation timeout: 20 minutes (`1200` seconds).
    - `/cancel` cleanses `context.user_data` and returns to Main Menu.

### 7.2 Admin Approval and Channel Broadcast Flow ([`bot/handlers/admin.py`](file:///c:/Users/hp/Documents/Events/bot/handlers/admin.py))
1. **Admin Group Notification:**
   - [`send_admin_pending_notification()`](file:///c:/Users/hp/Documents/Events/bot/handlers/admin.py#L188-L270) posts to the private Admin Group.
   - If media exists (photo/video), it is sent with the structured card as caption.
   - Attached inline keyboard: `[✅ Approve]`, `[❌ Reject]`, `[✏️ Edit Fields]`.
2. **Approval Action (`handle_admin_approve`):**
   - Broadcasts the event to the public channel (`TELEGRAM_PUBLIC_CHANNEL_ID`) via [`broadcast_event_to_channel()`](file:///c:/Users/hp/Documents/Events/bot/handlers/admin.py#L105-L186).
   - For **forwarded submissions (`is_forwarded=True`)**, the public channel post contains **only the original forwarded media and untouched caption**.
   - For **manual submissions (`is_forwarded=False`)**, the public channel post composes a **complete formatted summary** from structured fields.
   - Captures returned Telegram `channel_message_id`.
   - Calls `PATCH /api/events/<id>/status/` with `status='approved'` and `channel_message_id`.
   - Edits the Admin Group card in place: `✅ APPROVED by <AdminName> (Channel Post #<id>)`.
   - Sends a direct Telegram message to the submitter notifying them of approval.
3. **Rejection Action (`handle_admin_reject`):**
   - Calls `PATCH /api/events/<id>/status/` with `status='rejected'`.
   - Edits Admin Group card in place: `❌ REJECTED by <AdminName>`.
   - Sends a direct Telegram message to the submitter informing them of rejection.
4. **Admin In-Place Editing & Live Channel Sync (`handle_admin_edit_field_input`):**
   - Admin taps `[✏️ Edit Fields]` → selects field (Title, Date, Location, Category, Club).
   - Admin types new value.
   - Calls `PATCH /api/events/<id>/`.
   - If the event was already published to the channel (`channel_message_id` is set), [`update_channel_message_in_place()`](file:///c:/Users/hp/Documents/Events/bot/handlers/admin.py#L272-L304) immediately updates the existing channel post in place via `edit_message_caption` or `edit_message_text`.

### 7.3 Representative Management Flow ([`bot/handlers/officers.py`](file:///c:/Users/hp/Documents/Events/bot/handlers/officers.py))
- **Add Representative:** Owner taps `[➕ Add Club Admin]` → Selects Club from interactive list → Forwards a message from the representative (or types numeric ID) → API adds ID to `Club.verified_officers` → Confirmation with all active club officers.
- **Remove Representative:** Owner taps `[➖ Remove Club Admin]` → Selects Club → Displays list of verified officers with `[🗑️ Remove ID: <id>]` buttons → One-tap removal.
- **Create Club:** Owner taps `[🏛️ Register New Club]` → Enters club name → Selects genre (`Technology`, `Academic`, `Sports`, `Arts & Culture`, `Social & Community`, `General` or types custom) → Registered via `POST /api/clubs/`.

### 7.4 Conversation State Scoping & Session Isolation
- State is scoped to `context.user_data` using isolated namespaces:
  - Submissions: `context.user_data['submission']`
  - Officer Management: `context.user_data['officer_manage']`
  - Club Creation: `context.user_data['create_club']`
  - Admin Editing: `context.user_data['admin_edit']`
- Configured with `per_chat=True`, `per_user=True`, `per_message=False`, and `allow_reentry=True` to prevent state corruption across different chats and users.

---

## 8. Roles and Permissions Matrix

| Capability | Regular Viewer | Club Representative | Moderator / Admin | Bot Owner |
|---|---|---|---|---|
| **Browse / Query Events (`/today`, `/week`, `/events`)** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Submit Event for Verified Club (`/submit`)** | ❌ Blocked | ✅ Yes (Assigned clubs) | ✅ Yes | ✅ Yes (All clubs + custom) |
| **Access Admin Approval Queue (`/pending`)** | ❌ Blocked | ❌ Blocked | ✅ Yes | ✅ Yes |
| **Approve / Reject / Edit in Admin Group** | ❌ Blocked | ❌ Blocked | ✅ Yes | ✅ Yes |
| **Edit Structured Fields via REST API** | ❌ Blocked (403) | ❌ Blocked (403) | ✅ Yes | ✅ Yes |
| **Register New Club (`/add_club`)** | ❌ Blocked | ❌ Blocked | ❌ Blocked | ✅ Yes |
| **Add / Remove Club Officers (`/add_club_admin`)** | ❌ Blocked | ❌ Blocked | ❌ Blocked | ✅ Yes |
| **Django Admin Site (`/admin/`)** | ❌ Blocked | ❌ Blocked | ✅ Staff/Superuser | ✅ Superuser |

### Enforcement Mechanics:
- **Bot Layer:** Verified against `Club.verified_officers` or `is_owner()` before entering submission or management handlers.
- **API Layer:** Evaluated via [`IsTelegramAdminUser`](file:///c:/Users/hp/Documents/Events/events/permissions.py#L45-L58) matching `X-Telegram-User-Id` against active rows in `Admin` or the `TELEGRAM_OWNER_ID` env variable.

---

## 9. Message Formatting & Localization

### 9.1 Formatting Implementation ([`bot/formatters.py`](file:///c:/Users/hp/Documents/Events/bot/formatters.py))
- **Character Escaping ([`safe_escape`](file:///c:/Users/hp/Documents/Events/bot/formatters.py#L16-L26)):** Sanitizes `\`, `*`, `_`, `` ` ``, `[` to avoid Telegram entity parsing errors.
- **Category Emojis ([`CATEGORY_EMOJIS`](file:///c:/Users/hp/Documents/Events/bot/formatters.py#L5-L13)):**
  - Academic: 🎓, Career/Workshop: 💼, Sports: ⚽, Entertainment: 🎭, Club Social: 🎉, Religious: 🕊️, Other: 📌
- **Time Formatting ([`format_time_range`](file:///c:/Users/hp/Documents/Events/bot/formatters.py#L47-L56)):** Outputs 12-hour formatted time with AM/PM (e.g. `2:00 PM – 5:30 PM`).
- **Channel Broadcast Formatting ([`format_channel_post`](file:///c:/Users/hp/Documents/Events/bot/formatters.py#L271-L350)):**
  - Forwarded events preserve the original caption intact.
  - Manual events compose a structured header with title, organizer, category, date, time, venue, recurrence, and full description.

### 9.2 Internationalization & Language Status
- **Current Language:** **100% English**.
- **i18n Readiness:** String constants and UI prompts are **hardcoded directly in Python handler files**. There is currently no `gettext`, translation catalog, or per-user language preference model.

---

## 10. Configuration and Deployment

### 10.1 Environment Variables Reference (`.env`)

| Variable Name | Required | Default / Example | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Yes (in prod) | `django-insecure-...` | Django cryptographic signing key |
| `DEBUG` | Yes | `True` | Django debug mode flag (`True`/`False`) |
| `ALLOWED_HOSTS` | Yes | `localhost,127.0.0.1` | Comma-separated list of valid host/domain names |
| `USE_SQLITE` | No | `True` | If `True`, forces SQLite (`db.sqlite3`) |
| `DATABASE_URL` | Optional | `postgresql://user:pass@host:5432/db` | PostgreSQL connection string |
| `DB_NAME` | Optional | `events_db` | PostgreSQL database name |
| `DB_USER` | Optional | `postgres` | PostgreSQL username |
| `DB_PASSWORD` | Optional | `postgres` | PostgreSQL password |
| `DB_HOST` | Optional | `localhost` | PostgreSQL host |
| `DB_PORT` | Optional | `5432` | PostgreSQL port |
| `TELEGRAM_BOT_TOKEN` | **Yes** | `123456789:ABC...` | Telegram Bot API token from `@BotFather` |
| `API_BASE_URL` | Yes | `http://127.0.0.1:8000/api` | Base URL for REST API communication |
| `TELEGRAM_ADMIN_GROUP_ID`| Yes | `-100...` | Chat ID of private Telegram Admin Group |
| `TELEGRAM_PUBLIC_CHANNEL_ID`| Yes | `-100...` or `@channel` | Telegram ID or handle of public Broadcast Channel |
| `TELEGRAM_OWNER_ID` | Yes | `123456789` | Telegram user ID of platform Owner |
| `API_REQUEST_TIMEOUT` | No | `10.0` | Timeout in seconds for HTTP API calls |
| `BOT_PAGE_SIZE` | No | `3` | Number of events displayed per page |

### 10.2 Process Execution & Architecture
The system consists of two independent processes:

1. **Django REST API Server:**
   ```bash
   python manage.py migrate
   python manage.py runserver 127.0.0.1:8000
   ```
2. **Telegram Bot Subsystem:**
   ```bash
   python run_bot.py
   ```
   - [`run_bot.py`](file:///c:/Users/hp/Documents/Events/run_bot.py) includes a built-in socket mutex ([`acquire_bot_instance_lock`](file:///c:/Users/hp/Documents/Events/run_bot.py#L13-L29) on localhost port 48199) that prevents multiple bot instances from running simultaneously and causing polling conflicts.
   - **Update Delivery:** Long **Polling** (`application.run_polling()`) with auto-reconnect and exponential retry logic. Webhooks are not configured in v1.

---

## 11. Testing

### 11.1 Test Suite Inventory
The project contains **79 automated tests** across Django and python-telegram-bot:

1. **Django Backend Tests ([`events/tests.py`](file:///c:/Users/hp/Documents/Events/events/tests.py) — 18 tests):**
   - Category, Club, Admin, and Event model creation, strings, and officer verification.
   - Status transition helpers (`approve`, `reject`, `cancel`).
   - Django admin custom actions (`approve_selected_events`, `reject_selected_events`, `cancel_selected_events`).
   - Seed data command idempotency and status coverage.
   - REST API endpoints: range filters (`today`, `week`), category filtering, pending status enforcement on POST, admin status transitions, structured field updates, unauthorized access rejection (403), officer addition/deletion.
2. **Bot Subsystem Tests ([`bot/tests/test_bot.py`](file:///c:/Users/hp/Documents/Events/bot/tests/test_bot.py) & [`bot/tests/test_submission_and_admin.py`](file:///c:/Users/hp/Documents/Events/bot/tests/test_submission_and_admin.py) — 61 tests):**
   - Formatters: categories, timestamps, single cards, today list, week list, channel posts, admin cards.
   - Keyboard builders: pagination, category grid, confirm keyboard, club picker, owner menus.
   - API client methods: async GET, POST, PATCH, DELETE operations with mock responses.
   - Submission flows: media extraction (photo, video, document, animation, audio, voice, poll, text), date parsing, authorization checks, auto-fill for single-club officers, custom club/category inputs, preview actions, timeout handling.
   - Admin moderation flows: channel broadcasting, in-place message editing, approval callbacks, rejection notifications.
   - Owner management flows: user ID extraction from forwards and numbers, club creation, officer assignment.

### 11.2 How to Run Tests
```bash
# Run all tests using virtual environment
.\.venv\Scripts\python.exe manage.py test
```
*Current test result: 79 tests run in ~1.01s, 0 failures, 0 errors.*

### 11.3 What is NOT Covered by Tests
- Real live Telegram network calls (tests use mocks and synthetic objects).
- Real PostgreSQL database concurrency under load (tests execute on SQLite in-memory).
- Webhook SSL certificate negotiation.
- Telegram media upload size exceeding Telegram limits (e.g., >50MB files).

---

## 12. Known Bugs, Fragile Areas and Technical Debt

1. **Telegram Caption Length Constraint (1024 Characters):**  
   - Telegram enforces a strict limit of 1024 characters for captions on media messages (photos, videos, documents).
   - In [`bot/formatters.py`](file:///c:/Users/hp/Documents/Events/bot/formatters.py#L271-L350), truncation logic exists, but if a forwarded message caption is near 1024 characters and structured fields are added in certain views, caption overflow can cause Telegram API errors.
2. **API Authentication Header Spoofing:**  
   - The REST API relies on `X-Telegram-User-Id` passed in plaintext over HTTP.
   - While intended for internal bot-to-API communication on `localhost`, if the API is exposed publicly without a shared secret header or network boundary (e.g. firewall/reverse proxy), an external client could spoof any admin `telegram_id`.
3. **Hardcoded User Strings (No i18n):**  
   - All bot replies, prompts, error notices, and date formats are hardcoded in English. Adding Amharic will require extracting all user-facing strings into translation catalogs.
4. **PTB Warning regarding `per_message=False`:**  
   - Console logs output a warning regarding `CallbackQueryHandler` tracking when `per_message=False` in `ConversationHandler`. While functional, aligning with PTB best practices will prevent state tracking edge cases.
5. **No Database Cleanup for Past Events:**  
   - Past events remain in the database indefinitely. While `/today` and `/week` filter by date range, a background job or archival status is needed for high-volume deployments.
6. **Lack of Background Job Queue:**  
   - Everything currently runs synchronously inside the bot's async loop. If the public channel post or multiple DM notifications experience network delays, the handler awaits sequentially.

---

## 13. Gaps Against Planning Documents (SDD & Checklist)

| Planned Item | SDD / Checklist Spec | Actual Implementation Status | Variance / Notes |
|---|---|---|---|
| **Phase 1: Core Models & Admin** | Club, Category, Event, Admin | **Implemented** | Identical to spec. Includes additional `custom_club` and `custom_category` fields for unlisted organizers. |
| **Phase 2: REST API (DRF)** | Filtered list, create, status, field updates, officer management | **Implemented** | Fully matches spec with `IsTelegramAdminUser` permission checks. |
| **Phase 3: Bot Viewing** | `/start`, `/today`, `/week`, `/events`, pagination | **Implemented** | Fully matches spec with interactive inline grids and safe Markdown rendering. |
| **Phase 4: Bot Submission & Admin** | Forward/manual submit, admin group moderation, channel broadcast, in-place edit, officer management | **Implemented** | Matches spec. Added single-club auto-fill and single-field preview editing. |
| **Phase 5: Subscriptions & Reminders** | `Subscription` model, `/subscribe`, `/unsubscribe`, weekly digest, event reminders | **Not Started** | Deferred as planned for post-v1. |
| **Phase 6: Web Frontend** | Public web portal, club profile pages, calendar export | **Not Started** | Deferred as planned for post-v1. |

---

## 14. Scope Expansion Readiness: All Student Programs & Opportunities

The project needs to expand from purely physical campus events to **all student-relevant programs**: seminars, webinars, registration deadlines, scholarships, internships, competitions, and general announcements.

### 14.1 Detailed Impact Analysis by Feature

#### (a) Items with a Deadline instead of a Start Time (e.g., Scholarships, Competitions, Registrations)
- **Model Changes ([`events/models.py`](file:///c:/Users/hp/Documents/Events/events/models.py)):**
  - Add `is_deadline = models.BooleanField(default=False)`.
  - Add `deadline_datetime = models.DateTimeField(null=True, blank=True, db_index=True)`.
  - Make `start_datetime` nullable (`null=True, blank=True`).
- **Serializer & API Changes ([`events/serializers.py`](file:///c:/Users/hp/Documents/Events/events/serializers.py), [`events/views.py`](file:///c:/Users/hp/Documents/Events/events/views.py)):**
  - Update `EventSerializer`, `EventCreateSerializer`, and `EventStructuredFieldsUpdateSerializer` to expose `is_deadline` and `deadline_datetime`.
  - Update `EventListCreateView.get_queryset` date range filters (`today`, `week`) to evaluate `deadline_datetime` when `is_deadline=True`.
- **Bot Handlers & Formatters ([`bot/handlers/submit.py`](file:///c:/Users/hp/Documents/Events/bot/handlers/submit.py), [`bot/formatters.py`](file:///c:/Users/hp/Documents/Events/bot/formatters.py)):**
  - Submission wizard: add prompt asking "Is this an event with a start time or an opportunity with an application deadline?".
  - Formatters: render `⏰ Deadline: <Date>` with ⏳ emoji instead of `📅 Date: ... ⏰ Time: ...`.
- **Effort:** **Low-Medium (1-2 days)**. **Risk:** **Low** (Backwards compatible with default `is_deadline=False`).

#### (b) Online Items with No Physical Location and External Link (Webinars, Virtual Info Sessions)
- **Model Changes ([`events/models.py`](file:///c:/Users/hp/Documents/Events/events/models.py)):**
  - Add `is_online = models.BooleanField(default=False)`.
  - Add `link_url = models.URLField(max_length=500, blank=True, default='')`.
  - Make `location` optional (`blank=True, default=''`).
- **Serializer & API Changes:** Expose `is_online` and `link_url` in serializers.
- **Bot Handlers & Formatters:**
  - Submission wizard: location prompt offers `[🌐 Online / Virtual]` button. If chosen, prompts for meeting/application URL (Google Meet, Zoom, Telegram link, portal).
  - Formatters: render `🌐 Online: [Join Meeting / Apply Here](link)` instead of `📍 Location: ...`.
- **Effort:** **Low (1 day)**. **Risk:** **Very Low**.

#### (c) Program Type Field (`event` / `opportunity` / `announcement`)
- **Model Changes ([`events/models.py`](file:///c:/Users/hp/Documents/Events/events/models.py)):**
  - Add `ProgramType` enum (`EVENT = 'event'`, `OPPORTUNITY = 'opportunity'`, `ANNOUNCEMENT = 'announcement'`).
  - Add `program_type = models.CharField(max_length=20, choices=ProgramType.choices, default=ProgramType.EVENT, db_index=True)`.
- **Serializer & API Changes:**
  - Expose `program_type` and add query parameter `?type=event|opportunity|announcement` to `GET /api/events/`.
- **Bot Handlers & Menus ([`bot/handlers/start.py`](file:///c:/Users/hp/Documents/Events/bot/handlers/start.py), [`bot/pagination.py`](file:///c:/Users/hp/Documents/Events/bot/pagination.py)):**
  - Main menu buttons: `[📅 Events]`, `[💼 Opportunities]`, `[📢 Announcements]`.
- **Effort:** **Medium (2 days)**. **Risk:** **Low**.

#### (d) Bilingual Interface (Amharic + English) with Per-User Language Setting
- **Model Changes:**
  - Create `UserProfile` model: `telegram_id = BigIntegerField(unique=True)`, `language = CharField(max_length=5, default='en', choices=[('en', 'English'), ('am', 'Amharic')])`.
  - Optional: add `title_am`, `description_am` fields on `Event` for bilingual broadcasts.
- **Bot Architecture Changes:**
  - Create centralized dictionary/strings catalog (`bot/locales/en.json`, `bot/locales/am.json`) with string helper `get_text(key, lang)`.
  - Add `/language` command and language picker buttons on `/start`.
  - Store language preference in `context.user_data['lang']` and persist to `UserProfile`.
- **Effort:** **High (3-4 days)**. **Risk:** **Medium** (requires touching all formatting strings and prompt messages).

#### (e) "Closing Soon / Deadlines" View (`/deadlines`)
- **API Changes ([`events/views.py`](file:///c:/Users/hp/Documents/Events/events/views.py)):**
  - Support `GET /api/events/?range=deadlines` or `?is_deadline=true&ordering=deadline_datetime`.
  - Returns active opportunities sorted by nearest deadline.
- **Bot Handlers & Formatting ([`bot/handlers/deadlines.py`](file:///c:/Users/hp/Documents/Events/bot/handlers/), [`bot/formatters.py`](file:///c:/Users/hp/Documents/Events/bot/formatters.py)):**
  - Command `/deadlines` and menu button `[⏳ Closing Soon / Deadlines]`.
  - Renders urgency badges: `🔴 Today`, `🟠 Tomorrow`, `🟡 In 3 Days`, `🟢 Next Week`.
- **Effort:** **Low-Medium (1-2 days)**. **Risk:** **Low**.

---

## 15. Suggested Next Steps & Engineering Roadmap

### Priority 1: High-Impact Program Scope Expansion (Immediate)
1. **Implement `program_type` (`event`, `opportunity`, `announcement`) and `is_deadline`**:
   - Allows ASTU students to track hackathon application deadlines, scholarship applications, internship openings, and urgent campus notices.
2. **Support Online Events (`is_online` & `link_url`)**:
   - Crucial for virtual workshops, webinars, and tech meetups.

### Priority 2: Security & Architecture Hardening
1. **API Shared Secret Token**:
   - Add a shared header secret (e.g. `X-Hub-Internal-Secret`) between `api_client.py` and Django middleware so that the DRF API cannot be accessed or manipulated by unauthorized local processes.
2. **Move to PostgreSQL for Production**:
   - Switch `.env` to `USE_SQLITE=False` and configure managed PostgreSQL with connection pooling.

### Priority 3: User Engagement & Retention (Phase 5)
1. **Bilingual Support (English + Amharic)**:
   - Implement `/language` selection to make the bot accessible to all students across campus.
2. **Subscriptions & Instant Notification Pipeline (`/subscribe`)**:
   - Allow students to subscribe to their favorite clubs (e.g. Software Development Club, Athletics) or categories (Tech, Sports) to receive instant notifications upon event approval.
3. **Closing Soon Digest (`/deadlines`)**:
   - Weekly summary of upcoming application deadlines broadcast every Sunday evening.

---

## 16. Security & Stability Hardening Round Summary

A dedicated hardening round was executed across both Django backend and python-telegram-bot subsystems:

1. **Timezone Standardization (`Africa/Addis_Ababa` / UTC+3)**:
   - Configured `TIME_ZONE = 'Africa/Addis_Ababa'` with `USE_TZ = True` in `events_hub/settings.py`.
   - Updated `parse_event_datetime` to interpret user inputs strictly in Addis Ababa local time with +03:00 ISO timestamps.
   - Ensured `/today` and `/week` queries and formatters compute day boundaries in local Addis Ababa time (`timezone.localtime(timezone.now())`).
   - Added tests for midnight boundaries (23:30 local time today vs. 00:30 local time tomorrow).

2. **API Shared Secret & Identity Hardening**:
   - Implemented `InternalApiSecretMiddleware` enforcing `INTERNAL_API_SECRET` (`X-Hub-Internal-Secret` header) across all `/api/` endpoints (rejects with HTTP 403 if missing or invalid).
   - Enforced single identity standard: only trusted `X-Telegram-User-Id` header is used for user authorization. Removed legacy `telegram_admin_id` query parameters and alternate header keys.
   - Enforced submitter authorization on `POST /api/events/` (denying unauthorized non-officers/non-admins with HTTP 403).

3. **Robust Handling of Stray Messages & Forwards**:
   - Forwards and media received outside an active session now safely prompt the user (friendly hint for verified representatives; polite menu hint for general users).
   - In "Add Club Admin", protected against forward privacy (`hidden_user` / channel posts) with clear instructions to provide numeric Telegram IDs manually.

4. **Preservation of Long Captions (>1024 / >4096 chars)**:
   - Fixed media caption truncations: media items with captions >1024 chars are posted with a short title header and the full un-truncated text is sent as a follow-up reply message.
   - Subsystem stores `channel_extra_message_id` for accurate in-place updates. Messages >4096 chars are split into 4096-char chunks.

5. **Direct Publish Pipeline for Bot Owner & Admins**:
   - Submissions made by the bot owner or active admins are automatically saved as `status='approved'` (skipping the approval queue).
   - The bot immediately broadcasts the event to the public channel, logs a one-line info message to the Admin Group (`📢 Event [Title] posted directly by [Admin Name / Owner].`), and indicates Direct Publish mode in the preview screen.
   - Normal club representatives continue through the standard approval queue (`status='pending'`).

6. **Cleanups & University Branding**:
   - Filtered Python Telegram Bot `per_message=False` UserWarnings cleanly across all conversation handlers.
   - Replaced all university branding with "Addis Ababa Science and Technology University (AASTU)" / "AASTU".

---

*Report compiled directly from workspace source code analysis.*  
*Artifact saved at [`Docs/PROJECT_REPORT.md`](file:///c:/Users/hp/Documents/Events/Docs/PROJECT_REPORT.md).*
