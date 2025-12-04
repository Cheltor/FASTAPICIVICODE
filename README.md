# CiviCode API

FastAPI + SQLAlchemy backend that powers the CiviCode/CodeSoft municipal code-enforcement platform. It exposes RESTful endpoints for addresses, inspections, violations, licensing, permits, notifications, admin chat, document generation, and resident-facing submissions while orchestrating Azure Blob Storage, SendGrid, and OpenAI integrations.

## Stack At A Glance

| Area | Technology |
| --- | --- |
| Web framework | FastAPI (lifespan events, dependency injection, automatic OpenAPI docs) |
| Persistence | SQLAlchemy ORM + Alembic migrations backed by PostgreSQL (Heroku-style `DATABASE_URL`) |
| Auth | First-party JWT bearer tokens (`/login`) shared with the React frontend; roles stored on `User.role` |
| Storage | Azure Blob Storage for photos/videos/docs (`storage.py`, `media_service.py`, `ActiveStorage*` tables) |
| Email | SendGrid transactional email with feature flag + per-user test overrides (`email_service.py`) |
| Documents | `docxtpl` templates for violation notices, compliance letters, and license PDFs (`routes/word_templates.py`) |
| AI Assistant | OpenAI Assistants API via `genai_client.py` with chat logs persisted in `ChatLog` + SSE toggle |
| Background | Server-Sent Events for settings pushes (`/settings/stream`), media normalization via Pillow/FFmpeg |

## Repository Layout

```text
FastAPI/
├─ CiviCodeAPI/
│  ├─ main.py                # FastAPI app, router wiring, CORS config
│  ├─ models.py / schemas.py # SQLAlchemy models + Pydantic response/request models
│  ├─ routes/                # Feature routers (addresses, inspections, permits, chat, etc.)
│  ├─ email_service.py       # SendGrid helper + password reset templates
│  ├─ storage.py             # Lazy Azure Blob client initialization
│  ├─ media_service.py       # HEIC/MOV → browser-safe conversions (Pillow + FFmpeg)
│  ├─ genai_client.py        # OpenAI assistant wrapper with thread management
│  ├─ settings_broadcast.py  # Async broadcaster for SSE consumers
│  ├─ sdat_client.py         # Maryland SDAT owner lookup scraper
│  ├─ templates/*.docx       # Merge templates for notices/licenses
│  ├─ maintenance/           # One-off scripts (e.g., HEIC backfill)
│  └─ tests/                 # Pytest suite + dependency overrides
├─ alembic/                  # Migration environment + versions
├─ requirements.txt
├─ Procfile                  # `uvicorn CiviCodeAPI.main:app …` for Heroku/Aptible
├─ Aptfile                   # Extra system packages (FFmpeg for MOV transcoding)
└─ .env*, .env.development   # Environment variable samples (never commit secrets)
```

OpenAPI documentation is available at `/docs` (Swagger UI) and `/redoc` when the server is running.

## Getting Started

1. **Install Python dependencies**
   ```bash
   cd FastAPI
   python -m venv venv
   source venv/Scripts/activate        # on Windows use venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. **Configure environment variables**
   - Copy `.env.development` → `.env` and populate secrets (see table below).
   - For local Postgres defaults, `database.py` falls back to `postgresql://rchelton:password@localhost:5433/codeenforcement_development`.
3. **Run migrations**
   ```bash
   alembic upgrade head
   ```
4. **Start the API**
   ```bash
   uvicorn CiviCodeAPI.main:app --host 0.0.0.0 --port 8000 --reload
   ```
5. **Hit it from the React app**
   - Point `REACT_APP_API_URL` at `http://localhost:8000`.

