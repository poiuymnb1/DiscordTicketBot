"""SQLite connection, table schema, CRUD methods."""
import aiosqlite
import os
from typing import Optional
from models import TicketSystem, Ticket


_db_path: Optional[str] = None


async def init(db_path: str = "data/tickets.db") -> None:
    """Initialize database and create tables."""
    global _db_path
    
    # Create directory if not exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    _db_path = db_path
    print(f"🔗 Connecting to SQLite: {db_path}")
    
    await _create_tables()
    print("✅ SQLite connection established")


def _get_db() -> aiosqlite.Connection:
    """Get database connection."""
    if _db_path is None:
        raise RuntimeError("Database not initialized - call database.init() first")
    return aiosqlite.connect(_db_path)


async def close() -> None:
    """Close database connection (no-op for SQLite)."""
    pass


# ── Schema ─────────────────────────────────────────────────────────────────────

async def _create_tables() -> None:
    async with _get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_systems (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id              INTEGER NOT NULL,
                name                  TEXT    NOT NULL,
                channel_id            INTEGER,
                message_id            INTEGER,
                category_id           INTEGER,
                transcript_channel_id INTEGER,
                admin_role_ids        TEXT    NOT NULL DEFAULT '[]',
                channel_prefix        TEXT    NOT NULL DEFAULT 'ticket',
                embed_title           TEXT    NOT NULL DEFAULT '🎫 Create Ticket',
                embed_description     TEXT    NOT NULL DEFAULT 'Click the button below to create a ticket.',
                embed_color           INTEGER NOT NULL DEFAULT 2829105,
                footer_text           TEXT    NOT NULL DEFAULT 'Ticket System',
                footer_icon_url       TEXT    NOT NULL DEFAULT '',
                ticket_embed_title    TEXT    NOT NULL DEFAULT '🎫 Ticket #{number}',
                ticket_embed_desc     TEXT    NOT NULL DEFAULT '{user.mention}, your ticket has been created!\n\nPlease describe your issue.',
                ticket_embed_color    INTEGER NOT NULL DEFAULT 2829105,
                ticket_embed_show_creator  INTEGER NOT NULL DEFAULT 1,
                ticket_embed_show_number   INTEGER NOT NULL DEFAULT 1,
                ticket_embed_show_system   INTEGER NOT NULL DEFAULT 1,
                ticket_counter        INTEGER NOT NULL DEFAULT 0,
                UNIQUE (guild_id, name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id     INTEGER NOT NULL REFERENCES ticket_systems(id) ON DELETE CASCADE,
                guild_id      INTEGER NOT NULL,
                channel_id    INTEGER NOT NULL UNIQUE,
                owner_id      INTEGER NOT NULL,
                ticket_number INTEGER NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'open',
                opened_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at     TEXT,
                closer_id     INTEGER,
                message_id    INTEGER
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_systems_guild ON ticket_systems(guild_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_system      ON tickets(system_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_channel     ON tickets(channel_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_owner       ON tickets(owner_id, system_id)")
        await db.commit()


def _parse_role_ids(role_ids_str: str) -> list[int]:
    """Parse JSON array string to list of ints."""
    if not role_ids_str or role_ids_str == "[]":
        return []
    try:
        import json
        return json.loads(role_ids_str)
    except:
        return []


def _format_role_ids(role_ids: list[int]) -> str:
    """Format list of ints to JSON array string."""
    import json
    return json.dumps(role_ids)


# ── TicketSystem CRUD ──────────────────────────────────────────────────────────

async def create_system(guild_id: int, name: str) -> TicketSystem:
    """Create a new ticket system with default settings."""
    async with _get_db() as db:
        cursor = await db.execute("""
            INSERT INTO ticket_systems (guild_id, name)
            VALUES (?, ?)
            RETURNING *
        """, (guild_id, name))
        row = await cursor.fetchone()
        await db.commit()
    return TicketSystem.from_row_sqlite(row)


async def get_system(guild_id: int, name: str) -> Optional[TicketSystem]:
    """Get system by name or None."""
    async with _get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM ticket_systems WHERE guild_id=? AND name=?
        """, (guild_id, name))
        row = await cursor.fetchone()
    return TicketSystem.from_row_sqlite(row) if row else None


async def get_system_by_id(system_id: int) -> Optional[TicketSystem]:
    async with _get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM ticket_systems WHERE id=?", (system_id,)
        )
        row = await cursor.fetchone()
    return TicketSystem.from_row_sqlite(row) if row else None


async def get_systems(guild_id: int) -> list[TicketSystem]:
    """Get all systems for a guild."""
    async with _get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM ticket_systems WHERE guild_id=? ORDER BY id", (guild_id,)
        )
        rows = await cursor.fetchall()
    return [TicketSystem.from_row_sqlite(r) for r in rows]


async def get_all_systems() -> list[TicketSystem]:
    """Get all systems across all guilds (for registering persistent views)."""
    async with _get_db() as db:
        cursor = await db.execute("SELECT * FROM ticket_systems ORDER BY id")
        rows = await cursor.fetchall()
    return [TicketSystem.from_row_sqlite(r) for r in rows]


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

    # Handle admin_role_ids conversion
    if "admin_role_ids" in fields and isinstance(fields["admin_role_ids"], list):
        fields["admin_role_ids"] = _format_role_ids(fields["admin_role_ids"])

    set_clauses = ", ".join(f"{col} = ?" for col in fields.keys())
    values = list(fields.values())

    async with _get_db() as db:
        cursor = await db.execute(
            f"UPDATE ticket_systems SET {set_clauses} WHERE id=? RETURNING *",
            (*values, system_id)
        )
        row = await cursor.fetchone()
        await db.commit()
    return TicketSystem.from_row_sqlite(row) if row else None


async def delete_system(guild_id: int, name: str) -> bool:
    """Delete system (cascades to delete all tickets)."""
    async with _get_db() as db:
        cursor = await db.execute("""
            DELETE FROM ticket_systems WHERE guild_id=? AND name=?
        """, (guild_id, name))
        await db.commit()
        return cursor.rowcount > 0


async def increment_counter(system_id: int) -> int:
    """Atomically increment counter and return new value."""
    async with _get_db() as db:
        cursor = await db.execute("""
            UPDATE ticket_systems
            SET ticket_counter = ticket_counter + 1
            WHERE id = ?
            RETURNING ticket_counter
        """, (system_id,))
        row = await cursor.fetchone()
        await db.commit()
    return row[0] if row else 0


# ── Ticket CRUD ────────────────────────────────────────────────────────────────

async def create_ticket(
    system_id: int,
    guild_id: int,
    channel_id: int,
    owner_id: int,
    ticket_number: int,
) -> Ticket:
    async with _get_db() as db:
        cursor = await db.execute("""
            INSERT INTO tickets (system_id, guild_id, channel_id, owner_id, ticket_number)
            VALUES (?, ?, ?, ?, ?)
            RETURNING *
        """, (system_id, guild_id, channel_id, owner_id, ticket_number))
        row = await cursor.fetchone()
        await db.commit()
    return Ticket.from_row_sqlite(row)


async def get_ticket_by_channel(channel_id: int) -> Optional[Ticket]:
    async with _get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE channel_id=?", (channel_id,)
        )
        row = await cursor.fetchone()
    return Ticket.from_row_sqlite(row) if row else None


async def get_open_ticket(system_id: int, owner_id: int) -> Optional[Ticket]:
    """Get user's open ticket in this system."""
    async with _get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM tickets
            WHERE system_id=? AND owner_id=? AND status='open'
        """, (system_id, owner_id))
        row = await cursor.fetchone()
    return Ticket.from_row_sqlite(row) if row else None


async def close_ticket(channel_id: int, closer_id: int) -> Optional[Ticket]:
    """Mark ticket as closed."""
    async with _get_db() as db:
        cursor = await db.execute("""
            UPDATE tickets
            SET status='closed', closed_at=CURRENT_TIMESTAMP, closer_id=?
            WHERE channel_id=?
            RETURNING *
        """, (closer_id, channel_id))
        row = await cursor.fetchone()
        await db.commit()
    return Ticket.from_row_sqlite(row) if row else None


async def delete_ticket_by_channel(channel_id: int) -> bool:
    """Delete ticket by channel ID."""
    async with _get_db() as db:
        cursor = await db.execute(
            "DELETE FROM tickets WHERE channel_id=?", (channel_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_ticket_channel(channel_id: int, message_id: int) -> Optional[Ticket]:
    """Update message ID in ticket."""
    async with _get_db() as db:
        cursor = await db.execute("""
            UPDATE tickets
            SET message_id=?
            WHERE channel_id=?
            RETURNING *
        """, (message_id, channel_id))
        row = await cursor.fetchone()
        await db.commit()
    return Ticket.from_row_sqlite(row) if row else None
