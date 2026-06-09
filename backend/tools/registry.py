import subprocess
import os
import sys
import platform
import webbrowser
from backend.core.logger import logger

class ToolRegistry:
    def __init__(self):
        logger.info("  [Module] ToolRegistry initialized.")
        self._tools = {
            "open_app": self._tool_open_app,
            "search_web": self._tool_search_web,
            "sleep": self._tool_sleep,
            "get_system_info": self._tool_get_system_info
        }

    def execute_tool(self, name: str, args: dict) -> dict:
        logger.info(f"[ToolRegistry] Executing '{name}' with args: {args}")
        
        if name not in self._tools:
            error_msg = f"Tool '{name}' not found in registry."
            logger.error(f"[ToolRegistry] {error_msg}")
            return self._format_result(name, "fail", {}, error_msg)

        try:
            # Execute the pure Python function synchronously
            func = self._tools[name]
            result_data = func(**args)
            logger.info(f"[ToolRegistry] '{name}' execution successful. Output: {result_data}")
            return self._format_result(name, "success", result_data, None)
        except TypeError as te:
            error_msg = f"Invalid arguments for '{name}': {te}"
            logger.error(f"[ToolRegistry] {error_msg}")
            return self._format_result(name, "fail", {}, error_msg)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[ToolRegistry] Tool '{name}' failed: {error_msg}")
            return self._format_result(name, "fail", {}, error_msg)

    def _format_result(self, name: str, status: str, data: dict, error: str) -> dict:
        return {
            "tool": name,
            "status": status,
            "data": data,
            "error": error
        }

    def get_schema(self) -> list:
        # Returns Ollama native tool schema definition
        return [
            {
                "type": "function",
                "function": {
                    "name": "open_app",
                    "description": "Open a desktop application on Windows",
                    "parameters": {
                        "type": "object",
                        "properties": {"app_name": {"type": "string"}},
                        "required": ["app_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the internet using a browser",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sleep",
                    "description": "Put the assistant into sleep mode",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_system_info",
                    "description": "Get current system OS and CPU information",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

    # -------------------------------------------------------------------------
    # TOOL IMPLEMENTATIONS (No side effects outside this class)
    # -------------------------------------------------------------------------

    def _tool_open_app(self, app_name: str) -> dict:
        if sys.platform == "win32":
            # Using Popen to fire and forget so it remains synchronous and non-blocking
            subprocess.Popen(f'start "" {app_name}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"message": f"{app_name.capitalize()} launched"}
        else:
            raise NotImplementedError("open_app is currently only supported on Windows.")

    def _tool_search_web(self, query: str) -> dict:
        import urllib.parse
        url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return {"message": f"Searched web for: {query}"}

    def _tool_sleep(self) -> dict:
        return {"message": "Assistant entering sleep mode."}

    def _tool_get_system_info(self) -> dict:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "cpu_cores": os.cpu_count()
        }
