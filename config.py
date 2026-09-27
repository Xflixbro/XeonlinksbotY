# Upgraded by @Unrated_Coder from Telegram
import os
import re
from os import environ
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

# Recommended
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
APP_ID = int(os.environ.get("APP_ID", os.environ.get("API_ID", "30128415")) or "0")
API_HASH = os.environ.get("API_HASH", "7e02885160c39ed21e7b2a76ad625dd2")

# Main
OWNER_ID = int(os.environ.get("OWNER_ID", "8365451390") or "0")
PORT = int(os.environ.get("PORT", "8080") or "8080")

# Database
DB_URI = os.environ.get("DB_URI", os.environ.get("DB_URL", os.environ.get("DATABASE_URL", "")))
DB_NAME = os.environ.get("DB_NAME", "LinkShare")

#Auto approve 
id_pattern = re.compile(r'^.\d+$')
CHAT_ID = [int(app_chat_id) if id_pattern.search(app_chat_id) else app_chat_id for app_chat_id in environ.get('CHAT_ID', '').replace(',', ' ').split()] # dont change anything
TEXT = environ.get("APPROVED_WELCOME_TEXT", "<b>{mention},\n\nʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ᴛᴏ ᴊᴏɪɴ {title} ɪs ᴀᴘᴘʀᴏᴠᴇᴅ.\n‣ ᴘᴏᴡᴇʀᴇᴅ ʙʏ @Unrated_Coder</b>")
APPROVED = environ.get("APPROVED_WELCOME", "on").lower()

# Default
TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "40"))
#--- ---- ---- --- --- --- - -- -  - - - - - - - - - - - --  - -

# Start pic
START_PIC = os.environ.get("START_PIC", "https://ibb.co/DHqBS4V7")
START_IMG = os.environ.get("START_IMG", "https://ibb.co/DHqBS4V7")
# Messages
START_MSG = os.environ.get("START_MSG", "<b>👋 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴀᴅᴠᴀɴᴄᴇᴅ ʟɪɴᴋs sʜᴀʀɪɴɢ ʙᴏᴛ!</b>\n\n<blockquote><b>ᴛʜɪs ʙᴏᴛ ɪs ᴀɴ ᴇxᴄʟᴜsɪᴠᴇ ɢᴀᴛᴇᴡᴀʏ ғᴏʀ ᴏᴜʀ ᴄᴏᴍᴍᴜɴɪᴛʏ ᴛᴏ ᴀᴄᴄᴇss ᴄᴏɴᴛᴇɴᴛ sᴇᴄᴜʀᴇʟʏ. ᴘʟᴇᴀsᴇ ᴜsᴇ ᴛʜᴇ ʟɪɴᴋs ᴘʀᴏᴠɪᴅᴇᴅ ɪɴ ᴛʜᴇ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs.</b></blockquote>\n\n<b>• 💠 ᴛʜɪs ɪs ᴀ ᴘʀɪᴠᴀᴛᴇʟʏ ᴍᴀɴᴀɢᴇᴅ sʏsᴛᴇᴍ ᴛᴏ ᴘʀᴏᴛᴇᴄᴛ ᴏᴜʀ ᴄᴏɴᴛᴇɴᴛ ғʀᴏᴍ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs.</b>")
HELP = os.environ.get("HELP_MESSAGE", "<b>›› ᴏғғɪᴄɪᴀʟ ᴄʜᴀɴɴᴇʟs:\n<blockquote>╭━━━━━━━━━━━━━━━━━━━━━\n├›› ᴜᴘᴅᴀᴛᴇs: @Unrateoder\n├›› sᴜᴘᴘᴏʀᴛ: @Unratoder\n├›› ᴅᴇᴠᴇʟᴏᴘᴇʀ: @Unrateoder\n╰━━━━━━━━━━━━━━━━━━━━━</blockquote></b>")
ABOUT = os.environ.get("ABOUT_MESSAGE", "<b>›› ᴄᴏᴍᴍᴜɴɪᴛʏ: @Unratedoder</b>\n<blockquote><b>╭━━━━━━━━━━━━━━━━━━━━━\n├›› ʟᴀɴɢᴜᴀɢᴇ: <a href='https://docs.python.org/3'>Pʏᴛʜᴏɴ 3.10</a>\n├›› ʟɪʙʀᴀʀʏ: <a href='https://www.mongodb.com/docs/'>Pʏʀᴏɢʀᴀᴍ ᴠ2</a>\n├›› ᴅᴀᴛᴀʙᴀsᴇ: <a href='https://www.mongodb.com/docs/'>Mᴏɴɢᴏ ᴅʙ</a>\n├›› ᴅᴇᴠᴇʟᴏᴘᴇʀ: @Unrated_Coder\n╰━━━━━━━━━━━━━━━━━━━━━</b></blockquote>")

ABOUT_TXT = """<b>›› ᴄᴏᴍᴍᴜɴɪᴛʏ: @Unrader</b>
<blockquote><b>╭━━━━━━━━━━━━━━━━━━━━━
├›› ʟᴀɴɢᴜᴀɢᴇ: <a href='https://docs.python.org/3'>Pʏᴛʜᴏɴ 3.10</a>
├›› ʟɪʙʀᴀʀʏ: <a href='https://www.mongodb.com/docs/'>Pʏʀᴏɢʀᴀᴍ ᴠ2</a>
├›› ᴅᴀᴛᴀʙᴀsᴇ: <a href='https://www.mongodb.com/docs/'>Mᴏɴɢᴏ ᴅʙ</a>
├›› ᴅᴇᴠᴇʟᴏᴘᴇʀ: @Unrateder
╰━━━━━━━━━━━━━━━━━━━━━</b></blockquote>""" 

CHANNELS_TXT = """<b>›› ᴏғғɪᴄɪᴀʟ ᴄʜᴀɴɴᴇʟs:
<blockquote>╭━━━━━━━━━━━━━━━━━━━━━
├›› ᴜᴘᴅᴀᴛᴇs: @Unrateer
├›› sᴜᴘᴘᴏʀᴛ: @Unrateer
├›› ᴅᴇᴠᴇʟᴏᴘᴇʀ: @Unratder
╰━━━━━━━━━━━━━━━━━━━━━</blockquote></b>"""

#--- ---- ---- --- --- --- - -- -  - - - - - - - - - - - --  - -
# Default
BOT_STATS_TEXT = "<b>BOT UPTIME</b>\n{uptime}"
USER_REPLY_TEXT = "<b>ʙᴀᴋᴋᴀ ! ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴍʏ ꜱᴇɴᴘᴀɪ!!</b>"
USER_ROAST = "<b>⚠️ ғᴜᴄᴋ ʏᴏᴜ, ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴍʏ ᴍᴀsᴛᴇʀ. ɢᴏ ᴀᴡᴀʏ, ʙɪᴛᴄʜ 🥱!</b>"

# Logging
LOG_FILE_NAME = "links-sharingbot.txt"
DATABASE_CHANNEL = int(os.environ.get("DATABASE_CHANNEL", "-1002327650917") or "0") # Channel where user links are stored
#--- ---- ---- --- --- --- - -- -  - - - - - - - - - - - --  - -

try:
    ADMINS = []
    for x in (os.environ.get("ADMINS", "8365451390 8741514787").split()):
        ADMINS.append(int(x))
except ValueError:
    raise Exception("Your Admins list does not contain valid integers.")

# Admin == OWNER_ID
if OWNER_ID and OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
