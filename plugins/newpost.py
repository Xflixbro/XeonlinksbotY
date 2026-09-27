# Upgraded by @Unrated_Coder from Telegram
import asyncio
import base64
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired, RPCError
from pyrogram.errors import InviteHashExpired, InviteRequestSent, MessageNotModified, QueryIdInvalid
from database.database import save_channel, delete_channel, get_channels, is_admin
from config import *
from config import OWNER_ID, ADMINS
from database.database import *
from helper_func import *
from datetime import datetime, timedelta

PAGE_SIZE = 6

chat_info_cache = {}


# ────────────── Helper: admin check for callbacks ──────────────
async def _is_callback_admin(callback_query) -> bool:
    try:
        uid = callback_query.from_user.id
    except Exception:
        return False
    if uid == OWNER_ID or uid in ADMINS:
        return True
    try:
        return await is_admin(uid)
    except Exception:
        return False


async def revoke_invite_after_5_minutes(client: Client, channel_id: int, link: str, is_request: bool = False):
    await asyncio.sleep(300)
    try:
        await client.revoke_chat_invite_link(channel_id, link)
        print(f"{'Join request' if is_request else 'Invite'} link revoked for channel {channel_id}")
    except (InviteHashExpired, RPCError) as e:
        print(f"Link already revoked or expired for {channel_id}: {e}")
    except Exception as e:
        print(f"Failed to revoke invite for channel {channel_id}: {e}")


