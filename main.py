"""
main.py
FastAPI application — WebSocket real-time rooms, REST API, static files.

Run locally:
    uvicorn main:app --reload --port 8000

Deploy (Railway / Render / DigitalOcean):
    uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import asyncio, json, os, shutil, time, uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    HTTPException, UploadFile, File, Form, Request
)
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import database as db
import game as gm

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Guess Who? India")

BASE_DIR    = Path(__file__).parent
STATIC_DIR  = BASE_DIR / "static"
PHOTOS_DIR  = STATIC_DIR / "photos"
TMPL_DIR    = BASE_DIR / "templates"

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TMPL_DIR))

# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    db.init_db()
    # Periodically clean up old rooms
    asyncio.create_task(_room_cleanup_loop())


async def _room_cleanup_loop():
    while True:
        await asyncio.sleep(3600)   # every hour
        db.cleanup_old_rooms(max_age_hours=6)


# ── WebSocket room manager ─────────────────────────────────────────────────────

class RoomManager:
    """Tracks active WebSocket connections per room code."""

    def __init__(self):
        # code → {ws_id: WebSocket}
        self._rooms: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, code: str, ws: WebSocket) -> str:
        await ws.accept()
        ws_id = str(uuid.uuid4())
        self._rooms.setdefault(code, {})[ws_id] = ws
        return ws_id

    def disconnect(self, code: str, ws_id: str):
        if code in self._rooms:
            self._rooms[code].pop(ws_id, None)
            if not self._rooms[code]:
                del self._rooms[code]

    async def broadcast(self, code: str, payload: dict, exclude: Optional[str] = None):
        """Send payload to all connections in a room."""
        msg = json.dumps(payload)
        dead = []
        for ws_id, ws in list(self._rooms.get(code, {}).items()):
            if ws_id == exclude:
                continue
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws_id)
        for ws_id in dead:
            self.disconnect(code, ws_id)

    async def broadcast_all(self, code: str, payload: dict):
        await self.broadcast(code, payload, exclude=None)


manager = RoomManager()


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/{code}")
async def websocket_endpoint(ws: WebSocket, code: str):
    ws_id = await manager.connect(code, ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            await handle_ws_message(code, ws_id, ws, msg)
    except WebSocketDisconnect:
        manager.disconnect(code, ws_id)


async def handle_ws_message(code: str, ws_id: str, ws: WebSocket, msg: dict):
    """
    Process an incoming WebSocket message and broadcast updated state.
    All game actions go through here — the client sends an action,
    Python mutates the room state, and broadcasts the new state to all clients.
    """
    action  = msg.get("action")
    role    = msg.get("role")          # "p1" | "p2"
    chars   = db.get_all_characters()

    room = db.load_room(code)
    if not room and action != "create":
        await ws.send_text(json.dumps({"error": "Room not found"}))
        return

    try:
        # ── Actions ──────────────────────────────────────────────────────────

        if action == "create":
            # Room already created via REST; just send current state
            room = db.load_room(code)
            if not room:
                await ws.send_text(json.dumps({"error": "Room not found"}))
                return

        elif action == "join":
            if room["status"] != "waiting":
                await ws.send_text(json.dumps({"error": "Room already in progress"}))
                return
            room["p2"]["name"] = msg.get("name", "Player 2")
            room["status"] = "picking"
            db.save_room(code, room)

        elif action == "pick":
            char_id = int(msg["charId"])
            gm.player_confirm_pick(room, role, char_id)
            db.save_room(code, room)

        elif action == "ask":
            gm.player_ask_question(room, role, msg["text"])
            db.save_room(code, room)
            # vs AI: AI auto-answers then asks its own question
            if room["mode"] == "ai" and role == "p1":
                await manager.broadcast_all(code, {"type": "state", "room": room})
                await asyncio.sleep(0.8)
                gm.ai_auto_answer(room, chars)
                db.save_room(code, room)
                await manager.broadcast_all(code, {"type": "state", "room": room})
                await asyncio.sleep(1.1)
                q = gm.ai_choose_question(room, chars)
                if q:
                    room["pendingQ"] = {"text": q["label"], "val": q["val"], "asker": "p2"}
                else:
                    gm.ai_submit_guess(room, chars)
                db.save_room(code, room)

        elif action == "answer":
            answer = bool(msg["answer"])
            gm.player_answer_question(room, role, answer, chars)
            db.save_room(code, room)
            # vs AI: after human answers AI's question, AI already asked so nothing extra needed

        elif action == "lock":
            char_id = msg.get("charId")
            room[role]["lockedGuess"] = char_id  # None to unlock
            db.save_room(code, room)

        elif action == "eliminate":
            char_id = int(msg["charId"])
            elim = room[role]["eliminated"]
            if char_id not in elim:
                elim.append(char_id)
            if room[role]["lockedGuess"] == char_id:
                room[role]["lockedGuess"] = None
            db.save_room(code, room)

        elif action == "uneliminate":
            char_id = int(msg["charId"])
            room[role]["eliminated"] = [x for x in room[role]["eliminated"] if x != char_id]
            db.save_room(code, room)

        elif action == "guess":
            gm.player_submit_guess(room, role, chars)
            db.save_room(code, room)

        elif action == "leave":
            room["status"] = "abandoned"
            db.save_room(code, room)

        # Broadcast updated state to all clients in the room
        await manager.broadcast_all(code, {"type": "state", "room": room})

    except gm.GameError as e:
        await ws.send_text(json.dumps({"error": str(e)}))
    except Exception as e:
        await ws.send_text(json.dumps({"error": f"Server error: {e}"}))


# ── REST API ───────────────────────────────────────────────────────────────────

@app.post("/api/rooms")
async def api_create_room(request: Request):
    """Create a new room. Returns the room code."""
    body   = await request.json()
    mode   = body.get("mode", "2p")
    name   = body.get("name", "Player 1")
    chars  = db.get_all_characters()

    # Generate a unique code
    for _ in range(20):
        code = gm.gen_code()
        if not db.load_room(code):
            break

    room = gm.create_room(code, mode, name, chars)
    db.save_room(code, room)
    return {"code": code, "room": room}


@app.get("/api/rooms/{code}")
async def api_get_room(code: str):
    room = db.load_room(code)
    if not room:
        raise HTTPException(404, "Room not found")
    return room


@app.get("/api/characters")
async def api_get_characters():
    return db.get_all_characters()


@app.patch("/api/characters/{char_id}")
async def api_update_character(char_id: int, request: Request):
    """Update character name and/or traits."""
    body = await request.json()
    allowed = {"name","gender","hair","hair_style","eyes","glasses","hat",
               "facial_hair","expression","skin","age","skin_hex"}
    fields = {k: v for k, v in body.items() if k in allowed}
    if not fields:
        raise HTTPException(400, "No valid fields provided")
    db.update_character(char_id, fields)
    return db.get_character(char_id)


@app.post("/api/characters/{char_id}/photo")
async def api_upload_photo(char_id: int, file: UploadFile = File(...)):
    """Upload a photo for a character. Saved to static/photos/."""
    char = db.get_character(char_id)
    if not char:
        raise HTTPException(404, "Character not found")

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(400, "Only jpg, png, webp, gif allowed")

    filename  = f"char_{char_id}{ext}"
    dest_path = PHOTOS_DIR / filename

    # Delete old photo if different extension
    for old in PHOTOS_DIR.glob(f"char_{char_id}.*"):
        if old != dest_path:
            old.unlink(missing_ok=True)

    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    photo_url = f"/static/photos/{filename}"
    db.update_character(char_id, {"photo": photo_url})
    return {"photo": photo_url}


@app.delete("/api/characters/{char_id}/photo")
async def api_delete_photo(char_id: int):
    """Remove a character's photo (revert to SVG avatar)."""
    char = db.get_character(char_id)
    if not char:
        raise HTTPException(404, "Character not found")
    for f in PHOTOS_DIR.glob(f"char_{char_id}.*"):
        f.unlink(missing_ok=True)
    db.update_character(char_id, {"photo": ""})
    return {"photo": ""}


# ── Page routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def game_page(request: Request):
    return templates.TemplateResponse("game.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    characters = db.get_all_characters()
    questions  = gm.QUESTIONS
    return templates.TemplateResponse("admin.html", {
        "request":    request,
        "characters": characters,
        "questions":  questions,
    })
