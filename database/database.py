import motor.motor_asyncio
import base64
from config import DB_URI, DB_NAME
from datetime import datetime, timedelta
from typing import List, Optional

dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
database = dbclient[DB_NAME]

# collections
user_data = database['users']
channels_collection = database['channels']
fsub_channels_collection = database['fsub_channels']


# ═══════════════════════════════════════════════════════════════
#  BASE64 HELPERS  (single source of truth, padding stripped)
# ═══════════════════════════════════════════════════════════════
def _b64_encode_channel_id(channel_id: int) -> str:
    """URL-safe base64 of channel_id, padding '=' stripped (canonical form)."""
    return base64.urlsafe_b64encode(str(channel_id).encode("ascii")).decode("ascii").rstrip("=")


def _b64_pad(token: str) -> str:
    """Add back '=' padding so base64 decode works."""
    return token + "=" * (-len(token) % 4)


# ═══════════════════════════════════════════════════════════════
#  USERS
# ═══════════════════════════════════════════════════════════════
async def add_user(user_id: int) -> bool:
    """Add a user to the database if they don't exist."""
    if not isinstance(user_id, int) or user_id <= 0:
        print(f"Invalid user_id: {user_id}")
        return False

    try:
        existing_user = await user_data.find_one({'_id': user_id})
        if existing_user:
            return False

        await user_data.insert_one({'_id': user_id, 'created_at': datetime.utcnow()})
        return True
    except Exception as e:
        print(f"Error adding user {user_id}: {e}")
        return False


async def present_user(user_id: int) -> bool:
    """Check if a user exists in the database."""
    if not isinstance(user_id, int):
        return False
    return bool(await user_data.find_one({'_id': user_id}))


async def full_userbase() -> List[int]:
    """Get all user IDs from the database."""
    try:
        user_docs = user_data.find()
        return [doc['_id'] async for doc in user_docs]
    except Exception as e:
        print(f"Error fetching userbase: {e}")
        return []


async def count_users() -> int:
    """Count total users in the database."""
    try:
        return await user_data.count_documents({})
    except Exception as e:
        print(f"Error counting users: {e}")
        return 0