# ═══════════════════════════════════════════════════════════════
#  /addch  /addchat
# ═══════════════════════════════════════════════════════════════
@Client.on_message((filters.command('addchat') | filters.command('addch')) & is_owner_or_admin)
async def set_channel(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("<b>Usage: <code>/addch &lt;chat_id&gt;</code></b>")

    try:
        channel_id = int(message.command[1])
    except (IndexError, ValueError):
        return await message.reply(
            f"<b>Invalid chat ID: <code>{message.command[1]}</code></b>"
        )

    try:
        chat = await client.get_chat(channel_id)

        if chat.permissions:
            has_permission = False
            if getattr(chat.permissions, 'can_post_messages', False):
                has_permission = True
            elif getattr(chat.permissions, 'can_edit_messages', False):
                has_permission = True
            elif chat.type.name in ['GROUP', 'SUPERGROUP']:
                try:
                    bot_member = await client.get_chat_member(chat.id, (await client.get_me()).id)
                    if bot_member.status.name in ['ADMINISTRATOR', 'CREATOR']:
                        has_permission = True
                except Exception:
                    pass

            if not has_permission:
                return await message.reply(
                    f"<b>I am in {chat.title}, but I lack posting/editing permissions.</b>"
                )

        # 1) Persist the channel row
        await save_channel(channel_id)

        # 2) Compute the token LOCALLY — never trust a save_* return value
        base64_invite = await encode(str(channel_id))       # canonical, padding stripped
        base64_request = base64_invite                      # same value; prefix added in URL

        # 3) Best-effort persist both tokens
        await save_encoded_link(channel_id)
        await save_encoded_link2(channel_id, base64_request)

        # 4) Build deep links from the LOCAL values
        normal_link  = f"https://t.me/{client.username}?start={base64_invite}"
        request_link = f"https://t.me/{client.username}?start=req_{base64_request}"

        reply_text = (
            f"<b><blockquote expandable>✅ Chat {chat.title} ({channel_id}) added successfully.</b>\n\n"
            f"<b>🔗 Normal  Link:</b> <code>{normal_link}</code>\n"
            f"<b>🔗 Request Link:</b> <code>{request_link}</code>"
        )
        return await message.reply(reply_text)

    except UserNotParticipant:
        return await message.reply(
            "<b>I am not a member of this channel. Please add me and try again.</b>"
        )
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await set_channel(client, message)
    except RPCError as e:
        return await message.reply(f"RPC Error: {e}")
    except Exception as e:
        return await message.reply(f"Unexpected Error: {e}")


# ═══════════════════════════════════════════════════════════════
#  /delch  /delchat
# ═══════════════════════════════════════════════════════════════
@Client.on_message((filters.command('delchat') | filters.command('delch')) & is_owner_or_admin)
async def del_channel(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("<b>Usage: <code>/delch &lt;chat_id&gt;</code></b>")

    try:
        channel_id = int(message.command[1])
    except (IndexError, ValueError):
        return await message.reply(
            f"<b>Invalid chat ID: <code>{message.command[1]}</code></b>"
        )

    deleted = await delete_channel(channel_id)
    if deleted:
        return await message.reply(
            f"<b>❌ Chat <code>{channel_id}</code> has been removed successfully.</b>"
        )
    return await message.reply(
        f"<b>⚠️ Chat <code>{channel_id}</code> was not found in the database.</b>"
    )


# ═══════════════════════════════════════════════════════════════
#  /ch_links  (channel buttons page)
# ═══════════════════════════════════════════════════════════════
@Client.on_message(filters.command('ch_links') & is_owner_or_admin)
async def channel_post(client: Client, message: Message):
    try:
        channels = await get_channels()
        if not channels:
            return await message.reply("<b>No channels are available. Please use /addch to add a channel.</b>")
        await send_channel_page(client, message, channels, page=0)
    except Exception as e:
        await message.reply(f"<b>Error:</b> <code>{str(e)}</code>")


async def send_channel_page(client, message, channels, page, edit=False):
    total_pages = (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    buttons = []

    chat_tasks = [get_chat_info(client, cid) for cid in channels[start_idx:end_idx]]
    try:
        chat_infos = await asyncio.gather(*chat_tasks, return_exceptions=True)
    except Exception as e:
        print(f"Error gathering chat info: {e}")
        chat_infos = [None] * len(channels[start_idx:end_idx])

    row = []
    for i, chat_info in enumerate(chat_infos):
        channel_id = channels[start_idx + i]
        if isinstance(chat_info, Exception) or chat_info is None:
            print(f"Error getting chat info for channel {channel_id}: {chat_info}")
            continue
        try:
            base64_invite = await encode(str(channel_id))
            await save_encoded_link(channel_id)
            button_link = f"https://t.me/{client.username}?start={base64_invite}"
            row.append(InlineKeyboardButton(chat_info.title, url=button_link))
            if len(row) == 2:
                buttons.append(row)
                row = []
        except Exception as e:
            print(f"Error for channel {channel_id}: {e}")

    if row:
        buttons.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("• Previous •", callback_data=f"channelpage_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("• Next •", callback_data=f"channelpage_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons)
    if edit:
        try:
            await message.edit_text("Select a channel to access:", reply_markup=reply_markup)
        except MessageNotModified:
            pass
    else:
        await message.reply("Select channel:", reply_markup=reply_markup)


@Client.on_callback_query(filters.regex(r"^channelpage_(\d+)$"), group=-1)
async def paginate_channels(client: Client, callback_query):
    if not await _is_callback_admin(callback_query):
        return await callback_query.answer("❌ Admin only!", show_alert=True)
    try:
        await callback_query.answer()
    except Exception:
        pass
    try:
        page = int(callback_query.data.split("_")[1])
        channels = await get_channels()
        await send_channel_page(client, callback_query.message, channels, page, edit=True)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"[paginate_channels] Error: {e}")
        try:
            await callback_query.answer(f"Error: {e}", show_alert=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  /reqlink  (request buttons page)
# ═══════════════════════════════════════════════════════════════
@Client.on_message(filters.command('reqlink') & is_owner_or_admin)
async def req_post(client: Client, message: Message):
    try:
        channels = await get_channels()
        if not channels:
            return await message.reply("<b>No channels are available. Please use /addch to add a channel.</b>")
        await send_request_page(client, message, channels, page=0)
    except Exception as e:
        await message.reply(f"<b>Error:</b> <code>{str(e)}</code>")


async def send_request_page(client, message, channels, page, edit=False):
    total_pages = (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    buttons = []

    chat_tasks = [get_chat_info(client, cid) for cid in channels[start_idx:end_idx]]
    try:
        chat_infos = await asyncio.gather(*chat_tasks, return_exceptions=True)
    except Exception as e:
        print(f"Error gathering chat info: {e}")
        chat_infos = [None] * len(channels[start_idx:end_idx])

    row = []
    for i, chat_info in enumerate(chat_infos):
        channel_id = channels[start_idx + i]
        if isinstance(chat_info, Exception) or chat_info is None:
            print(f"Error getting chat info for channel {channel_id}: {chat_info}")
            continue
        try:
            base64_request = await encode(str(channel_id))
            await save_encoded_link2(channel_id, base64_request)
            button_link = f"https://t.me/{client.username}?start=req_{base64_request}"
            row.append(InlineKeyboardButton(chat_info.title, url=button_link))
            if len(row) == 2:
                buttons.append(row)
                row = []
        except Exception as e:
            print(f"Error generating request link for channel {channel_id}: {e}")

    if row:
        buttons.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("• Previous •", callback_data=f"reqpage_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("• Next •", callback_data=f"reqpage_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons)
    if edit:
        try:
            await message.edit_text("Select a channel to request access:", reply_markup=reply_markup)
        except MessageNotModified:
            pass
    else:
        await message.reply("Select channel:", reply_markup=reply_markup)


@Client.on_callback_query(filters.regex(r"^reqpage_(\d+)$"), group=-1)
async def paginate_requests(client: Client, callback_query):
    if not await _is_callback_admin(callback_query):
        return await callback_query.answer("❌ Admin only!", show_alert=True)
    try:
        await callback_query.answer()
    except Exception:
        pass
    try:
        page = int(callback_query.data.split("_")[1])
        channels = await get_channels()
        await send_request_page(client, callback_query.message, channels, page, edit=True)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"[paginate_requests] Error: {e}")
        try:
            await callback_query.answer(f"Error: {e}", show_alert=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  /links  (text list with both links)
# ═══════════════════════════════════════════════════════════════
@Client.on_message(filters.command('links') & is_owner_or_admin)
async def show_links(client: Client, message: Message):
    try:
        channels = await get_channels()
        if not channels:
            return await message.reply("<b>No channels are available. Please use /addch to add a channel.</b>")
        await send_links_page(client, message, channels, page=0)
    except Exception as e:
        await message.reply(f"<b>Error:</b> <code>{str(e)}</code>")


async def send_links_page(client, message, channels, page, edit=False):
    total_pages = (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE

    links_text = "<b>➤ All Channel Links:</b>\n\n"
    for i, channel_id in enumerate(channels[start_idx:end_idx], start=1):
        idx = start_idx + i
        try:
            chat_info = await get_chat_info(client, channel_id)
            base64_invite = await encode(str(channel_id))
            base64_request = base64_invite
            await save_encoded_link(channel_id)
            await save_encoded_link2(channel_id, base64_request)

            normal_link = f"https://t.me/{client.username}?start={base64_invite}"
            request_link = f"https://t.me/{client.username}?start=req_{base64_request}"

            links_text += f"<b>{idx}. {chat_info.title}</b>\n"
            links_text += f"<b>➥ Normal:</b> <code>{normal_link}</code>\n"
            links_text += f"<b>➤ Request:</b> <code>{request_link}</code>\n\n"
        except Exception as e:
            print(f"Error for channel {channel_id}: {e}")
            links_text += f"<b>{idx}. Channel {channel_id}</b> (Error)\n\n"

    links_text += f"<b>📄 Page {page + 1} of {total_pages}</b>"

    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("• Previous •", callback_data=f"linkspage_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("• Next •", callback_data=f"linkspage_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    if edit:
        try:
            await message.edit_text(links_text, reply_markup=reply_markup)
        except MessageNotModified:
            pass
    else:
        await message.reply(links_text, reply_markup=reply_markup)


@Client.on_callback_query(filters.regex(r"^linkspage_(\d+)$"), group=-1)
async def paginate_links(client: Client, callback_query):
    if not await _is_callback_admin(callback_query):
        return await callback_query.answer("❌ Admin only!", show_alert=True)
    try:
        await callback_query.answer()
    except Exception:
        pass
    try:
        page = int(callback_query.data.split("_")[1])
        channels = await get_channels()
        await send_links_page(client, callback_query.message, channels, page, edit=True)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"[paginate_links] Error: {e}")
        try:
            await callback_query.answer(f"Error: {e}", show_alert=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  /bulklink
# ═══════════════════════════════════════════════════════════════
@Client.on_message(filters.command('bulklink') & is_owner_or_admin)
async def bulk_link(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("<b>Usage: <code>/bulklink &lt;id1&gt; &lt;id2&gt; ...</code></b>")

    ids = message.command[1:]
    reply_text = "<b>➤ Bulk Link Generation:</b>\n\n"
    for idx, id_str in enumerate(ids, start=1):
        try:
            channel_id = int(id_str)
            chat = await client.get_chat(channel_id)
            await save_channel(channel_id)

            base64_invite = await encode(str(channel_id))
            await save_encoded_link(channel_id)
            await save_encoded_link2(channel_id, base64_invite)

            normal_link = f"https://t.me/{client.username}?start={base64_invite}"
            request_link = f"https://t.me/{client.username}?start=req_{base64_invite}"

            reply_text += f"<b>{idx}. {chat.title} ({channel_id})</b>\n"
            reply_text += f"<b>➥ Normal:</b> <code>{normal_link}</code>\n"
            reply_text += f"<b>➤ Request:</b> <code>{request_link}</code>\n\n"
        except Exception as e:
            reply_text += f"<b>{idx}. Channel {id_str}</b> (Error: {e})\n\n"

    await message.reply(reply_text)


# ═══════════════════════════════════════════════════════════════
#  /genlink  (store a link in DATABASE_CHANNEL and encode its msg id)
# ═══════════════════════════════════════════════════════════════
@Client.on_message(filters.command('genlink') & filters.private & is_owner_or_admin)
async def generate_link_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("<b>Usage:</b> <code>/genlink &lt;link&gt;</code>")

    link = message.command[1]
    try:
        sent_msg = await client.send_message(DATABASE_CHANNEL, f"#LINK\n{link}")
        channel_id = sent_msg.id

        base64_invite = await encode(str(channel_id))
        await save_channel(channel_id)
        await save_encoded_link(channel_id)
        await save_encoded_link2(channel_id, base64_invite)

        from database.database import channels_collection
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"original_link": link}},
            upsert=True
        )

        normal_link = f"https://t.me/{client.username}?start={base64_invite}"
        request_link = f"https://t.me/{client.username}?start=req_{base64_invite}"

        reply_text = (
            f"<b>✅ Link stored and encoded successfully.</b>\n\n"
            f"<b>🔗 Normal Link:</b> <code>{normal_link}</code>\n"
            f"<b>🔗 Request Link:</b> <code>{request_link}</code>"
        )
        await message.reply(reply_text)
    except Exception as e:
        await message.reply(f"<b>Error storing link:</b> <code>{e}</code>")


# ═══════════════════════════════════════════════════════════════
#  /channels  (list channel IDs)
# ═══════════════════════════════════════════════════════════════
@Client.on_message(filters.command('channels') & is_owner_or_admin)
async def show_channel_ids(client: Client, message: Message):
    try:
        channels = await get_channels()
        if not channels:
            return await message.reply("<b>No channels are available. Please use /addch to add a channel.</b>")
        await send_channel_ids_page(client, message, channels, page=0)
    except Exception as e:
        await message.reply(f"<b>Error:</b> <code>{str(e)}</code>")


async def send_channel_ids_page(client, message, channels, page, edit=False):
    PAGE_SIZE_LOCAL = 10
    total_pages = (len(channels) + PAGE_SIZE_LOCAL - 1) // PAGE_SIZE_LOCAL
    start_idx = page * PAGE_SIZE_LOCAL
    end_idx = start_idx + PAGE_SIZE_LOCAL

    chat_tasks = [get_chat_info(client, cid) for cid in channels[start_idx:end_idx]]
    try:
        chat_infos = await asyncio.gather(*chat_tasks, return_exceptions=True)
    except Exception as e:
        print(f"Error gathering chat info: {e}")
        chat_infos = [None] * len(channels[start_idx:end_idx])

    text = "<b>➤ Connected Channels (ID & Name):</b>\n\n"
    for i, chat_info in enumerate(chat_infos):
        idx = start_idx + i + 1
        channel_id = channels[start_idx + i]
        if isinstance(chat_info, Exception) or chat_info is None:
            text += f"<b>{idx}. Channel {channel_id}</b> (Error)\n"
            continue
        text += f"<b>{idx}. {chat_info.title}</b> <code>({channel_id})</code>\n"

    text += f"\n<b>📄 Page {page + 1} of {total_pages}</b>"

    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("• Previous •", callback_data=f"channelids_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("• Next •", callback_data=f"channelids_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    if edit:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
        except MessageNotModified:
            pass
    else:
        await message.reply(text, reply_markup=reply_markup)


@Client.on_callback_query(filters.regex(r"^channelids_(\d+)$"), group=-1)
async def paginate_channel_ids(client: Client, callback_query):
    if not await _is_callback_admin(callback_query):
        return await callback_query.answer("❌ Admin only!", show_alert=True)
    try:
        await callback_query.answer()
    except Exception:
        pass
    try:
        page = int(callback_query.data.split("_")[1])
        channels = await get_channels()
        await send_channel_ids_page(client, callback_query.message, channels, page, edit=True)
    except MessageNotModified:
        pass
    except Exception as e:
        print(f"[paginate_channel_ids] Error: {e}")
        try:
            await callback_query.answer(f"Error: {e}", show_alert=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  Chat info cache
# ═══════════════════════════════════════════════════════════════
async def get_chat_info(client, channel_id):
    if channel_id in chat_info_cache:
        cached_info, timestamp = chat_info_cache[channel_id]
        if (datetime.now() - timestamp).total_seconds() < 300:
            return cached_info

    try:
        chat_info = await client.get_chat(channel_id)
        chat_info_cache[channel_id] = (chat_info, datetime.now())
        return chat_info
    except Exception as e:
        print(f"Error getting chat info for {channel_id}: {e}")
        if channel_id in chat_info_cache:
            return chat_info_cache[channel_id][0]
        raise e
