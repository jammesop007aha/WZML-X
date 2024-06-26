import asyncio
from typing import Any, Dict, Final

import aiofiles
from aiofiles.os import path as aiopath, makedirs
from aiofiles import open as aiopen
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from dotenv import dotenv_values

import bot
from bot import LOGGER

class DbManager:
    DATABASE_URL: Final = bot.DATABASE_URL
    bot_id: str
    config_dict: dict
    aria2_options: dict
    qbit_options: dict
    user_data: dict[str, dict] = {}
    rss_dict: dict[str, dict] = {}

    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.__err = False
        self.__db = None
        self.__connect()

    async def __connect(self):
        try:
            self.__conn = await AsyncIOMotorClient(self.DATABASE_URL).connect()
            self.__db = self.__conn["wzmlx"]
        except PyMongoError as e:
            self.handle_exception(e)
            self.__err = True

    def handle_exception(self, e: Exception) -> None:
        LOGGER.error(f"Error: {e}")

    async def db_load(self) -> None:
        if self.__err:
            return

        await self.__load_settings()
        await self.__load_users()
        await self.__load_rss()

    async def __load_settings(self) -> None:
        settings_collection = self.__db.settings

        settings = {
            "_id": self.bot_id,
            "config_dict": self.config_dict,
            "aria2_options": self.aria2_options,
            "qbit_options": self.qbit_options,
        }

        await settings_collection.update_one(
            {"_id": self.bot_id}, {"$set": settings}, upsert=True
        )

    async def __load_users(self) -> None:
        users_collection = self.__db.users

        async for row in users_collection.find({"_id": self.bot_id}):
            user_data = {k: v for k, v in row.items() if k != "_id"}
            thumb_path = f'Thumbnails/{row["_id"]}.jpg'
            rclone_path = f'rclone/{row["_id"]}.conf'

            if "thumb" in user_data:
                if not await aiopath.exists("Thumbnails"):
                    await makedirs("Thumbnails", exist_ok=True)

                async with aiopen(thumb_path, "wb+") as f:
                    await f.write(user_data["thumb"])

                user_data["thumb"] = thumb_path

            if "rclone" in user_data:
                if not await aiopath.exists("rclone"):
                    await makedirs("rclone", exist_ok=True)

                async with aiopen(rclone_path, "wb+") as f:
                    await f.write(user_data["rclone"])

                user_data["rclone"] = rclone_path

            self.user_data[row["_id"]] = user_data
            self.log_debug(f"Loaded user data for user_id={row['_id']}")

        self.log_success("Users data has been imported from Database")

    async def __load_rss(self) -> None:
        rss_collection = self.__db.rss

        async for row in rss_collection.find({"_id": self.bot_id}):
            self.rss_dict[row["_id"]] = {k: v for k, v in row.items() if k != "_id"}

        self.log_success("Rss data has been imported from Database.")

    async def update_deploy_config(self) -> None:
        if self.__err:
            return

        current_config = dict(dotenv_values("config.env"))
        await self.__db.settings.deployConfig.replace_one(
            {"_id": self.bot_id}, current_config, upsert=True
        )

    async def update_config(self, dict_: dict[str, Any]) -> None:
        if self.__err:
            return

        await self.__db.settings.config.update_one({"_id": self.bot_id}, {"$set": dict_}, upsert=True)

    async def update_aria2(self, key: str, value: Any) -> None:
        if self.__err:
            return

        await self.__db.settings.aria2c.update_one(
            {"_id": self.bot_id}, {"$set": {key: value}}, upsert=True
        )

    async def update_qbittorrent(self, key: str, value: Any) -> None:
        if self.__err:
            return

        await self.__db.settings.qbittorrent.update_one(
            {"_id": self.bot_id}, {"$set": {key: value}}, upsert=True
        )

    async def update_private_file(self, path: str) -> None:
        if self.__err:
            return

        if await aiopath.exists(path):
            async with aiopen(path, "rb+") as pf:
                pf_bin = await pf.read()
        else:
            pf_bin = b""

        path = path.replace(".", "__")
        await self.__db.settings.files.update_one(
            {"_id": self.bot_id}, {"$set": {path: pf_bin}}, upsert=True
        )

        if path == "config.env":
            await self.update_deploy_config()

    async def update_user_data(self, user_id: str) -> None:
        if self.__err:
            return

        data = self.user_data[user_id]
        del data["thumb"]
        del data["rclone"]

        await self.__db.users.update_one(
            {"_id": user_id}, {"$set": data}, upsert=True
        )

    async def update_user_doc(self, user_id: str, key: str, path: str = "") -> None:
        if self.__err:
            return

        if path:
            async with aiopen(path, "rb") as doc:
                doc_bin = await doc.read()
        else:
            doc_bin = b""

        await self.__db.users.update_one(
            {"_id": user_id}, {"$set": {key: doc_bin}}, upsert=True
        )

    async def get_pm_uids(self) -> list[str]:
        if self.__err:
            return []

        return [doc["_id"] async for doc in self.__db.pm_users.find({"_id": self.bot_id})]

    async def update_pm_users(self, user_id: str) -> None:
        if self.__err:
            return

        if not bool(await self.__db.pm_users.find_one({"_id": user_id})):
            await self.__db.pm_users.insert_one({"_id": user_id})
            self.log_info(f"New PM User Added : {user_id}")

    async def rm_pm_user(self, user_id: str) -> None:
        if self.__err:
            return

        await self.__db.pm_users.delete_one({"_id": user_id})

    async def rss_update_all(self) -> None:
        if self.__err:
            return

        for user_id in list(self.rss_dict.keys()):
            await self.__db.rss.update_one(
                {"_id": user_id}, {"$set": self.rss_dict[user_id]}, upsert=True
            )

    async def rss_update(self, user_id: str) -> None:
        if self.__err:
            return

        await self.__db.rss.update_one(
            {"_id": user_id}, {"$set": self.rss_dict[user_id]}, upsert=True
        )

    async def rss_delete(self, user_id: str) -> None:
        if self.__err:
            return

        await self.__db.rss.delete_one({"_id": user_id})

    async def add_incomplete_task(self, cid: str, link: str, tag: str, msg_link: str, msg: str) -> None:
        if self.__err:
            return

        await self.__db.tasks.insert_one(
            {"_id": link, "cid": cid, "tag": tag, "source": msg_link, "org_msg": msg}
        )

    async def rm_complete_task(self, link: str) -> None:
        if self.__err:
            return

        await self.__db.tasks.delete_one({"_id": link})

    async def get_incomplete_tasks(self) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        notifier_dict = {}

        if self.__err:
            return notifier_dict

        if await self.__db.tasks.find_one():
            rows = self.__db.tasks.find({})
            async for row in rows:
                if row["cid"] in list(notifier_dict.keys()):
                    if row["tag"] in list(notifier_dict[row["cid"]]):
                        notifier_dict[row["cid"]][row["tag"]].append(
                            {row["_id"]: row["source"]}
                        )
                    else:
                        notifier_dict[row["cid"]][row["tag"]] = [
                            {row["_id"]: row["source"]}
                        ]
                else:
                    notifier_dict[row["cid"]] = {row["tag"]: [{row["_id"]: row["source"]}]}

        await self.__db.tasks.drop()

        return notifier_dict

    async def trunc_table(self, name: str) -> None:
        if self.__err:
            return

        await self.__db[name].drop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.shutdown()

    async def shutdown(self) -> None:
        if self.__conn:
            await self.__conn.close()

if DbManager.DATABASE_URL:
    async with DbManager(bot.bot_id) as db:
        await db.db_load()
