import secrets
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from database import get_connection

router = APIRouter()

# In-memory token store: token -> user dict
active_sessions: dict[str, dict] = {}


# ── Dependency: extract current user from Authorization header ─────────────────
def get_current_user(authorization: str = Header(...)) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    user  = active_sessions.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized — please log in again.")
    return user


# ── Request schema ─────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/login")
def login(req: LoginRequest):
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, email FROM users WHERE username = %s AND password = %s",
        (req.username, req.password)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = secrets.token_hex(32)
    active_sessions[token] = user

    return {
        "token":    token,
        "user_id":  user["id"],
        "username": user["username"],
        "email":    user["email"]
    }


@router.post("/logout")
def logout(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    active_sessions.pop(token, None)
    return {"message": "Logged out successfully."}
