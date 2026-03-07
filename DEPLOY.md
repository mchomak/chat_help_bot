# Деплой на VPS (Ubuntu 22.04 / 24.04) с Docker

## Что нужно получить перед деплоем

Прежде чем трогать сервер, подготовь эти данные:

| Переменная | Где взять | Пример |
|---|---|---|
| `BOT_TOKEN` | @BotFather в Telegram | `7123456789:AAH...` |
| `WEBHOOK_HOST` | Твой домен или IP сервера | `https://yourdomain.com` |
| `WEBHOOK_SECRET` | Сгенерировать самому | см. ниже |
| `AI_API_KEY` | Личный кабинет OpenAI | `sk-proj-...` |
| `POSTGRES_PASSWORD` | Придумать надёжный пароль | `S3cur3P@ss!` |

---

## Шаг 1 — Получить BOT_TOKEN

1. Открой Telegram, найди **@BotFather**
2. Напиши `/newbot`
3. Придумай имя бота (видят пользователи): `Dating Helper Bot`
4. Придумай username (уникальный, с суффиксом `bot`): `my_dating_helper_bot`
5. BotFather пришлёт токен: `7123456789:AAHxxxxxxxx`

Это и есть `BOT_TOKEN`.

---

## Шаг 2 — Получить WEBHOOK_HOST

### Вариант А: есть домен (рекомендуется)

1. Купи домен или используй уже имеющийся
2. В DNS-панели добавь A-запись: `yourdomain.com → IP_твоего_VPS`
3. `WEBHOOK_HOST=https://yourdomain.com`

TLS-сертификат Caddy/Certbot выдаст автоматически (см. Шаг 6A).

### Вариант Б: только IP сервера (без домена)

Telegram поддерживает самоподписанный сертификат, но это сложнее.
Рекомендую взять бесплатный домен (например, [afraid.org](https://freedns.afraid.org) или [duckdns.org](https://www.duckdns.org)) и идти по Варианту А.

---

## Шаг 3 — Сгенерировать WEBHOOK_SECRET

SSH на сервер или запусти локально:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Скопируй вывод — это твой `WEBHOOK_SECRET`.
Telegram будет отправлять это значение в заголовке `X-Telegram-Bot-Api-Secret-Token`, бот его проверит.

---

## Шаг 4 — Подготовить VPS

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить Docker + compose plugin
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Разрешить запуск Docker без sudo (перелогиниться после)
sudo usermod -aG docker $USER
```

---

## Шаг 5 — Загрузить код на сервер

```bash
# На сервере
git clone https://github.com/mchomak/chat_help_bot.git
cd chat_help_bot
```

или через scp:
```bash
# Локально
scp -r ./chat_help_bot user@YOUR_SERVER_IP:/home/user/
```

---

## Шаг 6 — Настроить Nginx + TLS (вариант А: с доменом)

### Установить Nginx и Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Создать конфиг Nginx

```bash
sudo nano /etc/nginx/sites-available/dating-bot
```

Вставь (замени `yourdomain.com`):

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/dating-bot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Получить TLS-сертификат

```bash
sudo certbot --nginx -d yourdomain.com
```

Certbot сам обновит конфиг Nginx под HTTPS. Автопродление уже настроено через systemd timer.

---

## Шаг 7 — Создать .env

```bash
cd /home/user/chat_help_bot   # или где лежит проект
cp .env.example .env
nano .env
```

Заполни обязательные поля:

```dotenv
BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxx          # из BotFather
WEBHOOK_HOST=https://yourdomain.com               # твой домен с https://
WEBHOOK_PATH=/webhook
WEBHOOK_PORT=8080
WEBHOOK_SECRET=a1b2c3d4...                        # сгенерированный токен

BOT_INTERNAL_PORT=8080                            # должен совпадать с WEBHOOK_PORT

POSTGRES_DB=chat_help_bot
POSTGRES_USER=botuser
POSTGRES_PASSWORD=ВашНадёжныйПароль               # придумай сам

# DATABASE_URL автоматически переопределяется в docker-compose,
# но оставь правильный формат:
DATABASE_URL=postgresql+asyncpg://botuser:ВашНадёжныйПароль@db:5432/chat_help_bot

AI_API_KEY=sk-proj-...                            # OpenAI API key
AI_API_BASE_URL=https://api.openai.com/v1
AI_DEFAULT_MODEL=gpt-4o
AI_VISION_MODEL=gpt-4o
```

---

## Шаг 8 — Запустить

```bash
# Собрать образ и запустить всё (db + migrate + bot)
docker compose up -d --build

# Проверить логи
docker compose logs -f bot

# Проверить статус контейнеров
docker compose ps
```

Ожидаемый вывод через ~20 секунд:

```
NAME              STATUS          PORTS
chat_help_bot-db-1       Up (healthy)
chat_help_bot-migrate-1  Exited (0)   ← это нормально, миграция завершилась
chat_help_bot-bot-1      Up (healthy) 0.0.0.0:8080->8080/tcp
```

---

## Шаг 9 — Проверить webhook

```bash
# Проверить health endpoint бота
curl http://localhost:8080/health

# Проверить что Telegram видит webhook (замени токен)
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

Ожидаемый ответ getWebhookInfo:
```json
{
  "ok": true,
  "result": {
    "url": "https://yourdomain.com/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "last_error_message": ""
  }
}
```

Если `url` пустой — бот не запустился. Смотри логи: `docker compose logs bot`

---

## Управление

```bash
# Остановить
docker compose down

# Перезапустить бота (без пересборки)
docker compose restart bot

# Обновить код и пересобрать
git pull
docker compose up -d --build

# Посмотреть логи PostgreSQL
docker compose logs db

# Зайти в PostgreSQL
docker compose exec db psql -U botuser -d chat_help_bot

# Запустить только миграции вручную
docker compose run --rm migrate
```

---

## Решение проблем

| Симптом | Причина | Решение |
|---|---|---|
| `bot` не запускается, `CONNECTION REFUSED` | БД не успела подняться | Подождать 30 сек, `docker compose restart bot` |
| webhook не устанавливается | Nginx не проксирует на порт 8080 | Проверить конфиг Nginx, `sudo nginx -t` |
| Telegram пишет 401 | Неверный `WEBHOOK_SECRET` | Убедиться что в .env и в боте одно значение |
| `SSL certificate problem` от Telegram | Нет TLS или самоподписанный cert | Выпустить cert через Certbot |
| `ERROR: relation "users" does not exist` | Миграция не прошла | `docker compose logs migrate`, затем `docker compose run --rm migrate` |

---

## Порты

```
Telegram → (443/HTTPS) → Nginx/Caddy → (8080/HTTP) → Docker bot container
                                                    → Docker db container (5432, внутренняя сеть)
```

Порт **5432** PostgreSQL наружу **не открывается** — только внутри compose-сети.
