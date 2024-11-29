from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import List
from . import schemas, auth, database
import uvicorn

app = FastAPI()

database.init_db()

@app.post("/users/", response_model=schemas.User)
def register_user(user: schemas.UserCreate):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    # Проверка на уникальность имени пользователя
    cursor.execute("SELECT * FROM users WHERE username = ?", (user.username,))
    existing_user = cursor.fetchone()
    if existing_user:
        conn.close()
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    hashed_password = auth.get_password_hash(user.password)
    cursor.execute(
        "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
        (user.username, hashed_password)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return schemas.User(
        id=user_id,
        username=user.username,
        is_moderator=False,
        is_active=True
    )

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = auth.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Некорректный логин или пароль")
    access_token = auth.create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: dict = Depends(auth.get_current_active_user)):
    return schemas.User(
        id=current_user["id"],
        username=current_user["username"],
        is_moderator=bool(current_user["is_moderator"]),
        is_active=bool(current_user["is_active"])
    )

@app.post("/channels/", response_model=schemas.Channel)
def create_channel(channel: schemas.ChannelCreate, current_user: dict = Depends(auth.get_current_active_user)):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    # Проверка на уникальность названия канала
    cursor.execute("SELECT * FROM channels WHERE name = ?", (channel.name,))
    existing_channel = cursor.fetchone()
    if existing_channel:
        conn.close()
        raise HTTPException(status_code=400, detail="Канал с таким названием уже существует")

    cursor.execute(
        "INSERT INTO channels (name) VALUES (?)",
        (channel.name,)
    )
    conn.commit()
    channel_id = cursor.lastrowid
    conn.close()
    return schemas.Channel(
        id=channel_id,
        name=channel.name,
        is_private=True
    )

@app.get("/channels/{channel_id}/messages/", response_model=List[schemas.Message])
def get_channel_messages(channel_id: int, current_user: dict = Depends(auth.get_current_active_user)):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE channel_id = ? ORDER BY timestamp", (channel_id,))
    messages = cursor.fetchall()
    conn.close()
    return [
        schemas.Message(
            id=msg["id"],
            content=msg["content"],
            timestamp=msg["timestamp"],
            sender_id=msg["sender_id"],
            channel_id=msg["channel_id"]
        ) for msg in messages
    ]

@app.post("/channels/{channel_id}/messages/", response_model=schemas.Message)
def send_message(channel_id: int, message: schemas.MessageCreate, current_user: dict = Depends(auth.get_current_active_user)):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (content, sender_id, channel_id) VALUES (?, ?, ?)",
        (message.content, current_user["id"], channel_id)
    )
    conn.commit()
    message_id = cursor.lastrowid
    cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
    msg = cursor.fetchone()
    conn.close()
    return schemas.Message(
        id=msg["id"],
        content=msg["content"],
        timestamp=msg["timestamp"],
        sender_id=msg["sender_id"],
        channel_id=msg["channel_id"]
    )

# WebSocket для реального времени
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = defaultdict(list)

    async def connect(self, websocket: WebSocket, channel_id: int):
        await websocket.accept()
        self.active_connections[channel_id].append(websocket)

    def disconnect(self, websocket: WebSocket, channel_id: int):
        self.active_connections[channel_id].remove(websocket)

    async def broadcast(self, message: str, channel_id: int):
        for connection in self.active_connections[channel_id]:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{channel_id}")
async def websocket_endpoint(websocket: WebSocket, channel_id: int):
    await manager.connect(websocket, channel_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{data}", channel_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
