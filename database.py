"""
database.py
SQLite database setup — characters and rooms.
"""
import sqlite3, json, os, time

# Use /tmp on read-only filesystems (Render free tier)
# or override with DB_PATH env variable for persistent storage
_default_db = "/tmp/guesswhoindia.db"
DB_PATH = os.environ.get("DB_PATH", _default_db)

# ── Default character seed data ────────────────────────────────────────────────
DEFAULT_CHARS = [
    {"id":0,  "name":"Aarav Shah",      "gender":"male",   "hair":"black", "hair_style":"short",  "eyes":"brown", "glasses":False,"hat":False,"facial_hair":False,"expression":"smiling","skin":"fair",  "age":"young", "skin_hex":"#f5cba7","photo":""},
    {"id":1,  "name":"Priya Nair",      "gender":"female", "hair":"black", "hair_style":"long",   "eyes":"brown", "glasses":False,"hat":False,"facial_hair":False,"expression":"smiling","skin":"wheat", "age":"young", "skin_hex":"#d4956a","photo":""},
    {"id":2,  "name":"Rajesh Iyer",     "gender":"male",   "hair":"black", "hair_style":"short",  "eyes":"dark",  "glasses":True, "hat":False,"facial_hair":True, "expression":"neutral","skin":"medium","age":"middle","skin_hex":"#b5724a","photo":""},
    {"id":3,  "name":"Meena Pillai",    "gender":"female", "hair":"grey",  "hair_style":"short",  "eyes":"brown", "glasses":True, "hat":False,"facial_hair":False,"expression":"smiling","skin":"medium","age":"senior","skin_hex":"#b5724a","photo":""},
    {"id":4,  "name":"Vikram Rao",      "gender":"male",   "hair":"black", "hair_style":"short",  "eyes":"dark",  "glasses":False,"hat":False,"facial_hair":True, "expression":"serious","skin":"dark",  "age":"middle","skin_hex":"#8b4513","photo":""},
    {"id":5,  "name":"Sunita Devi",     "gender":"female", "hair":"black", "hair_style":"long",   "eyes":"dark",  "glasses":False,"hat":True, "facial_hair":False,"expression":"smiling","skin":"dark",  "age":"middle","skin_hex":"#8b4513","photo":""},
    {"id":6,  "name":"Amir Mustafa",    "gender":"male",   "hair":"brown", "hair_style":"curly",  "eyes":"brown", "glasses":True, "hat":False,"facial_hair":False,"expression":"smiling","skin":"wheat", "age":"young", "skin_hex":"#d4956a","photo":""},
    {"id":7,  "name":"Lakshmi Reddy",   "gender":"female", "hair":"black", "hair_style":"long",   "eyes":"brown", "glasses":False,"hat":False,"facial_hair":False,"expression":"neutral","skin":"deep",  "age":"young", "skin_hex":"#5c3317","photo":""},
    {"id":8,  "name":"Arjun Sharma",    "gender":"male",   "hair":"black", "hair_style":"short",  "eyes":"brown", "glasses":False,"hat":True, "facial_hair":False,"expression":"smiling","skin":"fair",  "age":"young", "skin_hex":"#f5cba7","photo":""},
    {"id":9,  "name":"Kavitha Menon",   "gender":"female", "hair":"brown", "hair_style":"curly",  "eyes":"light", "glasses":True, "hat":False,"facial_hair":False,"expression":"smiling","skin":"wheat", "age":"young", "skin_hex":"#d4956a","photo":""},
    {"id":10, "name":"Suresh Nayak",    "gender":"male",   "hair":"grey",  "hair_style":"short",  "eyes":"brown", "glasses":True, "hat":False,"facial_hair":True, "expression":"neutral","skin":"medium","age":"senior","skin_hex":"#b5724a","photo":""},
    {"id":11, "name":"Anjali Singh",    "gender":"female", "hair":"black", "hair_style":"long",   "eyes":"dark",  "glasses":False,"hat":False,"facial_hair":False,"expression":"serious","skin":"fair",  "age":"middle","skin_hex":"#f5cba7","photo":""},
    {"id":12, "name":"Deepak Gupta",    "gender":"male",   "hair":"black", "hair_style":"bald",   "eyes":"dark",  "glasses":False,"hat":False,"facial_hair":True, "expression":"neutral","skin":"dark",  "age":"middle","skin_hex":"#8b4513","photo":""},
    {"id":13, "name":"Radha Krishnan",  "gender":"female", "hair":"white", "hair_style":"long",   "eyes":"brown", "glasses":True, "hat":False,"facial_hair":False,"expression":"smiling","skin":"fair",  "age":"senior","skin_hex":"#f5cba7","photo":""},
    {"id":14, "name":"Mohan Das",       "gender":"male",   "hair":"white", "hair_style":"short",  "eyes":"brown", "glasses":True, "hat":False,"facial_hair":True, "expression":"neutral","skin":"deep",  "age":"senior","skin_hex":"#5c3317","photo":""},
    {"id":15, "name":"Pooja Verma",     "gender":"female", "hair":"black", "hair_style":"curly",  "eyes":"brown", "glasses":False,"hat":True, "facial_hair":False,"expression":"smiling","skin":"medium","age":"young", "skin_hex":"#b5724a","photo":""},
    {"id":16, "name":"Ravi Kumar",      "gender":"male",   "hair":"black", "hair_style":"short",  "eyes":"brown", "glasses":False,"hat":True, "facial_hair":False,"expression":"serious","skin":"deep",  "age":"young", "skin_hex":"#5c3317","photo":""},
    {"id":17, "name":"Nisha Agarwal",   "gender":"female", "hair":"brown", "hair_style":"short",  "eyes":"brown", "glasses":False,"hat":False,"facial_hair":False,"expression":"neutral","skin":"wheat", "age":"middle","skin_hex":"#d4956a","photo":""},
    {"id":18, "name":"Ganesh Murthy",   "gender":"male",   "hair":"grey",  "hair_style":"short",  "eyes":"dark",  "glasses":True, "hat":True, "facial_hair":False,"expression":"smiling","skin":"dark",  "age":"senior","skin_hex":"#8b4513","photo":""},
    {"id":19, "name":"Saraswati Bhat",  "gender":"female", "hair":"grey",  "hair_style":"long",   "eyes":"brown", "glasses":False,"hat":False,"facial_hair":False,"expression":"smiling","skin":"medium","age":"senior","skin_hex":"#b5724a","photo":""},
    {"id":20, "name":"Amit Chopra",     "gender":"male",   "hair":"black", "hair_style":"curly",  "eyes":"brown", "glasses":False,"hat":False,"facial_hair":True, "expression":"smiling","skin":"wheat", "age":"young", "skin_hex":"#d4956a","photo":""},
    {"id":21, "name":"Divya Joshi",     "gender":"female", "hair":"black", "hair_style":"long",   "eyes":"dark",  "glasses":True, "hat":False,"facial_hair":False,"expression":"serious","skin":"dark",  "age":"young", "skin_hex":"#8b4513","photo":""},
    {"id":22, "name":"Prakash Johnson", "gender":"male",   "hair":"black", "hair_style":"bald",   "eyes":"brown", "glasses":False,"hat":False,"facial_hair":False,"expression":"serious","skin":"medium","age":"middle","skin_hex":"#b5724a","photo":""},
    {"id":23, "name":"Uma Shankar",     "gender":"female", "hair":"black", "hair_style":"short",  "eyes":"brown", "glasses":False,"hat":False,"facial_hair":False,"expression":"neutral","skin":"deep",  "age":"middle","skin_hex":"#5c3317","photo":""},
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and seed characters if they don't exist."""
    conn = get_conn()
    c = conn.cursor()

    # Characters table
    c.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id          INTEGER PRIMARY KEY,
            name        TEXT    NOT NULL,
            gender      TEXT    NOT NULL,
            hair        TEXT    NOT NULL,
            hair_style  TEXT    NOT NULL,
            eyes        TEXT    NOT NULL,
            glasses     INTEGER NOT NULL DEFAULT 0,
            hat         INTEGER NOT NULL DEFAULT 0,
            facial_hair INTEGER NOT NULL DEFAULT 0,
            expression  TEXT    NOT NULL,
            skin        TEXT    NOT NULL,
            age         TEXT    NOT NULL,
            skin_hex    TEXT    NOT NULL,
            photo       TEXT    NOT NULL DEFAULT ''
        )
    """)

    # Seed if empty
    c.execute("SELECT COUNT(*) FROM characters")
    if c.fetchone()[0] == 0:
        for ch in DEFAULT_CHARS:
            c.execute("""
                INSERT INTO characters
                (id,name,gender,hair,hair_style,eyes,glasses,hat,facial_hair,
                 expression,skin,age,skin_hex,photo)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                ch["id"], ch["name"], ch["gender"], ch["hair"], ch["hair_style"],
                ch["eyes"], int(ch["glasses"]), int(ch["hat"]), int(ch["facial_hair"]),
                ch["expression"], ch["skin"], ch["age"], ch["skin_hex"], ch["photo"]
            ))

    # Rooms table — full game state stored as JSON blob
    c.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            code        TEXT PRIMARY KEY,
            state       TEXT NOT NULL,
            updated_at  REAL NOT NULL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ── Character helpers ──────────────────────────────────────────────────────────

