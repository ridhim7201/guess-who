"""
game.py
All game logic — room creation, turn flow, question answering, guessing.
The room state dict is the single source of truth, persisted to SQLite.
"""
import random, string, time
from typing import Optional


# ── Room code generation ───────────────────────────────────────────────────────

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I, O (look like 1, 0)


def gen_code() -> str:
    return "".join(random.choices(ALPHABET, k=4))


# ── Default player state ───────────────────────────────────────────────────────

def empty_player(name: str) -> dict:
    return {
        "name":        name,
        "pick":        None,   # character id they picked as their secret
        "lives":       2,
        "questions":   [],     # [{text, val, answer}]
        "eliminated":  [],     # character ids the player eliminated
        "lockedGuess": None,   # character id locked as final guess candidate
    }


# ── Room factory ───────────────────────────────────────────────────────────────

def create_room(code: str, mode: str, p1_name: str, all_chars: list) -> dict:
    room = {
        "code":     code,
        "mode":     mode,       # "2p" | "ai"
        "status":   "waiting",  # waiting | picking | playing | abandoned
        "p1":       empty_player(p1_name),
        "p2":       empty_player("AI" if mode == "ai" else ""),
        "turn":     "p1",
        "pendingQ": None,       # {text, val, asker} | None
        "gameOver": False,
        "winner":   None,
        "createdAt": time.time(),
    }
    if mode == "ai":
        # AI picks a random character immediately
        room["p2"]["pick"] = random.choice(all_chars)["id"]
        room["status"] = "picking"
    return room


# ── Question definitions ───────────────────────────────────────────────────────

QUESTIONS = [
    {"val": "gender|male",       "label": "Is it a man?"},
    {"val": "gender|female",     "label": "Is it a woman?"},
    {"val": "hair|black",        "label": "Do they have black hair?"},
    {"val": "hair|brown",        "label": "Do they have brown hair?"},
    {"val": "hair|grey",         "label": "Do they have grey hair?"},
    {"val": "hair|white",        "label": "Do they have white hair?"},
    {"val": "hair_style|long",   "label": "Do they have long hair?"},
    {"val": "hair_style|short",  "label": "Do they have short hair?"},
    {"val": "hair_style|curly",  "label": "Do they have curly hair?"},
    {"val": "hair_style|bald",   "label": "Are they bald?"},
    {"val": "eyes|brown",        "label": "Do they have brown eyes?"},
    {"val": "eyes|dark",         "label": "Do they have dark eyes?"},
    {"val": "eyes|light",        "label": "Do they have light eyes?"},
    {"val": "glasses|true",      "label": "Do they wear glasses?"},
    {"val": "hat|true",          "label": "Do they wear a hat?"},
    {"val": "facial_hair|true",  "label": "Do they have facial hair?"},
    {"val": "expression|smiling","label": "Are they smiling?"},
    {"val": "expression|neutral","label": "Do they look neutral?"},
    {"val": "expression|serious","label": "Do they look serious?"},
    {"val": "skin|fair",         "label": "Do they have fair skin?"},
    {"val": "skin|wheat",        "label": "Do they have wheatish skin?"},
    {"val": "skin|medium",       "label": "Do they have medium brown skin?"},
    {"val": "skin|dark",         "label": "Do they have dark brown skin?"},
    {"val": "skin|deep",         "label": "Do they have deep dark skin?"},
    {"val": "age|young",         "label": "Are they young (20s–30s)?"},
    {"val": "age|middle",        "label": "Are they middle-aged?"},
    {"val": "age|senior",        "label": "Are they a senior?"},
]

# AI asks these in priority order (most discriminating first)
AI_Q_ORDER = [
    "gender|male", "glasses|true", "hat|true", "facial_hair|true",
    "hair_style|long", "hair_style|bald", "hair_style|curly",
    "skin|fair", "skin|deep", "skin|dark", "skin|wheat",
    "age|senior", "age|young", "hair|black", "hair|grey", "hair|white",
    "expression|smiling", "expression|serious", "eyes|light", "gender|female",
]


def eval_trait(char: dict, val: str) -> bool:
    """Check if a character matches a trait|value string."""
    trait, value = val.split("|", 1)
    if trait in ("glasses", "hat", "facial_hair"):
        return bool(char[trait]) == (value == "true")
    return str(char[trait]) == value


def fuzzy_match_question(text: str) -> Optional[dict]:
    """Match free-text input to a known question definition."""
    t = text.lower().strip().rstrip("?")
    # Exact label match
    for q in QUESTIONS:
        if q["label"].lower().rstrip("?") == t:
            return q
    # Keyword match — all meaningful words must appear
    for q in QUESTIONS:
        kw = [w for w in q["label"].lower().rstrip("?").split() if len(w) > 3]
        if kw and all(w in t for w in kw):
            return q
    return None


# ── Turn actions ───────────────────────────────────────────────────────────────

class GameError(Exception):
    pass


