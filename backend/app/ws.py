import uuid
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from app.db import db
from app.utils import now_utc


class WSConnectionManager:
    """Gerçek zamanlı bildirim için WebSocket bağlantı yöneticisi."""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, hotel_id: str, websocket: WebSocket):
        await websocket.accept()
        if hotel_id not in self.active_connections:
            self.active_connections[hotel_id] = []
        self.active_connections[hotel_id].append(websocket)

    def disconnect(self, hotel_id: str, websocket: WebSocket):
        if hotel_id in self.active_connections:
            try:
                self.active_connections[hotel_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[hotel_id]:
                del self.active_connections[hotel_id]

    async def send_to_hotel(self, hotel_id: str, message: dict):
        """Belirli otele gerçek zamanlı bildirim gönder."""
        if hotel_id in self.active_connections:
            dead = []
            for ws in self.active_connections[hotel_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                try:
                    self.active_connections[hotel_id].remove(ws)
                except ValueError:
                    pass

    async def broadcast(self, message: dict):
        for hotel_id in list(self.active_connections.keys()):
            await self.send_to_hotel(hotel_id, message)

    def get_online_count(self) -> int:
        return sum(len(conns) for conns in self.active_connections.values())

    def get_online_hotels(self) -> List[str]:
        return list(self.active_connections.keys())


ws_manager = WSConnectionManager()


async def create_notification(hotel_id: str, ntype: str, title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    doc = {
        "_id": str(uuid.uuid4()),
        "hotel_id": hotel_id,
        "type": ntype,
        "title": title,
        "message": message,
        "is_read": False,
        "metadata": metadata or {},
        "created_at": now_utc(),
    }
    await db.notifications.insert_one(doc)

    try:
        ws_payload = {
            "type": "notification",
            "data": {
                "id": doc["_id"],
                "type": ntype,
                "title": title,
                "message": message,
                "is_read": False,
                "metadata": metadata or {},
                "created_at": doc["created_at"].isoformat(),
            }
        }
        await ws_manager.send_to_hotel(hotel_id, ws_payload)
    except Exception:
        pass

    return doc["_id"]
