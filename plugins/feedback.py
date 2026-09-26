# ──────────────────────────────────────────────────────────────
# Feedback / Live Support System (Livegram-style)
# Users message the bot → admins see it → admins reply back
# + AUTO-DELETE admin replies after a configurable timer
# + RESTRICTED content (anti-forward / anti-save)
# ──────────────────────────────────────────────────────────────

import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from config import OWNER_ID, ADMINS, LOGGER
from database.database import database, is_admin, add_user

# ───────────── Collections ─────────────
feedback_map = database['feedback_map']
feedback_settings = database['feedback_settings']


# ══════════════════ SETTINGS HELPERS ══════════════════
async def get_feedback_admin() -> int:
    doc = await feedback_settings.find_one({'_id': 'config'})
    if doc and doc.get('admin_chat_id'):
        return doc['admin_chat_id']
    return OWNER_ID


async def set_feedback_admin(chat_id: int):
    await feedback_settings.update_one(
        {'_id': 'config'},
        {'$set': {'admin_chat_id': chat_id, 'updated_at': datetime.utcnow()}},
        upsert=True
    )


async def is_feedback_enabled() -> bool:
    doc = await feedback_settings.find_one({'_id': 'config'})
    if doc:
        return doc.get('enabled', True)
    return True


async def set_feedback_enabled(enabled: bool):
    await feedback_settings.update_one(
        {'_id': 'config'},
        {'$set': {'enabled': enabled, 'updated_at': datetime.utcnow()}},
        upsert=True
    )


# ══════════════════ AUTO-DELETE TIMER ══════════════════
async def get_auto_delete_timer() -> int:
    """Return auto-delete seconds. 0 = disabled."""
    doc = await feedback_settings.find_one({'_id': 'config'})
    if doc:
        return int(doc.get('auto_delete_seconds', 0))
    return 0


async def set_auto_delete_timer(seconds: int):
    await feedback_settings.update_one(
        {'_id': 'config'},
        {'$set': {'auto_delete_seconds': int(seconds), 'updated_at': datetime.utcnow()}},
        upsert=True
    )


# ══════════════════ RESTRICT MESSAGE ══════════════════
async def is_restrict_enabled() -> bool:
    """Return True if content protection is enabled."""
    doc = await feedback_settings.find_one({'_id': 'config'})
    if doc:
        return bool(doc.get('restrict_content', False))
    return False


async def set_restrict_enabled(enabled: bool):
    await feedback_settings.update_one(
        {'_id': 'config'},
        {'$set': {'restrict_content': bool(enabled), 'updated_at': datetime.utcnow()}},
        upsert=True
    )


# ══════════════════ AUTO-DELETE HELPER ══════════════════
async def auto_delete_message(client: Client, chat_id: int, message_id: int, delay: int):
    """Wait `delay` seconds then delete the message."""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        LOGGER(__name__).info(f"[AutoDelete] Deleted msg {message_id} in chat {chat_id}")
    except Exception as e:
        LOGGER(__name__).warning(f"[AutoDelete] Failed: {e}")


# ══════════════════ MAPPING HELPERS ══════════════════
async def save_map(admin_msg_id: int, admin_chat_id: int, user_id: int):
    await feedback_map.update_one(
        {'admin_msg_id': admin_msg_id, 'admin_chat_id': admin_chat_id},
        {'$set': {
            'admin_msg_id': admin_msg_id,
            'admin_chat_id': admin_chat_id,
            'user_id': user_id,
            'created_at': datetime.utcnow()
        }},
        upsert=True
    )


async def get_user_from_reply(admin_msg_id: int, admin_chat_id: int):
    doc = await feedback_map.find_one({
        'admin_msg_id': admin_msg_id,
        'admin_chat_id': admin_chat_id
    })
    return doc['user_id'] if doc else None


# ══════════════════ USER  →  ADMIN ══════════════════
@Client.on_message(filters.private & filters.incoming & ~filters.service, group=-3)
async def user_to_admin(client: Client, message: Message):
    user = message.from_user
    if not user:
        return

    if message.text and message.text.startswith('/'):
        return

    if user.id == OWNER_ID or user.id in ADMINS or await is_admin(user.id):
        return

    if not await is_feedback_enabled():
        return

    try:
        await add_user(user.id)
    except Exception:
        pass

    admin_chat = await get_feedback_admin()

    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    username = f"@{user.username}" if user.username else "N/A"
    dc = user.dc_id if user.dc_id else "N/A"

    header = (
        "<b>📩 ɴᴇᴡ ᴍᴇꜱꜱᴀɢᴇ ꜰʀᴏᴍ ᴜꜱᴇʀ</b>\n\n"
        f"<b>👤 ɴᴀᴍᴇ:</b> {name}\n"
        f"<b>🆔 ᴜꜱᴇʀ ɪᴅ:</b> <code>{user.id}</code>\n"
        f"<b>🔗 ᴜꜱᴇʀɴᴀᴍᴇ:</b> {username}\n"
        f"<b>🌎 ᴅᴄ:</b> {dc}\n\n"
        "<i>↩️ Reply to the message below to respond.</i>"
    )

    try:
        await client.send_message(admin_chat, header)
        forwarded = await message.forward(admin_chat)
        await save_map(forwarded.id, admin_chat, user.id)

        # ── No confirmation reply sent to the user (silent delivery) ──

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        LOGGER(__name__).error(f"[Feedback] Forward failed: {e}")


