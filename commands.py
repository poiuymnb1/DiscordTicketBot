import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, TYPE_CHECKING

import database
from utils import sanitize_text
from views import TicketCreateView

if TYPE_CHECKING:
    from main import TicketBot


def is_admin():
    """Проверяет что у пользователя есть права администратора на сервере."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("❌ Только на сервере.", ephemeral=True)
            return False
        member = interaction.user
        if not member.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Нужны права **Администратора** на сервере.",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)


async def system_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Автодополнение названий систем для текущего сервера."""
    systems = await database.get_systems(interaction.guild_id)
    return [
        app_commands.Choice(name=s.name, value=s.name)
        for s in systems
        if current.lower() in s.name.lower()
    ][:25]


class TicketCommands(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    ticket = app_commands.Group(
        name="ticket",
        description="Управление тикетными системами",
    )

    # ── /ticket create ─────────────────────────────────────────────────────────

    @ticket.command(name="create", description="Создать новую тикетную систему")
    @app_commands.describe(name="Название системы (например: вступление, main-набор)")
    @is_admin()
    async def ticket_create(self, interaction: discord.Interaction, name: str):
        existing = await database.get_system(interaction.guild_id, name)
        if existing:
            await interaction.response.send_message(
                f"❌ Система **{name}** уже существует. Используйте `/ticket info name:{name}` для просмотра настроек.",
                ephemeral=True
            )
            return

        system = await database.create_system(interaction.guild_id, name)

        embed = discord.Embed(
            title=f"✅ Система **{name}** создана",
            description=(
                "Теперь настройте систему:\n\n"
                f"1. `/ticket set-channel name:{name} channel:#канал` — канал для кнопки\n"
                f"2. `/ticket set-category name:{name} category_id:ID` — ID категории (или бот создаст сам)\n"
                f"3. `/ticket set-roles name:{name} roles:@роль1 @роль2` — роли модераторов\n"
                f"4. `/ticket set-prefix name:{name} prefix:ticket` — префикс имени канала\n"
                f"5. `/ticket set-embed name:{name}` — заголовок и описание кнопки\n"
                f"6. `/ticket publish name:{name}` — опубликовать кнопку\n\n"
                f"Или сразу запустите `/ticket setup name:{name}` — пошаговая настройка."
            ),
            color=0x57f287,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /ticket delete ─────────────────────────────────────────────────────────

    @ticket.command(name="delete", description="Удалить тикетную систему")
    @app_commands.describe(name="Название системы")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def ticket_delete(self, interaction: discord.Interaction, name: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        # Подтверждение через эфемерную кнопку
        view = _ConfirmDeleteView(self.bot, system.id, name)
        await interaction.response.send_message(
            f"⚠️ Удалить систему **{name}**? Все записи о тикетах будут удалены из БД. "
            f"Каналы тикетов на сервере **не** удаляются.",
            view=view,
            ephemeral=True,
        )

    # ── /ticket list ───────────────────────────────────────────────────────────

    @ticket.command(name="list", description="Список всех тикетных систем сервера")
    @is_admin()
    async def ticket_list(self, interaction: discord.Interaction):
        systems = await database.get_systems(interaction.guild_id)
        if not systems:
            await interaction.response.send_message(
                "📭 На этом сервере нет тикетных систем. Создайте первую: `/ticket create`",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🎫 Тикетные системы сервера ({len(systems)})",
            color=0x5865f2,
        )
        for s in systems:
            ok, issues = s.is_configured()
            status = "✅ Настроена" if ok else f"⚠️ Не настроена ({len(issues)} проблемы)"
            channel = f"<#{s.channel_id}>" if s.channel_id else "не задан"
            embed.add_field(
                name=f"{'🟢' if ok else '🔴'} {s.name}",
                value=(
                    f"Канал: {channel}\n"
                    f"Префикс: `{s.channel_prefix}`\n"
                    f"Тикетов создано: {s.ticket_counter}\n"
                    f"Статус: {status}"
                ),
                inline=True,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /ticket info ───────────────────────────────────────────────────────────

    @ticket.command(name="info", description="Подробные настройки системы")
    @app_commands.describe(name="Название системы")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def ticket_info(self, interaction: discord.Interaction, name: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        ok, issues = system.is_configured()
        roles = ", ".join(f"<@&{r}>" for r in system.admin_role_ids) or "не заданы"

        embed = discord.Embed(
            title=f"🎫 Система: {system.name}",
            color=0x5865f2 if ok else 0xfaa61a,
        )
        embed.add_field(name="📢 Канал кнопки",       value=f"<#{system.channel_id}>" if system.channel_id else "❌ не задан", inline=True)
        embed.add_field(name="📁 Категория",           value=f"<#{system.category_id}>" if system.category_id else "⚠️ автосоздание", inline=True)
        embed.add_field(name="📋 Транскрипты",         value=f"<#{system.transcript_channel_id}>" if system.transcript_channel_id else "отключены", inline=True)
        embed.add_field(name="🛡️ Роли модераторов",   value=roles, inline=False)
        embed.add_field(name="🏷️ Префикс канала",     value=f"`{system.channel_prefix}`", inline=True)
        embed.add_field(name="🔢 Счётчик тикетов",    value=str(system.ticket_counter), inline=True)
        embed.add_field(name="📝 Заголовок embed",     value=system.embed_title, inline=False)
        embed.add_field(name="📄 Описание embed",      value=system.embed_description[:200] + ("..." if len(system.embed_description) > 200 else ""), inline=False)

        if issues:
            embed.add_field(
                name="⚠️ Требуется настройка",
                value="\n".join(f"• {i}" for i in issues),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /ticket set-channel ────────────────────────────────────────────────────

    @ticket.command(name="set-channel", description="Задать канал для публикации кнопки")
    @app_commands.describe(name="Название системы", channel="Канал для сообщения с кнопкой")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def set_channel(self, interaction: discord.Interaction, name: str, channel: discord.TextChannel):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        await database.update_system(system.id, channel_id=channel.id, message_id=None)
        await interaction.response.send_message(
            f"✅ Канал для системы **{name}** → {channel.mention}\n"
            f"Запустите `/ticket publish name:{name}` чтобы опубликовать кнопку.",
            ephemeral=True
        )

    # ── /ticket set-category ───────────────────────────────────────────────────

    @ticket.command(name="set-category", description="Задать категорию для тикетов")
    @app_commands.describe(name="Название системы", category_id="ID категории Discord")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def set_category(self, interaction: discord.Interaction, name: str, category_id: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        try:
            cat_id = int(category_id)
        except ValueError:
            await interaction.response.send_message("❌ ID должен быть числом.", ephemeral=True)
            return

        category = interaction.guild.get_channel(cat_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                f"❌ Категория с ID `{cat_id}` не найдена на сервере.",
                ephemeral=True
            )
            return

        await database.update_system(system.id, category_id=cat_id)
        await interaction.response.send_message(
            f"✅ Категория для системы **{name}** → **{category.name}**",
            ephemeral=True
        )

    # ── /ticket set-roles ──────────────────────────────────────────────────────

    @ticket.command(name="set-roles", description="Задать роли модераторов (до 5 ролей)")
    @app_commands.describe(
        name="Название системы",
        role1="Роль модераторов",
        role2="Дополнительная роль (необязательно)",
        role3="Дополнительная роль (необязательно)",
        role4="Дополнительная роль (необязательно)",
        role5="Дополнительная роль (необязательно)",
    )
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def set_roles(
        self,
        interaction: discord.Interaction,
        name: str,
        role1: discord.Role,
        role2: Optional[discord.Role] = None,
        role3: Optional[discord.Role] = None,
        role4: Optional[discord.Role] = None,
        role5: Optional[discord.Role] = None,
    ):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]
        role_ids = [r.id for r in roles]
        await database.update_system(system.id, admin_role_ids=role_ids)

        roles_mention = ", ".join(r.mention for r in roles)
        await interaction.response.send_message(
            f"✅ Роли модераторов для системы **{name}**: {roles_mention}",
            ephemeral=True
        )

    # ── /ticket set-prefix ─────────────────────────────────────────────────────

    @ticket.command(name="set-prefix", description="Задать префикс имени канала тикета")
    @app_commands.describe(name="Название системы", prefix="Префикс (например: ticket, entry, main)")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def set_prefix(self, interaction: discord.Interaction, name: str, prefix: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        # Только буквы, цифры и дефис
        import re
        clean = re.sub(r"[^a-z0-9\-]", "", prefix.lower())
        if not clean:
            await interaction.response.send_message(
                "❌ Префикс может содержать только латинские буквы, цифры и дефис.",
                ephemeral=True
            )
            return

        await database.update_system(system.id, channel_prefix=clean)
        await interaction.response.send_message(
            f"✅ Префикс для системы **{name}**: `{clean}-N` (например: `{clean}-1`)",
            ephemeral=True
        )

    # ── /ticket edit-embed ─────────────────────────────────────────────────────

    @ticket.command(name="edit-embed", description="Настроить embed сообщения при создании тикета")
    @app_commands.describe(name="Название системы")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def edit_embed(self, interaction: discord.Interaction, name: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        # Открываем модал с текущими значениями для embed внутри тикета
        from views import EmbedPreviewModal
        modal = EmbedPreviewModal(
            bot=self.bot,
            system_id=system.id,
            title=system.ticket_embed_title,
            description=system.ticket_embed_desc,
            color=system.ticket_embed_color,
            footer_text=system.footer_text,
            footer_icon_url=system.footer_icon_url,
            is_ticket_embed=True,  # Это embed внутри тикета
        )
        await interaction.response.send_modal(modal)

    # ── /ticket set-embed ──────────────────────────────────────────────────────

    @ticket.command(name="set-embed", description="Настроить embed сообщения с кнопкой")
    @app_commands.describe(name="Название системы")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def set_embed(self, interaction: discord.Interaction, name: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        # Открываем модал с текущими значениями для embed с кнопкой
        from views import EmbedPreviewModal
        modal = EmbedPreviewModal(
            bot=self.bot,
            system_id=system.id,
            title=system.embed_title,
            description=system.embed_description,
            color=system.embed_color,
            footer_text=system.footer_text,
            footer_icon_url=system.footer_icon_url,
            is_ticket_embed=False,  # Это embed с кнопкой, не внутри тикета
        )
        await interaction.response.send_modal(modal)

    # ── /ticket set-transcript ─────────────────────────────────────────────────

    @ticket.command(name="set-transcript", description="Задать канал для транскриптов")
    @app_commands.describe(name="Название системы", channel="Канал для отправки транскриптов")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def set_transcript(self, interaction: discord.Interaction, name: str, channel: discord.TextChannel):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        await database.update_system(system.id, transcript_channel_id=channel.id)
        await interaction.response.send_message(
            f"✅ Канал транскриптов для системы **{name}** → {channel.mention}",
            ephemeral=True
        )

    # ── /ticket publish ────────────────────────────────────────────────────────

    @ticket.command(name="publish", description="Опубликовать или обновить кнопку создания тикета")
    @app_commands.describe(name="Название системы")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def ticket_publish(self, interaction: discord.Interaction, name: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(f"❌ Система **{name}** не найдена.", ephemeral=True)
            return

        ok, issues = system.is_configured()
        if not ok:
            problems = "\n".join(f"• {i}" for i in issues)
            await interaction.response.send_message(
                f"❌ Система **{name}** не готова к публикации:\n{problems}",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Регистрируем view на случай если это первая публикация
        self.bot.add_view(TicketCreateView(self.bot, system.id))  # noqa

        success = await self.bot.publish_system_message(system)
        if success:
            await interaction.followup.send(
                f"✅ Кнопка для системы **{name}** опубликована в <#{system.channel_id}>",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Не удалось опубликовать. Проверьте права бота в канале <#{system.channel_id}>.",
                ephemeral=True
            )

    # ── /ticket setup (пошаговый мастер) ──────────────────────────────────────

    @ticket.command(name="setup", description="Пошаговая настройка системы через форму")
    @app_commands.describe(name="Название системы")
    @app_commands.autocomplete(name=system_autocomplete)
    @is_admin()
    async def ticket_setup(self, interaction: discord.Interaction, name: str):
        system = await database.get_system(interaction.guild_id, name)
        if not system:
            await interaction.response.send_message(
                f"❌ Система **{name}** не найдена. Сначала создайте: `/ticket create name:{name}`",
                ephemeral=True
            )
            return

        modal = SetupModal(system)
        await interaction.response.send_modal(modal)


# ── Modal для /ticket setup ────────────────────────────────────────────────────

class SetupModal(discord.ui.Modal, title="Настройка тикетной системы"):
    def __init__(self, system):
        super().__init__()
        self.system = system

        self.embed_title = discord.ui.TextInput(
            label="Заголовок embed",
            default=system.embed_title,
            max_length=256,
        )
        self.embed_desc = discord.ui.TextInput(
            label="Описание embed",
            style=discord.TextStyle.paragraph,
            default=system.embed_description,
            max_length=4000,
        )
        self.prefix = discord.ui.TextInput(
            label="Префикс канала тикета",
            default=system.channel_prefix,
            max_length=20,
            placeholder="ticket, entry, main..."
        )
        self.footer = discord.ui.TextInput(
            label="Текст футера",
            default=system.footer_text,
            max_length=200,
        )
        self.footer_icon = discord.ui.TextInput(
            label="Ссылка на иконку футера (HTTPS или пусто)",
            default=system.footer_icon_url,
            required=False,
            max_length=500,
        )

        self.add_item(self.embed_title)
        self.add_item(self.embed_desc)
        self.add_item(self.prefix)
        self.add_item(self.footer)
        self.add_item(self.footer_icon)

    async def on_submit(self, interaction: discord.Interaction):
        import re
        clean_prefix = re.sub(r"[^a-z0-9\-]", "", self.prefix.value.lower())
        if not clean_prefix:
            clean_prefix = "ticket"

        await database.update_system(
            self.system.id,
            embed_title=sanitize_text(self.embed_title.value),
            embed_description=sanitize_text(self.embed_desc.value.replace("\\n", "\n")),
            channel_prefix=clean_prefix,
            footer_text=sanitize_text(self.footer.value, max_length=200),
            footer_icon_url=self.footer_icon.value.strip(),
        )
        await interaction.response.send_message(
            f"✅ Система **{self.system.name}** обновлена!\n"
            f"Не забудьте запустить `/ticket publish name:{self.system.name}`",
            ephemeral=True
        )


# ── View для подтверждения удаления ───────────────────────────────────────────

class _ConfirmDeleteView(discord.ui.View):
    def __init__(self, bot: "TicketBot", system_id: int, system_name: str):
        super().__init__(timeout=30)
        self.bot = bot
        self.system_id = system_id
        self.system_name = system_name

    @discord.ui.button(label="🗑️ Удалить", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, btn: discord.ui.Button):
        deleted = await database.delete_system(interaction.guild_id, self.system_name)
        if deleted:
            await interaction.response.edit_message(
                content=f"✅ Система **{self.system_name}** удалена.",
                view=None
            )
        else:
            await interaction.response.edit_message(
                content=f"❌ Не удалось удалить систему **{self.system_name}**.",
                view=None
            )

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.edit_message(content="✅ Удаление отменено.", view=None)


# ── Загрузка Cog ───────────────────────────────────────────────────────────────

async def setup(bot: "TicketBot"):
    await bot.add_cog(TicketCommands(bot))
