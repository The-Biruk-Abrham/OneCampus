# Task Checklist
## University Events Hub — ASTU

---

## Phase 1 — Core Data & Admin

- [x] Set up Django project + PostgreSQL connection
- [x] Create `Club` model (name, category_type, verified_officers, contact_info)
- [x] Create `Category` model + seed default categories
- [x] Create `Event` model (raw_content fields, structured fields, status, recurring, channel_message_id, timestamps)
- [x] Create `Admin` model (telegram_id, permission_level)
- [x] Register all models in Django admin
- [x] Configure Django admin list views/filters for the approval queue (filter by status)
- [x] Seed test data: 2-3 clubs, a handful of sample events in each status
- [x] Write basic model tests (Event status transitions, required fields)

## Phase 2 — REST API (DRF)

- [x] Install & configure Django REST Framework
- [x] Serializers: Event, Club, Category
- [x] `GET /api/events/?range=today|week&category=` — filtered listing
- [x] `POST /api/events/` — create submission (status=pending)
- [x] `PATCH /api/events/{id}/status` — approve/reject/cancel
- [x] `PATCH /api/events/{id}` — edit structured fields
- [x] `GET /api/clubs/` — list clubs
- [x] `POST /api/clubs/{id}/officers` — admin adds verified officer
- [x] Add basic auth/permission checks (admin-only actions restricted)
- [x] Write API tests for each endpoint

## Phase 3 — Bot v1 (Viewing)

- [x] Set up bot project (python-telegram-bot or aiogram), connect to API base URL
- [x] `/start` — welcome + help message
- [x] `/today` — fetch & format today's events
- [x] `/week` — fetch & format this week's events
- [x] `/events <category>` — filtered listing with inline category buttons
- [x] Inline "next/prev day" or pagination for longer lists
- [x] Auto-post formatting function (shared by channel-post logic later)
- [x] Deploy bot to a always-on host (test with polling first, webhook later if needed)

## Phase 4 — Bot v2 (Submission + Admin Flow)

- [x] Detect forwarded messages (photo/video + caption) vs. direct text
- [x] Store raw_content (file_id + caption) on submission start
- [x] Guided follow-up: category (inline buttons), date/time (fixed format prompt + validation), location (text), club (auto-fill if single verified club, else select)
- [x] Submission preview + confirm step
- [x] POST to `/api/events/` on confirm
- [x] Admin group notification with Approve / Reject / Edit inline buttons
- [x] Approve handler → PATCH status, post to public channel, store channel_message_id
- [x] Reject handler → notify organizer, optional reason prompt
- [x] Edit handler → walk through structured field updates
- [x] Edit-after-approval → auto-edit the existing channel message via channel_message_id
- [x] Officer verification: admin command to add/remove verified officers for a club

## Phase 5 — Engagement Features

- [ ] `Subscription` model + migrations
- [ ] `/subscribe <category|club>` command
- [ ] `/unsubscribe` command
- [ ] Notification job: new approved event → notify relevant subscribers
- [ ] Weekly digest job (Celery beat or cron) — Sunday evening summary to subscribers
- [ ] Reminder job — notify before saved/subscribed events start
- [ ] "🔔 Remind me" inline button on channel posts, deep-linking into the bot

## Phase 6 — Web Frontend (Later, Once There's Usage)

- [ ] Decide frontend approach (Django templates vs. separate React app) once needed
- [ ] Public views: today/week/month, search, filter by category/club
- [ ] Event detail page
- [ ] Club profile pages
- [ ] Calendar export (iCal/Google Calendar)
- [ ] Optional: conflict detection UI, analytics dashboard for organizers