def get_all_characters():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM characters ORDER BY id").fetchall()
    conn.close()
    chars = []
    for r in rows:
        c = dict(r)
        c["id"] = int(c["id"]) if c["id"] is not None else 0
        chars.append(c)
    return chars


def get_character(char_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM characters WHERE id=?", (char_id,)).fetchone()
    conn.close()
    if not row:
        return None
    c = dict(row)
    c["id"] = int(c["id"]) if c["id"] is not None else char_id
    return c


def update_character(char_id: int, fields: dict):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [char_id]
    conn = get_conn()
    conn.execute(f"UPDATE characters SET {cols} WHERE id=?", vals)
    conn.commit()
    conn.close()


# ── Room helpers ───────────────────────────────────────────────────────────────

def save_room(code: str, state: dict):
    conn = get_conn()
    now = time.time()
    conn.execute("""
        INSERT INTO rooms (code, state, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            state=excluded.state,
            updated_at=excluded.updated_at
    """, (code, json.dumps(state), now))
    conn.commit()
    conn.close()


def load_room(code: str):
    conn = get_conn()
    row = conn.execute("SELECT state FROM rooms WHERE code=?", (code,)).fetchone()
    conn.close()
    return json.loads(row["state"]) if row else None


def delete_room(code: str):
    conn = get_conn()
    conn.execute("DELETE FROM rooms WHERE code=?", (code,))
    conn.commit()
    conn.close()


def cleanup_old_rooms(max_age_hours: int = 6):
    """Remove rooms older than max_age_hours to keep the DB small."""
    conn = get_conn()
    import time as _time
    conn.execute(
        "DELETE FROM rooms WHERE updated_at < ?",
        (_time.time() - max_age_hours * 3600,)
    )
    conn.commit()
    conn.close()