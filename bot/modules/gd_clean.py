import asyncio
import os
import re
import shutil
import sys
import telethon.utils
from contextlib import suppress
from pyrogram.errors import FloodWait
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from telethon.errors import SessionPasswordNeededError
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, deleteMessage  # Import utility functions for Telegram messaging
from bot.helper.telegram_helper.filters import CustomFilters  # Import custom filters
from bot.helper.telegram_helper.button_build import ButtonMaker  # Import class for building inline keyboards
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper  # Import Google Drive helper functions
from bot.helper.ext_utils.bot_utils import is_gdrive_link, get_readable_file_size, new_task  # Import utility functions for bot
from telethon import TelegramClient, events  # Import Telethon client and event classes
from pyrogram import Client as PyrogramClient  # Import Pyrogram client
from typing import List, Tuple, Union, Optional  # Import type hints

OWNER_ID = 0  # Make sure to define this variable

# Function to clean Google Drive using the provided link
async def driveclean(bot: Union[TelegramClient, PyrogramClient], update):
    message = update.effective_message
    args = message.text.split()
    link = get_gdrive_link(args, message)
    if not link:
        return
    clean_msg = await sendMessage(message, 'Fetching ...')
    async with GoogleDriveHelper() as gd:
        name, mime_type, size, files, folders = await gd.count(link)
    try:
        drive_id = GoogleDriveHelper.getIdFromUrl(link)
    except (KeyError, IndexError):
        return await editMessage(clean_msg, "Google Drive ID could not be found in the provided link")
    buttons = ButtonMaker()
    buttons.ibutton('Move to Bin', f'gdclean clear {drive_id} trash')
    buttons.ibutton('Permanent Clean', f'gdclean clear {drive_id}')
    buttons.ibutton('Stop GDrive Clean', 'gdclean stop', 'footer')
    await bot.edit_message_text(
        clean_msg,
        f'''<b><i>GDrive Clean/Trash :</i></b>
┎ <b>Name:</b> {name}
┃ <b>Size:</b> {get_readable_file_size(size)}
┖ <b>Files:</b> {files} | <b>Folders:</b> {folders}
    
<b>NOTES:</b>
<i>1. All files are permanently deleted if Permanent Del, not moved to trash.
2. Folder doesn't gets Deleted.
3. Delete files of custom folder via giving link along with cmd, but it should have delete permissions.
4. Move to Bin Moves all your files to trash but can be restored again if have permissions.</i>
    
<code>Choose the Required Action below to Clean your Drive!</code>''',
        reply_markup=buttons.build_menu(2)
    )

# Callback function to handle Google Drive cleaning actions
@new_task
async def drivecleancb(bot: Union[TelegramClient, PyrogramClient], query: telegram.CallbackQuery) -> None:
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != OWNER_ID:
        await bot.answer(query, text="Not Owner!", show_alert=True)
        return
    if data[1] == "clear":
        await bot.answer(query)
        await editMessage(message, '<i>Processing Drive Clean / Trash...</i>')
        async with GoogleDriveHelper() as gd:
            msg = await gd.driveclean(data[2], trash=len(data)==4)
        await bot.edit_message_text(message, msg)
    elif data[1] == "stop":
        await bot.answer(query)
        await bot.edit_message_text(message, '⌬ <b>DriveClean Stopped!</b>')
        await bot.delete_message(message)

# Function to extract Google Drive link from arguments or reply message
def get_gdrive_link(args, message) -> Union[str, None]:
    if len(args) > 1:
        link = args[1].strip()
    elif message.reply_to_message:
        link = message.reply_to_message.text.split(maxsplit=1)[0].strip()
    else:
        link = f"https://drive.google.com/drive/folders/{config_dict['GDRIVE_ID']}"
    return link if is_gdrive_link(link) else None

# Function to get Google Drive ID from URL
async def get_id_from_url(link: str) -> Optional[str]:
    try:
        return GoogleDriveHelper.getIdFromUrl(link)
    except (KeyError, IndexError):
        return None
    except SessionPasswordNeededError:
        return None

# Add handlers for Google Drive cleaning commands
if bot.loop.current_instance() is bot.loop.instance(0):
    bot.add_handler(MessageHandler(command(BotCommands.GDCleanCommand) & CustomFilters.owner, driveclean))
    bot.add_handler(CallbackQueryHandler(drivecleancb, filters=regex(r'^gdclean')))

    # Add event-based handler for better performance
    @bot.on(events.CallbackQuery(data=r'^gdclean'))
    async def drivecleancb_event(event):
        await drivecleancb(bot, event)
