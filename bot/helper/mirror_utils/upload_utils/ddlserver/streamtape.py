#!/usr/bin/env python3
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles
import aiohttp
from aiohttp import ClientSession

# Allowed file extensions for upload
ALLOWED_EXTS = [
    ".avi",
    ".mkv",
    ".mpg",
    ".mpeg",
    ".vob",
    ".wmv",
    ".flv",
    ".mp4",
    ".mov",
    ".m4v",
    ".m2v",
    ".divx",
    ".3gp",
    ".webm",
    ".ogv",
    ".ogg",
    ".ts",
    ".ogm",
]

class Streamtape:
    def __init__(self, dluploader, login: str, key: str):
        """
        Initialize the Streamtape class with the required parameters.

        :param dluploader: An instance of the DownloadUploader class.
        :param login: The Streamtape account login.
        :param key: The Streamtape account key.
        """
        self.dluploader = dluploader
        self.__userLogin = login
        self.__passKey = key
        self.base_url = "https://api.streamtape.com"
        self.session = None

    async def __aenter__(self):
        """
        Asynchronous context manager enter method.

        :return: The Streamtape instance itself.
        """
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Asynchronous context manager exit method.

        :param exc_type: Exception type.
        :param exc: Exception instance.
        :param tb: Traceback object.
        """
        if self.session:
            await self.session.close()

    async def __get_acc_info(self) -> Optional[Dict]:
        """
        Get account information.

        :return: Account information as a dictionary or None if an error occurs.
        """
        url = f"{self.base_url}/account/info?login={self.__userLogin}&key={self.__passKey}"
        async with self.session.get(url) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError:
                return None
            data = await response.json()
            if data.get("status") == 200:
                return data.get("result")
        return None

    async def __get_upload_url(
        self, folder: Optional[str] = None, sha256: Optional[str] = None, httponly: bool = False
    ) -> Optional[Dict]:
        """
        Get upload URL.

        :param folder: Optional folder ID.
        :param sha256: Optional SHA256 hash.
        :param httponly: Optional HTTP-only flag.

        :return: Upload URL as a dictionary or None if an error occurs.
        """
        _url = f"{self.base_url}/file/ul?login={self.__userLogin}&key={self.__passKey}"
        if folder is not None:
            _url += f"&folder={folder}"
        if sha256 is not None:
            _url += f"&sha256={sha256}"
        if httponly:
            _url += "&httponly=true"

        async with self.session.get(_url) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError:
                return None
            data = await response.json()
            if data.get("status") == 200:
                return data.get("result")
        return None

    async def upload_file(
        self, file_path: Path, folder_id: Optional[str] = None, sha256: Optional[str] = None, httponly: bool = False
    ) -> Optional[str]:
        """
        Upload a file.

        :param file_path: Path to the file.
        :param folder_id: Optional folder ID.
        :param sha256: Optional SHA256 hash.
        :param httponly: Optional HTTP-only flag.

        :return: The Streamtape URL or a message if the file is skipped.
        """
        if file_path.suffix.lower() not in ALLOWED_EXTS:
            return f"Skipping '{file_path}' due to disallowed extension."

        file_name = file_path.name
        if not folder_id:
            genfolder = await self.create_folder(file_name.rsplit(".", 1)[0])
            if genfolder is None:
                return None
            folder_id = genfolder["folderid"]

        upload_info = await self.__get_upload_url(folder=folder_id, sha256=sha256, httponly=httponly)
        if upload_info is None:
            return None

        if hasattr(self.dluploader, "is_cancelled") and self.dluploader.is_cancelled:
            return

        self.dluploader.last_uploaded = 0
        async with aiofiles.open(file_path, mode="rb") as f:
            async with self.session.post(
                upload_info["url"], data=f, headers={"Content-Type": "application/octet-stream"}
            ) as response:
                try:
                    response.raise_for_status()
                except aiohttp.ClientResponseError:
                    return None
                file_id = (await response.json()).get("result")
                await self.rename(file_id, file_name)
                return f"https://streamtape.to/v/{file_id}"
        return None

    async def create_folder(self, name: str, parent: Optional[str] = None) -> Optional[Dict]:
        """
        Create a folder.

        :param name: Name of the folder.
        :param parent: Optional parent folder ID.

        :return: The folder information as a dictionary or None if an error occurs.
        """
        exfolders = [
            folder["name"] for folder in (await self.list_folder(folder=parent) or {"folders": []})["folders"]
        ]
        if name in exfolders:
            i = 1
            while f"{i} {name}" in exfolders:
                i += 1
            name = f"{i} {name}"

        url = f"{self.base_url}/file/createfolder?login={self.__userLogin}&key={self.__passKey}&name={name}"
        if parent is not None:
            url += f"&pid={parent}"

        async with self.session.post(url) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError:
                return None
            data = await response.json()
            if data.get("status") == 200:
                return data.get("result")
        return None

    async def rename(self, file_id: str, name: str) -> Optional[Dict]:
        """
        Rename a file.

        :param file_id: File ID.
        :param name: New file name.

        :return: The file information as a dictionary or None if an error occurs.
        """
        url = f"{self.base_url}/file/rename?login={self.__userLogin}&key={self.__passKey}&file={file_id}&name={name}"

        async with self.session.post(url) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError:
                return None
            data = await response.json()
            if data.get("status") == 200:
                return data.get("result")
        return None

    async def list_telegraph(
        self, folder_id: str, nested: bool = False
    ) -> Optional[str]:
        """
        Generate a Telegraph page with the folder content.

        :param folder_id: Folder ID.
        :param nested: Flag to include nested folders.

        :return: The Telegraph page URL or None if an error occurs.
        """
        tg_html = ""
        contents = await self.list_folder(folder_id)

        for fid in contents["folders"]:
            tg_html += f"<aside>╾──────────────────────╼</aside><br><aside><b>🗂 {fid['name']}</b></aside><br><aside>╾──────────────────────╼</aside><br>"
            if nested:
                tg_html += await self.list_telegraph(fid["id"], True)

        tg_html += "<ol>"
        for finfo in contents["files"]:
            tg_html += f"""<li> <code>{finfo['name']}</code><br>🔗 <a href="https://streamtape.to/v/{finfo['linkid']}">StreamTape URL</a><br> </li>"""
        tg_html += "</ol>"

        if nested:
            return tg_html

        tg_html = f"""<figure><img src='{config_dict["COVER_IMAGE"]}'></figure>""" + tg_html
        try:
            page = await telegraph.create_page(title=f"StreamTape X", content=tg_html)
            return f"https://te.legra.ph/{page['path']}"
        except Exception as e:
            print(f"Failed to create telegraph page: {e}")
            return None

    async def list_folder(self, folder: Optional[str] = None) -> Optional[Dict]:
        """
        Get folder content.

        :param folder: Optional folder ID.

        :return: The folder content as a dictionary or None if an error occurs.
        """
        url = f"{self.base_url}/file/listfolder?login={self.__userLogin}&key={self.__passKey}"
        if folder is not None:
            url += f"&folder={folder}"

        async with self.session.get(url) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError:
                return None
            data = await response.json()
            if data.get("status") == 200:
                return data.get("result")
        return None

    async def upload_folder(
        self, folder_path: Path, parent_folder_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload a folder.

        :param folder_path: Path to the folder.
        :param parent_folder_id: Optional parent folder ID.

        :return: The Telegraph page URL or None if an error occurs.
        """
        folder_name = folder_path.name
        genfolder = await self.create_folder(name=folder_name, parent=parent_folder_id)

        if genfolder and (newfid := genfolder.get("folderid")):
            for entry in folder_path.iterdir():
                if entry.is_file():
                    await self.upload_file(entry.path, newfid)
                    self.dluploader.total_files += 1
                elif entry.is_dir():
                    await self.upload_folder(entry.path, newfid)
                    self.dluploader.total_folders += 1
            return await self.list_telegraph(newfid)
        return None

    async def upload(self, file_path: Path) -> Optional[str]:
        """
        Upload a file or a folder.

        :param file_path: Path to the file or folder.

        :return: The Streamtape URL or None if an error occurs.
        """
        if os.path.isfile(file_path):
            return await self.upload_file(file_path)
        elif os.path.isdir(file_path):
            return await self.upload_folder(file_path)
        return None

    async def close(self):
        """
        Close the session.
        """
        if self.session:
            await self.session.close()

# Usage example:
async with Streamtape(dluploader, login, key) as streamtape:
    result = await streamtape.upload(path_to_file_or_folder)
    print(result)

