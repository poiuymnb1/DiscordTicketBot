"""Dataclasses for database models."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class TicketSystem:
    id: int
    guild_id: int
    name: str
    channel_id: Optional[int]
    message_id: Optional[int]
    category_id: Optional[int]
    transcript_channel_id: Optional[int]
    admin_role_ids: list[int]
    channel_prefix: str
    embed_title: str
    embed_description: str
    embed_color: int
    footer_text: str
    footer_icon_url: str
    ticket_embed_title: str
    ticket_embed_desc: str
    ticket_embed_color: int
    ticket_embed_show_creator: bool
    ticket_embed_show_number: bool
    ticket_embed_show_system: bool
    ticket_counter: int

    @classmethod
    def from_row(cls, row) -> "TicketSystem":
        """Parse from PostgreSQL asyncpg row."""
        return cls(
            id=row["id"],
            guild_id=row["guild_id"],
            name=row["name"],
            channel_id=row["channel_id"],
            message_id=row["message_id"],
            category_id=row["category_id"],
            transcript_channel_id=row["transcript_channel_id"],
            admin_role_ids=list(row["admin_role_ids"] or []),
            channel_prefix=row["channel_prefix"],
            embed_title=row["embed_title"],
            embed_description=row["embed_description"],
            embed_color=row["embed_color"],
            footer_text=row["footer_text"],
            footer_icon_url=row["footer_icon_url"],
            ticket_embed_title=row["ticket_embed_title"],
            ticket_embed_desc=row["ticket_embed_desc"],
            ticket_embed_color=row["ticket_embed_color"],
            ticket_embed_show_creator=row.get("ticket_embed_show_creator", True),
            ticket_embed_show_number=row.get("ticket_embed_show_number", True),
            ticket_embed_show_system=row.get("ticket_embed_show_system", True),
            ticket_counter=row["ticket_counter"],
        )

    @classmethod
    def from_row_sqlite(cls, row) -> "TicketSystem":
        """Parse from SQLite aiosqlite row (tuple-like with column indices)."""
        # Get column names from cursor description
        return cls(
            id=row[0],
            guild_id=row[1],
            name=row[2],
            channel_id=row[3],
            message_id=row[4],
            category_id=row[5],
            transcript_channel_id=row[6],
            admin_role_ids=json.loads(row[7]) if row[7] else [],
            channel_prefix=row[8],
            embed_title=row[9],
            embed_description=row[10],
            embed_color=row[11],
            footer_text=row[12],
            footer_icon_url=row[13],
            ticket_embed_title=row[14],
            ticket_embed_desc=row[15],
            ticket_embed_color=row[16],
            ticket_embed_show_creator=bool(row[17]) if len(row) > 17 and row[17] is not None else True,
            ticket_embed_show_number=bool(row[18]) if len(row) > 18 and row[18] is not None else True,
            ticket_embed_show_system=bool(row[19]) if len(row) > 19 and row[19] is not None else True,
            ticket_counter=row[20] if len(row) > 20 else 0,
        )

    def is_configured(self) -> tuple[bool, list[str]]:
        """
        Check if system is ready for publishing.
        Returns (ok, list of issues).
        """
        issues = []
        if not self.channel_id:
            issues.append("channel not set (`/ticket set-channel`)")
        if not self.category_id:
            issues.append("category not set (`/ticket set-category`)")
        if not self.admin_role_ids:
            issues.append("moderator roles not set (`/ticket set-roles`)")
        return (len(issues) == 0, issues)


@dataclass
class Ticket:
    id: int
    system_id: int
    guild_id: int
    channel_id: int
    owner_id: int
    ticket_number: int
    status: str
    opened_at: datetime
    closed_at: Optional[datetime]
    closer_id: Optional[int]
    message_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> "Ticket":
        """Parse from PostgreSQL asyncpg row."""
        return cls(
            id=row["id"],
            system_id=row["system_id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            owner_id=row["owner_id"],
            ticket_number=row["ticket_number"],
            status=row["status"],
            opened_at=row["opened_at"],
            closed_at=row["closed_at"],
            closer_id=row["closer_id"],
        )

    @classmethod
    def from_row_sqlite(cls, row) -> "Ticket":
        """Parse from SQLite aiosqlite row (tuple-like)."""
        return cls(
            id=row[0],
            system_id=row[1],
            guild_id=row[2],
            channel_id=row[3],
            owner_id=row[4],
            ticket_number=row[5],
            status=row[6],
            opened_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
            closed_at=datetime.fromisoformat(row[8]) if row[8] else None,
            closer_id=row[9],
            message_id=row[10] if len(row) > 10 else None,
        )

    @property
    def is_open(self) -> bool:
        return self.status == "open"
