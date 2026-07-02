"""Discord UI Views — кнопки привязаны к конкретной тикетной системе через custom_id."""
import discord
from discord.ui import View, Button, button, Modal, TextInput
from discord import Embed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import TicketBot


class TicketCreateView(View):
    """
    Persistent view с кнопкой 'Создать тикет'.
    custom_id формата: ticket:create:{system_id}
    Благодаря system_id в custom_id бот после рестарта знает
    к какой системе относится кнопка.
    """

    def __init__(self, bot: "TicketBot", system_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.system_id = system_id

        # Добавляем кнопку вручную чтобы передать динамический custom_id
        btn = Button(
            label="🎫 Создать тикет",
            style=discord.ButtonStyle.primary,
            custom_id=f"ticket:create:{system_id}",
        )
        btn.callback = self._callback
        self.add_item(btn)

    async def _callback(self, interaction: discord.Interaction):
        await self.bot.create_ticket(interaction, self.system_id)


class TicketCloseView(View):
    """
    Persistent view с кнопкой 'Закрыть тикет'.
    custom_id формата: ticket:close:{system_id}
    """

    def __init__(self, bot: "TicketBot", system_id: int, ticket_owner_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.system_id = system_id
        self.ticket_owner_id = ticket_owner_id

        btn = Button(
            label="🔒 Закрыть тикет",
            style=discord.ButtonStyle.danger,
            custom_id=f"ticket:close:{system_id}",
        )
        btn.callback = self._callback
        self.add_item(btn)

    async def _callback(self, interaction: discord.Interaction):
        import database
        system = await database.get_system_by_id(self.system_id)
        if not system:
            await interaction.response.send_message("❌ Система тикетов не найдена.", ephemeral=True)
            return

        is_owner = interaction.user.id == self.ticket_owner_id
        is_admin = any(role.id in system.admin_role_ids for role in interaction.user.roles)

        if not (is_owner or is_admin):
            await interaction.response.send_message(
                "❌ Только создатель тикета или модератор могут закрыть тикет.",
                ephemeral=True
            )
            return

        confirm_view = ConfirmCloseView(self.bot, interaction.channel, self.system_id, self.ticket_owner_id)
        await interaction.response.send_message(
            "Вы уверены, что хотите закрыть тикет?",
            view=confirm_view,
            ephemeral=True
        )


class ConfirmCloseView(View):
    """Подтверждение закрытия тикета."""

    def __init__(self, bot: "TicketBot", channel: discord.TextChannel, system_id: int, ticket_owner_id: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.channel = channel
        self.system_id = system_id
        self.ticket_owner_id = ticket_owner_id

    @button(label="✅ Да, закрыть", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, btn: Button):
        import database
        system = await database.get_system_by_id(self.system_id)
        if not system:
            await interaction.response.send_message("❌ Система не найдена.", ephemeral=True)
            return

        is_owner = interaction.user.id == self.ticket_owner_id
        is_admin = any(role.id in system.admin_role_ids for role in interaction.user.roles)

        if not (is_owner or is_admin):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        await interaction.response.edit_message(content="🔒 Закрытие тикета...", view=None)
        await self.bot.close_ticket(self.channel, interaction.user, system)

    @button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.edit_message(content="✅ Закрытие отменено.", view=None)

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass


# ── Modal для предпросмотра embed ─────────────────────────────────────────────

class EmbedPreviewModal(Modal):
    """Модальное окно для предпросмотра изменений embed."""
    
    def __init__(self, bot: "TicketBot", system_id: int, title: str, description: str, color: int, footer_text: str, footer_icon_url: str, is_ticket_embed: bool = False):
        title_text = "Предпросмотр embed тикета" if is_ticket_embed else "Предпросмотр embed с кнопкой"
        super().__init__(title=title_text)
        self.bot = bot
        self.system_id = system_id
        self.is_ticket_embed = is_ticket_embed
        
        # Отображаемые поля
        desc_hint = "Описание ({user}, {number})" if is_ticket_embed else "Описание"
        self.add_item(TextInput(label="Заголовок", default=title, max_length=256, required=True))
        self.add_item(TextInput(label=desc_hint, default=description, style=discord.TextStyle.paragraph, max_length=4000, required=False))
        hex_color = f"#{color:06x}"
        self.add_item(TextInput(label="Цвет (HEX)", default=hex_color, max_length=7, required=False))
        self.add_item(TextInput(label="Текст футера", default=footer_text, max_length=200, required=False))
        self.add_item(TextInput(label="Иконка футера (HTTPS)", default=footer_icon_url, required=False))

    async def on_submit(self, interaction: discord.Interaction):
        # Валидация цвета
        color_str = self.children[2].value.strip()
        try:
            color = int(color_str.lstrip("#"), 16) if color_str else 2829105
        except ValueError:
            await interaction.response.send_message("❌ Неверный формат цвета. Используйте HEX (например: #2b2d31)", ephemeral=True)
            return

        # Генерируем embed для предпросмотра
        embed = Embed(
            title=self.children[0].value,
            description=self.children[1].value or "Описание отсутствует",
            color=color,
        )
        embed.set_footer(text=self.children[3].value or "Ticket System")

        if self.children[4].value.strip():
            embed.set_footer(text=self.children[3].value, icon_url=self.children[4].value.strip())

        view = ConfirmEmbedView(
            bot=self.bot,
            system_id=self.system_id,
            title=self.children[0].value,
            description=self.children[1].value,
            color=color,
            footer_text=self.children[3].value,
            footer_icon_url=self.children[4].value.strip(),
            is_ticket_embed=self.is_ticket_embed,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ConfirmEmbedView(View):
    """Подтверждение изменений embed."""

    def __init__(
        self,
        bot: "TicketBot",
        system_id: int,
        title: str,
        description: str,
        color: int,
        footer_text: str,
        footer_icon_url: str,
        is_ticket_embed: bool = False,
        show_creator: bool = True,
        show_number: bool = True,
        show_system: bool = True,
    ):
        super().__init__(timeout=30)
        self.bot = bot
        self.system_id = system_id
        self.title = title
        self.description = description
        self.color = color
        self.footer_text = footer_text
        self.footer_icon_url = footer_icon_url
        self.is_ticket_embed = is_ticket_embed
        self.show_creator = show_creator
        self.show_number = show_number
        self.show_system = show_system

        # Только для embed тикета добавляем кнопки переключения полей
        if is_ticket_embed:
            creator_style = discord.ButtonStyle.success if show_creator else discord.ButtonStyle.secondary
            number_style = discord.ButtonStyle.success if show_number else discord.ButtonStyle.secondary
            system_style = discord.ButtonStyle.success if show_system else discord.ButtonStyle.secondary

            self.add_item(Button(label=f"👤 {'✓' if show_creator else '✗'}", style=creator_style, custom_id="toggle_creator"))
            self.add_item(Button(label=f"🆔 {'✓' if show_number else '✗'}", style=number_style, custom_id="toggle_number"))
            self.add_item(Button(label=f"📂 {'✓' if show_system else '✗'}", style=system_style, custom_id="toggle_system"))

        self.add_item(Button(label="✅ Применить", style=discord.ButtonStyle.success, custom_id="apply"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Обработка переключения кнопок
        if interaction.data.get("custom_id") == "toggle_creator":
            self.show_creator = not self.show_creator
            creator_style = discord.ButtonStyle.success if self.show_creator else discord.ButtonStyle.secondary
            for child in self.children:
                if getattr(child, "custom_id", None) == "toggle_creator":
                    child.label = f"👤 {'✓' if self.show_creator else '✗'}"
                    child.style = creator_style
            await interaction.response.edit_message(view=self)
            return False

        elif interaction.data.get("custom_id") == "toggle_number":
            self.show_number = not self.show_number
            number_style = discord.ButtonStyle.success if self.show_number else discord.ButtonStyle.secondary
            for child in self.children:
                if getattr(child, "custom_id", None) == "toggle_number":
                    child.label = f"🆔 {'✓' if self.show_number else '✗'}"
                    child.style = number_style
            await interaction.response.edit_message(view=self)
            return False

        elif interaction.data.get("custom_id") == "toggle_system":
            self.show_system = not self.show_system
            system_style = discord.ButtonStyle.success if self.show_system else discord.ButtonStyle.secondary
            for child in self.children:
                if getattr(child, "custom_id", None) == "toggle_system":
                    child.label = f"📂 {'✓' if self.show_system else '✗'}"
                    child.style = system_style
            await interaction.response.edit_message(view=self)
            return False

        elif interaction.data.get("custom_id") == "apply":
            await self._apply_changes(interaction)
            return False

        return True

    async def _apply_changes(self, interaction: discord.Interaction):
        import database
        system = await database.get_system_by_id(self.system_id)
        if not system:
            await interaction.response.edit_message(content="❌ Система не найдена.", view=None)
            return

        if self.is_ticket_embed:
            updates = {
                "ticket_embed_title": self.title,
                "ticket_embed_desc": self.description.replace("\\n", "\n"),
                "ticket_embed_color": self.color,
                "ticket_embed_show_creator": self.show_creator,
                "ticket_embed_show_number": self.show_number,
                "ticket_embed_show_system": self.show_system,
            }
        else:
            updates = {
                "embed_title": self.title,
                "embed_description": self.description.replace("\\n", "\n"),
                "embed_color": self.color,
                "footer_text": self.footer_text,
                "footer_icon_url": self.footer_icon_url,
            }

        await database.update_system(system.id, **updates)
        await interaction.response.edit_message(
            content="✅ Embed успешно обновлён!",
            view=None
        )

    @button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.edit_message(content="❌ Изменения отменены.", view=None)