def player_confirm_pick(room: dict, role: str, char_id: int) -> dict:
    """Player confirms their secret character pick."""
    room[role]["pick"] = char_id
    opp = "p2" if role == "p1" else "p1"
    if room[opp]["pick"] is not None:
        room["status"] = "playing"
    return room


def player_ask_question(room: dict, role: str, text: str) -> dict:
    """
    Player asks a question.
    Stores pendingQ — the opponent must answer it next.
    This does NOT change R.turn yet (turn changes after answer).
    """
    if room["gameOver"]:
        raise GameError("Game is over.")
    if room["turn"] != role:
        raise GameError("It is not your turn.")
    if room["pendingQ"]:
        raise GameError("Waiting for previous question to be answered.")

    q = fuzzy_match_question(text)
    if not q:
        raise GameError("Question not recognised. Try a suggestion from the list.")

    already = room[role]["questions"]
    if any(existing["text"] == q["label"] for existing in already):
        raise GameError("You already asked that question.")

    room["pendingQ"] = {"text": q["label"], "val": q["val"], "asker": role}
    return room


def player_answer_question(room: dict, role: str, answer: bool, all_chars: list) -> dict:
    """
    Opponent answers the pending question.
    Turn passes to the answerer (strict alternation).
    """
    if not room["pendingQ"]:
        raise GameError("No pending question to answer.")

    pq = room["pendingQ"]
    if pq["asker"] == role:
        raise GameError("You cannot answer your own question.")

    asker = pq["asker"]
    room[asker]["questions"].append({
        "text":   pq["text"],
        "val":    pq["val"],
        "answer": answer,
    })
    room["pendingQ"] = None
    # Turn passes to the answerer — strict alternation
    room["turn"] = role
    return room


def player_submit_guess(room: dict, role: str, all_chars: list) -> dict:
    """
    Player submits their locked guess as a final answer.
    Correct = win. Wrong = lose a life, turn passes.
    """
    if room["gameOver"]:
        raise GameError("Game is over.")
    if room["turn"] != role:
        raise GameError("It is not your turn.")

    me = room[role]
    opp_key = "p2" if role == "p1" else "p1"
    opp = room[opp_key]

    if me["lockedGuess"] is None:
        raise GameError("Lock a character first before guessing.")

    correct = me["lockedGuess"] == opp["pick"]
    if correct:
        room["gameOver"] = True
        room["winner"] = role
    else:
        me["lives"] -= 1
        me["lockedGuess"] = None
        if me["lives"] <= 0:
            room["gameOver"] = True
            room["winner"] = opp_key
        else:
            # Wrong guess — turn passes to opponent
            room["turn"] = opp_key

    return room


# ── AI logic ───────────────────────────────────────────────────────────────────

def ai_auto_answer(room: dict, all_chars: list) -> dict:
    """AI answers a question the human asked about AI's secret character."""
    pq = room["pendingQ"]
    if not pq or pq["asker"] != "p1":
        return room

    ai_char = next((c for c in all_chars if c["id"] == room["p2"]["pick"]), None)
    if not ai_char:
        return room

    answer = eval_trait(ai_char, pq["val"])
    room["p1"]["questions"].append({"text": pq["text"], "val": pq["val"], "answer": answer})
    room["pendingQ"] = None
    # AI answered → now AI's turn to ask
    room["turn"] = "p2"
    return room


def ai_choose_question(room: dict, all_chars: list) -> Optional[dict]:
    """
    AI picks its next question using priority list + candidate filtering.
    Returns the matched question dict, or None if AI should guess.
    """
    ai = room["p2"]
    asked_vals = {q["val"] for q in ai["questions"]}
    untried = [v for v in AI_Q_ORDER if v not in asked_vals]

    # Filter remaining candidates by AI's question history
    remaining = [c for c in all_chars if c["id"] != ai["pick"]]
    for q in ai["questions"]:
        remaining = [c for c in remaining if eval_trait(c, q["val"]) == q["answer"]]

    if len(remaining) <= 1 or not untried:
        return None  # signal to guess

    next_val = untried[0]
    return next((q for q in QUESTIONS if q["val"] == next_val), None)


def ai_get_guess(room: dict, all_chars: list) -> Optional[int]:
    """Return the character ID the AI wants to guess."""
    ai = room["p2"]
    remaining = [c for c in all_chars if c["id"] != ai["pick"]]
    for q in ai["questions"]:
        remaining = [c for c in remaining if eval_trait(c, q["val"]) == q["answer"]]
    return remaining[0]["id"] if remaining else None


def ai_submit_guess(room: dict, all_chars: list) -> dict:
    """AI makes its final guess."""
    guess_id = ai_get_guess(room, all_chars)
    if guess_id is None:
        return room

    room["p2"]["lockedGuess"] = guess_id
    correct = guess_id == room["p1"]["pick"]

    if correct:
        room["gameOver"] = True
        room["winner"] = "p2"
    else:
        room["p2"]["lives"] -= 1
        room["p2"]["lockedGuess"] = None
        if room["p2"]["lives"] <= 0:
            room["gameOver"] = True
            room["winner"] = "p1"
        else:
            room["turn"] = "p1"

    return room
