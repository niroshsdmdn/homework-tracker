"""Run ONCE on your own computer to let the app use your Google Drive.

1. Put the OAuth client file you downloaded from Google Cloud next to this script
   and name it client_secret.json.
2. pip install google-auth-oauthlib
3. python tools/get_refresh_token.py
4. A browser opens: sign in with the Google account whose Drive should hold the
   homework, and allow access.
5. Copy the [google] block it prints into your secrets.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
here = Path(__file__).resolve().parent
candidates = [here / "client_secret.json", Path.cwd() / "client_secret.json"]
secret_file = next((p for p in candidates if p.exists()), None)
if secret_file is None:
    raise SystemExit("client_secret.json not found. Put it in the tools folder or the current folder.")

flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
if not creds.refresh_token:
    raise SystemExit("Google did not return a refresh token. Run the script again.")

print("\nCopy everything between the lines into your secrets:\n" + "-" * 60)
print("[google]")
print(f'client_id = "{creds.client_id}"')
print(f'client_secret = "{creds.client_secret}"')
print(f'refresh_token = "{creds.refresh_token}"')
print("-" * 60)
print("Then delete client_secret.json from this folder, or at least never upload it to GitHub.")
