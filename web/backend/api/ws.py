"""WebSocket endpoint: live trade tape broadcaster.

Clients connect to /ws/tape and receive real-time paper fill broadcasts.
The broadcast_tape() coroutine lives in state.py so any router (broker,
execution) can push fills to all connected clients via state.broadcast_tape().
"""
import asyncio
from fastapi import APIRouter, WebSocket
from .. import state

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/tape")
async def ws_tape(websocket: WebSocket):
    await websocket.accept()
    state.TAPE_CLIENTS.append(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except Exception:
        if websocket in state.TAPE_CLIENTS:
            state.TAPE_CLIENTS.remove(websocket)
