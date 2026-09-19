"""Settings read from Streamlit secrets (.streamlit/secrets.toml or Streamlit Cloud)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import streamlit as st

DEFAULT_SUBJECTS = {"Maths": 2, "Science": 2, "Geography": 2}


@dataclass
class Settings:
    backend: str = "drive"                 # "drive" (Google Drive) or "local" (testing)
    root_folder: str = "Homework Tracker"  # folder the app creates in your Google Drive
    local_dir: str = "local_data"
    timezone: str = "Asia/Colombo"
    deadline: time = time(18, 15)
    son_name: str = "Son"
    parent_name: str = "Parent"
    subjects: dict = field(default_factory=lambda: dict(DEFAULT_SUBJECTS))


def _section(name: str) -> dict:
    try:
        return dict(st.secrets.get(name, {}))
    except Exception:  # no secrets file at all
        return {}


def _parse_time(text: str, fallback: time) -> time:
    try:
        h, m = str(text).split(":")
        return time(int(h), int(m))
    except Exception:
        return fallback


def load_settings() -> Settings:
    app = _section("app")
    s = Settings()
    s.backend = app.get("backend", s.backend)
    s.root_folder = app.get("root_folder", s.root_folder)
    s.local_dir = app.get("local_dir", s.local_dir)
    s.timezone = app.get("timezone", s.timezone)
    s.deadline = _parse_time(app.get("deadline", "18:15"), s.deadline)
    s.son_name = app.get("son_name", s.son_name)
    s.parent_name = app.get("parent_name", s.parent_name)
    subjects = _section("subjects")
    if subjects:
        s.subjects = {k: int(v) for k, v in subjects.items()}
    return s


def passwords() -> dict:
    """{'son': ..., 'parent': ...} — empty strings if not configured."""
    auth = _section("auth")
    return {"son": str(auth.get("son_password", "")), "parent": str(auth.get("parent_password", ""))}


def google_secrets() -> dict:
    return _section("google")
