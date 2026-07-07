# 🎫 DiscordTicketBot

Мощный Discord-бот для управления тикетными системами с поддержкой множества систем на одном сервере.

[English](#english) | [中文](#中文)

---

## ✨ Возможности

- **Мульти-системы** — несколько независимых тикетных систем на одном сервере
- **Persistent Views** — кнопки работают после перезапуска бота
- **Приватные тикеты** — каналы видимы только создателю и модераторам
- **HTML-транскрипты** — красивые логи закрытых тикетов
- **Настраиваемые embed** — заголовки, описания, цвета, футеры
- **Slash-команды** — полное управление через `/ticket`
- **Гибкая настройка полей** — показ/скрытие создателя, номера, системы
- **Rate Limiting** — защита от спама тикетов

---

## 🚀 Быстрый старт

### 1. Настройка Discord

1. Создайте приложение: https://discord.com/developers/applications
2. В **Bot** → включите **Message Content Intent**
3. В **OAuth2** → **URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Manage Channels`, `View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, `Attach Files`, `Manage Roles`

### 2. Запуск через Docker (рекомендуется для хостинга)

```bash
# Клонируйте репозиторий
git clone https://github.com/your-repo/DiscordTicketBot.git
cd DiscordTicketBot

# Создайте .env файл
# ВАЖНО: Для Docker используйте 'db' как хост в DATABASE_URL
cat > .env << EOF
DISCORD_TOKEN=ваш_токен_бота
DATABASE_URL=postgresql://postgres:changeme@db:5432/discordticketbot
DB_PASSWORD=changeme
COMMAND_PREFIX=!
EOF

# Запуск
docker-compose up -d --build
```

### 3. Локальный запуск (без Docker)

```bash
# Клонируйте репозиторий
git clone https://github.com/your-repo/DiscordTicketBot.git
cd DiscordTicketBot

# Скопируйте конфиг
cp .env.example .env

# Отредактируйте .env:
# - DISCORD_TOKEN=ваш_токен
# - DATABASE_URL=postgresql://user:password@localhost:5432/discordticketbot

# Убедитесь, что PostgreSQL запущен
# Создайте базу данных:
# sudo -u postgres psql -c "CREATE DATABASE discordticketbot;"

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python main.py
```

### 3. Настройка тикетной системы

После запуска бота используйте slash-команды:

```
/ticket create name:Вступление
/ticket set-channel name:Вступление channel:#тикеты
/ticket set-roles name:Вступление roles:@Модератор @Админ
/ticket publish name:Вступление
```

---

## 🐳 Docker

```bash
# Создаём .env из примера и заполняем данные
cp .env.example .env
nano .env

# Запуск
docker-compose up -d --build
```

---

## 📝 Настройка логов

По умолчанию логи выводятся в консоль. Вы можете настроить вывод в файл или использовать внешние сервисы.

### Консоль (по умолчанию)

Логи уже настроены и выводятся в stdout с timestamp:

```
2024-01-15 10:30:00 | INFO     | __main__ | ✅ Бот запущен: DiscordTicketBot#1234
2024-01-15 10:30:01 | INFO     | __main__ | 🔁 Зарегистрировано 2 persistent view(s)
2024-01-15 10:30:02 | INFO     | __main__ | ✅ Синхронизировано 15 slash-команд(ы)
```

### Файл

Добавьте в `main.py` перед запуском бота:

```python
import logging
from logging.handlers import RotatingFileHandler

# Настройка логирования в файл
file_handler = RotatingFileHandler(
    "discord_ticket_bot.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

# Добавляем обработчик
logging.getLogger().addHandler(file_handler)
```

### Уровни логирования

| Уровень | Описание |
|---------|----------|
| `DEBUG` | Подробная отладочная информация |
| `INFO` | Общие информационные сообщения |
| `WARNING` | Предупреждения (некритичные ошибки) |
| `ERROR` | Ошибки, влияющие на работу |
| `CRITICAL` | Критические ошибки |

Изменить уровень:

```python
logging.getLogger().setLevel(logging.WARNING)  # Только предупреждения и ошибки
```

### Внешние сервисы (например, Sentry)

```bash
pip install sentry-sdk
```

```python
import sentry_sdk
from sentry_sdk.integrations.logging import SentryIntegration

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[
        SentryIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        )
    ]
)
```

---

## 📋 Команды

| Команда | Описание |
|---------|----------|
| `/ticket create` | Создать новую тикетную систему |
| `/ticket delete` | Удалить систему |
| `/ticket list` | Список всех систем |
| `/ticket info` | Подробные настройки системы |
| `/ticket set-channel` | Канал для кнопки |
| `/ticket set-category` | Категория для тикетов |
| `/ticket set-roles` | Роли модераторов |
| `/ticket set-prefix` | Префикс имени канала |
| `/ticket set-embed` | Настроить embed с кнопкой |
| `/ticket edit-embed` | Настроить embed внутри тикета |
| `/ticket set-transcript` | Канал для транскриптов |
| `/ticket publish` | Опубликовать/обновить кнопку |
| `/ticket setup` | Пошаговая настройка |

### Пример полной настройки

```
/ticket create name:Поддержка
/ticket set-channel name:Поддержка channel:#тикеты-поддержки
/ticket set-roles name:Поддержка role1:@Модератор role2:@Админ
/ticket set-transcript name:Поддержка channel:#транскрипты
/ticket set-embed name:Поддержка
/ticket publish name:Поддержка
```

---

## 📁 Структура проекта

```
DiscordTicketBot/
├── main.py              # Точка входа, логика бота
├── config.py            # Конфигурация через .env
├── views.py             # Discord UI (кнопки, модалы)
├── database.py          # PostgreSQL подключение и методы
├── models.py            # Датаклассы для БД
├── commands.py          # Slash-команды /ticket
├── transcript.py        # Генератор HTML-транскриптов
├── utils.py             # Утилиты (rate limiting)
├── requirements.txt     # Зависимости
├── Dockerfile           # Docker образ
├── docker-compose.yml   # Docker Compose с PostgreSQL
└── .env.example         # Пример конфигурации
```

---

## 🔧 Переменные окружения

|    Переменная    | Обязательна |              Описание              |
|------------------|-------------|------------------------------------|
| `DISCORD_TOKEN`  |     Да      | Токен Discord-бота                 |
| `DATABASE_URL`   |     Да      | PostgreSQL connection string       |
| `COMMAND_PREFIX` |     Нет     | Префикс команд (по умолчанию: `!`) |

### Пример DATABASE_URL

```
postgresql://user:password@localhost:5432/discordticketbot
```

### Docker переменные

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `DB_PASSWORD` | changeme | Пароль для PostgreSQL |

---

## 🔒 Безопасность

- Используются параметризованные SQL-запросы (защита от SQL-инъекций)
- Rate limiting защищает от спама тикетов
- Текст очищается от потенциально опасных символов
- Токен бота и данные БД хранятся в .env (не коммитьте!)

---

## 🛠️ Устранение неполадок

| Проблема | Решение |
|----------|---------|
| Бот не подключается к БД | Проверьте DATABASE_URL и запущен ли PostgreSQL |
| Кнопки не работают после рестарта | Проверьте права бота: Manage Channels |
| Ошибка "Missing Access" | Роль бота должна быть выше ролей модераторов |
| Транскрипт не отправляется | Проверьте что канал транскриптов существует и бот имеет права |

---

## 📄 Лицензия

MIT License — используйте свободно, указав авторство.

---

<a name="english"></a>

# 🎫 DiscordTicketBot (English)

Powerful Discord bot for managing ticket systems with support for multiple systems on one server.

---

## ✨ Features

- **Multi-systems** — multiple independent ticket systems on one server
- **Persistent Views** — buttons work after bot restart
- **Private tickets** — channels visible only to creator and moderators
- **HTML transcripts** — beautiful logs of closed tickets
- **Customizable embeds** — titles, descriptions, colors, footers
- **Slash commands** — full control via `/ticket`
- **Flexible field settings** — show/hide creator, number, system
- **Rate Limiting** — spam protection

---

## 🚀 Quick Start

### 1. Discord Setup

1. Create an application: https://discord.com/developers/applications
2. In **Bot** → enable **Message Content Intent**
3. In **OAuth2** → **URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Manage Channels`, `View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, `Attach Files`, `Manage Roles`

### 2. Run

```bash
# Clone the repository
git clone https://github.com/your-repo/DiscordTicketBot.git
cd DiscordTicketBot

# Copy config
cp .env.example .env

# Edit .env — fill DISCORD_TOKEN and DATABASE_URL

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### 3. Configure Ticket System

After starting the bot, use slash commands:

```
/ticket create name:Support
/ticket set-channel name:Support channel:#tickets
/ticket set-roles name:Support roles:@Moderator @Admin
/ticket publish name:Support
```

---

## 🐳 Docker

```bash
cp .env.example .env
nano .env
docker-compose up -d --build
```

---

## 📝 Logging Configuration

Logs are output to console by default. You can configure file output or use external services.

### Console (default)

```
2024-01-15 10:30:00 | INFO     | __main__ | ✅ Bot started: DiscordTicketBot#1234
2024-01-15 10:30:01 | INFO     | __main__ | 🔁 Registered 2 persistent view(s)
2024-01-15 10:30:02 | INFO     | __main__ | ✅ Synced 15 slash command(s)
```

### File

Add to `main.py` before running the bot:

```python
import logging
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler(
    "discord_ticket_bot.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

logging.getLogger().addHandler(file_handler)
```

### Log Levels

| Level | Description |
|-------|-------------|
| `DEBUG` | Detailed debug info |
| `INFO` | General information |
| `WARNING` | Non-critical warnings |
| `ERROR` | Errors affecting operation |
| `CRITICAL` | Critical errors |

---

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/ticket create` | Create new ticket system |
| `/ticket delete` | Delete system |
| `/ticket list` | List all systems |
| `/ticket info` | System details |
| `/ticket set-channel` | Channel for button |
| `/ticket set-category` | Category for tickets |
| `/ticket set-roles` | Moderator roles |
| `/ticket set-prefix` | Channel name prefix |
| `/ticket set-embed` | Configure button embed |
| `/ticket edit-embed` | Configure ticket embed |
| `/ticket set-transcript` | Transcript channel |
| `/ticket publish` | Publish/update button |
| `/ticket setup` | Step-by-step setup |

---

## 📁 Project Structure

```
DiscordTicketBot/
├── main.py              # Entry point, bot logic
├── config.py            # Configuration via .env
├── views.py             # Discord UI (buttons, modals)
├── database.py          # PostgreSQL connection and methods
├── models.py            # Database dataclasses
├── commands.py          # Slash commands /ticket
├── transcript.py        # HTML transcript generator
├── utils.py             # Utilities (rate limiting)
├── requirements.txt     # Dependencies
├── Dockerfile           # Docker image
├── docker-compose.yml   # Docker Compose with PostgreSQL
└── .env.example         # Example configuration
```

---

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | ✅ | Discord bot token |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `COMMAND_PREFIX` | ❌ | Command prefix (default: `!`) |

---

## 🔒 Security

- Parameterized SQL queries (SQL injection protection)
- Rate limiting prevents ticket spam
- Text sanitization removes dangerous characters
- Bot token and DB data stored in .env (don't commit!)

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot can't connect to DB | Check DATABASE_URL and PostgreSQL running |
| Buttons don't work after restart | Check bot permissions: Manage Channels |
| "Missing Access" error | Bot role must be above moderator roles |
| Transcript not sent | Check transcript channel exists and bot has permissions |

---

## 📄 License

MIT License — use freely, please credit the author.

---

<a name="中文"></a>

# 🎫 DiscordTicketBot (中文)

强大的 Discord 机器人，支持在单个服务器上管理多个工单系统。

---

## ✨ 功能

- **多系统** — 在一个服务器上运行多个独立的工单系统
- **持久化视图** — 按钮在机器人重启后仍然有效
- **私密工单** — 频道仅对创建者和管理员可见
- **HTML 记录** — 关闭工单的精美日志
- **可自定义嵌入** — 标题、描述、颜色、页脚
- **斜杠命令** — 通过 `/ticket` 完全控制
- **灵活字段设置** — 显示/隐藏创建者、编号、系统
- **频率限制** — 防止工单刷屏

---

## 🚀 快速开始

### 1. Discord 设置

1. 创建应用：https://discord.com/developers/applications
2. 在 **Bot** 中启用 **Message Content Intent**
3. 在 **OAuth2** → **URL Generator** 中：
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Manage Channels`, `View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, `Attach Files`, `Manage Roles`

### 2. 运行

```bash
# 克隆仓库
git clone https://github.com/your-repo/DiscordTicketBot.git
cd DiscordTicketBot

# 复制配置
cp .env.example .env

# 编辑 .env — 填写 DISCORD_TOKEN 和 DATABASE_URL

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

### 3. 配置工单系统

启动机器人后，使用斜杠命令：

```
/ticket create name:支持
/ticket set-channel name:支持 channel:#工单
/ticket set-roles name:支持 roles:@管理员 @版主
/ticket publish name:支持
```

---

## 🐳 Docker

```bash
cp .env.example .env
nano .env
docker-compose up -d --build
```

---

## 📝 日志配置

日志默认输出到控制台。您可以配置文件输出或使用外部服务。

### 控制台（默认）

```
2024-01-15 10:30:00 | INFO     | __main__ | ✅ 机器人已启动: DiscordTicketBot#1234
2024-01-15 10:30:01 | INFO     | __main__ | 🔁 已注册 2 个持久化视图
2024-01-15 10:30:02 | INFO     | __main__ | ✅ 已同步 15 个斜杠命令
```

### 文件

在运行机器人前，在 `main.py` 中添加：

```python
import logging
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler(
    "discord_ticket_bot.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

logging.getLogger().addHandler(file_handler)
```

### 日志级别

| 级别 | 描述 |
|------|------|
| `DEBUG` | 详细调试信息 |
| `INFO` | 一般信息 |
| `WARNING` | 非关键警告 |
| `ERROR` | 影响运行的错误 |
| `CRITICAL` | 严重错误 |

---

## 📋 命令

| 命令 | 描述 |
|------|------|
| `/ticket create` | 创建新工单系统 |
| `/ticket delete` | 删除系统 |
| `/ticket list` | 列出所有系统 |
| `/ticket info` | 系统详情 |
| `/ticket set-channel` | 按钮所在频道 |
| `/ticket set-category` | 工单分类 |
| `/ticket set-roles` | 管理员角色 |
| `/ticket set-prefix` | 频道名前缀 |
| `/ticket set-embed` | 配置按钮嵌入 |
| `/ticket edit-embed` | 配置工单嵌入 |
| `/ticket set-transcript` | 记录频道 |
| `/ticket publish` | 发布/更新按钮 |
| `/ticket setup` | 逐步设置 |

---

## 📁 项目结构

```
DiscordTicketBot/
├── main.py              # 入口点，机器人逻辑
├── config.py            # 通过 .env 配置
├── views.py             # Discord UI（按钮、模态框）
├── database.py          # PostgreSQL 连接和方法
├── models.py            # 数据库数据类
├── commands.py          # 斜杠命令 /ticket
├── transcript.py        # HTML 记录生成器
├── utils.py             # 工具（频率限制）
├── requirements.txt     # 依赖
├── Dockerfile           # Docker 镜像
├── docker-compose.yml   # 包含 PostgreSQL 的 Docker Compose
└── .env.example         # 配置示例
```

---

## 🔧 环境变量

| 变量 | 必需 | 描述 |
|------|------|------|
| `DISCORD_TOKEN` | ✅ | Discord 机器人令牌 |
| `DATABASE_URL` | ✅ | PostgreSQL 连接字符串 |
| `COMMAND_PREFIX` | ❌ | 命令前缀（默认：`!`）|

---

## 🔒 安全

- 参数化 SQL 查询（防止 SQL 注入）
- 频率限制防止工单刷屏
- 文本清理移除危险字符
- 机器人和数据库令牌存储在 .env 中（请勿提交！）

---

## 🛠️ 故障排除

| 问题 | 解决方案 |
|------|----------|
| 机器人无法连接数据库 | 检查 DATABASE_URL 和 PostgreSQL 是否运行 |
| 重启后按钮不工作 | 检查机器人权限：Manage Channels |
| "Missing Access" 错误 | 机器人角色必须在管理员角色之上 |
| 记录未发送 | 检查记录频道存在且机器人有权限 |

---

## 📄 许可证

MIT 许可证 — 自由使用，请注明作者。