async def del_user(user_id: int) -> bool:
    """Delete a user from the database."""
    try:
        result = await user_data.delete_one({'_id': user_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  ADMINS
# ═══════════════════════════════════════════════════════════════
async def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    admins_collection = database['admins']
    try:
        user_id = int(user_id)
        return bool(await admins_collection.find_one({'_id': user_id}))
    except Exception as e:
        print(f"Error checking admin status for {user_id}: {e}")
        return False


async def add_admin(user_id: int) -> bool:
    """Add a user as admin."""
    admins_collection = database['admins']
    try:
        user_id = int(user_id)
        await admins_collection.update_one({'_id': user_id}, {'$set': {'_id': user_id}}, upsert=True)
        return True
    except Exception as e:
        print(f"Error adding admin {user_id}: {e}")
        return False


async def remove_admin(user_id: int) -> bool:
    """Remove a user from admins."""
    admins_collection = database['admins']
    try:
        result = await admins_collection.delete_one({'_id': user_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error removing admin {user_id}: {e}")
        return False


async def list_admins() -> list:
    """List all admin user IDs."""
    admins_collection = database['admins']
    try:
        admins = await admins_collection.find().to_list(None)
        return [admin['_id'] for admin in admins]
    except Exception as e:
        print(f"Error listing admins: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
#  CHANNELS  —  /addch  /delch  /channels  + token encoding
# ═══════════════════════════════════════════════════════════════

async def save_channel(channel_id) -> bool:
    """Save/update a channel row. Always stores channel_id as int."""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        print(f"[save_channel] Invalid channel_id: {channel_id!r}")
        return False

    try:
        result = await channels_collection.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "created_at": datetime.utcnow(),
                    "status": "active",
                }
            },
            upsert=True
        )
        print(f"[save_channel] channel_id={channel_id} matched={result.matched_count} upserted={result.upserted_id}")
        return True
    except Exception as e:
        print(f"[save_channel] Error: {e}")
        return False


async def get_channels() -> List[int]:
    """Return every stored channel_id as int (no status filter)."""
    try:
        channels = await channels_collection.find({}).to_list(None)
        valid: List[int] = []
        for ch in channels:
            cid = ch.get("channel_id")
            if isinstance(cid, int):
                valid.append(cid)
            else:
                # try converting if stored as string
                try:
                    valid.append(int(cid))
                except (TypeError, ValueError):
                    print(f"[get_channels] Skipping bad row: {ch}")
        print(f"[get_channels] Returning {valid}")
        return valid
    except Exception as e:
        print(f"[get_channels] Error: {e}")
        return []


async def delete_channel(channel_id) -> bool:
    """Delete every doc with this exact channel_id. Returns True if something was deleted."""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        print(f"[delete_channel] Invalid channel_id: {channel_id!r}")
        return False

    try:
        result = await channels_collection.delete_many({"channel_id": channel_id})
        print(f"[delete_channel] channel_id={channel_id} deleted_count={result.deleted_count}")
        return result.deleted_count > 0
    except Exception as e:
        print(f"[delete_channel] Error: {e}")
        return False


async def save_encoded_link(channel_id) -> Optional[str]:
    """Persist the canonical (padding-stripped) base64 of channel_id. Returns the token."""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        print(f"[save_encoded_link] Invalid channel_id: {channel_id!r}")
        return None

    try:
        encoded_link = _b64_encode_channel_id(channel_id)
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "encoded_link": encoded_link,
                    "status": "active",
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True
        )
        print(f"[save_encoded_link] channel_id={channel_id} -> {encoded_link}")
        return encoded_link
    except Exception as e:
        print(f"[save_encoded_link] Error: {e}")
        return None


async def get_channel_by_encoded_link(encoded_link: str) -> Optional[int]:
    """Look up channel_id from the normal token. Tolerates old padded rows."""
    if not isinstance(encoded_link, str) or not encoded_link:
        return None

    token = encoded_link.rstrip("=")
    try:
        # new canonical form (no padding)
        doc = await channels_collection.find_one({"encoded_link": token})
        if doc:
            cid = doc.get("channel_id")
            return int(cid) if cid is not None else None

        # legacy rows that still have padding
        doc = await channels_collection.find_one({"encoded_link": _b64_pad(token)})
        if doc:
            cid = doc.get("channel_id")
            return int(cid) if cid is not None else None

        return None
    except Exception as e:
        print(f"[get_channel_by_encoded_link] Error: {e}")
        return None


async def save_encoded_link2(channel_id, encoded_link: str) -> Optional[str]:
    """Persist the canonical request token. Returns the stored token."""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        print(f"[save_encoded_link2] Invalid channel_id: {channel_id!r}")
        return None
    if not isinstance(encoded_link, str) or not encoded_link:
        return None

    token = encoded_link.rstrip("=")
    try:
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "req_encoded_link": token,
                    "status": "active",
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True
        )
        print(f"[save_encoded_link2] channel_id={channel_id} -> {token}")
        return token
    except Exception as e:
        print(f"[save_encoded_link2] Error: {e}")
        return None


