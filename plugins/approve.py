# Upgraded by @Unrated_Coder from Telegram — with Supreme BAM Request Mode
import os
import asyncio
from datetime import datetime

from config import *
from pyrogram import Client, filters
from pyrogram.types import (
    Message, User, ChatJoinRequest,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait, ChatAdminRequired, RPCError, UserNotParticipant
from database.database import (
    set_approval_off, is_approval_off, get_fsub_channels,
    lookup_invite_link, is_admin
)
from helper_func import *

# ────────────── Default settings ──────────────
APPROVAL_WAIT_TIME = 90
AUTO_APPROVE_ENABLED = True


def build_message_link(chat_id: int, message_id: int = 1) -> str:
    cid = str(chat_id)
    if cid.startswith("-100"):
        cid = cid[4:]
    elif cid.startswith("-"):
        cid = cid[1:]
    return f"https://t.me/c/{cid}/{message_id}"


# ────────────── Normal auto-approval welcome ──────────────
async def send_welcome_message(client, user, chat):
    if APPROVED != "on":
        return
    try:
        message_link = build_message_link(chat.id, message_id=1)
        buttons = [
            [InlineKeyboardButton('• ᴊᴏɪɴ ᴍʏ ᴜᴘᴅᴀᴛᴇs •', url='https://t.me/Unroder')],
            [InlineKeyboardButton(f'• ᴊᴏɪɴ {chat.title} •', url=message_link)]
        ]
        markup = InlineKeyboardMarkup(buttons)
        caption = TEXT.format(mention=user.mention, title=chat.title)
        await client.send_photo(
            chat_id=user.id,
            photo=START_PIC,
            caption=caption,
            reply_markup=markup
        )
    except Exception as e:
        print(f"[welcome] Failed to send to {user.id}: {e}")


# ══════════════════════════════════════════════════════════════
# ★★★ ADDED: DEDICATED BAM APPROVAL NOTIFICATION ★★★
# This is sent ONLY when an admin manually approves a BAM
# join-request via the APPROVE button. It is completely separate
# from the normal auto-approval welcome message above, so the
# existing auto-approval flow is not affected in any way.
# ══════════════════════════════════════════════════════════════
async def send_bam_approval_message(client, user, chat):
    """BAM-only approval notification — sent after admin approves."""
    try:
        message_link = build_message_link(chat.id, message_id=1)

        buttons = [
            [InlineKeyboardButton(
                '• ᴊᴏɪɴ ᴍʏ ᴜᴘᴅᴀᴛᴇs •',
                url='https://t.me/Unroder'
            )],
            [InlineKeyboardButton(
                f'• ᴊᴏɪɴ {chat.title} •',
                url=message_link
            )]
        ]
        markup = InlineKeyboardMarkup(buttons)

        caption = (
            f"ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ᴛᴏ ᴊᴏɪɴ "
            f"<b>{chat.title}</b> ɪs ᴀᴘᴘʀᴏᴠᴇᴅ.\n"
            f"‣ ᴘᴏᴡᴇʀᴇᴅ ʙʏ @Unrated_Coder"
        )

        await client.send_photo(
            chat_id=user.id,
            photo=START_PIC,
            caption=caption,
            reply_markup=markup
        )
    except Exception as e:
        print(f"[BAM approval] Failed to send approval notice to {user.id}: {e}")
# ══════════════════════════════════════════════════════════════


def _bam_targets():
    targets = []
    if OWNER_ID:
        targets.append(OWNER_ID)
    for a in ADMINS:
        if a not in targets:
            targets.append(a)
    return targets


@Client.on_chat_join_request()
async def on_chat_join_request(client: Client, request: ChatJoinRequest):
    global AUTO_APPROVE_ENABLED

    chat = request.chat
    user = request.from_user

    invite_link_str = None
    try:
        if request.invite_link:
            invite_link_str = getattr(request.invite_link, "invite_link", None) \
                              or str(request.invite_link)
    except Exception:
        invite_link_str = None

    is_bam = False
    if invite_link_str:
        info = await lookup_invite_link(invite_link_str)
        if info and info.get("is_bam"):
            is_bam = True

    # ★ BAM flow — DO NOT auto-approve. Notify admins instead.
    if is_bam:
        await _notify_admins_bam(client, chat, user, request)
        return

    # ── Normal auto-approval flow (unchanged) ──
    if not AUTO_APPROVE_ENABLED:
        return

    is_fsub = False
    fsub_channels = await get_fsub_channels()
    if fsub_channels:
        fsub_ids = [ch['channel_id'] for ch in fsub_channels]
        if chat.id in fsub_ids:
            is_fsub = True

    if CHAT_ID and (chat.id not in CHAT_ID) and not is_fsub:
        return

    if await is_approval_off(chat.id):
        print(f"Auto-approval is OFF for channel {chat.id}")
        return

    print(f"{user.first_name} requested to join {chat.title}")
    await asyncio.sleep(APPROVAL_WAIT_TIME)

    try:
        member = await client.get_chat_member(chat.id, user.id)
        if member.status in [ChatMemberStatus.MEMBER,
                             ChatMemberStatus.ADMINISTRATOR,
                             ChatMemberStatus.OWNER]:
            print(f"User {user.id} already in {chat.id}, skipping.")
            return
    except Exception as e:
        print(f"Member check failed for {user.id} in {chat.id}: {e}")

    try:
        await client.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
    except Exception as e:
        print(f"Failed to approve {user.id} in {chat.id}: {e}")
        return

    await send_welcome_message(client, user, chat)


async def _notify_admins_bam(client: Client, chat, user, request: ChatJoinRequest):
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    username = f"@{user.username}" if user.username else "N/A"

    try:
        requested_time = request.date.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        requested_time = datetime.utcnow().strftime("%d %b %Y, %I:%M %p")

    text = (
        "🔔 <b>NEW JOIN REQUEST</b>\n\n"
        f"👤 <b>User:</b> {name} ({username})\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"📅 <b>Requested:</b> {requested_time}\n"
        f"📢 <b>Channel:</b> {chat.title}\n"
        f"🆔 <b>Channel ID:</b> <code>{chat.id}</code>\n\n"
        "<b>Action Required:</b>\n"
        "<i>Approve or decline this join request.</i>"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ᴀᴘᴘʀᴏᴠᴇ", callback_data=f"bam_ap_{chat.id}_{user.id}"),
            InlineKeyboardButton("❌ ᴅᴇᴄʟɪɴᴇ", callback_data=f"bam_dc_{chat.id}_{user.id}")
        ]
    ])

    for admin_id in _bam_targets():
        try:
            await client.send_message(admin_id, text, reply_markup=buttons)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.send_message(admin_id, text, reply_markup=buttons)
            except Exception:
                pass
        except Exception as e:
            print(f"[BAM] Failed to notify admin {admin_id}: {e}")


