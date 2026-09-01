# Software Design Document (SDD)
## University Events Hub — ASTU

---

## 1. Overview

A Telegram bot + Django backend that aggregates all university events (club events, sports, entertainment, academic, etc.) into one searchable, always-current source, with a public broadcast channel and structured `/today` / `/week` querying. A public web frontend is planned but deferred to a later phase.

---

## 2. Goals

- Single source of truth for "what's happening at ASTU this week."
- Zero-friction access via Telegram (channel to scroll, bot to query).
- Simple, low-overhead approval pipeline so event quality/trust stays high.
- Architecture that lets a web frontend be added later without rework.

## 3. Non-Goals (v1)

- No public web frontend yet.
- No payments/ticketing.
- No native mobile app.
- No automatic natural-language parsing of dates from free text (structured input requested explicitly instead).

---

## 4. User Roles

| Role | Description | Capabilities |
|---|---|---|
| Viewer | Any student, no login | View channel, use bot query commands |
| Organizer | Verified club officer | Submit events (forward or direct), edit own pending submissions |
| Admin | Trusted small team | Approve/reject/edit any submission, manage clubs/categories |

---

## 5. System Architecture

```
PostgreSQL  ⇄  Django + DRF (models, REST API, Django admin)  ⇄  Telegram Bot (separate process)
                                                                     │
                                                        Public Channel / Admin Group / DMs
```

- **Django + Django REST Framework**: single backend. All clients (bot now, web later) talk to the same API.
- **PostgreSQL**: primary datastore; supports efficient date-range queries.
- **Telegram Bot** (python-telegram-bot or aiogram): stateless-ish client process, calls the REST API, never touches the DB directly.
- **Celery + Redis** (or cron for v1): scheduled jobs — weekly digest, event expiry, reminders (v2).

---

## 6. Data Model

### Club
- `id`, `name`, `category_type`, `verified_officers` (list of Telegram user IDs), `contact_info`

### Category
- `id`, `name` (Club Social, Sports, Academic, Entertainment, Career/Workshop, Religious, Other)

### Event
- `id`
- `club` (FK → Club)
- `category` (FK → Category)
- `title` (short, entered or derived)
- `raw_content`: forwarded media `file_id`(s) + original caption text — shown as-is in the channel post
- `start_datetime`, `end_datetime` (nullable)
- `location` (text)
- `status`: `pending` / `approved` / `rejected` / `cancelled`
- `recurring` (bool), `recurrence_pattern` (nullable)
- `channel_message_id` (nullable — set once posted, enables in-place edits)
- `submitted_at`, `approved_at`, `approved_by`

### Admin
- `telegram_id`, `permission_level`

### Subscription *(v2)*
- `telegram_id`, `category` or `club` FK, `reminder_enabled`

---

## 7. Core Flows

### 7.1 Submission
1. Organizer forwards a post (photo/video + caption) or sends content directly to the bot.
2. Bot stores raw content unmodified.
3. Bot asks only for missing structured fields: category, exact start date/time (fixed format), location, club (auto-filled if unambiguous).
4. Bot shows a full preview; organizer confirms.
5. Event created with `status = pending`.

### 7.2 Approval
1. New pending event triggers a message in the **admin group** with inline buttons: Approve / Reject / Edit.
2. Approve → `status = approved`, API call posts formatted content to the **public channel**, stores `channel_message_id`.
3. Reject → organizer notified, optional reason.
4. Edit → bot walks the admin through updating structured fields.
5. Any later edit to an approved event → bot edits the channel message in place using `channel_message_id`.
6. Django admin available as a secondary tool for bulk edits/debugging.

### 7.3 Viewing
- `/today`, `/week`, `/events <category>` — bot queries the API and returns formatted results with inline navigation.
- Public channel — passive scroll feed of all approved events, always current via auto-edit.

---

## 8. API Endpoints (draft)

- `GET /api/events/?range=today|week&category=`
- `POST /api/events/` (create submission — pending)
- `PATCH /api/events/{id}/status` (approve/reject/cancel)
- `PATCH /api/events/{id}` (edit structured fields)
- `GET /api/clubs/`
- `POST /api/clubs/{id}/officers` (admin-managed verification)

---

## 9. Open Items

- Fixed date/time input format for organizers (e.g. `DD/MM/YYYY HH:MM`).
- Officer verification process (manual, off-bot conversation with admin team for v1).
- Past-event handling: auto-hide from `/today`/`/week`, retained in DB.
- Large video handling: prefer re-sending via Telegram `file_id` to avoid bot download size limits.

---

## 10. Future (Post-v1)

- Public web frontend (browsable/searchable, club pages, calendar export) — same API, new client.
- Subscriptions & reminders.
- Weekly digest broadcast.
- Conflict detection (overlapping time/location).
- Analytics for organizers.
- Amharic/English toggle.
