"""Homework rules: weeks, deadlines, saving uploads and acknowledgements."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta

from .images import prepare_photo
from .storage import Storage

WORK_TYPES = {"examples": "Examples", "exercises": "Exercises", "revisions": "Revisions"}
STATUS = {"pending": "Waiting for acknowledgement", "acknowledged": "Acknowledged", "redo": "Please redo"}


# ---------- dates ----------
def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_label(d: date) -> str:
    ws = week_start(d)
    return f"{ws:%d %b} to {ws + timedelta(days=4):%d %b %Y}"


def deadline_at(d: date, deadline: time, tz) -> datetime:
    return datetime.combine(d, deadline, tzinfo=tz)


def fmt_time(t: str | time) -> str:
    if isinstance(t, str):
        t = time.fromisoformat(t)
    return t.strftime("%I:%M %p").lstrip("0").lower()


def minutes_between(start: str, end: str) -> int:
    s, e = time.fromisoformat(start), time.fromisoformat(end)
    return (e.hour * 60 + e.minute) - (s.hour * 60 + s.minute)


# ---------- validation ----------
def validate(fields: dict, photo_count: int, today: date) -> list[str]:
    errors = []
    if not fields.get("subject"):
        errors.append("Choose the subject.")
    if not fields.get("lesson", "").strip():
        errors.append("Write the lesson name or number.")
    if not any(fields.get(k, "").strip() for k in WORK_TYPES):
        errors.append("Fill in at least one of Examples, Exercises or Revisions.")
    if fields.get("start") and fields.get("end") and fields["end"] <= fields["start"]:
        errors.append("The finish time must be after the start time.")
    if fields.get("date") and fields["date"] > today:
        errors.append("The date can't be in the future.")
    if photo_count == 0:
        errors.append("Add at least one photo of your work.")
    return errors


# ---------- changes ----------
def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:30] or "work"


def create_submission(storage: Storage, fields: dict, photos: list[bytes], now: datetime,
                      deadline: time) -> dict:
    """Save photos and a new record. fields: date(date), start/end(time), subject, lesson,
    examples, exercises, revisions, completed(bool), notes."""
    d: date = fields["date"]
    sid = uuid.uuid4().hex[:10]
    folder = week_key(d)
    photo_ids = []
    for i, raw in enumerate(photos, start=1):
        name = f"{d.isoformat()}_{_safe(fields['subject'])}_{sid}_{i}.jpg"
        photo_ids.append(storage.put_photo(prepare_photo(raw), name, folder))

    record = {
        "id": sid,
        "date": d.isoformat(),
        "start": fields["start"].strftime("%H:%M"),
        "end": fields["end"].strftime("%H:%M"),
        "subject": fields["subject"],
        "lesson": fields["lesson"].strip(),
        "examples": fields.get("examples", "").strip(),
        "exercises": fields.get("exercises", "").strip(),
        "revisions": fields.get("revisions", "").strip(),
        "completed": bool(fields.get("completed")),
        "notes": fields.get("notes", "").strip(),
        "photos": photo_ids,
        "submitted_at": now.isoformat(timespec="seconds"),
        "late": now > deadline_at(d, deadline, now.tzinfo),
        "status": "pending",
        "parent_comment": "",
        "reviewed_at": None,
    }
    storage.update(lambda db: db["submissions"].append(record))
    return record


def review(storage: Storage, sid: str, status: str, comment: str, now: datetime) -> None:
    assert status in ("acknowledged", "redo")

    def change(db):
        for s in db["submissions"]:
            if s["id"] == sid:
                s["status"] = status
                s["parent_comment"] = comment.strip()
                s["reviewed_at"] = now.isoformat(timespec="seconds")

    storage.update(change)


def delete_submission(storage: Storage, sid: str) -> None:
    removed = []

    def change(db):
        keep = []
        for s in db["submissions"]:
            (removed if s["id"] == sid else keep).append(s)
        db["submissions"] = keep

    storage.update(change)
    for s in removed:
        for pid in s.get("photos", []):
            try:
                storage.delete_photo(pid)
            except Exception:
                pass


# ---------- summaries ----------
def sort_newest(subs: list[dict]) -> list[dict]:
    return sorted(subs, key=lambda s: (s["date"], s["submitted_at"]), reverse=True)


def in_week(subs: list[dict], d: date) -> list[dict]:
    ws = week_start(d)
    we = ws + timedelta(days=6)
    return [s for s in subs if ws.isoformat() <= s["date"] <= we.isoformat()]


def subject_progress(subs: list[dict], d: date, subjects: dict) -> dict:
    """For the week containing d: per subject, the days worked, target, lessons, completed."""
    week = in_week(subs, d)
    out = {}
    for name, target in subjects.items():
        mine = [s for s in week if s["subject"] == name]
        lessons = []
        for s in sorted(mine, key=lambda s: s["date"]):
            if s["lesson"] not in lessons:
                lessons.append(s["lesson"])
        out[name] = {
            "days": sorted({s["date"] for s in mine}),
            "target": target,
            "lessons": lessons,
            "completed": any(s["completed"] for s in mine),
            "minutes": sum(max(minutes_between(s["start"], s["end"]), 0) for s in mine),
        }
    return out