@Client.on_callback_query(filters.regex(r"^bam_(ap|dc)_(-?\d+)_(-?\d+)$"))
async def bam_callback(client: Client, query: CallbackQuery):
    # ── Authorization: only owner / listed admins / DB admins ──
    uid = query.from_user.id
    authorized = (uid == OWNER_ID) or (uid in ADMINS) or (await is_admin(uid))
    if not authorized:
        return await query.answer("❌ Admins only!", show_alert=True)

    parts = query.data.split("_")
    action   = parts[1]
    chat_id  = int(parts[2])
    user_id  = int(parts[3])

    try:
        chat = await client.get_chat(chat_id)
    except Exception:
        chat = None

    if action == "ap":
        try:
            # 1) Actually approve the Telegram join request
            await client.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
        except Exception as e:
            # Approval failed → DO NOT send approval notice
            return await query.answer(f"❌ Approval failed: {e}", show_alert=True)

        # 2) Fetch the approved user object (needed for the notification)
        target_user = None
        try:
            member = await client.get_chat_member(chat_id, user_id)
            target_user = member.user
        except Exception:
            target_user = None

        # ★★★ ADDED: send DEDICATED BAM approval notification ★★★
        # (only reached if approve_chat_join_request() succeeded above)
        if target_user and chat:
            await send_bam_approval_message(client, target_user, chat)

        # 3) Update admin's request message → remove buttons, mark approved
        try:
            base_text = query.message.text.html if query.message.text else ""
            new_text = (
                base_text
                + f"\n\n✅ <b>APPROVED</b> by <a href='tg://user?id={uid}'>admin</a>"
            )
            await query.message.edit_text(new_text, reply_markup=None)
        except Exception as e:
            print(f"[BAM] Failed to update admin message: {e}")

        return await query.answer("✅ Approved!", show_alert=False)

    else:
        # ── Decline branch ──
        try:
            await client.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
            base_text = query.message.text.html if query.message.text else ""
            new_text = (
                base_text
                + f"\n\n❌ <b>DECLINED</b> by <a href='tg://user?id={uid}'>admin</a>"
            )
            await query.message.edit_text(new_text, reply_markup=None)
            await query.answer("❌ Declined.", show_alert=False)
        except Exception as e:
            await query.answer(f"❌ Failed: {e}", show_alert=True)


@Client.on_message(filters.command("reqtime") & filters.private & is_owner_or_admin)
async def set_reqtime(client: Client, message: Message):
    global APPROVAL_WAIT_TIME
    if len(message.command) != 2 or not message.command[1].isdigit():
        return await message.reply_text("Usage: <code>/reqtime {seconds}</code>")
    APPROVAL_WAIT_TIME = int(message.command[1])
    await message.reply_text(f"✅ Request approval time set to <b>{APPROVAL_WAIT_TIME}</b> seconds.")


@Client.on_message(filters.command("reqmode") & filters.private & is_owner_or_admin)
async def toggle_reqmode(client: Client, message: Message):
    global AUTO_APPROVE_ENABLED
    if len(message.command) != 2 or message.command[1].lower() not in ["on", "off"]:
        return await message.reply_text("Usage: <code>/reqmode on</code> or <code>/reqmode off</code>")
    mode = message.command[1].lower()
    AUTO_APPROVE_ENABLED = (mode == "on")
    status = "enabled ✅" if AUTO_APPROVE_ENABLED else "disabled ❌"
    await message.reply_text(f"Auto-approval has been {status}.")


@Client.on_message(filters.command("approveoff") & filters.private & is_owner_or_admin)
async def approve_off_command(client: Client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage: <code>/approveoff {channel_id}</code>")
    channel_id = int(message.command[1])
    success = await set_approval_off(channel_id, True)
    if success:
        await message.reply_text(f"✅ Auto-approval is now <b>OFF</b> for channel <code>{channel_id}</code>.")
    else:
        await message.reply_text(f"❌ Failed for channel <code>{channel_id}</code>.")


@Client.on_message(filters.command("approveon") & filters.private & is_owner_or_admin)
async def approve_on_command(client: Client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage: <code>/approveon {channel_id}</code>")
    channel_id = int(message.command[1])
    success = await set_approval_off(channel_id, False)
    if success:
        await message.reply_text(f"✅ Auto-approval is now <b>ON</b> for channel <code>{channel_id}</code>.")
    else:
        await message.reply_text(f"❌ Failed for channel <code>{channel_id}</code>.")
