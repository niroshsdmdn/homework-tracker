# 📚 Homework Tracker

Your son uploads photos of each day's homework by 6:15 pm with the date, start and finish
time, subject, lesson, and the examples, exercises and revisions he did. You see the work,
acknowledge it (or ask him to redo it) with a comment, and he sees your response.
Photos and records are saved in **your Google Drive**, in a folder named **Homework Tracker**.

**What your son sees:** today's deadline countdown, the upload form, his uploads with your
acknowledgement and comments, and the week's progress per subject.

**What you see:** a "To acknowledge" list, today's status (uploaded, not yet, or missed),
a week view (Mon–Fri uploads, on time or late, days per subject against target, whether each
lesson was finished by Friday), full history by week, and a CSV download of all records.

---

## Setup (about 30–40 minutes, once)

### 1. Google Cloud: allow the app to use your Drive
1. Go to <https://console.cloud.google.com> and sign in with the Google account whose Drive
   will store the homework (e.g. niroshsdmdn@gmail.com).
2. Top bar → project picker → **New project** → name it `homework-tracker` → **Create**, then select it.
3. **APIs & Services → Library** → search **Google Drive API** → **Enable**.
4. Menu → **Google Auth Platform** (called "OAuth consent screen" on older screens) → **Get started**:
   app name `Homework Tracker`, your email for support and contact, Audience **External** → **Create**.
5. **Audience** → **Publish app** → confirm. Status must say **In production**.
   In "Testing" mode Google logs the app out every 7 days. The app only asks for the
   `drive.file` permission (it can only see files it creates), so no Google review is needed.
6. **Clients** → **Create client** → Application type **Desktop app** → name `homework-tracker` →
   **Create** → **Download JSON**. Rename the file to `client_secret.json`.

### 2. Put the project on your computer
Unzip the project to a short path outside OneDrive, e.g. `D:\homework-tracker`
(long OneDrive paths cause Python install errors). In PowerShell:

```powershell
cd D:\homework-tracker
python -m venv C:\venvs\homework-tracker
C:\venvs\homework-tracker\Scripts\Activate.ps1
pip install -r requirements.txt google-auth-oauthlib
```

### 3. Get the Drive login (refresh token)
Copy `client_secret.json` into the `tools` folder, then:

```powershell
python tools\get_refresh_token.py
```

A browser opens. Choose your Google account. If you see **"Google hasn't verified this app"**,
click **Advanced → Go to Homework Tracker (unsafe)**; it's your own app. Tick the Drive
permission and **Continue**. The PowerShell window prints a `[google]` block. Keep it for step 4.

Then delete `tools\client_secret.json` (or keep it somewhere outside the project).

### 4. Create your secrets file
```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```
Fill in: your son's first name (`son_name`), two **different** passwords, and paste the three
`[google]` lines from step 3. Save. Check the name is `secrets.toml`, not `secrets.toml.txt`
(`dir .streamlit`).

Try it on your computer:
```powershell
streamlit run app.py
```
Sign in as your son, upload a test photo, then sign out and sign in as parent to acknowledge it.
Open Google Drive: you'll see the new **Homework Tracker** folder. Stop the app with **Ctrl + C**.
Delete the test upload from the son's **My uploads** tab if you like.

### 5. Put the code on GitHub
```powershell
git init
git add .
git status          # secrets.toml and client_secret.json must NOT be listed
git commit -m "Homework tracker"
git branch -M main
gh repo create homework-tracker --private --source . --push
```

### 6. Publish on Streamlit Community Cloud
1. <https://share.streamlit.io> → sign in with GitHub → **Create app** → **Deploy a public app from GitHub**.
2. Repository `niroshsdmdn/homework-tracker`, branch `main`, main file `app.py`.
   Choose an easy app URL, e.g. `kavin-homework`.
3. **Advanced settings** → Python **3.12** → in **Secrets**, paste the whole content of your
   `secrets.toml` → **Save** → **Deploy**.
4. When it opens, test sign-in as both son and parent.

### 7. On your son's phone
Open the app URL in Chrome (Android) or Safari (iPhone) → menu → **Add to Home screen**.
When he taps **Photos of your work**, the phone offers the camera or the gallery.

---

## Changing settings later
Edit the secrets in Streamlit Cloud (**app menu → Settings → Secrets**); the app restarts itself.
- `deadline = "18:15"`: daily deadline.
- `[subjects]`: subject names and the number of days each should take per week.
- Passwords: change either password any time.

## Good to know
- **Late uploads** are accepted but marked **Late** (after 6:15 pm on the date he chose).
  He can choose a date up to 14 days back, and those are marked late too.
- Your son can delete an upload only while it's still waiting for you. After you acknowledge
  it, it's locked.
- **Ask to redo** shows him a red notice; he then uploads the corrected work as a new upload.
- Deleted photos go to Drive's Bin (recoverable for 30 days).
- Don't rename or move the **Homework Tracker** folder in Drive; the app finds it by name and
  would create a new empty one.
- Free Streamlit apps go to sleep when nobody uses them for a while. If you see
  "This app has gone to sleep", tap **Yes, get this app back up** and wait about 30 seconds.
- Photos are resized to 1800 px before saving: clear enough to read handwriting, small enough to load fast.

## Troubleshooting
| Message | Fix |
|---|---|
| "Google refused the saved Drive login" | Run step 3 again, paste the new `refresh_token` into Streamlit secrets. Check the app is **In production** (step 1.5). |
| "Google Drive isn't set up yet" | The `[google]` block is missing or empty in Streamlit secrets. |
| "Passwords aren't set" | Add the `[auth]` block to the secrets. |
| `ModuleNotFoundError` on Streamlit Cloud | Make sure `requirements.txt` was pushed to GitHub, then **Reboot app**. |

## For testing without Google Drive
Set `backend = "local"` in `[app]`; data is saved to a `local_data` folder instead.
Run the automated checks with `pip install pytest` then `pytest`.
