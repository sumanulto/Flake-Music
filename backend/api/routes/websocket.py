from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.api.websocket.manager import manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/{guild_id}")
async def websocket_endpoint(websocket: WebSocket, guild_id: str):
    # TODO: Add authentication! Verify token from query param usually.
    # For MVP, we might skip strict token check on WS or pass it blindly? 
    # Better to verify.
    # token = websocket.query_params.get("token")
    
    await manager.connect(websocket, guild_id)
    try:
        while True:
            # Keep alive, or handle client messages if needed
            data = await websocket.receive_text()
            # await manager.broadcast(guild_id, f"Client says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, guild_id)
