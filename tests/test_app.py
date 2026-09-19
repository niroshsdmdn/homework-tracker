import io
import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from hw import service as svc
from hw.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Colombo")


def jpeg(w=3000, h=2000) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), (200, 220, 255)).save(b, "JPEG")
    return b.getvalue()


def fields(**over):
    f = {"date": date(2026, 9, 21), "start": time(16, 0), "end": time(17, 30), "subject": "Maths",
         "lesson": "Lesson 5: Fractions", "examples": "5.1 to 5.4", "exercises": "", "revisions": "",
         "completed": False, "notes": ""}
    f.update(over)
    return f


def test_week_helpers():
    assert svc.week_start(date(2026, 9, 24)) == date(2026, 9, 21)
    assert svc.week_key(date(2026, 9, 21)) == "2026-W39"
    assert svc.fmt_time("18:15") == "6:15 pm"
    assert svc.minutes_between("16:00", "17:30") == 90


def test_validate():
    today = date(2026, 9, 21)
    assert svc.validate(fields(), 1, today) == []
    errs = svc.validate(fields(subject=None, lesson=" ", examples="", end=time(15, 0)), 0, today)
    assert len(errs) == 5


def test_create_on_time_and_late(tmp_path):
    st = LocalStorage(tmp_path)
    on_time = svc.create_submission(st, fields(), [jpeg(), jpeg()],
                                    datetime(2026, 9, 21, 17, 45, tzinfo=TZ), time(18, 15))
    late = svc.create_submission(st, fields(subject="Science"), [jpeg()],
                                 datetime(2026, 9, 21, 18, 30, tzinfo=TZ), time(18, 15))
    assert not on_time["late"] and late["late"]
    img = Image.open(io.BytesIO(st.get_photo(on_time["photos"][0])))
    assert max(img.size) == 1800  # resized
    assert len(st.load_db()["submissions"]) == 2


def test_review_and_delete(tmp_path):
    st = LocalStorage(tmp_path)
    rec = svc.create_submission(st, fields(), [jpeg()], datetime(2026, 9, 21, 17, 0, tzinfo=TZ), time(18, 15))
    svc.review(st, rec["id"], "acknowledged", "Well done", datetime(2026, 9, 21, 20, 0, tzinfo=TZ))
    s = st.load_db()["submissions"][0]
    assert s["status"] == "acknowledged" and s["parent_comment"] == "Well done"
    svc.delete_submission(st, rec["id"])
    assert st.load_db()["submissions"] == []
    assert not list((tmp_path / "photos").rglob("*.jpg"))


def test_progress(tmp_path):
    st = LocalStorage(tmp_path)
    for d, subj, done in [(21, "Maths", False), (22, "Maths", True), (23, "Science", False)]:
        svc.create_submission(st, fields(date=date(2026, 9, d), subject=subj, completed=done), [jpeg(100, 100)],
                              datetime(2026, 9, d, 17, 0, tzinfo=TZ), time(18, 15))
    p = svc.subject_progress(st.load_db()["submissions"], date(2026, 9, 25),
                             {"Maths": 2, "Science": 2, "Geography": 2})
    assert len(p["Maths"]["days"]) == 2 and p["Maths"]["completed"]
    assert len(p["Science"]["days"]) == 1 and not p["Science"]["completed"]
    assert p["Geography"]["days"] == []


# ---------------- whole app ----------------
def app(tmp_path, role=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.secrets["app"] = {"backend": "local", "local_dir": str(tmp_path), "son_name": "Kavin", "parent_name": "Dad"}
    at.secrets["auth"] = {"son_password": "s1", "parent_password": "p1"}
    if role:
        at.session_state["role"] = role
    return at


def test_sign_in(tmp_path):
    at = app(tmp_path).run()
    at.text_input[0].input("wrong")
    at.button[0].click().run()
    assert at.error and "role" not in at.session_state
    at.radio[0].set_value("Dad")
    at.text_input[0].input("p1")
    at.button[0].click().run()
    assert at.session_state["role"] == "parent"
    assert not at.exception


def test_son_validation_message(tmp_path):
    at = app(tmp_path, "son").run()
    assert not at.exception
    submit = [b for b in at.button if b.label == "Upload work"][0]
    submit.click().run()
    assert any("Choose the subject" in e.value for e in at.error)


def test_parent_acknowledges_and_son_sees_it(tmp_path):
    st = LocalStorage(tmp_path)
    now = datetime.now(TZ)
    rec = svc.create_submission(st, fields(date=now.date(), subject="Geography"), [jpeg(400, 300)], now, time(23, 59))

    at = app(tmp_path, "parent").run()
    assert not at.exception
    assert "To acknowledge (1)" in [t.label for t in at.tabs]
    at.text_input(key=f"todo_c_{rec['id']}").input("Good work!")
    at.button(key=f"todo_a_{rec['id']}").click().run()
    assert not at.exception
    saved = st.load_db()["submissions"][0]
    assert saved["status"] == "acknowledged" and saved["parent_comment"] == "Good work!"

    son = app(tmp_path, "son").run()
    assert not son.exception
    md = " ".join(m.value for m in son.markdown)
    assert "Acknowledged" in md
    assert any("Good work!" in i.value for i in son.info)


def test_parent_redo(tmp_path):
    st = LocalStorage(tmp_path)
    now = datetime.now(TZ)
    rec = svc.create_submission(st, fields(date=now.date()), [jpeg(400, 300)], now, time(23, 59))
    at = app(tmp_path, "parent").run()
    at.button(key=f"todo_r_{rec['id']}").click().run()
    assert st.load_db()["submissions"][0]["status"] == "redo"
    son = app(tmp_path, "son").run()
    assert any("need redoing" in e.value for e in son.error)
