"""HTML transcript generator for tickets."""
import html
import discord
from datetime import datetime, timezone


# Labels for bot system messages
_BOT_SYSTEM_LABELS = {
    "ticket:welcome": "Bot welcome message",
    "ticket:closed":  "Ticket closure message",
}

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _fmt_time(dt: datetime) -> str:
    """Format datetime to readable string (UTC+0, can be adjusted)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%d.%m.%Y %H:%M:%S UTC")


def _is_image_url(url: str) -> bool:
    low = url.lower().split("?")[0]
    return any(low.endswith(ext) for ext in _IMAGE_EXTENSIONS)


def _clean_url(url: str) -> str:
    """
    Remove format= and quality= parameters from Discord CDN URL
    that turn GIFs into static webp.
    Keep only authorization parameters (ex=, is=, hm=).
    """
    if "?" not in url:
        return url
    base, query = url.split("?", 1)
    # Параметры которые ломают анимацию — убираем
    _STRIP = {"format", "quality", "width", "height"}
    kept = [p for p in query.split("&") if p.split("=")[0].lower() not in _STRIP]
    return base + ("?" + "&".join(kept) if kept else "")


def _esc(text: str) -> str:
    return html.escape(str(text))


def _render_attachment(attachment: discord.Attachment) -> str:
    """Render attachment: image/gif or file link."""
    if _is_image_url(attachment.url):
        # Для отображения чистим URL от параметров format=webp/quality= (ломают гифки)
        display_url = _clean_url(attachment.url)
        is_gif = attachment.filename.lower().endswith(".gif")
        extra_class = " gif-attachment" if is_gif else ""
        return (
            f'<div class="attachment image-attachment{extra_class}">'
            f'<a href="{_esc(attachment.url)}" target="_blank">'
            f'<img src="{_esc(display_url)}" alt="{_esc(attachment.filename)}" '
            f'title="{_esc(attachment.filename)}" loading="lazy">'
            f'</a>'
            f'<div class="attachment-name">{_esc(attachment.filename)}'
            f'{" 🎞️" if is_gif else ""}</div>'
            f'</div>'
        )
    else:
        size_kb = round(attachment.size / 1024, 1)
        return (
            f'<div class="attachment file-attachment">'
            f'<span class="file-icon">📎</span> '
            f'<a href="{_esc(attachment.url)}" target="_blank">{_esc(attachment.filename)}</a>'
            f' <span class="file-size">({size_kb} KB)</span>'
            f'</div>'
        )


def _render_embed(embed: discord.Embed) -> str:
    """Render Discord embed."""
    color = f"#{embed.color.value:06x}" if embed.color else "#2b2d31"
    parts = [f'<div class="embed" style="border-left-color:{color}">']

    if embed.author:
        icon = (f'<img src="{_esc(embed.author.icon_url)}" class="embed-author-icon">'
                if embed.author.icon_url else "")
        parts.append(f'<div class="embed-author">{icon}{_esc(embed.author.name)}</div>')

    if embed.title:
        title_html = (
            f'<a href="{_esc(embed.url)}" target="_blank">{_esc(embed.title)}</a>'
            if embed.url else _esc(embed.title)
        )
        parts.append(f'<div class="embed-title">{title_html}</div>')

    if embed.description:
        parts.append(f'<div class="embed-description">{_esc(embed.description)}</div>')

    if embed.fields:
        parts.append('<div class="embed-fields">')
        for field in embed.fields:
            inline_class = "inline" if field.inline else ""
            parts.append(
                f'<div class="embed-field {inline_class}">'
                f'<div class="embed-field-name">{_esc(field.name)}</div>'
                f'<div class="embed-field-value">{_esc(field.value)}</div>'
                f'</div>'
            )
        parts.append('</div>')

    if embed.image and embed.image.url:
        parts.append(
            f'<div class="embed-image">'
            f'<img src="{_esc(embed.image.url)}" loading="lazy">'
            f'</div>'
        )

    if embed.thumbnail and embed.thumbnail.url:
        parts.append(
            f'<img src="{_esc(embed.thumbnail.url)}" class="embed-thumbnail" loading="lazy">'
        )

    if embed.footer:
        icon = (f'<img src="{_esc(embed.footer.icon_url)}" class="embed-footer-icon">'
                if embed.footer.icon_url else "")
        parts.append(f'<div class="embed-footer">{icon}{_esc(embed.footer.text)}</div>')

    parts.append('</div>')
    return "\n".join(parts)


def _render_message(msg: discord.Message, edits: list[discord.Message]) -> str:
    """Рендерит одно сообщение со всеми редактированиями."""
    is_bot = msg.author.bot

    # Определяем системную метку для сообщений бота
    system_label = ""
    if is_bot:
        # Пытаемся определить тип по содержимому embed'а
        if msg.embeds:
            title = (msg.embeds[0].title or "").lower()
            if "тикет" in title and ("создан" in title or "№" in title or "#" in title):
                system_label = "Приветственное сообщение бота"
            elif "закрыт" in title:
                system_label = "Сообщение о закрытии тикета"
            else:
                system_label = "Сообщение бота"
        else:
            system_label = "Сообщение бота"

    avatar_url = msg.author.display_avatar.url if msg.author.display_avatar else ""
    author_name = _esc(str(msg.author.display_name))
    author_tag = _esc(str(msg.author))
    timestamp = _fmt_time(msg.created_at)

    row_class = "message bot-message" if is_bot else "message"

    parts = [
        f'<div class="{row_class}" id="msg-{msg.id}">',
        f'  <div class="avatar-wrap">',
        f'    <img src="{_esc(avatar_url)}" class="avatar" alt="{author_name}" loading="lazy">',
        f'  </div>',
        f'  <div class="message-body">',
        f'    <div class="message-header">',
        f'      <span class="author" title="{author_tag}">{author_name}</span>',
    ]

    if is_bot:
        parts.append(f'      <span class="bot-badge">БОТ</span>')
    if system_label:
        parts.append(f'      <span class="system-label">{_esc(system_label)}</span>')

    parts.append(f'      <span class="timestamp">{timestamp}</span>')
    parts.append(f'    </div>')  # /message-header

    # Текст оригинального сообщения
    if msg.content:
        # Заменяем упоминания вида <@ID> на @username если возможно
        content_text = _esc(msg.content)
        parts.append(f'    <div class="message-content">{content_text}</div>')

    # Редактирования
    if edits:
        parts.append('    <div class="edits">')
        parts.append('      <div class="edits-label">✏️ История редактирований:</div>')
        for i, edit_ver in enumerate(edits, 1):
            edit_time = _fmt_time(edit_ver.edited_at or edit_ver.created_at)
            parts.append(
                f'      <div class="edit-version">'
                f'        <span class="edit-num">Версия {i}</span>'
                f'        <span class="edit-time">{edit_time}</span>'
                f'        <div class="edit-content">{_esc(edit_ver.content)}</div>'
                f'      </div>'
            )
        parts.append('    </div>')  # /edits

    # Вложения
    if msg.attachments:
        parts.append('    <div class="attachments">')
        for att in msg.attachments:
            parts.append(_render_attachment(att))
        parts.append('    </div>')

    # Embed'ы
    if msg.embeds:
        parts.append('    <div class="embeds">')
        for emb in msg.embeds:
            parts.append(_render_embed(emb))
        parts.append('    </div>')

    # Реакции
    if msg.reactions:
        reactions_html = " ".join(
            f'<span class="reaction" title="{_esc(str(r.emoji))}">'
            f'{_esc(str(r.emoji))} {r.count}'
            f'</span>'
            for r in msg.reactions
        )
        parts.append(f'    <div class="reactions">{reactions_html}</div>')

    parts.append('  </div>')  # /message-body
    parts.append('</div>')    # /message

    return "\n".join(parts)


def generate_html(
    channel: discord.TextChannel,
    messages: list[discord.Message],
    message_edits: dict[int, list[discord.Message]],
    opened_at: datetime,
    closed_at: datetime,
    closer: discord.User | discord.Member,
    ticket_number: str,
) -> str:
    """
    Генерирует полный HTML транскрипт.

    :param channel: Канал тикета
    :param messages: Список сообщений в хронологическом порядке
    :param message_edits: dict[message_id -> список версий после редактирований]
    :param opened_at: Время создания тикета
    :param closed_at: Время закрытия
    :param closer: Кто закрыл
    :param ticket_number: Номер тикета (строка)
    """
    messages_html = "\n".join(
        _render_message(msg, message_edits.get(msg.id, []))
        for msg in messages
    )

    # Участники
    seen_ids: set[int] = set()
    participants: list[str] = []
    for msg in messages:
        if msg.author.id not in seen_ids:
            seen_ids.add(msg.author.id)
            badge = ' <span class="bot-badge">БОТ</span>' if msg.author.bot else ""
            participants.append(
                f'<span class="participant">{_esc(str(msg.author.display_name))}{badge}</span>'
            )

    participants_html = ", ".join(participants) if participants else "—"
    msg_count = len(messages)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Транскрипт тикета #{ticket_number}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #1e1f22;
      color: #dbdee1;
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}

    a {{ color: #00aff4; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* ── Header ── */
    .header {{
      background: #2b2d31;
      border-bottom: 2px solid #1e1f22;
      padding: 20px 32px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .header-icon {{ font-size: 32px; }}
    .header-info h1 {{ font-size: 20px; color: #fff; font-weight: 700; }}
    .header-info p  {{ color: #949ba4; font-size: 13px; margin-top: 2px; }}

    /* ── Meta block ── */
    .meta {{
      background: #2b2d31;
      margin: 16px 32px;
      border-radius: 8px;
      padding: 16px 20px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 12px;
    }}
    .meta-item {{ display: flex; flex-direction: column; gap: 2px; }}
    .meta-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase;
                   letter-spacing: .5px; color: #949ba4; }}
    .meta-value {{ color: #dbdee1; font-size: 13px; }}

    /* ── Messages wrapper ── */
    .messages {{
      padding: 8px 32px 32px;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}

    /* ── Single message ── */
    .message {{
      display: flex;
      gap: 12px;
      padding: 6px 8px;
      border-radius: 4px;
      transition: background .1s;
    }}
    .message:hover {{ background: #2e3035; }}
    .bot-message {{ background: rgba(88,101,242,.06); }}
    .bot-message:hover {{ background: rgba(88,101,242,.12); }}

    .avatar-wrap {{ flex-shrink: 0; padding-top: 2px; }}
    .avatar {{
      width: 38px; height: 38px;
      border-radius: 50%;
      object-fit: cover;
      background: #36393f;
    }}

    .message-body {{ flex: 1; min-width: 0; }}

    .message-header {{
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 3px;
    }}

    .author {{ font-weight: 600; color: #fff; font-size: 14px; }}
    .timestamp {{ font-size: 11px; color: #72767d; }}

    .bot-badge {{
      background: #5865f2;
      color: #fff;
      font-size: 10px;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 3px;
      text-transform: uppercase;
      letter-spacing: .3px;
    }}

    .system-label {{
      background: #2b2d31;
      border: 1px solid #3f4147;
      color: #949ba4;
      font-size: 10px;
      padding: 1px 6px;
      border-radius: 3px;
    }}

    .message-content {{
      color: #dbdee1;
      white-space: pre-wrap;
      word-break: break-word;
    }}

    /* ── Edits ── */
    .edits {{
      margin-top: 6px;
      border-left: 3px solid #faa61a;
      padding-left: 10px;
    }}
    .edits-label {{ font-size: 11px; color: #faa61a; font-weight: 600; margin-bottom: 4px; }}
    .edit-version {{ margin-bottom: 6px; }}
    .edit-num  {{ font-size: 11px; font-weight: 700; color: #949ba4; margin-right: 6px; }}
    .edit-time {{ font-size: 11px; color: #72767d; }}
    .edit-content {{
      margin-top: 2px;
      color: #dbdee1;
      white-space: pre-wrap;
      word-break: break-word;
    }}

    /* ── Attachments ── */
    .attachments {{ margin-top: 6px; display: flex; flex-wrap: wrap; gap: 8px; }}

    .attachment {{ border-radius: 4px; overflow: hidden; }}

    .image-attachment img {{
      max-width: 520px;
      max-height: 400px;
      display: block;
      border-radius: 4px;
      border: 1px solid #3f4147;
      cursor: zoom-in;
    }}
    .gif-attachment img {{
      max-width: 520px;
      max-height: 400px;
    }}
    .attachment-name {{ font-size: 11px; color: #949ba4; margin-top: 3px; }}

    .file-attachment {{
      background: #2b2d31;
      border: 1px solid #3f4147;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 13px;
    }}
    .file-size {{ color: #72767d; font-size: 12px; }}

    /* ── Embeds ── */
    .embeds {{ margin-top: 6px; display: flex; flex-direction: column; gap: 6px; }}

    .embed {{
      background: #2b2d31;
      border-left: 4px solid #4f545c;
      border-radius: 0 4px 4px 0;
      padding: 10px 14px;
      max-width: 520px;
      position: relative;
    }}

    .embed-author {{
      display: flex; align-items: center; gap: 6px;
      font-size: 13px; font-weight: 600; margin-bottom: 6px;
    }}
    .embed-author-icon {{
      width: 20px; height: 20px; border-radius: 50%;
    }}

    .embed-title {{ font-weight: 700; font-size: 15px; color: #fff; margin-bottom: 4px; }}
    .embed-title a {{ color: #00aff4; }}

    .embed-description {{ font-size: 13px; color: #dbdee1; white-space: pre-wrap; margin-bottom: 6px; }}

    .embed-fields {{
      display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 6px;
    }}
    .embed-field {{ min-width: 100px; }}
    .embed-field.inline {{ flex: 1; }}
    .embed-field-name  {{ font-size: 12px; font-weight: 700; color: #fff; margin-bottom: 2px; }}
    .embed-field-value {{ font-size: 13px; color: #dbdee1; white-space: pre-wrap; }}

    .embed-image img {{
      max-width: 100%; border-radius: 4px; margin-top: 6px;
    }}

    .embed-thumbnail {{
      position: absolute; top: 10px; right: 10px;
      width: 64px; height: 64px;
      object-fit: cover; border-radius: 4px;
    }}

    .embed-footer {{
      display: flex; align-items: center; gap: 6px;
      font-size: 11px; color: #72767d; margin-top: 8px;
    }}
    .embed-footer-icon {{
      width: 16px; height: 16px; border-radius: 50%;
    }}

    /* ── Reactions ── */
    .reactions {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }}
    .reaction {{
      background: #2b2d31;
      border: 1px solid #3f4147;
      border-radius: 12px;
      padding: 2px 8px;
      font-size: 13px;
    }}

    /* ── Dividers ── */
    .day-divider {{
      text-align: center;
      color: #72767d;
      font-size: 12px;
      margin: 12px 0;
      position: relative;
    }}
    .day-divider::before, .day-divider::after {{
      content: '';
      position: absolute;
      top: 50%;
      width: 40%;
      height: 1px;
      background: #3f4147;
    }}
    .day-divider::before {{ left: 0; }}
    .day-divider::after  {{ right: 0; }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 20px;
      color: #72767d;
      font-size: 12px;
      border-top: 1px solid #3f4147;
      margin-top: 16px;
    }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-icon">🎫</div>
  <div class="header-info">
    <h1>Транскрипт тикета #{ticket_number}</h1>
    <p>Канал: #{_esc(channel.name)} &nbsp;·&nbsp; Сервер: {_esc(channel.guild.name)}</p>
  </div>
</div>

<div class="meta">
  <div class="meta-item">
    <span class="meta-label">Открыт</span>
    <span class="meta-value">{_fmt_time(opened_at)}</span>
  </div>
  <div class="meta-item">
    <span class="meta-label">Закрыт</span>
    <span class="meta-value">{_fmt_time(closed_at)}</span>
  </div>
  <div class="meta-item">
    <span class="meta-label">Закрыл</span>
    <span class="meta-value">{_esc(str(closer))}</span>
  </div>
  <div class="meta-item">
    <span class="meta-label">Сообщений</span>
    <span class="meta-value">{msg_count}</span>
  </div>
  <div class="meta-item">
    <span class="meta-label">Участники</span>
    <span class="meta-value">{participants_html}</span>
  </div>
</div>

<div class="messages">
{messages_html}
</div>

<div class="footer">
  Транскрипт сгенерирован {_fmt_time(closed_at)} &nbsp;·&nbsp; Discord Ticket Bot
</div>

</body>
</html>"""
