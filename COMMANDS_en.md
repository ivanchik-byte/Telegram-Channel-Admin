# Pipeline Management (Docker Compose)

This document contains a command reference for administering the bot, worker, parser, and database.

**Important:** All the following commands must be executed from the project's root directory, where the `docker-compose.yml` file is located.

## Basic Startup Commands

### Full Restart with Rebuild
Use this command after changing the source code (`.py`) or updating the list of dependencies for the changes to take effect:
```bash
docker compose down
docker compose up -d --build
```

If Docker cached an old version of the code and the changes were not applied, use the build without cache:
```bash
docker compose build --no-cache
docker compose up -d
```

### Quick Start
Used for standard system startup when the source code has not changed:
```bash
docker compose up -d
```

### Parser Authorization
A one-time operation to generate the `anon.session` file required for Telethon to work (you will need to enter your phone number and verification code from Telegram):
```bash
docker compose up -d redis db
docker compose run --rm parser python src/login.py
```

## Monitoring and Logging

### Check Container Status
This command outputs a list of all project containers and their current state:
```bash
docker compose ps
```

### Read General Logs in Real Time
Outputs aggregated logs from all running microservices. Press `Ctrl+C` to exit:
```bash
docker compose logs -f
```

### Logging Individual Microservices
Commands for isolated viewing of logs of specific system components:
```bash
docker compose logs -f bot      # Moderation interface and command processing logs
docker compose logs -f worker   # AI rewriter and external API call logs
docker compose logs -f parser   # Logs for the process of capturing new messages from channels
docker compose logs -f db       # PostgreSQL DBMS system logs
```

## Stop and Reset

### Safe System Stop
Graceful shutdown of all processes. The database and task queue in Redis are preserved:
```bash
docker compose down
```

### Hard Reset
**Warning:** This command completely stops the system and deletes all data (the PostgreSQL database and Redis cache). The session file `anon.session` is not deleted.
Use it only if you need to completely clear the history of processed posts.
```bash
docker compose down -v
```
