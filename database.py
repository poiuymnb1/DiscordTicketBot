"""Подключение к PostgreSQL, схема таблиц, CRUD методы."""
import asyncpg
from typing import Optional
from models import TicketSystem, Ticket


_pool: Optional[asyncpg.Pool] = None


async def init(dsn: str) -> None:
    """Инициализирует пул соединений и создаёт таблицы."""
    global _pool
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)
    await _create_tables()
    print("✅ Подключение к PostgreSQL установлено")


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("БД не инициализирована — вызовите database.init() первым")
    return _pool


async def close() -> None:
    if _pool:
        await _pool.close()


# ── Схема ─────────────────────────────────────────────────────────────────────

async def _create_tables() -> None:
    async with pool().acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_systems (
                id                    SERIAL PRIMARY KEY,
                guild_id              BIGINT NOT NULL,
                name                  TEXT   NOT NULL,
                channel_id            BIGINT,
                message_id            BIGINT,
                category_id           BIGINT,
                transcript_channel_id BIGINT,
                admin_role_ids        BIGINT[] NOT NULL DEFAULT '{}',
                channel_prefix        TEXT   NOT NULL DEFAULT 'ticket',
                embed_title           TEXT   NOT NULL DEFAULT '🎫 Создать тикет',
                embed_description     TEXT   NOT NULL DEFAULT 'Нажмите кнопку ниже, чтобы создать тикет.',
                embed_color           INT    NOT NULL DEFAULT 2829105,
                footer_text           TEXT    NOT NULL DEFAULT 'Ticket System',
                footer_icon_url       TEXT    NOT NULL DEFAULT '',
                ticket_embed_title    TEXT    NOT NULL DEFAULT '🎫 Тикет #{number}',
                ticket_embed_desc     TEXT    NOT NULL DEFAULT '{user.mention}, ваш тикет создан!\n\nОпишите ваш вопрос.',
                ticket_embed_color    INT     NOT NULL DEFAULT 2829105,
                ticket_counter        INT     NOT NULL DEFAULT 0,
                UNIQUE (guild_id, name)
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id            SERIAL PRIMARY KEY,
                system_id     INT    NOT NULL REFERENCES ticket_systems(id) ON DELETE CASCADE,
                guild_id      BIGINT NOT NULL,
                channel_id    BIGINT NOT NULL UNIQUE,
                owner_id      BIGINT NOT NULL,
                ticket_number INT    NOT NULL,
                status        TEXT   NOT NULL DEFAULT 'open',
                opened_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                closed_at     TIMESTAMPTZ,
                closer_id     BIGINT
            );

            CREATE INDEX IF NOT EXISTS idx_ticket_systems_guild ON ticket_systems(guild_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_system      ON tickets(system_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_channel     ON tickets(channel_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_owner       ON tickets(owner_id, system_id);
        """)


# ── TicketSystem CRUD ──────────────────────────────────────────────────────────

async def create_system(guild_id: int, name: str) -> TicketSystem:
    """Создаёт новую тикетную систему с дефолтными настройками."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO ticket_systems (guild_id, name)
            VALUES ($1, $2)
            RETURNING *
        """, guild_id, name)
    return TicketSystem.from_row(row)


async def get_system(guild_id: int, name: str) -> Optional[TicketSystem]:
    """Возвращает систему по названию или None."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM ticket_systems WHERE guild_id=$1 AND name=$2
        """, guild_id, name)
    return TicketSystem.from_row(row) if row else None


async def get_system_by_id(system_id: int) -> Optional[TicketSystem]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM ticket_systems WHERE id=$1", system_id
        )
    return TicketSystem.from_row(row) if row else None


async def get_systems(guild_id: int) -> list[TicketSystem]:
    """Возвращает все системы сервера."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM ticket_systems WHERE guild_id=$1 ORDER BY id", guild_id
        )
    return [TicketSystem.from_row(r) for r in rows]


async def get_all_systems() -> list[TicketSystem]:
    """Возвращает все системы всех серверов (для регистрации persistent views)."""
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM ticket_systems ORDER BY id")
    return [TicketSystem.from_row(r) for r in rows]


async def update_system(system_id: int, **fields) -> Optional[TicketSystem]:
    """
    Обновляет произвольные поля системы.
    Пример: update_system(1, channel_id=123, embed_title="Новый заголовок")
    """
    if not fields:
        return await get_system_by_id(system_id)

    allowed = {
        "channel_id", "message_id", "category_id", "transcript_channel_id",
        "admin_role_ids", "channel_prefix", "embed_title", "embed_description",
        "embed_color", "footer_text", "footer_icon_url", "ticket_counter",
        "ticket_embed_title", "ticket_embed_desc", "ticket_embed_color",
        "ticket_embed_show_creator", "ticket_embed_show_number", "ticket_embed_show_system",
    }
    invalid = set(fields) - allowed
    if invalid:
        raise ValueError(f"Недопустимые поля для обновления: {invalid}")

    set_clauses = ", ".join(
        f"{col} = ${i + 2}" for i, col in enumerate(fields)
    )
    values = list(fields.values())

    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE ticket_systems SET {set_clauses} WHERE id=$1 RETURNING *",
            system_id, *values
        )
    return TicketSystem.from_row(row) if row else None


async def delete_system(guild_id: int, name: str) -> bool:
    """Удаляет систему (каскадно удаляет все тикеты)."""
    async with pool().acquire() as conn:
        result = await conn.execute("""
            DELETE FROM ticket_systems WHERE guild_id=$1 AND name=$2
        """, guild_id, name)
    return result == "DELETE 1"


async def increment_counter(system_id: int) -> int:
    """Атомарно увеличивает счётчик и возвращает новое значение."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE ticket_systems
            SET ticket_counter = ticket_counter + 1
            WHERE id = $1
            RETURNING ticket_counter
        """, system_id)
    return row["ticket_counter"]


