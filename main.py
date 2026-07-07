"""Главный файл бота - мульти-сервер, мульти-система тикетов."""
import logging
import sys
import os

import discord
from discord.ext import commands
from datetime import datetime, timezone

import database
from config import Config
from models import TicketSystem, Ticket
from views import TicketCreateView, TicketCloseView
from transcript import generate_html
from utils import ticket_rate_limiter, sanitize_text

# Настройка прокси для обхода блокировки Discord
# Добавьте в .env: PROXY_URL=socks5://user:pass@host:port или http://host:port
PROXY_URL = os.getenv("PROXY_URL", "")
if PROXY_URL:
    try:
        from discord.http import Route
        import aiohttp
        from python_socks.async_.asyncio.v2 import Proxy
        
        logger_proxy = logging.getLogger("discord.http")
        logger_proxy.info(f"🌐 Используется прокси: {PROXY_URL[:20]}...")
        
        # Патчим сессию aiohttp для использования прокси
        original_connector = aiohttp.TCPConnector
        
        class ProxyConnector:
            def __init__(self, *args, **kwargs):
                self.proxy = Proxy.from_url(PROXY_URL)
            
            async def connect(self, host, port, *args, **kwargs):
                return await self.proxy.connect(dest_host=host, dest_port=port)
    except ImportError:
        logging.warning("⚠️ Для прокси установите: pip install python-socks[asyncio] aiohttp")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        """Инициализация БД, регистрация persistent views, загрузка команд."""
        logger.info("🚀 Запуск бота...")

        # Подключаемся к БД (SQLite)
        await database.init(Config.DATABASE_PATH)

        # Загружаем все системы и регистрируем persistent views
        # чтобы кнопки работали после рестарта
        systems = await database.get_all_systems()
        for system in systems:
            self.add_view(TicketCreateView(self, system.id))
            self.add_view(TicketCloseView(self, system.id, ticket_owner_id=0))

        logger.info(f"🔁 Зарегистрировано {len(systems)} persistent view(s)")

        # Загружаем команды из commands.py
        await self.load_extension("commands")

        # Синхронизируем slash-команды
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Синхронизировано {len(synced)} slash-команд(ы)")
        except Exception as e:
            logger.error(f"⚠️ Ошибка синхронизации команд: {e}")

    async def on_ready(self):
        logger.info(f"✅ Бот запущен: {self.user} (ID: {self.user.id})")
        logger.info(f"📡 Подключен к {len(self.guilds)} серверам")

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"➕ Добавлен на сервер: {guild.name} (ID: {guild.id})")

    async def close(self):
        await database.close()
        await super().close()

    # ── Создание тикета ────────────────────────────────────────────────────────

    async def create_ticket(self, interaction: discord.Interaction, system_id: int):
        """Создаёт новый тикет для указанной системы."""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Только на сервере.", ephemeral=True)
            return

        system = await database.get_system_by_id(system_id)
        if not system:
            await interaction.response.send_message("❌ Система тикетов не найдена.", ephemeral=True)
            return

        # Проверяем дубликат в рамках этой системы
        existing = await database.get_open_ticket(system_id, interaction.user.id)
        if existing:
            channel = guild.get_channel(existing.channel_id)
            mention = channel.mention if channel else f"(ID: {existing.channel_id})"
            await interaction.response.send_message(
                f"❌ У вас уже есть открытый тикет в системе **{system.name}**: {mention}",
                ephemeral=True
            )
            return

        # Rate limiting — защита от спама
        if not ticket_rate_limiter.is_allowed(interaction.user.id):
            await interaction.response.send_message(
                "⏳ Слишком много запросов. Подождите несколько секунд.",
                ephemeral=True
            )
            return

        # Получаем/создаём категорию
        category = await self._get_or_create_category(guild, system)
        if not category:
            await interaction.response.send_message("❌ Не удалось получить категорию.", ephemeral=True)
            return

        # Атомарно получаем номер тикета
        ticket_number = await database.increment_counter(system_id)
        channel_name = f"{system.channel_prefix}-{ticket_number}"

        # Права доступа
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                manage_channels=True,
                send_messages=True,
                read_message_history=True,
            ),
        }
        for role_id in system.admin_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                )

        # Создаём канал
        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Тикет #{ticket_number} | Система: {system.name} | Создатель: {interaction.user} (ID: {interaction.user.id})",
                reason=f"Тикет создан пользователем {interaction.user}",
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка создания канала: {e}", ephemeral=True)
            return

        # Сохраняем в БД
        await database.create_ticket(
            system_id=system_id,
            guild_id=guild.id,
            channel_id=ticket_channel.id,
            owner_id=interaction.user.id,
            ticket_number=ticket_number,
        )

        # Приветственный embed (из настроек системы)
        # Заменяем {user}, {user.mention} на упоминание и {number} на номер
        title = system.ticket_embed_title.replace("{user}", interaction.user.mention).replace("{user.mention}", interaction.user.mention).replace("{number}", str(ticket_number))
        description = system.ticket_embed_desc.replace("{user}", interaction.user.mention).replace("{user.mention}", interaction.user.mention).replace("{number}", str(ticket_number))
        color = system.ticket_embed_color

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        # Добавляем поля только если они включены в настройках
        if system.ticket_embed_show_creator:
            embed.add_field(name="👤 Создатель", value=interaction.user.mention, inline=True)
        if system.ticket_embed_show_number:
            embed.add_field(name="🆔 Номер", value=f"#{ticket_number}", inline=True)
        if system.ticket_embed_show_system:
            embed.add_field(name="📂 Система", value=system.name, inline=True)
        self._set_footer(embed, system)

        close_view = TicketCloseView(self, system_id, interaction.user.id)

        # Собираем упоминания: пользователь + роли модераторов
        mentions = [interaction.user.mention]
        for role_id in system.admin_role_ids:
            role = guild.get_role(role_id)
            if role:
                mentions.append(role.mention)
        content = " ".join(mentions)

        try:
            msg = await ticket_channel.send(
                content=content,
                embed=embed,
                view=close_view,
            )
        except Exception as e:
            logger.warning(f"Ошибка отправки приветствия в тикет: {e}")
            msg = None

        # Обновляем ticket в БД с ID сообщения embed'а
        if msg:
            await database.update_ticket_channel(msg.channel.id, message_id=msg.id)
        else:
            # Если не удалось отправить сообщение, удаляем тикет из БД и канал
            try:
                await database.delete_ticket_by_channel(ticket_channel.id)
                await ticket_channel.delete(reason="Ошибка создания тикета — не удалось отправить сообщение")
                await interaction.response.send_message(
                    "❌ Не удалось отправить приветственное сообщение в тикет. Канал удалён.",
                    ephemeral=True
                )
            except Exception as del_e:
                logger.warning(f"Ошибка удаления пустого тикета: {del_e}")
                await interaction.response.send_message(
                    "❌ Тикет создан, но не удалось отправить сообщение. Обратитесь к модераторам.",
                    ephemeral=True
                )
            return

        await interaction.response.send_message(
            f"✅ Тикет создан: {ticket_channel.mention}",
            ephemeral=True,
        )
        logger.info(f"🎫 [{system.name}] Тикет #{ticket_number} создан для {interaction.user} на {guild.name}")

    # ── Закрытие тикета ───────────────────────────────────────────────────────

    async def close_ticket(
        self,
        channel: discord.TextChannel,
        closer: discord.User | discord.Member,
        system: TicketSystem,
    ):
        """Закрывает тикет: транскрипт → убирает права → переименовывает."""
        try:
            # Получаем тикет из БД
            ticket = await database.get_ticket_by_channel(channel.id)

            # Собираем историю сообщений
            messages: list[discord.Message] = []
            async for msg in channel.history(limit=None, oldest_first=True):
                messages.append(msg)

            opened_at = ticket.opened_at if ticket else channel.created_at
            closed_at = datetime.now(tz=timezone.utc)

            # Отправляем транскрипт
            if system.transcript_channel_id:
                transcript_channel = self.get_channel(system.transcript_channel_id)
                if not transcript_channel:
                    logger.warning(f"[{system.name}] Канал транскриптов {system.transcript_channel_id} не найден")
                elif not isinstance(transcript_channel, discord.TextChannel):
                    logger.warning(f"[{system.name}] Канал {system.transcript_channel_id} не является текстовым")
                else:
                    ticket_number = ticket.ticket_number if ticket else channel.name.split("-")[-1]
                    html_content = generate_html(
                        channel=channel,
                        messages=messages,
                        message_edits={},
                        opened_at=opened_at,
                        closed_at=closed_at,
                        closer=closer,
                        ticket_number=str(ticket_number),
                    )
                    import io
                    file = discord.File(
                        fp=io.BytesIO(html_content.encode("utf-8")),
                        filename=f"{system.channel_prefix}-{ticket_number}-transcript.html",
                    )
                    t_embed = discord.Embed(
                        title=f"📋 Транскрипт | {system.name} #{ticket_number}",
                        description=(
                            f"**Канал:** #{channel.name}\n"
                            f"**Система:** {system.name}\n"
                            f"**Закрыл:** {closer.mention}\n"
                            f"**Сообщений:** {len(messages)}\n"
                            f"**Открыт:** <t:{int(opened_at.timestamp())}:F>\n"
                            f"**Закрыт:** <t:{int(closed_at.timestamp())}:F>"
                        ),
                        color=0x5865f2,
                    )
                    self._set_footer(t_embed, system)
                    await transcript_channel.send(embed=t_embed, file=file)
                    logger.info(f"[{system.name}] Транскрипт #{ticket_number} отправлен в #{transcript_channel.name}")

            # Помечаем тикет закрытым в БД
            await database.close_ticket(channel.id, closer.id)

            # Убираем кнопку закрытия из первого сообщения бота
            async for msg in channel.history(limit=20, oldest_first=True):
                if msg.author == channel.guild.me and msg.components:
                    try:
                        await msg.edit(view=None)
                    except Exception:
                        pass
                    break

            # Убираем права создателя
            if ticket:
                owner = channel.guild.get_member(ticket.owner_id)
                if owner:
                    await channel.set_permissions(owner, overwrite=None, reason="Тикет закрыт")

            # Переименовываем канал
            ticket_number = ticket.ticket_number if ticket else channel.name.split("-")[-1]
            new_name = f"closed-{system.channel_prefix}-{ticket_number}"
            await channel.edit(name=new_name, reason=f"Тикет закрыт пользователем {closer}")

            # Финальное сообщение
            close_embed = discord.Embed(
                title="🔒 Тикет закрыт",
                description=f"Закрыт пользователем {closer.mention}.",
                color=0xff4444,
            )
            self._set_footer(close_embed, system)
            await channel.send(embed=close_embed)

            logger.info(f"🔒 [{system.name}] Тикет #{ticket_number} закрыт пользователем {closer}")
        except Exception as e:
            logger.error(f"Ошибка закрытия тикета: {e}")

    # ── Публикация сообщения с кнопкой ────────────────────────────────────────

    async def publish_system_message(self, system: TicketSystem) -> bool:
        """
        Публикует или обновляет сообщение с кнопкой для системы.
        Возвращает True при успехе.
        """
        if not system.channel_id:
            return False

        try:
            channel = await self.fetch_channel(system.channel_id)
        except Exception as e:
            logger.error(f"[{system.name}] Не удалось получить канал {system.channel_id}: {e}")
            return False

        if not isinstance(channel, discord.TextChannel):
            return False

        embed = discord.Embed(
            title=system.embed_title,
            description=system.embed_description,
            color=system.embed_color,
        )
        self._set_footer(embed, system)

        view = TicketCreateView(self, system.id)

        # Обновляем существующее сообщение
        if system.message_id:
            try:
                msg = await channel.fetch_message(system.message_id)
                await msg.edit(embed=embed, view=view)
                logger.info(f"[{system.name}] Сообщение обновлено")
                return True
            except discord.NotFound:
                logger.info(f"[{system.name}] Старое сообщение не найдено, создаём новое")
            except Exception as e:
                logger.warning(f"[{system.name}] Ошибка обновления: {e}")

        # Создаём новое
        try:
            msg = await channel.send(embed=embed, view=view)
            await database.update_system(system.id, message_id=msg.id)
            logger.info(f"[{system.name}] Новое сообщение создано (ID: {msg.id})")
            return True
        except Exception as e:
            logger.error(f"[{system.name}] Ошибка создания сообщения: {e}")
            return False

    # ── Вспомогательные методы ─────────────────────────────────────────────────

    async def _get_or_create_category(
        self,
        guild: discord.Guild,
        system: TicketSystem,
    ) -> discord.CategoryChannel | None:
        """Возвращает категорию из БД или создаёт новую."""
        if system.category_id:
            cat = guild.get_channel(system.category_id)
            if cat and isinstance(cat, discord.CategoryChannel):
                return cat

        # Создаём с правами
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
        }
        for role_id in system.admin_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, manage_channels=True)

        try:
            cat = await guild.create_category(
                name=f"🎫 {system.name}",
                overwrites=overwrites,
                reason=f"Автосоздание категории для системы {system.name}",
            )
            await database.update_system(system.id, category_id=cat.id)
            logger.info(f"[{system.name}] Создана категория: {cat.name} (ID: {cat.id})")
            return cat
        except Exception as e:
            logger.error(f"[{system.name}] Ошибка создания категории: {e}")
            return None

    @staticmethod
    def _set_footer(embed: discord.Embed, system: TicketSystem):
        if system.footer_icon_url:
            embed.set_footer(text=system.footer_text, icon_url=system.footer_icon_url)
        else:
            embed.set_footer(text=system.footer_text)


def main():
    errors = Config.validate()
    if errors:
        logger.error("❌ Ошибки конфигурации:")
        for err in errors:
            logger.error(f"  - {err}")
        return

    bot = TicketBot()
    bot.run(Config.TOKEN)


if __name__ == "__main__":
    main()
