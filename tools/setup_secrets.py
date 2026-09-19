"""Create a fresh, correct .streamlit/secrets.toml for the Homework Tracker.

It asks a few questions, signs you in to Google, and writes the whole file for
you, so there is nothing to copy, paste or edit by hand.

Run from the project folder:
    python tools\\setup_secrets.py
"""
import json
import shutil
import sys
import tomllib
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / ".streamlit" / "secrets.toml"
GLOBAL = Path.home() / ".streamlit" / "secrets.toml"


def ask(question: str, default: str = "", check=None, error: str = "") -> str:
    while True:
        hint = f" [{default}]" if default else ""
        value = input(f"{question}{hint}: ").strip().strip('"').strip()
        value = value or default
        if value and (check is None or check(value)):
            return value
        print("   " + (error or "Please type a value."))


def q(value: str) -> str:
    return json.dumps(value)  # safe TOML string with quotes


def main() -> None:
    print("\nHomework Tracker setup. Press Enter to accept the value in [brackets].\n")
    son = ask("Your son's name", "Yuhas")
    parent = ask("Your name on the sign-in screen", "Dad")
    son_pw = ask(f"Password for {son}")
    parent_pw = ask(f"Password for {parent}", check=lambda v: v != son_pw,
                    error="Use a different password from your son's.")
    print("\nFrom Google Cloud > Google Auth Platform > Clients > your Desktop client:")
    cid = ask("Client ID", check=lambda v: v.endswith(".apps.googleusercontent.com") and "...." not in v,
              error="It should end with .apps.googleusercontent.com")
    csec = ask("Client secret", check=lambda v: v.startswith("GOCSPX-"),
               error="It should start with GOCSPX-")

    print("\nA browser window will open. Sign in with niroshsdmdn@gmail.com (or the account that")
    print("should store the homework), click Continue / Advanced > Go to Homework Tracker, allow Drive.\n")
    from google_auth_oauthlib.flow import InstalledAppFlow

    config = {"installed": {
        "client_id": cid, "client_secret": csec,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}
    creds = InstalledAppFlow.from_client_config(config, SCOPES).run_local_server(
        port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("Google didn't return a refresh token. Run the script again.")

    text = f"""[app]
backend = "drive"
root_folder = "Homework Tracker"
timezone = "Asia/Colombo"
deadline = "18:15"
son_name = {q(son)}
parent_name = {q(parent)}

[subjects]
Maths = 2
Science = 2
Geography = 2

[auth]
son_password = {q(son_pw)}
parent_password = {q(parent_pw)}

[google]
client_id = {q(cid)}
client_secret = {q(csec)}
refresh_token = {q(creds.refresh_token)}
"""
    tomllib.loads(text)  # double-check it is valid
    SECRETS.parent.mkdir(exist_ok=True)
    if SECRETS.exists():
        shutil.copy(SECRETS, SECRETS.with_name("secrets.toml.old"))
        print("Your previous file was saved as .streamlit\\secrets.toml.old")
    SECRETS.write_text(text, encoding="utf-8")
    print(f"\nDone. Wrote a fresh {SECRETS}")

    if GLOBAL.exists():
        try:
            tomllib.loads(GLOBAL.read_text(encoding="utf-8"))
            print(f"\nNote: you also have {GLOBAL}. Streamlit reads it too.")
        except Exception as e:
            print(f"\nPROBLEM: {GLOBAL} has an error ({e}).")
            print("Streamlit reads that file too, so rename it, e.g.:")
            print(f'   ren "{GLOBAL}" secrets.toml.unused')

    print("\nNext: stop any running app (Ctrl + C), then run:  streamlit run app.py")


if __name__ == "__main__":
    main()
