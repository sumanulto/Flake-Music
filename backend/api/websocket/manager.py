from fastapi import WebSocket
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Map guild_id to list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, guild_id: str):
        await websocket.accept()
        if guild_id not in self.active_connections:
            self.active_connections[guild_id] = []
        self.active_connections[guild_id].append(websocket)
        logger.info(f"WebSocket connected for Guild {guild_id}")

    def disconnect(self, websocket: WebSocket, guild_id: str):
        if guild_id in self.active_connections:
            if websocket in self.active_connections[guild_id]:
                self.active_connections[guild_id].remove(websocket)
            if not self.active_connections[guild_id]:
                del self.active_connections[guild_id]
        logger.info(f"WebSocket disconnected for Guild {guild_id}")

    async def broadcast(self, guild_id: str, message: dict):
        if guild_id in self.active_connections:
            to_remove = []
            for connection in self.active_connections[guild_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send WS message: {e}")
                    to_remove.append(connection)
            
            for conn in to_remove:
                self.disconnect(conn, guild_id)

manager = ConnectionManager()
