import sys
import os

# Ensure backend module is resolvable in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.logger import logger
from backend.core.orchestrator import JarvisOrchestrator

def main():
    logger.info("Starting Jarvis OS Backend...")
    try:
        orchestrator = JarvisOrchestrator()
        
        # Start the infinite loop to keep the WebSocket server alive
        orchestrator.start()
        
    except Exception as e:
        logger.error(f"Fatal error during startup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
