# Agent Prompts
## University Events Hub — ASTU (for use with Antigravity)

Use these as starting prompts per phase. Paste the relevant SDD section and checklist items alongside each prompt for full context.

---

## Phase 1 — Core Data & Admin

```
You are building the backend foundation for a Django project called "University Events Hub."
Reference the attached SDD.md (sections 5-6) for architecture and data model.

Set up:
1. A Django project connected to PostgreSQL.
2. Models: Club, Category, Event, Admin — exactly as specified in SDD.md section 6,
   including the raw_content vs structured_fields split on Event (this distinction matters:
   raw_content stores forwarded media file_id(s) + original caption as-is; structured_fields
   are the queryable fields like start_datetime, location, category).
3. Register all models in Django admin with useful list_display and list_filter
   (especially filtering Event by status, for the approval queue).
4. Seed a management command or fixture with 2-3 sample clubs and a handful of events
   across pending/approved/rejected statuses for testing.

Follow Django best practices for model field choices (use TextChoices for status/category
where appropriate, proper FK relationships, sensible db_index on start_datetime).
```

---

## Phase 2 — REST API (DRF)

```
Continue the "University Events Hub" Django project. Reference SDD.md section 8 for the
API contract.

Add Django REST Framework and implement:
- GET /api/events/?range=today|week&category=<id> — filtered by date range and optional category
- POST /api/events/ — creates an Event with status=pending
- PATCH /api/events/{id}/status — admin-only, transitions status (approve/reject/cancel)
- PATCH /api/events/{id} — admin-only, edits structured fields
- GET /api/clubs/
- POST /api/clubs/{id}/officers — admin-only, adds a verified officer Telegram ID to a club

Add permission classes so status-changing and officer-management endpoints require
admin-level access (check against the Admin model, not Django's built-in superuser only).
Write DRF serializers that expose raw_content and structured fields separately, matching
the Event model split. Include basic tests for each endpoint (happy path + permission denial).
```

---

## Phase 3 — Telegram Bot v1 (Viewing)

```
Build the first version of the "University Events Hub" Telegram bot, as a separate
process/service from the Django backend, calling its REST API (see SDD.md sections 5, 7.3, 8).
Use python-telegram-bot (or aiogram if you prefer async-first).

Implement:
- /start — welcome message with a short list of available commands
- /today — calls GET /api/events/?range=today, formats results (title, time, location, category)
- /week — same but range=week, grouped by day
- /events <category> — inline category picker if no argument given, then filtered listing
- Pagination or "next page" inline buttons if a day/week has many events

Keep formatting logic in a shared function so it can be reused later for channel auto-posting.
The bot should only ever talk to the Django API — never touch the database directly.
```

---

## Phase 4 — Telegram Bot v2 (Submission + Admin Flow)

```
Extend the "University Events Hub" bot with submission and admin approval flows.
Reference SDD.md sections 7.1 and 7.2 closely — the flow must support forwarded posts,
not just structured form-filling.

Submission flow:
1. Detect when a user forwards a message (photo/video + caption) or sends content directly.
2. Store the raw content (file_id(s) + caption) as-is — do not attempt to parse or reformat it.
3. Ask only for missing structured fields: category (inline buttons), exact start date/time
   (require a fixed format like DD/MM/YYYY HH:MM, validate and re-prompt on bad input),
   location (free text), and club (auto-select if the sender is a verified officer for
   exactly one club, otherwise offer a picker).
4. Show a full preview (raw content + structured fields) and require explicit confirmation
   before submitting.
5. On confirm, POST to /api/events/.

Admin approval flow:
1. On new pending submission, post a formatted message to a designated admin group chat
   with inline buttons: Approve / Reject / Edit.
2. Approve → PATCH status to approved, then post the formatted event (raw content +
   structured details) to the public channel, and store the returned channel message ID
   back on the Event via the API.
3. Reject → notify the submitting organizer, optionally prompting the admin for a reason first.
4. Edit → walk the admin through updating structured fields before approval.
5. If an already-approved event's details are edited later, edit the existing channel
   message in place using its stored channel_message_id — do not post a duplicate.

Add an admin-only command for managing verified officers per club (add/remove Telegram IDs).
```

---

## Phase 5 — Engagement Features

```
Add subscription and reminder features to the "University Events Hub" bot and backend.

Backend: add a Subscription model (telegram_id, category or club FK, reminder_enabled) and
matching API endpoints for create/delete.

Bot:
- /subscribe <category|club> and /unsubscribe commands
- On new approved event, notify subscribers matching that category/club
- A scheduled job (Celery beat or cron) that sends a weekly digest every Sunday evening to
  all subscribers, summarizing the week ahead
- A scheduled reminder job that notifies users shortly before an event they've
  saved/subscribed to starts
- Add a "🔔 Remind me" inline button to channel posts that deep-links into the bot
  (using a start parameter) to subscribe the user to that specific event
```

---

## Phase 6 — Web Frontend (Later)

```
Build a public web frontend for "University Events Hub" on top of the existing Django REST
API (do not duplicate backend logic — this is purely a new client).

Scope for v1 of the frontend:
- Today / This Week / This Month views, matching the bot's data via the same API endpoints
- Filter by category and club, keyword search
- Event detail page showing raw content (media, caption) plus structured details
- Club profile pages listing upcoming/past events for that club
- Calendar export (iCal) for individual events

Keep this fully decoupled from the bot — both are just clients of the same Django API.
```
