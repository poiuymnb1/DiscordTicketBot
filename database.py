"""PostgreSQL connection, table schema, CRUD methods."""
import asyncpg
from typing import Optional
from models import TicketSystem, Ticket


_pool: Optional[asyncpg.Pool] = None


async def init(dsn: str) -> None:
    """Initialize connection pool and create tables."""
    global _pool
    
    # Debug info (without password)
    from urllib.parse import urlparse
    parsed = urlparse(dsn)
    safe_dsn = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}{parsed.path}"
    print(f"🔗 Connecting to DB: {safe_dsn}")
    
    try:
        # Try without SSL first (for local Docker DB)
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=10,
        )
        await _create_tables()
        print("✅ PostgreSQL connection established")
    except Exception as e:
        print(f"❌ Connection error: {type(e).__name__}: {e}")
        # Try with SSL (for cloud DBs like Supabase, Neon, etc.)
        try:
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=1,
                max_size=10,
                ssl=ssl_context
            )
            await _create_tables()
            print("✅ PostgreSQL connection established (via SSL)")
        except Exception as e2:
            print(f"❌ SSL connection error: {type(e2).__name__}: {e2}")
            raise


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialized - call database.init() first")
    return _pool


async def close() -> None:
    if _pool:
        await _pool.close()


# ── Schema ─────────────────────────────────────────────────────────────────────

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
                embed_title           TEXT   NOT NULL DEFAULT '🎫 Create Ticket',
                embed_description     TEXT   NOT NULL DEFAULT 'Click the button below to create a ticket.',
                embed_color           INT    NOT NULL DEFAULT 2829105,
                footer_text           TEXT    NOT NULL DEFAULT 'Ticket System',
                footer_icon_url       TEXT    NOT NULL DEFAULT '',
                ticket_embed_title    TEXT    NOT NULL DEFAULT '🎫 Ticket #{number}',
                ticket_embed_desc     TEXT    NOT NULL DEFAULT '{user.mention}, your ticket has been created!\n\nPlease describe your issue.',
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
    """Create a new ticket system with default settings."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO ticket_systems (guild_id, name)
            VALUES ($1, $2)
            RETURNING *
        """, guild_id, name)
    return TicketSystem.from_row(row)


async def get_system(guild_id: int, name: str) -> Optional[TicketSystem]:
    """Get system by name or None."""
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
    """Get all systems for a guild."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM ticket_systems WHERE guild_id=$1 ORDER BY id", guild_id
        )
    return [TicketSystem.from_row(r) for r in rows]


async def get_all_systems() -> list[TicketSystem]:
    """Get all systems across all guilds (for registering persistent views)."""
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM ticket_systems ORDER BY id")
    return [TicketSystem.from_row(r) for r in rows]


async def update_system(system_id: int, **fields) -> Optional[TicketSystem]:
    """
    Update arbitrary system fields.
    Example: update_system(1, channel_id=123, embed_title="New Title")
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
        raise ValueError(f"Invalid fields for update: {invalid}")

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
    """Delete system (cascades to delete all tickets)."""
    async with pool().acquire() as conn:
        result = await conn.execute("""
            DELETE FROM ticket_systems WHERE guild_id=$1 AND name=$2
        """, guild_id, name)
    return result == "DELETE 1"


async def increment_counter(system_id: int) -> int:
    """Atomically increment counter and return new value."""
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
    """Get user's open ticket in this system."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM tickets
            WHERE system_id=$1 AND owner_id=$2 AND status='open'
        """, system_id, owner_id)
    return Ticket.from_row(row) if row else None


async def close_ticket(channel_id: int, closer_id: int) -> Optional[Ticket]:
    """Mark ticket as closed."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE tickets
            SET status='closed', closed_at=NOW(), closer_id=$2
            WHERE channel_id=$1
            RETURNING *
        """, channel_id, closer_id)
    return Ticket.from_row(row) if row else None


async def delete_ticket_by_channel(channel_id: int) -> bool:
    """Delete ticket by channel ID."""
    async with pool().acquire() as conn:
        result = await conn.execute(
            "DELETE FROM tickets WHERE channel_id=$1", channel_id
        )
    return result == "DELETE 1"


async def update_ticket_channel(channel_id: int, message_id: int) -> Optional[Ticket]:
    """Update message ID in ticket."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE tickets
            SET message_id=$2
            WHERE channel_id=$1
            RETURNING *
        """, channel_id, message_id)
    return Ticket.from_row(row) if row else None
