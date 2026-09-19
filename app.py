"""Homework Tracker: daily homework photos from son, acknowledged by parent."""
from __future__ import annotations

import hmac
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from hw import service as svc
from hw.config import google_secrets, load_settings, passwords
from hw.storage import DriveStorage, LocalStorage

st.set_page_config(page_title="Homework Tracker", page_icon="📚", layout="centered")

S = load_settings()
TZ = ZoneInfo(S.timezone)
CACHE_KEY = f"{S.backend}|{S.local_dir}|{S.root_folder}"
DEADLINE_TXT = svc.fmt_time(S.deadline)


def now() -> datetime:
    return datetime.now(TZ)


# ------------------------------------------------------------------ storage
def get_storage():
    if "storage" not in st.session_state:
        if S.backend == "local":
            st.session_state.storage = LocalStorage(S.local_dir)
        else:
            g = google_secrets()
            missing = [k for k in ("client_id", "client_secret", "refresh_token") if not g.get(k)]
            if missing:
                st.error("Google Drive isn't set up yet. Add these to the [google] section of the "
                         f"app's secrets: {', '.join(missing)}. See README step 3.")
                st.stop()
            try:
                st.session_state.storage = DriveStorage(
                    g["client_id"], g["client_secret"], g["refresh_token"], S.root_folder)
            except Exception as e:
                msg = str(e)
                if "invalid_grant" in msg:
                    st.error("Google refused the saved Drive login (the refresh token expired or was "
                             "revoked). Run tools/get_refresh_token.py again and paste the new token "
                             "into the app's secrets. See README step 3.")
                else:
                    st.error(f"Couldn't connect to Google Drive: {msg}")
                st.stop()
    return st.session_state.storage


@st.cache_data(ttl=30, show_spinner=False)
def _load_db(_storage, cache_key: str) -> dict:
    return _storage.load_db()


@st.cache_data(max_entries=150, show_spinner=False)
def _photo(_storage, photo_id: str, cache_key: str) -> bytes:
    return _storage.get_photo(photo_id)


def load_subs() -> list[dict]:
    return _load_db(get_storage(), CACHE_KEY)["submissions"]


def after_change(message: str, kind: str = "success") -> None:
    _load_db.clear()
    st.session_state.flash = (kind, message)
    st.rerun()


def show_flash() -> None:
    if "flash" in st.session_state:
        kind, msg = st.session_state.pop("flash")
        getattr(st, kind)(msg)


# ------------------------------------------------------------------ sign in
def sign_in() -> None:
    st.title("📚 Homework Tracker")
    pw = passwords()
    if not pw["son"] or not pw["parent"]:
        st.error("Passwords aren't set. Add son_password and parent_password to the [auth] "
                 "section of the app's secrets.")
        st.stop()
    with st.form("sign_in"):
        who = st.radio("Who is signing in?", [S.son_name, S.parent_name], horizontal=True)
        typed = st.text_input("Password", type="password")
        go = st.form_submit_button("Sign in", type="primary")
    if go:
        role = "son" if who == S.son_name else "parent"
        if hmac.compare_digest(typed.encode(), pw[role].encode()):
            st.session_state.role = role
            st.rerun()
        st.error("That password isn't right. Try again.")


# ------------------------------------------------------------------ pieces
def status_line(s: dict) -> str:
    when = ""
    if s.get("reviewed_at"):
        when = datetime.fromisoformat(s["reviewed_at"]).strftime(" on %d %b at %I:%M %p").replace(" 0", " ")
    return {
        "pending": ":orange[**⏳ Waiting for acknowledgement**]",
        "acknowledged": f":green[**✅ Acknowledged**]{when}",
        "redo": f":red[**🔁 Please redo or complete this**]{when}",
    }[s["status"]]


