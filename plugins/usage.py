# Upgraded by @Unrated_Coder from Telegram
# Usage / Status command — CPU, RAM, Disk, Uptime, Ping

import time
import psutil
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from config import OWNER_ID, ADMINS
from helper_func import is_owner_or_admin, get_readable_time
from database.database import count_users


@Client.on_message(filters.command('status') & filters.private & is_owner_or_admin)
async def status_command(client: Client, message: Message):
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("• Close •", callback_data="close")]]
    )

    # ── Ping (DB round-trip time) ──
    start_time = time.time()
    total_users = await count_users()
    end_time = time.time()
    ping_time = (end_time - start_time) * 1000

    # ── CPU usage (0.5s sample) ──
    try:
        cpu_usage = psutil.cpu_percent(interval=0.5)
    except Exception:
        cpu_usage = 0.0

    # ── RAM usage ──
    try:
        ram = psutil.virtual_memory()
        ram_used = ram.used / (1024 ** 3)
        ram_total = ram.total / (1024 ** 3)
        ram_percent = ram.percent
    except Exception:
        ram_used = ram_total = ram_percent = 0

    # ── Disk usage ──
    try:
        disk = psutil.disk_usage('/')
        disk_used = disk.used / (1024 ** 3)
        disk_total = disk.total / (1024 ** 3)
        disk_free = disk.free / (1024 ** 3)
        disk_percent = disk.percent
    except Exception:
        disk_used = disk_total = disk_free = disk_percent = 0

    # ── Uptime ──
    now = datetime.now()
    delta = now - getattr(client, "uptime", now)
    bottime = get_readable_time(delta.seconds)

    text = (
        "<b>📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ</b>\n\n"
        f"<b>| ᴄᴘᴜ ᴜꜱᴀɢᴇ:</b> <code>{cpu_usage}%</code>\n"
        f"<b>| ʀᴀᴍ ᴜꜱᴀɢᴇ:</b> <code>{ram_used:.2f} GB / {ram_total:.2f} GB ({ram_percent}%)</code>\n"
        f"<b>| ᴅɪꜱᴋ ᴜꜱᴀɢᴇ:</b> <code>{disk_used:.2f} GB / {disk_total:.2f} GB ({disk_percent}%)</code>\n"
        f"<b>| ᴅɪꜱᴋ ꜰʀᴇᴇ:</b> <code>{disk_free:.2f} GB</code>\n"
        f"<b>| ᴜᴘᴛɪᴍᴇ:</b> <code>{bottime}</code>\n"
        f"<b>| ᴘɪɴɢ:</b> <code>{ping_time:.2f} ms</code>\n"
        f"<b>| ᴜꜱᴇʀꜱ:</b> <code>{total_users}</code>"
    )

    await message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