# ── Ticket CRUD ────────────────────────────────────────────────────────────────

async def create_ticket(
    system_id: int,
    guild_id: int,
    channel_id: int,
    owner_id: int,
    ticket_number: int,
) -> Ticket:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO tickets (system_id, guild_id, channel_id, owner_id, ticket_number)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """, system_id, guild_id, channel_id, owner_id, ticket_number)
    return Ticket.from_row(row)


async def get_ticket_by_channel(channel_id: int) -> Optional[Ticket]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tickets WHERE channel_id=$1", channel_id
        )
    return Ticket.from_row(row) if row else None


async def get_open_ticket(system_id: int, owner_id: int) -> Optional[Ticket]:
    """Возвращает открытый тикет пользователя в данной системе."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM tickets
            WHERE system_id=$1 AND owner_id=$2 AND status='open'
        """, system_id, owner_id)
    return Ticket.from_row(row) if row else None


async def close_ticket(channel_id: int, closer_id: int) -> Optional[Ticket]:
    """Помечает тикет как закрытый."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE tickets
            SET status='closed', closed_at=NOW(), closer_id=$2
            WHERE channel_id=$1
            RETURNING *
        """, channel_id, closer_id)
    return Ticket.from_row(row) if row else None


async def delete_ticket_by_channel(channel_id: int) -> bool:
    """Удаляет тикет по ID канала."""
    async with pool().acquire() as conn:
        result = await conn.execute(
            "DELETE FROM tickets WHERE channel_id=$1", channel_id
        )
    return result == "DELETE 1"


async def update_ticket_channel(channel_id: int, message_id: int) -> Optional[Ticket]:
    """Обновляет ID сообщения в тикете."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE tickets
            SET message_id=$2
            WHERE channel_id=$1
            RETURNING *
        """, channel_id, message_id)
    return Ticket.from_row(row) if row else None