def card(s: dict, role: str, prefix: str, actions: bool = True) -> None:
    d = date.fromisoformat(s["date"])
    sub_at = datetime.fromisoformat(s["submitted_at"])
    mins = svc.minutes_between(s["start"], s["end"])
    uploaded = svc.fmt_time(sub_at.time())
    if sub_at.date() != d:
        uploaded += sub_at.strftime(" on %d %b")
    with st.container(border=True):
        st.markdown(f"#### {s['subject']}: {s['lesson']}")
        late = " :red[**Late**]" if s["late"] else " :green[On time]"
        st.markdown(f"{d:%A %d %B}, {svc.fmt_time(s['start'])} to {svc.fmt_time(s['end'])} "
                    f"({mins} min). Uploaded {uploaded}.{late}")
        lines = [f"- **{label}:** {s[k]}" for k, label in svc.WORK_TYPES.items() if s.get(k)]
        if s.get("completed"):
            lines.append("- **Finished the whole lesson**")
        st.markdown("\n".join(lines))
        if s.get("notes"):
            st.caption(f"Note from {S.son_name}: {s['notes']}")

        photos = s.get("photos", [])
        cols = st.columns(3)
        for i, pid in enumerate(photos):
            with cols[i % 3]:
                try:
                    st.image(_photo(get_storage(), pid, CACHE_KEY))
                except Exception:
                    st.caption("This photo couldn't be loaded.")
        if photos:
            st.caption("Hover or tap a photo and use the expand icon to see it full size.")

        st.markdown(status_line(s))
        if s.get("parent_comment"):
            st.info(s["parent_comment"], icon="💬")

        if not actions:
            return
        if role == "parent":
            comment = st.text_input("Comment for " + S.son_name + " (optional)",
                                    value=s.get("parent_comment", ""), key=f"{prefix}_c_{s['id']}")
            b1, b2 = st.columns(2)
            ack_label = "Acknowledge" if s["status"] != "acknowledged" else "Update acknowledgement"
            if b1.button(ack_label, key=f"{prefix}_a_{s['id']}", type="primary", width="stretch"):
                svc.review(get_storage(), s["id"], "acknowledged", comment, now())
                after_change(f"Acknowledged {s['subject']} for {d:%A %d %B}.")
            if b2.button("Ask to redo", key=f"{prefix}_r_{s['id']}", width="stretch"):
                svc.review(get_storage(), s["id"], "redo", comment, now())
                after_change(f"Asked {S.son_name} to redo {s['subject']} for {d:%A %d %B}.", "warning")
        elif s["status"] == "pending":
            with st.popover("Delete this upload"):
                st.write("This removes the upload and its photos. Use it if you uploaded by mistake.")
                if st.button("Delete upload", key=f"{prefix}_d_{s['id']}", type="primary"):
                    svc.delete_submission(get_storage(), s["id"])
                    after_change("Upload deleted.", "info")


