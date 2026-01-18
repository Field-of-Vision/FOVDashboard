# websockets_manager.py
from typing import Dict, Optional
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

class WebSocketManager:
    # Track sockets AND per-socket context (stadium / admin)
    clients: Dict[WebSocket, Dict[str, object]] = {}  # {ws: {"stadium": Optional[str], "is_admin": bool}}

    @classmethod
    async def connect(cls, websocket: WebSocket, stadium: Optional[str], is_admin: bool):
        await websocket.accept()
        cls.clients[websocket] = {"stadium": stadium, "is_admin": is_admin}

    @classmethod
    async def disconnect(cls, websocket: WebSocket):
        cls.clients.pop(websocket, None)

    @classmethod
    async def notify_clients(cls, topic: str, message: dict, stadium: Optional[str] = None):
        """Broadcast only to admin OR sockets whose ctx.stadium matches the event stadium."""
        safe_message = jsonable_encoder(message)
        to_drop = []
        for ws, ctx in list(cls.clients.items()):
            try:
                if ctx.get("is_admin") or (stadium is not None and ctx.get("stadium") == stadium):
                    await ws.send_json({"topic": topic, "message": safe_message})
            except Exception as e:
                print(f"WS send failed; dropping client: {e}")
                to_drop.append(ws)
        for ws in to_drop:
            await cls.disconnect(ws)

    @classmethod
    async def websocket_endpoint(cls, websocket: WebSocket, stadium: Optional[str], is_admin: bool):
        """Optional helper if you want the manager to host an endpoint itself."""
        await cls.connect(websocket, stadium=stadium, is_admin=is_admin)
        try:
            while True:
                # keepalive / ignore incoming
                await websocket.receive_text()
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            await cls.disconnect(websocket)
