"""Connect (or reconnect) the Homework Tracker to your Google Drive.

It reads client_id and client_secret from .streamlit/secrets.toml, opens the
Google sign-in page, and writes the new refresh_token back into the same file.
No client_secret.json file is needed, so the three values always match.

Run from the project folder:
    python tools\\refresh_drive_login.py
"""
import re
import shutil
import sys
import tomllib
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / ".streamlit" / "secrets.toml"


def set_token(text: str, token: str) -> str:
    """Replace (or add) refresh_token inside the [google] section only."""
    head = re.search(r"^\[google\]\s*$", text, flags=re.M)
    if not head:
        return text.rstrip() + f'\n\n[google]\nrefresh_token = "{token}"\n'
    nxt = re.search(r"^\[", text[head.end():], flags=re.M)
    end = head.end() + nxt.start() if nxt else len(text)
    section = text[head.end():end]
    line = f'refresh_token = "{token}"'
    new_section, n = re.subn(r"^[ \t]*refresh_token[ \t]*=.*$", lambda m: line, section, count=1, flags=re.M)
    if n == 0:
        new_section = "\n" + line + section
    return text[:head.end()] + new_section + text[end:]


def main() -> None:
    if not SECRETS.exists():
        sys.exit(f"Can't find {SECRETS}. Run this from the project folder after creating secrets.toml.")
    text = SECRETS.read_text(encoding="utf-8")
    try:
        google = tomllib.loads(text).get("google", {})
    except Exception as e:
        sys.exit(f"secrets.toml has a mistake, fix it first: {e}")

    cid = str(google.get("client_id", "")).strip()
    csec = str(google.get("client_secret", "")).strip()
    if not cid.endswith(".apps.googleusercontent.com") or "...." in cid:
        sys.exit("client_id in secrets.toml is missing or still the example value.")
    if not csec.startswith("GOCSPX-"):
        sys.exit("client_secret in secrets.toml is missing or doesn't start with GOCSPX-.")

    print(f"Using client ID:     {cid}")
    print(f"Using client secret: {csec[:10]}... ({len(csec)} characters)")
    print("A browser window will open. Sign in with the Google account that should store the homework.\n")

    from google_auth_oauthlib.flow import InstalledAppFlow

    config = {"installed": {
        "client_id": cid,
        "client_secret": csec,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("Google didn't return a refresh token. Run the script again.")

    shutil.copy(SECRETS, SECRETS.with_name("secrets.toml.bak"))
    SECRETS.write_text(set_token(text, creds.refresh_token), encoding="utf-8")
    tomllib.loads(SECRETS.read_text(encoding="utf-8"))  # make sure the file is still valid
    print("\nDone. The new refresh_token is saved in .streamlit\\secrets.toml")
    print("(A copy of the old file is in .streamlit\\secrets.toml.bak)")
    print("Now start the app:  streamlit run app.py")


if __name__ == "__main__":
    main()