### Key Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` / `HEROKU_DATABASE_URL` | Primary Postgres connection string (SQLAlchemy URI). |
| `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_CONTAINER_NAME` | Blob storage for uploads, converted media, and generated documents. |
| `EMAIL_ENABLED`, `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, `TEST_EMAIL_USER_ID`, `FRONTEND_BASE_URL` | SendGrid email + optional override/test routing; `FRONTEND_BASE_URL` used in password reset links. |
| `OPENAI_API_KEY`, `OPENAI_ASSISTANT_ID` | Credentials for the admin-facing AI assistant. |
| `GOOGLE_API_KEY`, `RECAPTCHA_SECRET_KEY` | Optional integrations for geocoding or resident concern validation (present in `.env`, wire up as needed). |
| `AZURE_*`, `GOOGLE_*`, `OPENAI_*`, `SENDGRID_*` | Loaded automatically via `dotenv` in `main.py`/`database.py`. |
| `EMAIL_ENABLED`, `TEST_EMAIL_USER_ID` | Feature flag & per-env routing for notifications/test emails. |
| `WEB_PUSH_VAPID_PUBLIC_KEY`, `WEB_PUSH_VAPID_PRIVATE_KEY`, `WEB_PUSH_VAPID_CONTACT` | Browser push credentials (VAPID) used by `pywebpush` + the React PWA to send desktop notifications. |

> **Security:** Never commit `.env` files. Rotate the shared `SECRET_KEY` (currently hard-coded in several routers) when deploying to production—frontend JWTs must be updated to match.

## Domain Overview

`models.py` contains the authoritative schema. Highlights:

- **Core records:** `Address`, `Unit`, `Contact`, `Business`, `Inspection`, `Violation`, `Citation`, `Permit`, `License`, `Complaint`, each with created/updated metadata and relationships used for eager loading.
- **Comments & Attachments:** `Comment`, `ContactComment`, `ViolationComment`, `ActiveStorageAttachment`, `ActiveStorageBlob` capture per-entity notes + Azure blob metadata. `media_service.ensure_blob_browser_safe` normalizes HEIC/MOV uploads to JPEG/MP4.
- **Notifications & Settings:** `Notification`, `PushSubscription`, `AppSetting`, `AppSettingAudit`, and `ChatLog` track inbox updates, registered browser endpoints, chat toggle history, and OpenAI transcripts.
- **Aux tables:** `Observation`, `ObservationCode`, `UnitArea`, `Room`, etc., powering detailed inspection workflows.

Use Alembic (`alembic revision --autogenerate -m "…"`) when adding or altering models.

## Router Breakdown

| Module | Responsibility |
| --- | --- |
| `routes/addresses.py` | CRUD for addresses, contact associations, SDAT owner refresh, vacancy filters, Azure-hosted attachments. |
| `routes/inspections.py` | End-to-end inspection lifecycle (units/areas/rooms, observations, scheduling, attachments, potential observation counts). |
| `routes/violations.py`, `routes/citations.py`, `routes/codes.py`, `routes/codes_sync_mvp.py` | Compliance management, linking violations to code sections, and synchronizing external code catalogs. |
| `routes/licenses.py`, `routes/permits.py`, `routes/businesses.py` | License/permit issuance, renewal data, and business registry with closure tracking. |
| `routes/comments.py`, `routes/contacts.py`, `routes/users.py` | Comment threads with attachments, contact CRUD/deduplication, user authentication/profile updates. |
| `routes/dashboard.py`, `routes/sir.py` | Aggregate metrics for the dashboard + SIR (complaint/inspection/violation) stats. |
| `routes/notifications.py` | User inbox, read/unread endpoints, SendGrid fan-out, “test email” utility for admins. |
| `routes/push_subscriptions.py` | Register/list/remove browser push endpoints (VAPID) tied to the authenticated user. |
| `routes/assistant.py`, `routes/settings.py` | OpenAI assistant proxy, chat log export, chat-enabled toggle, and `/settings/stream` SSE feed. |
| `routes/word_templates.py` | DOCX generation for violation notices, compliance letters, and FY26 license certificates using `docxtpl`. |

Authentication is enforced via OAuth2 password flow (`/login`). Routes that mutate critical data often re-check roles (admin = `User.role == 3`). `CORS` is fully open in `main.py`; lock this down for production.

## Media & Storage

- Upload metadata lives in `ActiveStorage*` tables; actual bytes land in the configured Azure container.
- `media_service.py` converts HEIC/HEIF images to JPEG and QuickTime `.mov` video to MP4 + poster frames using FFmpeg (installed via `Aptfile` for Heroku dynos).
- `maintenance/backfill_heic_to_jpeg.py` batch-converts historical blobs (`--apply`, `--limit`, `--delete-old` flags).
- `storage.py` lazily instantiates `BlobServiceClient`, avoiding crashes when env vars are missing during tests.

## Email, Notifications, and Chat

- `email_service.py` centralizes SendGrid usage with HTML templates for notifications and password resets.
- `/notifications/test-email` replays the most recent notification to the current (or `TEST_EMAIL_USER_ID`) user—surfaced in the React dashboard.
- `/push-subscriptions` lets the PWA register or revoke browser endpoints; `WEB_PUSH_VAPID_*` env vars must be present for delivery.
- `/notifications/test-push` triggers a web push to the caller (requires at least one saved subscription).
- `/settings/chat` toggles the in-app assistant for all users, persisting audits and notifying browsers via `settings_broadcast.Broadcaster` + `/settings/stream`.
- `/chat` proxies messages to the configured OpenAI Assistant, persists `ChatLog` rows, and returns thread IDs so clients can continue conversations.

## Document Generation

`routes/word_templates.py` renders DOCX templates located in `CiviCodeAPI/templates/` using `docxtpl`. Templates cover:

- Violation notices + compliance letters (owner + address mail merge)
- FY26 Business License, Conditional SFR License, Multifamily License certificates

Extend by dropping new `.docx` files into `templates/` and adding matching endpoints.

## Testing

- Run `pytest` from the `FastAPI/` root. The suite lives in `CiviCodeAPI/tests/` and automatically overrides `get_db` with an in-memory SQLite (or `TEST_DATABASE_URL`) engine.
- Fixtures (`conftest.py`) create/drop the schema on startup and ensure deterministic primary keys for SQLite.
- Current coverage focuses on inspections, permits, password reset, and settings/chat flows. Add new tests alongside feature routers.

```bash
TEST_DATABASE_URL=sqlite:///./test.db pytest -q
```

## Deployment Notes

- **Process types:** `Procfile` runs `uvicorn CiviCodeAPI.main:app` from the API folder. Include `release: alembic upgrade head` if you need auto-migrations.
- **System packages:** Add OS-level dependencies (currently just `ffmpeg`) via `Aptfile` for Heroku/Render.
- **Static files:** Not served here—React handles the UI. Ensure `FRONTEND_BASE_URL` reflects the deployed frontend so email links work.
- **Long-lived connections:** `/settings/stream` sends heartbeat comments every 25s to survive Heroku’s idle timeout; reverse proxies should allow SSE.
- **Secrets:** Configure all env vars via your platform (Heroku config vars, Docker secrets, etc.). Remove plaintext secrets from `.env` before sharing.

## Maintenance & Troubleshooting

- **New schema fields:** update `models.py`, `schemas.py`, generate an Alembic revision, run tests, and update both frontend and backend DTOs as needed.
- **Media conversion queue:** If browsers can’t display attachments, run `python -m CiviCodeAPI.maintenance.backfill_heic_to_jpeg --apply --limit 100`.
- **Chat issues:** Verify `OPENAI_API_KEY`/`OPENAI_ASSISTANT_ID`, confirm `/settings/chat` returns `enabled: true`, and tail logs for OpenAI errors in `genai_client`.
- **Notification emails missing:** Ensure `EMAIL_ENABLED=true`, `SENDGRID_API_KEY` is valid, and check the SendGrid activity feed.
- **Resident concern spam:** When enabling reCAPTCHA, wire the `RECAPTCHA_SECRET_KEY` into the appropriate route (placeholder env already exists).

---

Need a starting point? Review `CiviCodeAPI/main.py` to see router registration, then dive into the relevant `routes/*.py` file alongside the matching React component (e.g., `routes/inspections.py` ↔ `src/Components/Inspection/*`). Update this README whenever you introduce new integrations, environment variables, or feature routers so the backend remains easy for future contributors to navigate.
