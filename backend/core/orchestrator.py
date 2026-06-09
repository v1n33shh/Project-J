from backend.core.logger import logger
from backend.agent.loop import AgentLoop
from backend.tools.registry import ToolRegistry
from backend.memory.manager import MemoryManager
from backend.voice.engine import VoiceEngine
from backend.model.service import ModelService
from backend.server.ws import EventEmitter

class JarvisOrchestrator:
    def __init__(self):
        logger.info("Initializing Jarvis OS Orchestrator...")
        
        # Initialize WebSocket Server
        self.emitter = EventEmitter()
        self.emitter.start_server(port=8765)
        
        # Initialize modules
        self.memory = MemoryManager()
        self.model = ModelService()
        self.tools = ToolRegistry()
        self.voice = VoiceEngine(self.emitter)
        self.agent = AgentLoop(self.model, self.memory, self.tools, self.emitter, self.voice)
        
        # Route incoming websocket messages to the agent loop
        def handle_ws_message(data: dict):
            msg_type = data.get("type")
            
            if msg_type == "user_message":
                user_req = data.get("payload", {}).get("text", "")
                import threading
                threading.Thread(target=self.agent.run_loop, args=(user_req,), daemon=True).start()
                
            elif msg_type == "start_voice_listening":
                import threading
                import time
                
                # Prevent overlapping voice sessions and watchdog check
                current_time = time.time()
                active_ts = getattr(self, "_voice_session_ts", 0)
                if getattr(self, "_voice_session_active", False):
                    if current_time - active_ts > 15:
                        logger.warning("[Orchestrator] Voice session watchdog timeout (15s). Force unlocking session.")
                        self.emitter.emit("voice_status", {"status": "idle"})
                        self.emitter.emit("final_response", {"text": "Voice session timed out. Please try again."})
                    else:
                        logger.warning("[Orchestrator] Discarding rapid repeated voice trigger: session already active.")
                        self.emitter.emit("voice_status", {"status": "idle"})
                        return
                        
                self._voice_session_active = True
                self._voice_session_ts = current_time
                
                def _voice_worker():
                    try:
                        res = self.voice.listen()
                        
                        # Handle structured error
                        if isinstance(res, dict) and res.get("error"):
                            err_type = res.get("error")
                            if err_type == "MIC_FAILURE":
                                ui_msg = "Microphone error. Please check your audio device."
                            elif err_type == "STT_FAILURE":
                                ui_msg = "Speech recognition failed. Please try again."
                            else:
                                ui_msg = "Voice engine error."
                            self.emitter.emit("voice_status", {"status": "idle"})
                            self.emitter.emit("final_response", {"text": ui_msg})
                            return
                            
                        # Handle text
                        text = res.get("text", "") if isinstance(res, dict) else res
                        if text:
                            # Feed transcribed text automatically into agent loop
                            self.emitter.emit("user_message", {"text": text})
                            self.agent.run_loop(text)
                        else:
                            # Force unlock UI
                            self.emitter.emit("voice_status", {"status": "idle"})
                    except Exception as e:
                        logger.error(f"[Orchestrator] Voice worker crashed: {e}")
                        self.emitter.emit("voice_status", {"status": "idle"})
                        self.emitter.emit("final_response", {"text": "Voice engine critical error."})
                    finally:
                        self._voice_session_active = False
                        
                threading.Thread(target=_voice_worker, daemon=True).start()
                
        self.emitter.set_callback(handle_ws_message)
        
        logger.info("All internal modules initialized successfully.")

    def start(self):
        import time
        import os
        logger.info("Jarvis Backend is running and waiting for UI connection.")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Jarvis Backend shutting down.")
            os._exit(0)

    def shutdown(self):
        logger.info("Shutting down internal modules...")
        # Placeholder for cleanup
        pass
