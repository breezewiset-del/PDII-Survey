# Deploy Survey App to Render

## 1. Prepare GitHub

1. Create a new GitHub repository.
2. Upload these files:
   - `survey_app.py`
   - `requirements.txt`
   - `render.yaml`
   - `DEPLOY_RENDER.md`
3. Commit and push to GitHub.

## 2. Create Render Web Service

1. Go to Render.
2. Click **New +**.
3. Choose **Web Service**.
4. Connect your GitHub repository.
5. Use these settings:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: python survey_app.py
Plan: Free
```

Render will provide the `PORT` automatically. The app is already configured to use it.

## 3. Open the Survey

After deploy finishes, Render gives a URL like:

```text
https://production-ii-kpp-survey.onrender.com
```

Share this URL or make it a QR code.

## 4. Admin

Open:

```text
https://your-render-url.onrender.com/admin
```

Login:

```text
User: UserAdM
Password: 1234
```

Download CSV:

```text
https://your-render-url.onrender.com/admin/export.csv
```

## Important Free Plan Notes

- Render Free services may sleep after inactivity, so first open can be slow.
- This prototype uses SQLite. On Render Free, local files can be lost on redeploy/restart.
- For real survey collection, export CSV often or move the database to PostgreSQL/Supabase.

