# Guess Who?

A real-time multiplayer guessing game built with **FastAPI + WebSockets + SQLite**.

## Project Structure

```
guesswhoindia/
├── main.py              ← FastAPI app, WebSocket, all routes
├── database.py          ← SQLite setup, character + room helpers
├── game.py              ← All game logic (turns, questions, AI, guessing)
├── requirements.txt
├── Procfile             ← For Railway / Render
├── runtime.txt          ← Python 3.11
├── static/
│   └── photos/          ← Uploaded character photos (auto-created)
└── templates/
    ├── game.html        ← Game UI (WebSocket client)
    └── admin.html       ← Character management page
```

## Pages

| URL | Description |
|-----|-------------|
| `/` | The game |
| `/admin` | Edit character names, traits, and upload photos |

## Run Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open:
- Game: http://localhost:8000
- Admin: http://localhost:8000/admin

## Deploy to Railway

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Select your repo
4. Railway auto-detects the Procfile and deploys
5. Done — Railway gives you a public URL

## Deploy to Render

1. Push to GitHub
2. Go to render.com → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Deploy

## Photo Storage Note

Photos are saved to `static/photos/` on disk. On Railway/Render the disk resets on redeploy. For permanent photo storage, either:
- Use a persistent disk (Railway Volumes, Render Disk — both free tier available)
- Or swap the upload logic in `main.py` to use an S3-compatible bucket (e.g. Cloudflare R2, free)

## Admin — Editing Characters

Go to `/admin` to:
- Upload a real photo for any character (jpg, png, webp)
- Edit their name, traits, and skin tone
- Remove a photo to revert to the SVG avatar

Changes are instant — no restart needed.
