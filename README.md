# Chat Help Bot — Telegram Dating Helper MVP

Telegram bot on aiogram 3 + webhook + async PostgreSQL that helps with dating conversations.

## Features

- **Reply suggestions** — analyze a conversation screenshot or text and get 3-5 reply options
- **First message** — generate opening messages based on a profile
- **Profile review** — get constructive feedback on your dating profile
- **Personalisation** — user settings (gender, situation, role, style, AI identity)
- **Trial** — 2-hour free trial activated on first AI request
- **Payment stub** — full transaction model, stub provider for testing
- **Proxy rotation** — outbound HTTP requests routed through configurable proxies with health tracking

## Quick Start

### 1. Prerequisites

- Python 3.12+
- PostgreSQL 15+
- A Telegram bot token from @BotFather
- An OpenAI API key (or compatible API)

### 2. Setup

```bash
# Clone and enter project
cd chat_help_bot

# Create virtual env
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy and fill env
cp .env.example .env
# Edit .env with your values
```

### 3. Database

```bash
# Create database
createdb chat_help_bot

# Run migrations
alembic upgrade head
```

### 4. Run

```bash
python -m app.main
```

The bot will start an aiohttp server on the configured port and set the webhook automatically.

### 5. Tests

```bash
pytest -v
```

## Project Structure

```
app/
├── main.py              # Entry point (webhook server)
├── config.py            # Settings from .env
├── bot/
│   ├── setup.py         # Bot + dispatcher factory
│   ├── handlers/        # All Telegram handlers
│   ├── keyboards/       # Inline and reply keyboards
│   ├── states/          # FSM state groups
│   └── middlewares/     # DB session, user ensure, error logging
├── db/
│   ├── session.py       # Async engine & session factory
│   ├── models/          # SQLAlchemy models
│   └── repositories/    # Data access layer
├── services/            # Business logic
├── ai/
│   ├── client.py        # AI API HTTP client
│   ├── prompt_builder.py
│   ├── response_parser.py
│   └── prompts/         # Prompt templates per scenario
└── proxy/
    └── manager.py       # Proxy rotation with health tracking
```

## Assumptions

- AI API is OpenAI-compatible (chat/completions endpoint)
- Webhook is terminated by a reverse proxy (nginx/caddy) with valid TLS
- FSM storage is in-memory (sufficient for MVP; swap to Redis adapter if needed)
- Proxy list is static from .env (no DB storage for proxies)
- Payment is a stub — no real payment provider is integrated
