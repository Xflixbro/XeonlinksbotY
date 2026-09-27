# Upgraded by @Unrated_Coder from Telegram
import os
import asyncio
from config import *
from pyrogram import Client, filters
from pyrogram.types import Message, User, ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait, ChatAdminRequired, RPCError, UserNotParticipant
from database.database import set_approval_off, is_approval_off, get_fsub_channels
from helper_func import *

# Default settings
APPROVAL_WAIT_TIME = 90  # seconds
AUTO_APPROVE_ENABLED = True  # Toggle for enabling/disabling auto approval 


# ────────────── Helper: build a protected t.me/c/ message link ──────────────
def build_message_link(chat_id: int, message_id: int = 1) -> str:
    """
    Convert a supergroup/channel ID (-100XXXXXXXXX) into a t.me/c/ link.
    Only members of the channel can open this link.
    Non-members will see "Join the channel to view this message".
    """
    cid = str(chat_id)
    if cid.startswith("-100"):
        cid = cid[4:]
    elif cid.startswith("-"):
        cid = cid[1:]
    return f"https://t.me/c/{cid}/{message_id}"


@Client.on_chat_join_request()
async def autoapprove(client, message: ChatJoinRequest):
    global AUTO_APPROVE_ENABLED

    if not AUTO_APPROVE_ENABLED:
        return

    chat = message.chat
    user = message.from_user

    # Check if the chat is in CHAT_ID or if it is an FSub channel
    is_fsub = False
    fsub_channels = await get_fsub_channels()
    if fsub_channels:
        fsub_ids = [ch['channel_id'] for ch in fsub_channels]
        if chat.id in fsub_ids:
            is_fsub = True

    if CHAT_ID and (chat.id not in CHAT_ID) and not is_fsub:
        return

    # check if approval is off for this channel
    if await is_approval_off(chat.id):
        print(f"Auto-approval is OFF for channel {chat.id}")
        return

    print(f"{user.first_name} requested to join {chat.title}")
    
    await asyncio.sleep(APPROVAL_WAIT_TIME)

    # Check if user is already a participant before approving
    try:
        member = await client.get_chat_member(chat.id, user.id)
        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            print(f"User {user.id} is already a participant of {chat.id}, skipping approval.")
            return
    except Exception as e:
        # Catch all exceptions so missing permissions or other errors don't halt approval
        print(f"Error checking chat member status for user {user.id} in chat {chat.id}: {e}. Proceeding with approval.")

    try:
        await client.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
    except Exception as e:
        print(f"Failed to approve {user.id} in {chat.id}: {e}")
        return
    
    if APPROVED == "on":
        try:
            # ✅ Use protected t.me/c/ message link instead of invite link
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
            print(f"Failed to send welcome message to {user.id}: {e}")


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
        await message.reply_text(f"❌ Failed to set auto-approval OFF for channel <code>{channel_id}</code>.")

@Client.on_message(filters.command("approveon") & filters.private & is_owner_or_admin)
async def approve_on_command(client: Client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage: <code>/approveon {channel_id}</code>")
    channel_id = int(message.command[1])
    success = await set_approval_off(channel_id, False)
    if success:
        await message.reply_text(f"✅ Auto-approval is now <b>ON</b> for channel <code>{channel_id}</code>.")
    else:
        await message.reply_text(f"❌ Failed to set auto-approval ON for channel <code>{channel_id}</code>.")
