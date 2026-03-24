"""WebSocket endpoint with JWT authentication."""

from fastapi import WebSocket, WebSocketDisconnect
from backend.api.auth.jwt_handler import verify_token


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # Require authentication before adding to active connections
        await websocket.send_json({"type": "auth_required"})
        try:
            auth_msg = await websocket.receive_json()
            if auth_msg.get("type") != "auth" or not auth_msg.get("token"):
                await websocket.close(code=4001, reason="Authentication required")
                return None

            payload = verify_token(auth_msg["token"])
            self.active_connections.append(websocket)
            await websocket.send_json({"type": "auth_success"})
            return payload
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return None

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()