def todays_status(subs: list[dict], today: date, role: str) -> None:
    todays = [s for s in subs if s["date"] == today.isoformat()]
    n, dl = now(), svc.deadline_at(today, S.deadline, TZ)
    who = "You have" if role == "son" else f"{S.son_name} has"
    if todays:
        subjects = ", ".join(sorted({s["subject"] for s in todays}))
        st.success(f"{who} uploaded {len(todays)} piece(s) of work today: {subjects}.")
    elif today.weekday() >= 5:
        st.info("It's the weekend, so there's no deadline today.")
    elif n < dl:
        left = int((dl - n).total_seconds() // 60)
        st.warning(f"Nothing uploaded yet today. Deadline {DEADLINE_TXT}, "
                   f"{left // 60} h {left % 60} min left.")
    else:
        extra = " Upload now; it will be marked late." if role == "son" else ""
        st.error(f"Nothing was uploaded by today's {DEADLINE_TXT} deadline.{extra}")


# ------------------------------------------------------------------ son
def upload_tab(subs: list[dict], today: date) -> None:
    todays_status(subs, today, "son")
    prog = svc.subject_progress(subs, today, S.subjects)
    started = [f"{k}: {', '.join(v['lessons'])}" for k, v in prog.items() if v["lessons"]]
    if started:
        st.caption("This week's lessons so far. " + "; ".join(started) + ".")

    n = st.session_state.setdefault("form_n", 0)
    with st.form(f"upload_{n}"):
        c1, c2, c3 = st.columns(3)
        d = c1.date_input("Date", value=today, max_value=today,
                          min_value=today - timedelta(days=14), format="DD/MM/YYYY")
        start = c2.time_input("Time started", value=time(16, 0), step=300)
        end = c3.time_input("Time finished", value=time(17, 0), step=300)
        subject = st.selectbox("Subject", list(S.subjects), index=None, placeholder="Choose a subject")
        lesson = st.text_input("Lesson", placeholder="e.g. Lesson 5: Fractions")
        st.markdown("**What did you do?** Fill in the ones you did today.")
        examples = st.text_input("Examples", placeholder="e.g. Examples 5.1 to 5.4")
        exercises = st.text_input("Exercises", placeholder="e.g. Exercise 5.2, questions 1 to 12")
        revisions = st.text_input("Revisions", placeholder="e.g. Revision exercise, page 58")
        completed = st.checkbox("I have now finished ALL the examples, exercises and revisions in this lesson")
        notes = st.text_area("Anything to tell your parent? (optional)", height=80)
        files = st.file_uploader("Photos of your work", accept_multiple_files=True,
                                 type=["jpg", "jpeg", "png", "webp", "heic", "heif"])
        go = st.form_submit_button("Upload work", type="primary", width="stretch")

    if not go:
        return
    fields = {"date": d, "start": start, "end": end, "subject": subject, "lesson": lesson,
              "examples": examples, "exercises": exercises, "revisions": revisions,
              "completed": completed, "notes": notes}
    errors = svc.validate(fields, len(files or []), today)
    if errors:
        st.error("Please fix these before uploading:\n\n" + "\n".join(f"- {e}" for e in errors))
        return
    try:
        with st.spinner(f"Uploading {len(files)} photo(s)…"):
            rec = svc.create_submission(get_storage(), fields, [f.getvalue() for f in files],
                                        now(), S.deadline)
    except Exception as e:
        st.error(f"Upload failed, nothing was saved. Try again. ({e})")
        return
    st.session_state.form_n = n + 1
    msg = f"Uploaded {rec['subject']}: {rec['lesson']}."
    if rec["late"]:
        msg += f" It was after {DEADLINE_TXT}, so it's marked late."
    after_change(msg, "warning" if rec["late"] else "success")


def son_page(subs: list[dict], today: date) -> None:
    redo = [s for s in subs if s["status"] == "redo"]
    t1, t2, t3 = st.tabs(["Upload work", "My uploads", "This week"])
    with t1:
        if redo:
            st.error(f"{len(redo)} upload(s) need redoing. See **My uploads**.")
        upload_tab(subs, today)
    with t2:
        if not subs:
            st.info("Your uploads will appear here, with your parent's acknowledgement.")
        for s in svc.sort_newest(subs)[:40]:
            card(s, "son", "mine")
    with t3:
        week_view(subs, today, "son")


# ------------------------------------------------------------------ both
def week_view(subs: list[dict], today: date, role: str) -> None:
    pick = st.date_input("Show the week containing", value=today, key=f"{role}_week", format="DD/MM/YYYY")
    ws = svc.week_start(pick)
    week = svc.in_week(subs, pick)
    st.markdown(f"#### Week of {svc.week_label(pick)}")

    rows = []
    for i in range(7):
        d = ws + timedelta(days=i)
        day = [s for s in week if s["date"] == d.isoformat()]
        if i >= 5 and not day:
            continue  # show weekend days only if work was done
        if day:
            on_time = "Late" if all(s["late"] for s in day) else "Yes"
        elif d < today or (d == today and now() > svc.deadline_at(d, S.deadline, TZ)):
            on_time = "No upload"
        else:
            on_time = ""
        rows.append({
            "Day": d.strftime("%a %d %b"),
            "Subjects": ", ".join(sorted({s["subject"] for s in day})),
            "Time": (f'{sum(max(svc.minutes_between(s["start"], s["end"]), 0) for s in day)} min'
                     if day else ""),
            "On time": on_time,
            "Acknowledged": f"{sum(s['status'] == 'acknowledged' for s in day)} of {len(day)}" if day else "",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    prog = svc.subject_progress(subs, pick, S.subjects)
    for name, p in prog.items():
        days, target = len(p["days"]), p["target"]
        frac = min(days / target, 1.0) if target else 1.0
        lessons = ", ".join(p["lessons"]) or "not started"
        done = "Lesson finished." if p["completed"] else "Lesson not finished yet."
        st.progress(frac, text=f"**{name}**: {days} of {target} days. Lesson: {lessons}. {done}")

    all_done = all(p["completed"] and len(p["days"]) >= p["target"] for p in prog.values())
    friday = svc.deadline_at(ws + timedelta(days=4), S.deadline, TZ)
    left = [k for k, p in prog.items() if not p["completed"]]
    if all_done:
        st.success("Every subject was finished this week.")
    elif now() > friday:
        st.error(f"Not finished by Friday: {', '.join(left) or 'day targets not met'}.")
    else:
        st.info(f"Still to finish by Friday: {', '.join(left) or 'more days needed'}.")

    if week:
        with st.expander(f"Uploads this week ({len(week)})"):
            for s in svc.sort_newest(week):
                card(s, role, f"{role}_wk", actions=(role == "parent"))


# ------------------------------------------------------------------ parent
def parent_page(subs: list[dict], today: date) -> None:
    pending = [s for s in svc.sort_newest(subs) if s["status"] == "pending"]
    t1, t2, t3, t4 = st.tabs([f"To acknowledge ({len(pending)})", "Today", "Week", "History"])
    with t1:
        if not pending:
            st.success("You're up to date. Nothing is waiting for acknowledgement.")
        for s in pending:
            card(s, "parent", "todo")
    with t2:
        todays_status(subs, today, "parent")
        for s in [s for s in svc.sort_newest(subs) if s["date"] == today.isoformat()]:
            card(s, "parent", "today")
    with t3:
        week_view(subs, today, "parent")
    with t4:
        history(subs)


def history(subs: list[dict]) -> None:
    if not subs:
        st.info("Nothing uploaded yet.")
        return
    chosen = st.multiselect("Subjects", list(S.subjects), default=list(S.subjects))
    shown = [s for s in svc.sort_newest(subs) if s["subject"] in chosen]
    weeks: dict[str, list] = {}
    for s in shown:
        weeks.setdefault(svc.week_key(date.fromisoformat(s["date"])), []).append(s)
    for i, (wk, items) in enumerate(weeks.items()):
        label = svc.week_label(date.fromisoformat(items[0]["date"]))
        with st.expander(f"{label} ({len(items)} uploads)", expanded=(i == 0)):
            for s in items:
                card(s, "parent", f"hist{i}")

    cols = ["date", "start", "end", "subject", "lesson", "examples", "exercises", "revisions",
            "completed", "late", "status", "parent_comment", "submitted_at", "notes"]
    csv = pd.DataFrame(svc.sort_newest(subs))[cols].to_csv(index=False).encode("utf-8")
    st.download_button("Download all records (CSV)", csv, "homework_records.csv", "text/csv")


# ------------------------------------------------------------------ main
def main() -> None:
    if "role" not in st.session_state:
        sign_in()
        return
    role = st.session_state.role
    name = S.son_name if role == "son" else S.parent_name
    with st.sidebar:
        st.markdown(f"Signed in as **{name}**")
        if st.button("Refresh", width="stretch"):
            _load_db.clear()
            st.rerun()
        if st.button("Sign out", width="stretch"):
            st.session_state.clear()
            st.rerun()

    st.markdown("## 📚 Homework Tracker")
    today = now().date()
    try:
        subs = load_subs()
    except Exception as e:
        st.error(f"Couldn't read the homework records from storage: {e}")
        st.stop()
    show_flash()
    if role == "son":
        son_page(subs, today)
    else:
        parent_page(subs, today)


main()