# ══════════════════ ADMIN  →  USER ══════════════════
@Client.on_message(
    (filters.private | filters.group) & filters.incoming & filters.reply & ~filters.service,
    group=-2
)
async def admin_to_user(client: Client, message: Message):
    user = message.from_user
    if not user:
        return

    is_auth = user.id == OWNER_ID or user.id in ADMINS or await is_admin(user.id)
    if not is_auth:
        return

    reply_to = message.reply_to_message
    if not reply_to:
        return

    target_user_id = await get_user_from_reply(reply_to.id, message.chat.id)
    if not target_user_id:
        return

    auto_delete_secs = await get_auto_delete_timer()
    restrict = await is_restrict_enabled()

    try:
        try:
            if restrict:
                sent_to_user = await message.copy(
                    target_user_id,
                    protect_content=True
                )
            else:
                sent_to_user = await message.copy(target_user_id)
        except TypeError:
            sent_to_user = await message.copy(target_user_id)

        if auto_delete_secs > 0:
            asyncio.create_task(
                auto_delete_message(client, target_user_id, sent_to_user.id, auto_delete_secs)
            )

        parts = [f"<b>✅ Reply delivered to user <code>{target_user_id}</code></b>"]
        if restrict:
            parts.append("<b>🔒 Content:</b> <code>PROTECTED</code>")
        else:
            parts.append("<b>🔓 Content:</b> <code>Normal</code>")
        if auto_delete_secs > 0:
            parts.append(f"<b>🗑️ Auto-delete in:</b> <code>{auto_delete_secs}s</code>")

        confirm_msg = await message.reply_text("\n".join(parts), quote=True)

        asyncio.create_task(
            auto_delete_message(client, message.chat.id, confirm_msg.id, 8)
        )

    except UserIsBlocked:
        await message.reply_text("<b>❌ User has blocked the bot.</b>")
    except InputUserDeactivated:
        await message.reply_text("<b>❌ User account is deactivated.</b>")
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply_text("<b>⚠️ Flood wait, try again.</b>")
    except Exception as e:
        LOGGER(__name__).error(f"[Feedback] Reply delivery failed: {e}")
        await message.reply_text(f"<b>❌ Failed to deliver: {e}</b>")


# ══════════════════ MANAGEMENT COMMAND ══════════════════
@Client.on_message(filters.command('feedback') & filters.private & ~filters.service)
async def feedback_cmd(client: Client, message: Message):
    user = message.from_user
    if not user:
        return

    is_auth = user.id == OWNER_ID or user.id in ADMINS or await is_admin(user.id)
    if not is_auth:
        return await message.reply_text("<b>❌ You are not authorized to use this command.</b>")

    args = message.command[1:]
    enabled = await is_feedback_enabled()
    admin_chat = await get_feedback_admin()

    if not args:
        status = "✅ ᴏɴ" if enabled else "❌ ᴏꜰꜰ"
        return await message.reply_text(
            f"<b>📢 ꜰᴇᴇᴅʙᴀᴄᴋ ꜱʏꜱᴛᴇᴍ</b>\n\n"
            f"<b>ꜱᴛᴀᴛᴜꜱ:</b> {status}\n"
            f"<b>ᴀᴅᴍɪɴ ᴄʜᴀᴛ:</b> <code>{admin_chat}</code>\n\n"
            f"<b>ᴜꜱᴀɢᴇ:</b>\n"
            f"• <code>/feedback on</code> — Enable\n"
            f"• <code>/feedback off</code> — Disable\n"
            f"• <code>/feedback set &lt;chat_id&gt;</code> — Set destination chat\n"
            f"• <code>/feedback status</code> — Show current status"
        )

    cmd = args[0].lower()

    if cmd == 'on':
        await set_feedback_enabled(True)
        await message.reply_text("<b>✅ Feedback system enabled.</b>")

    elif cmd == 'off':
        await set_feedback_enabled(False)
        await message.reply_text("<b>❌ Feedback system disabled.</b>")

    elif cmd == 'set':
        if len(args) < 2:
            return await message.reply_text("<b>Usage:</b> <code>/feedback set &lt;chat_id&gt;</code>")
        try:
            cid = int(args[1])
            await set_feedback_admin(cid)
            await message.reply_text(f"<b>✅ Admin chat set to <code>{cid}</code></b>")
        except ValueError:
            await message.reply_text("<b>❌ Invalid chat ID.</b>")

    elif cmd == 'status':
        status = "✅ ᴏɴ" if enabled else "❌ ᴏꜰꜰ"
        await message.reply_text(
            f"<b>ꜱᴛᴀᴛᴜꜱ:</b> {status}\n"
            f"<b>ᴀᴅᴍɪɴ ᴄʜᴀᴛ:</b> <code>{admin_chat}</code>"
        )
    else:
        await message.reply_text("<b>❓ Unknown option. Use /feedback for help.</b>")


