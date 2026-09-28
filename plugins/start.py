# Bluuuuuuuuuuhh....❤️ Visit our Channel ~ t.me/Unrated_Coder
import asyncio
import base64
import time
from asyncio import Lock
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatMemberStatus, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram.errors import FloodWait, UserNotParticipant, UserIsBlocked, InputUserDeactivated, MessageNotModified
from pyrogram.errors import InviteHashExpired, RPCError
import os
from asyncio import sleep
import random

from datetime import datetime, timedelta
from config import *
from database.database import *
import database.database as db
from plugins.newpost import revoke_invite_after_5_minutes
from helper_func import *

channel_locks = defaultdict(asyncio.Lock)
user_banned_until = {}

cancel_lock = asyncio.Lock()
is_canceled = False


@Client.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id in user_banned_until:
        if datetime.now() < user_banned_until[user_id]:
            return await message.reply_text(
                "<b><blockquote expandable>You are temporarily banned from using commands due to spamming. Try again later.</b>",
                parse_mode=ParseMode.HTML
            )

    await add_user(user_id)

    # Check FSub requirements
    fsub_data = await get_fsub_channels()
    if fsub_data:
        must_join = []

        async def check_fsub(ch):
            channel_id = ch['channel_id']
            mode = ch.get('mode', 'normal')
            try:
                member = await client.get_chat_member(channel_id, user_id)
                if mode == "request" and member.status == ChatMemberStatus.BANNED:
                    return ch
            except UserNotParticipant:
                return ch
            except Exception as e:
                print(f"FSub Check Error for {channel_id}: {e}")
            return None

        results = await asyncio.gather(*[check_fsub(ch) for ch in fsub_data])
        must_join = [res for res in results if res is not None]

        if must_join:
            buttons = []
            for ch in must_join:
                try:
                    fsub_id = ch['channel_id']
                    mode = ch.get('mode', 'normal')
                    chat = await client.get_chat(fsub_id)

                    if mode == "request":
                        try:
                            link = (await client.create_chat_invite_link(fsub_id, creates_join_request=True)).invite_link
                        except Exception as e:
                            print(f"Failed to create join request link for {fsub_id}: {e}")
                            link = chat.invite_link or (await client.export_chat_invite_link(fsub_id))
                    else:
                        link = chat.invite_link or (await client.export_chat_invite_link(fsub_id))

                    buttons.append([InlineKeyboardButton(f"Join {chat.title}", url=link)])
                except Exception as e:
                    print(f"FSub Button Error: {e}")

            if buttons:
                me = client.me or (await client.get_me())
                start_param = message.command[1] if len(message.command) > 1 else ''
                buttons.append([InlineKeyboardButton("🔄 Check Again", url=f"https://t.me/{me.username}?start={start_param}")])
                return await message.reply_text(
                    "<b>👋 Welcome!\n\nTo use this bot, you must join our channels first. Click the buttons below to join, then click 'Check Again'.</b>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]

            # ── Detect link type ─────────────────────────────
            is_bam = False
            is_request = False
            if base64_string.startswith("bamreq_"):
                is_bam = True
                is_request = True
                base64_string = base64_string[7:]
            elif base64_string.startswith("req_"):
                is_request = True
                base64_string = base64_string[4:]

            if is_request:
                channel_id = await get_channel_by_encoded_link2(base64_string)
            else:
                channel_id = await get_channel_by_encoded_link(base64_string)

            if not channel_id:
                return await message.reply_text(
                    "<b><blockquote expandable>Invalid or expired invite link.</b>",
                    parse_mode=ParseMode.HTML
                )

            # genlink-style original link redirect
            from database.database import get_original_link
            original_link = await get_original_link(channel_id)
            if original_link:
                button = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("• Proceed to Link •", url=original_link)]]
                )
                return await message.reply_text(
                    "<b><blockquote expandable>Your link is ready! Click below to continue.</b>",
                    reply_markup=button,
                    parse_mode=ParseMode.HTML
                )

            # ★ FIX: Always create a FRESH invite link per user.
            # No sharing/reuse → each user's revoke task only kills their own link.
            async with channel_locks[channel_id]:
                # Use UTC to stay consistent with DB timestamps
                current_time = datetime.utcnow()

                # Best-effort revoke of previously stored link (its own revoke task may also fire later — harmless)
                try:
                    old_link_info = await get_current_invite_link(channel_id)
                    if old_link_info and old_link_info.get("invite_link"):
                        try:
                            await client.revoke_chat_invite_link(
                                channel_id, old_link_info["invite_link"]
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

                invite = await client.create_chat_invite_link(
                    chat_id=channel_id,
                    expire_date=current_time + timedelta(minutes=10),
                    creates_join_request=is_request
                )
                invite_link = invite.invite_link
                await save_invite_link(channel_id, invite_link, is_request, is_bam)
                await register_invite_link(invite_link, channel_id, is_request, is_bam)

            if is_bam:
                button_text = "• 📩 Send Join Request •"
            elif is_request:
                button_text = "• Join Request •"
            else:
                button_text = "• Join Channel •"

            button = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=invite_link)]])
            await message.reply_text(
                "<b><blockquote expandable>Your link is ready! Click below to continue.</b>",
                reply_markup=button,
                parse_mode=ParseMode.HTML
            )

            note_msg = await message.reply_text(
                "<u><b>Note: If the link is expired, please click the post link again to get a new one.</b></u>",
                parse_mode=ParseMode.HTML
            )
            asyncio.create_task(delete_after_delay(note_msg, 300))

            # ★ 5-minute revoke task KEPT — but now safe because
            # each user has their OWN unique invite link.
            asyncio.create_task(
                revoke_invite_after_5_minutes(client, channel_id, invite_link, is_request)
            )

        except Exception as e:
            await message.reply_text(
                "<b><blockquote expandable>Invalid or expired invite link.</b>",
                parse_mode=ParseMode.HTML
            )
            print(f"Decoding error: {e}")
    else:
        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• About", callback_data="about"),
                 InlineKeyboardButton("Channels •", callback_data="channels")],
                [InlineKeyboardButton("• Join Updates •", url="https://t.me/Unrer")]
            ]
        )

        try:
            await message.reply_photo(
                photo=START_PIC,
                caption=START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Error sending start picture: {e}")
            await message.reply_text(
                START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )


async def check_subscription_status(client: Client, user_id: int, fsub_channels: list):
    must_join = []
    for ch in fsub_channels:
        channel_id = ch['channel_id']
        mode = ch.get('mode', 'normal')
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if mode == "request" and member.status == ChatMemberStatus.BANNED:
                must_join.append(ch)
        except UserNotParticipant:
            must_join.append(ch)
        except Exception as e:
            print(f"FSub Check Error for {channel_id}: {e}")

    if not must_join:
        return True, "", None

    buttons = []
    for ch in must_join:
        try:
            fsub_id = ch['channel_id']
            mode = ch.get('mode', 'normal')
            chat = await client.get_chat(fsub_id)
            if mode == "request":
                try:
                    link = (await client.create_chat_invite_link(fsub_id, creates_join_request=True)).invite_link
                except Exception as e:
                    print(f"Failed to create join request link for {fsub_id}: {e}")
                    link = chat.invite_link or (await client.export_chat_invite_link(fsub_id))
            else:
                link = chat.invite_link or (await client.export_chat_invite_link(fsub_id))
            buttons.append([InlineKeyboardButton(f"Join {chat.title}", url=link)])
        except Exception as e:
            print(f"FSub Button Error: {e}")

    buttons.append([InlineKeyboardButton("🔄 Check Again", callback_data="check_sub")])

    markup = InlineKeyboardMarkup(buttons)
    message_text = "<b>👋 Welcome!\n\nTo use this bot, you must join our channels first. Click the buttons below to join, then click 'Check Again'.</b>"
    return False, message_text, markup


@Client.on_callback_query(filters.regex("close"))
async def close_callback(client: Client, callback_query):
    await callback_query.answer()
    await callback_query.message.delete()


@Client.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    fsub_channels = await get_fsub_channels()

    if not fsub_channels:
        await callback_query.message.edit_text(
            "<b>No FSub channels configured!</b>",
            parse_mode=ParseMode.HTML
        )
        return

    is_subscribed, subscription_message, subscription_buttons = await check_subscription_status(client, user_id, fsub_channels)
    if is_subscribed:
        await callback_query.message.edit_text(
            "<b>You are subscribed to all required channels! Use /start to proceed.</b>",
            parse_mode=ParseMode.HTML
        )
    else:
        await callback_query.message.edit_text(
            subscription_message,
            reply_markup=subscription_buttons,
            parse_mode=ParseMode.HTML
        )


WAIT_MSG = "<b>Processing...</b>"

REPLY_ERROR = """Use this as a reply to a user message in the bot's PM, not in the channel."""


@Client.on_message(filters.command('cancel') & filters.private & is_owner_or_admin)
async def cancel_broadcast(client: Client, message: Message):
    global is_canceled
    async with cancel_lock:
        is_canceled = True


@Client.on_message(filters.private & filters.command('broadcast') & is_owner_or_admin)
async def broadcast(client: Client, message: Message):
    global is_canceled
    args = message.text.split()[1:]

    if not message.reply_to_message:
        msg = await message.reply(
            "Reply to a message to broadcast.\n\nUsage examples:\n"
            "`/broadcast normal`\n"
            "`/broadcast pin`\n"
            "`/broadcast delete 30`\n"
            "`/broadcast pin delete 30`\n"
            "`/broadcast silent`\n"
        )
        await asyncio.sleep(8)
        return await msg.delete()

    do_pin = False
    do_delete = False
    duration = 0
    silent = False
    mode_text = []

    i = 0
    while i < len(args):
        arg = args[i].lower()
        if arg == "pin":
            do_pin = True
            mode_text.append("PIN")
        elif arg == "delete":
            do_delete = True
            try:
                duration = int(args[i + 1])
                i += 1
            except (IndexError, ValueError):
                return await message.reply("<b>Provide valid duration for delete mode.</b>\nUsage: `/broadcast delete 30`")
            mode_text.append(f"DELETE({duration}s)")
        elif arg == "silent":
            silent = True
            mode_text.append("SILENT")
        else:
            mode_text.append(arg.upper())
        i += 1

    if not mode_text:
        mode_text.append("NORMAL")

    async with cancel_lock:
        is_canceled = False

    from database.database import user_data
    total = await count_users()
    broadcast_msg = message.reply_to_message
    successful = blocked = deleted = unsuccessful = 0

    pls_wait = await message.reply(f"<i>Broadcasting in <b>{' + '.join(mode_text)}</b> mode...</i>")

    bar_length = 20
    progress_bar = ''
    last_update_percentage = 0
    update_interval = 0.05

    i = 0
    async for user in user_data.find():
        i += 1
        chat_id = user['_id']
        async with cancel_lock:
            if is_canceled:
                await pls_wait.edit(f"❌ BROADCAST ({' + '.join(mode_text)}) CANCELED ❌")
                return

        try:
            sent_msg = await broadcast_msg.copy(chat_id, disable_notification=silent)

            if do_pin:
                await client.pin_chat_message(chat_id, sent_msg.id, both_sides=True)
            if do_delete:
                asyncio.create_task(auto_delete(sent_msg, duration))

            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                sent_msg = await broadcast_msg.copy(chat_id, disable_notification=silent)
                if do_pin:
                    await client.pin_chat_message(chat_id, sent_msg.id, both_sides=True)
                if do_delete:
                    asyncio.create_task(auto_delete(sent_msg, duration))
                successful += 1
            except:
                unsuccessful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except:
            unsuccessful += 1
            await del_user(chat_id)

        percent_complete = i / total
        if percent_complete - last_update_percentage >= update_interval or last_update_percentage == 0:
            num_blocks = int(percent_complete * bar_length)
            progress_bar = "█" * num_blocks + "░" * (bar_length - num_blocks)
            status_update = f"""<b>❖ BROADCAST ({' + '.join(mode_text)}) IN PROGRESS...

<blockquote>⏳:</b> [{progress_bar}] <code>{percent_complete:.0%}</code></blockquote>

<b>❖ Total Users: <code>{total}</code>
❖ Successful: <code>{successful}</code>
❖ Blocked: <code>{blocked}</code>
❖ Deleted: <code>{deleted}</code>
❖ Unsuccessful: <code>{unsuccessful}</code></b>

<i>➢ To stop broadcasting click: <b>/cancel</b></i>"""
            await pls_wait.edit(status_update)
            last_update_percentage = percent_complete

    final_status = f"""<b>❖ BROADCAST ({' + '.join(mode_text)}) COMPLETED ✅

<blockquote>Done:</b> [{progress_bar}] {percent_complete:.0%}</blockquote>

<b>❖ Total Users: <code>{total}</code>
❖ Successful: <code>{successful}</code>
❖ Blocked: <code>{blocked}</code>
❖ Deleted: <code>{deleted}</code>
❖ Unsuccessful: <code>{unsuccessful}</code></b>"""
    return await pls_wait.edit(final_status)


async def auto_delete(sent_msg, duration):
    await asyncio.sleep(duration)
    try:
        await sent_msg.delete()
    except:
        pass


user_message_count = {}

MAX_MESSAGES = 3
TIME_WINDOW = timedelta(seconds=10)
BAN_DURATION = timedelta(hours=1)


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    chat_id = query.message.chat.id

    if data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass

    elif data == "about":
        try:
            await query.edit_message_media(
                InputMediaPhoto(
                    "https://graph.org/file/7228e9fe7ebf6145cca11-38b598b785ee91950b.jpg",
                    ABOUT_TXT
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('• Home', callback_data='start'), InlineKeyboardButton('Close •', callback_data='close')]
                ]),
            )
        except MessageNotModified:
            await query.answer("Nothing changed ❗", show_alert=False)

    elif data == "channels":
        try:
            await query.edit_message_media(
                InputMediaPhoto("https://graph.org/file/7228e9fe7ebf6145cca11-38b598b785ee91950b.jpg",
                                CHANNELS_TXT
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('• Home', callback_data='start'), InlineKeyboardButton('Close •', callback_data='close')]
                ]),
            )
        except MessageNotModified:
            await query.answer("Nothing changed ❗", show_alert=False)

    elif data in ["start", "home"]:
        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• About", callback_data="about"),
                 InlineKeyboardButton("Channels •", callback_data="channels")],
                [InlineKeyboardButton("• Join Updates •", url="https://t.me/Unrder")]
            ]
        )
        try:
            await query.edit_message_media(
                InputMediaPhoto(
                    START_PIC,
                    START_MSG
                ),
                reply_markup=inline_buttons
            )
        except MessageNotModified:
            await query.answer("Nothing changed ❗", show_alert=False)
        except Exception as e:
            print(f"Error sending start/home photo: {e}")
            try:
                await query.edit_message_text(
                    START_MSG,
                    reply_markup=inline_buttons,
                    parse_mode=ParseMode.HTML
                )
            except MessageNotModified:
                pass

    elif data.startswith("rfs_ch_"):
        cid = int(data.split("_")[2])
        try:
            chat = await client.get_chat(cid)
            mode = await db.get_channel_mode(cid)
            status = "🟢 ON" if mode == "on" else "🔴 OFF"
            new_mode = "off" if mode == "on" else "on"
            buttons = [
                [InlineKeyboardButton(f"Toggle Force {'OFF' if mode == 'on' else 'ON'}", callback_data=f"rfs_toggle_{cid}_{new_mode}")],
                [InlineKeyboardButton("‹ Back", callback_data="fsub_back")]
            ]
            await query.message.edit_text(
                f"Channel: {chat.title}\nCurrent Force-Sub Mode: {status}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            await query.answer("Failed to fetch channel info", show_alert=True)

    elif data.startswith("rfs_toggle_"):
        cid, action = data.split("_")[2:]
        cid = int(cid)
        mode = "on" if action == "on" else "off"

        await db.set_channel_mode(cid, mode)
        await query.answer(f"Force-Sub set to {'ON' if mode == 'on' else 'OFF'}")

        chat = await client.get_chat(cid)
        status = "🟢 ON" if mode == "on" else "🔴 OFF"
        new_mode = "off" if mode == "on" else "on"
        buttons = [
            [InlineKeyboardButton(f"Toggle Force {'OFF' if mode == 'on' else 'ON'}", callback_data=f"rfs_toggle_{cid}_{new_mode}")],
            [InlineKeyboardButton("‹ Back", callback_data="fsub_back")]
        ]
        await query.message.edit_text(
            f"Channel: {chat.title}\nCurrent Force-Sub Mode: {status}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "fsub_back":
        channels = await db.show_channels()
        buttons = []
        for cid in channels:
            try:
                chat = await client.get_chat(cid)
                mode = await db.get_channel_mode(cid)
                status = "🟢" if mode == "on" else "🔴"
                buttons.append([InlineKeyboardButton(f"{status} {chat.title}", callback_data=f"rfs_ch_{cid}")])
            except:
                continue

        await query.message.edit_text(
            "Select a channel to toggle Force-Sub:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )


def delete_after_delay(msg, delay):
    async def inner():
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except:
            pass
    return inner()