async def get_channel_by_encoded_link2(encoded_link: str) -> Optional[int]:
    """Look up channel_id from the request token. Tolerates old padded rows."""
    if not isinstance(encoded_link, str) or not encoded_link:
        return None

    token = encoded_link.rstrip("=")
    try:
        doc = await channels_collection.find_one({"req_encoded_link": token})
        if doc:
            cid = doc.get("channel_id")
            return int(cid) if cid is not None else None

        doc = await channels_collection.find_one({"req_encoded_link": _b64_pad(token)})
        if doc:
            cid = doc.get("channel_id")
            return int(cid) if cid is not None else None

        return None
    except Exception as e:
        print(f"[get_channel_by_encoded_link2] Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  INVITE-LINK CACHE  (still used by /start)
# ═══════════════════════════════════════════════════════════════
async def save_invite_link(channel_id: int, invite_link: str, is_request: bool) -> bool:
    if not isinstance(channel_id, int) or not isinstance(invite_link, str):
        return False
    try:
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "current_invite_link": invite_link,
                    "is_request_link": is_request,
                    "invite_link_created_at": datetime.utcnow(),
                    "status": "active",
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error saving invite link for channel {channel_id}: {e}")
        return False


async def get_current_invite_link(channel_id: int) -> Optional[dict]:
    if not isinstance(channel_id, int):
        return None
    try:
        channel = await channels_collection.find_one({"channel_id": channel_id})
        if channel and "current_invite_link" in channel:
            return {
                "invite_link": channel["current_invite_link"],
                "is_request": channel.get("is_request_link", False)
            }
        return None
    except Exception as e:
        print(f"Error fetching current invite link for channel {channel_id}: {e}")
        return None


async def get_link_creation_time(channel_id: int):
    try:
        channel = await channels_collection.find_one({"channel_id": channel_id})
        if channel and "invite_link_created_at" in channel:
            return channel["invite_link_created_at"]
        return None
    except Exception as e:
        print(f"Error fetching link creation time for channel {channel_id}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  FSUB
# ═══════════════════════════════════════════════════════════════
async def add_fsub_channel(channel_id: int, mode: str = "normal") -> bool:
    if not isinstance(channel_id, int):
        print(f"Invalid channel_id: {channel_id}")
        return False
    try:
        await fsub_channels_collection.update_one(
            {'channel_id': channel_id},
            {
                '$set': {
                    'channel_id': channel_id,
                    'mode': mode,
                    'created_at': datetime.utcnow(),
                    'status': 'active'
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error adding FSub channel {channel_id}: {e}")
        return False


async def remove_fsub_channel(channel_id: int) -> bool:
    try:
        result = await fsub_channels_collection.delete_one({'channel_id': channel_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error removing FSub channel {channel_id}: {e}")
        return False


async def get_fsub_channels() -> List[dict]:
    try:
        return await fsub_channels_collection.find({'status': 'active'}).to_list(None)
    except Exception as e:
        print(f"Error fetching FSub channels: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
#  /genlink ORIGINAL LINK
# ═══════════════════════════════════════════════════════════════
async def get_original_link(channel_id: int) -> Optional[str]:
    if not isinstance(channel_id, int):
        return None
    try:
        channel = await channels_collection.find_one({"channel_id": channel_id})
        return channel.get("original_link") if channel and "original_link" in channel else None
    except Exception as e:
        print(f"Error fetching original link for channel {channel_id}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  APPROVAL TOGGLE
# ═══════════════════════════════════════════════════════════════
async def set_approval_off(channel_id: int, off: bool = True) -> bool:
    if not isinstance(channel_id, int):
        print(f"Invalid channel_id: {channel_id}")
        return False
    try:
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"approval_off": off}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting approval_off for channel {channel_id}: {e}")
        return False


async def is_approval_off(channel_id: int) -> bool:
    if not isinstance(channel_id, int):
        return False
    try:
        channel = await channels_collection.find_one({"channel_id": channel_id})
        return bool(channel and channel.get("approval_off", False))
    except Exception as e:
        print(f"Error checking approval_off for channel {channel_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  FSUB SHORTCUTS
# ═══════════════════════════════════════════════════════════════
async def show_channels() -> List[int]:
    try:
        channels = await fsub_channels_collection.find({'status': 'active'}).to_list(None)
        return [ch['channel_id'] for ch in channels if isinstance(ch, dict) and 'channel_id' in ch]
    except Exception as e:
        print(f"Error fetching show_channels: {e}")
        return []


async def get_channel_mode(channel_id: int) -> str:
    if not isinstance(channel_id, int):
        return "off"
    try:
        channel = await fsub_channels_collection.find_one({'channel_id': channel_id, 'status': 'active'})
        if channel:
            mode = channel.get('mode', 'normal')
            return "on" if mode == "request" else "off"
        return "off"
    except Exception as e:
        print(f"Error getting channel mode for {channel_id}: {e}")
        return "off"


async def set_channel_mode(channel_id: int, mode: str) -> bool:
    if not isinstance(channel_id, int):
        return False
    try:
        db_mode = "request" if mode == "on" else "normal"
        await fsub_channels_collection.update_one(
            {'channel_id': channel_id},
            {'$set': {'mode': db_mode}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting channel mode for {channel_id}: {e}")
        return False
