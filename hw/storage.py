"""Where data lives.

DriveStorage  – your Google Drive (used online).
LocalStorage  – a folder on disk (for trying the app on your computer).

All records are in one file, homework_db.json. Photos are kept in weekly folders:
    Homework Tracker/homework_db.json
    Homework Tracker/photos/2026-W39/2026-09-21_Maths_ab12cd34_1.jpg
"""
from __future__ import annotations

import io
import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path

DB_NAME = "homework_db.json"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_LOCK = threading.Lock()


def empty_db() -> dict:
    return {"version": 1, "submissions": []}


class Storage(ABC):
    @abstractmethod
    def load_db(self) -> dict: ...

    @abstractmethod
    def save_db(self, db: dict) -> None: ...

    @abstractmethod
    def put_photo(self, data: bytes, name: str, folder: str) -> str: ...

    @abstractmethod
    def get_photo(self, photo_id: str) -> bytes: ...

    @abstractmethod
    def delete_photo(self, photo_id: str) -> None: ...

    def update(self, change) -> dict:
        """Read the latest records, apply change(db), save. Returns the saved records."""
        with _LOCK:
            db = self.load_db()
            change(db)
            self.save_db(db)
            return db


class LocalStorage(Storage):
    def __init__(self, root: str | Path):
        self.root = Path(root)
        (self.root / "photos").mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / DB_NAME

    def load_db(self) -> dict:
        if not self.db_path.exists():
            return empty_db()
        return json.loads(self.db_path.read_text(encoding="utf-8"))

    def save_db(self, db: dict) -> None:
        tmp = self.db_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.db_path)

    def put_photo(self, data: bytes, name: str, folder: str) -> str:
        d = self.root / "photos" / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(data)
        return f"{folder}/{name}"

    def get_photo(self, photo_id: str) -> bytes:
        return (self.root / "photos" / photo_id).read_bytes()

    def delete_photo(self, photo_id: str) -> None:
        p = self.root / "photos" / photo_id
        if p.exists():
            p.unlink()


class DriveStorage(Storage):
    """Stores everything in your own Google Drive using an OAuth refresh token.

    The drive.file permission means the app can only see files it created
    itself, never anything else in your Drive.
    """

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, root_folder: str):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._folders: dict[tuple, str] = {}
        self.root_id = self._folder(root_folder, None)
        self.photos_id = self._folder("photos", self.root_id)
        self._db_id: str | None = None

    @staticmethod
    def _q(text: str) -> str:
        return text.replace("\\", "\\\\").replace("'", "\\'")

    def _find(self, name: str, parent: str | None, mime: str | None = None) -> str | None:
        q = [f"name = '{self._q(name)}'", "trashed = false"]
        if parent:
            q.append(f"'{parent}' in parents")
        if mime:
            q.append(f"mimeType = '{mime}'")
        res = self.svc.files().list(
            q=" and ".join(q), spaces="drive", fields="files(id, name)",
            pageSize=5, orderBy="createdTime",
        ).execute(num_retries=3)
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def _folder(self, name: str, parent: str | None) -> str:
        key = (name, parent)
        if key not in self._folders:
            fid = self._find(name, parent, FOLDER_MIME)
            if not fid:
                body = {"name": name, "mimeType": FOLDER_MIME}
                if parent:
                    body["parents"] = [parent]
                fid = self.svc.files().create(body=body, fields="id").execute(num_retries=3)["id"]
            self._folders[key] = fid
        return self._folders[key]

    @staticmethod
    def _media(data: bytes, mime: str):
        from googleapiclient.http import MediaIoBaseUpload

        return MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)

    def load_db(self) -> dict:
        if self._db_id is None:
            self._db_id = self._find(DB_NAME, self.root_id)
        if self._db_id is None:
            return empty_db()
        raw = self.svc.files().get_media(fileId=self._db_id).execute(num_retries=3)
        return json.loads(raw.decode("utf-8"))

    def save_db(self, db: dict) -> None:
        media = self._media(json.dumps(db, indent=2, ensure_ascii=False).encode("utf-8"), "application/json")
        if self._db_id is None:
            self._db_id = self._find(DB_NAME, self.root_id)
        if self._db_id is None:
            self._db_id = self.svc.files().create(
                body={"name": DB_NAME, "parents": [self.root_id]}, media_body=media, fields="id",
            ).execute(num_retries=3)["id"]
        else:
            self.svc.files().update(fileId=self._db_id, media_body=media).execute(num_retries=3)

    def put_photo(self, data: bytes, name: str, folder: str) -> str:
        parent = self._folder(folder, self.photos_id)
        return self.svc.files().create(
            body={"name": name, "parents": [parent]},
            media_body=self._media(data, "image/jpeg"), fields="id",
        ).execute(num_retries=3)["id"]

    def get_photo(self, photo_id: str) -> bytes:
        return self.svc.files().get_media(fileId=photo_id).execute(num_retries=3)

    def delete_photo(self, photo_id: str) -> None:
        # Goes to Drive's Bin (recoverable for 30 days), not permanently deleted.
        self.svc.files().update(fileId=photo_id, body={"trashed": True}).execute(num_retries=3)
