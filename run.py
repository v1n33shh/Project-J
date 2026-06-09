from backend.core.logger import logger
from backend.core.orchestrator import JarvisOrchestrator

def main():
    logger.info("Starting Jarvis OS Backend...")
    try:
        orchestrator = JarvisOrchestrator()
        orchestrator.start()
    except Exception as e:
        logger.error(f"Fatal error during startup: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