# ══════════════════ AUTO-DELETE COMMAND ══════════════════
@Client.on_message(filters.command('livegram_autodelete') & filters.private & ~filters.service)
async def livegram_autodelete_cmd(client: Client, message: Message):
    user = message.from_user
    if not user:
        return

    is_auth = user.id == OWNER_ID or user.id in ADMINS or await is_admin(user.id)
    if not is_auth:
        return await message.reply_text("<b>❌ You are not authorized to use this command.</b>")

    args = message.command[1:]
    current = await get_auto_delete_timer()

    if not args:
        if current > 0:
            status = f"<code>{current}</code> seconds"
        else:
            status = "❌ ᴅɪꜱᴀʙʟᴇᴅ"
        return await message.reply_text(
            f"<b>🗑️ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ꜱʏꜱᴛᴇᴍ</b>\n\n"
            f"<b>ᴄᴜʀʀᴇɴᴛ:</b> {status}\n\n"
            f"<b>ᴜꜱᴀɢᴇ:</b>\n"
            f"• <code>/livegram_autodelete &lt;seconds&gt;</code> — Set timer\n"
            f"• <code>/livegram_autodelete off</code> — Disable auto-delete\n"
            f"• <code>/livegram_autodelete</code> — Show current status\n\n"
            f"<i>💡 When enabled, admin replies sent to users\nwill auto-delete after the set time.</i>"
        )

    cmd = args[0].lower()

    if cmd in ['off', 'disable', '0']:
        await set_auto_delete_timer(0)
        return await message.reply_text("<b>✅ Auto-delete DISABLED.</b>")

    try:
        secs = int(cmd)
        if secs < 5:
            return await message.reply_text("<b>❌ Minimum timer is 5 seconds.</b>")
        if secs > 86400:
            return await message.reply_text("<b>❌ Maximum timer is 86400 seconds (24 hours).</b>")

        await set_auto_delete_timer(secs)
        await message.reply_text(
            f"<b>✅ Auto-delete timer set to <code>{secs}</code> seconds.</b>\n\n"
            f"<i>Admin replies will now auto-delete after {secs}s.</i>"
        )
    except ValueError:
        await message.reply_text("<b>❌ Invalid input. Use a number or 'off'.</b>")


# ══════════════════ RESTRICT MESSAGE COMMAND ══════════════════
@Client.on_message(filters.command('livegram_rstrmsg') & filters.private & ~filters.service)
async def livegram_rstrmsg_cmd(client: Client, message: Message):
    user = message.from_user
    if not user:
        return

    is_auth = user.id == OWNER_ID or user.id in ADMINS or await is_admin(user.id)
    if not is_auth:
        return await message.reply_text("<b>❌ You are not authorized to use this command.</b>")

    args = message.command[1:]
    current = await is_restrict_enabled()

    if not args:
        status = "🔒 ᴏɴ (ᴘʀᴏᴛᴇᴄᴛᴇᴅ)" if current else "🔓 ᴏꜰꜰ (ɴᴏʀᴍᴀʟ)"
        return await message.reply_text(
            f"<b>🔒 ʀᴇꜱᴛʀɪᴄᴛᴇᴅ ᴍᴇꜱꜱᴀɢᴇ ꜱʏꜱᴛᴇᴍ</b>\n\n"
            f"<b>ᴄᴜʀʀᴇɴᴛ:</b> {status}\n\n"
            f"<b>ᴜꜱᴀɢᴇ:</b>\n"
            f"• <code>/livegram_rstrmsg on</code> — Enable (users can't forward/save)\n"
            f"• <code>/livegram_rstrmsg off</code> — Disable (normal)\n"
            f"• <code>/livegram_rstrmsg</code> — Show current status\n\n"
            f"<i>💡 When enabled, messages you send to users\nwill be protected from forwarding & saving.</i>"
        )

    cmd = args[0].lower()

    if cmd in ['on', 'enable', 'true', '1']:
        await set_restrict_enabled(True)
        return await message.reply_text(
            "<b>🔒 Restricted message mode ENABLED.</b>\n\n"
            "<i>Users will NOT be able to forward, save, or copy\n"
            "the messages you send to them.</i>"
        )

    elif cmd in ['off', 'disable', 'false', '0']:
        await set_restrict_enabled(False)
        return await message.reply_text(
            "<b>🔓 Restricted message mode DISABLED.</b>\n\n"
            "<i>Users can forward & save messages normally.</i>"
        )

    else:
        return await message.reply_text(
            "<b>❌ Invalid option.</b>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/livegram_rstrmsg on</code>\n"
            "• <code>/livegram_rstrmsg off</code>"
        )
