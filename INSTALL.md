# AI Agent Installation & Execution Guide (`INSTALL.md`)

This guide is specifically structured for **AI Coding Agents** (Claude Code, Cursor, Codex, Windsurf, Antigravity, etc.) and developers automating the deployment of **Telegram Channel Admin**.

---

## 1. System Overview

This project is an asynchronous microservice system running in Docker containers:
- **`db`**: PostgreSQL 15 (stores posts, moderation logs, deduplication hashes, and settings).
- **`redis`**: Redis 7 (task queue managed via Arq and caching).
- **`migrator`**: One-off Alembic runner (`alembic upgrade head`) ensuring schema migrations.
- **`parser`**: Telethon Userbot capturing posts from donor channels into DB & Redis queue.
- **`worker`**: Arq background worker performing AI deduplication, ad filtering, and rewrites.
- **`bot`**: aiogram 3 Telegram bot providing the interactive moderation UI.

---

## 2. Prerequisites Check

Before starting execution, verify that the host environment has:
- **Docker** (`docker --version`) & **Docker Compose v2** (`docker compose version`).
- **Network access** to Telegram MTProto, Telegram Bot API, and the chosen AI provider API.
- The following required credentials from the user:
  1. `API_ID` & `API_HASH` (from [my.telegram.org](https://my.telegram.org)).
  2. `TELEGRAM_BOT_TOKEN` (from [@BotFather](https://t.me/BotFather)).
  3. `AI_API_KEY` (OpenAI, DeepSeek, OpenRouter, etc.).
  4. `ADMIN_IDS` (Telegram numerical User IDs of the administrator).
  5. `CHANNELS_TO_TRACK` (Comma-separated donor channel IDs or usernames).
  6. `TARGET_CHANNEL_ID` (Channel where approved posts are published).

---

## 3. Step-by-Step Agent Execution Workflow

### Step 1: Clone Repository (if not already in workspace)
```bash
git clone https://github.com/ivanchik-byte/Telegram-Channel-Admin.git
cd Telegram-Channel-Admin
```

### Step 2: Setup Environment File (`.env`)
Create `.env` from `.env.example`:
```bash
cp .env.example .env
```

Ensure the following variables are properly populated in `.env`:
```ini
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=tg_admin
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/tg_admin

# Redis
REDIS_URL=redis://redis:6379/0

# Telegram MTProto (Userbot)
API_ID=12345678
API_HASH=your_api_hash_here
CHANNELS_TO_TRACK=-1001234567890,@channel_username

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TARGET_CHANNEL_ID=-1001234567890
MODERATOR_CHAT_ID=-1001987654321
ADMIN_IDS=123456789

# AI Provider
AI_API_KEY=sk-your-ai-api-key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
AI_EXTRA_BODY={"temperature": 0.6, "top_p": 0.9, "max_tokens": 800}
AD_KEYWORDS=реклама,erid,промокод,подписывайтесь,розыгрыш,подписаться

# Optional interface language (ru / en)
LANGUAGE=ru
```

### Step 3: Telethon Session Authorization (Interactive Step)
> [!IMPORTANT]
> Telethon requires an interactive one-time login to create `data/anon.session`.
> **Agent Note**: If running in an automated non-interactive terminal, prompt the user to input their phone number, confirmation code, and 2FA password.

Execute:
```bash
docker compose up -d db redis
docker compose run --rm parser python src/login.py
```
**Expected Prompts**:
1. `Please enter your phone (or bot token):` -> Enter phone number with country code (e.g. `+1234567890`).
2. `Please enter the code you received:` -> Enter code sent by Telegram.
3. `Please enter your password:` -> Enter 2FA Cloud Password (if enabled on the account).

After successful authorization, the session file will be stored at `data/anon.session`.

### Step 4: Build and Launch Services
```bash
docker compose up -d --build
```

### Step 5: Verification & Health Checks

1. **Check running containers**:
   ```bash
   docker compose ps
   ```
   All services (`db`, `redis`, `parser`, `worker`, `bot`) should be in state `Up` / `healthy` (`migrator` should be `Exited (0)`).

2. **Inspect logs for errors**:
   ```bash
   docker compose logs -f --tail=50
   ```
   - Verify `db` and `redis` health checks pass.
   - Verify `migrator` ran `alembic upgrade head` without errors.
   - Verify `bot` logged `Bot started successfully` / polling.
   - Verify `parser` connected to Telegram and began listening to `CHANNELS_TO_TRACK`.
   - Verify `worker` registered Arq functions and connected to Redis.

---

## 4. Agent Diagnostics & Troubleshooting

| Symptom | Cause | Solution for Agent |
| :--- | :--- | :--- |
| `parser` exits with `SessionPasswordNeededError` or auth error | `data/anon.session` is missing or unauthorized | Re-run `docker compose run --rm parser python src/login.py` |
| `migrator` fails with connection refused | `db` not ready or wrong `DATABASE_URL` | Ensure `db` container is healthy; verify `DATABASE_URL` in `.env` |
| `worker` fails to generate posts | Invalid `AI_API_KEY` or unreachable `AI_BASE_URL` | Check `.env` `AI_API_KEY` and `AI_BASE_URL`; check `docker compose logs -f worker` |
| `bot` fails with `TelegramUnauthorizedError` | Invalid `TELEGRAM_BOT_TOKEN` | Verify bot token with [@BotFather](https://t.me/BotFather) |
| Posts not captured | Bot not added / userbot not joined to donor channels | Ensure the userbot account is subscribed to channels listed in `CHANNELS_TO_TRACK` |

---

## 5. Maintenance Commands Reference

- **Stop all services gracefully**: `docker compose down`
- **Rebuild after code modification**: `docker compose down && docker compose up -d --build`
- **View individual service logs**:
  - Bot: `docker compose logs -f bot`
  - Worker: `docker compose logs -f worker`
  - Parser: `docker compose logs -f parser`
  - Migrations / DB: `docker compose logs -f db`
