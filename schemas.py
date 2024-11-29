from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_moderator: bool
    is_active: bool

    class Config:
        orm_mode = True

class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    timestamp: datetime
    sender_id: int
    channel_id: int

    class Config:
        orm_mode = True

class ChannelBase(BaseModel):
    name: str

class ChannelCreate(ChannelBase):
    pass

class Channel(ChannelBase):
    id: int
    is_private: bool

    class Config:
        orm_mode = True
