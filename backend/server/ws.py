import asyncio
import json
import threading
import datetime
import websockets
from websockets.server import serve
from backend.core.logger import logger

class EventEmitter:
    def __init__(self):
        self.clients = set()
        self.loop = None
        self._thread = None
        self._message_callback = None

    def set_callback(self, callback):
        self._message_callback = callback

    def start_server(self, host="127.0.0.1", port=8765):
        logger.info(f"  [Module] WebSocket Server initializing on {host}:{port}")
        self._thread = threading.Thread(target=self._run_loop, args=(host, port), daemon=True)
        self._thread.start()

    def _run_loop(self, host, port):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        async def handler(websocket):
            self.clients.add(websocket)
            logger.info(f"[WebSocket] UI Client connected.")
            try:
                async for message in websocket:
                    logger.info(f"[WebSocket] Received: {message}")
                    if self._message_callback:
                        try:
                            data = json.loads(message)
                            # Call the message router (AgentLoop)
                            self._message_callback(data)
                        except Exception as ex:
                            logger.error(f"[WebSocket] Router Error: {ex}")
            except websockets.exceptions.ConnectionClosedError:
                pass
            finally:
                self.clients.remove(websocket)
                logger.info(f"[WebSocket] UI Client disconnected.")

        try:
            start_server = serve(handler, host, port)
            self.loop.run_until_complete(start_server)
            self.loop.run_forever()
        except OSError as e:
            logger.error(f"[WebSocket] Failed to bind to {host}:{port}. Another instance is likely running. Exiting. ({e})")
            import os
            os._exit(1)

    def emit(self, event_name: str, payload: dict):
        if not self.loop or not self.clients:
            return
            
        message = {
            "type": event_name,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "payload": payload
        }
        json_msg = json.dumps(message)
        
        # Fire and forget emission safely across threads
        asyncio.run_coroutine_threadsafe(
            self._broadcast(json_msg), 
            self.loop
        )

    async def _broadcast(self, message: str):
        if self.clients:
            # Send to all connected UIs
            await asyncio.gather(*(client.send(message) for client in self.clients), return_exceptions=True)
