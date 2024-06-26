import typing
import asyncio
import aiohttp
import html
import urllib.parse
import ast
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from pyrogram.context import AsyncContextManager
from pyrogram.errors import SessionPasswordNeeded
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import get_readable_file_size, sync_to_async, new_task, checking_access
from bot.helper.telegram_helper.button_build import ButtonMaker

# Initialize global variables
PLUGINS = []  # List to store the names of installed plugins
SITES = None  # Variable to store the supported sites for search
TELEGRAPH_LIMIT = 300  # Limit for the number of characters in a Telegraph post

async def initiate_search_tools() -> None:
    """
    Initialize search tools.
    This function installs the required plugins for search and fetches the supported sites from the provided API link.
    """
    async with AsyncContextManager(get_client()) as qbclient:
        try:
            qb_plugins = await sync_to_async(qbclient.search_plugins)
        except SessionPasswordNeeded:
            return

        if SEARCH_PLUGINS := config_dict.get('SEARCH_PLUGINS'):
            PLUGINS = []
            src_plugins = ast.literal_eval(SEARCH_PLUGINS)
            if qb_plugins:
                names = [plugin['name'] for plugin in qb_plugins]
                await sync_to_async(qbclient.search_uninstall_plugin, names=names)
            await sync_to_async(qbclient.search_install_plugin, src_plugins)
        elif qb_plugins:
            for plugin in qb_plugins:
                await sync_to_async(qbclient.search_uninstall_plugin, names=plugin['name'])
            PLUGINS = []
        await sync_to_async(qbclient.auth_log_out)

        if SEARCH_API_LINK := config_dict.get('SEARCH_API_LINK'):
            try:
                async with AsyncContextManager(aiohttp.ClientSession(trust_env=True)) as c:
                    async with c.get(f'{SEARCH_API_LINK}/api/v1/sites') as res:
                        data = await res.json()
              
