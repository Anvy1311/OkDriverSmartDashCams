import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ...database import SessionLocal
from ...dependencies import get_current_user, get_websocket_token
from ...models import User
from ...realtime import realtime
from ...security import decode_access_token

router = APIRouter(tags=["Real-time"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = get_websocket_token(websocket)
    payload = decode_access_token(token or "")
    if not payload:
        await websocket.close(code=1008, reason="Authentication required")
        return
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == payload.get("sub"), User.is_active.is_(True)))
    if not user:
        await websocket.close(code=1008, reason="User is not active")
        return
    await realtime.connect(websocket)
    await websocket.send_json({"type": "connected", "user": user.username, "role": user.role})
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=25)
                if message == "ping":
                    await websocket.send_json({"type": "pong", "at": datetime.now(timezone.utc).isoformat()})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat", "at": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        pass
    finally:
        await realtime.disconnect(websocket)


@router.get("/api/v1/realtime/stream")
async def sse_stream(_user: User = Depends(get_current_user)) -> StreamingResponse:
    async def event_generator():
        queue = await realtime.subscribe()
        try:
            yield "event: ready\ndata: connected\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"event: {payload.get('type', 'message')}\ndata: {json.dumps(payload, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await realtime.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
