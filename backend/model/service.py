import ollama
from backend.core.logger import logger

class ModelService:
    def __init__(self, primary_model="qwen2.5:7b", fallback_model="llama3.1:8b"):
        logger.info("  [Module] ModelService initialized.")
        self.model = primary_model
        self.fallback = fallback_model
        
        self._verify_model()

    def _verify_model(self):
        try:
            models_info = ollama.list()
            models = [m.get('model', '') for m in models_info.get('models', [])]
            
            # Simple check since ollama models often have :latest tags
            if not any(self.model in m for m in models):
                logger.warning(f"[ModelService] Primary model {self.model} not found locally. Trying fallback {self.fallback}.")
                self.model = self.fallback
        except Exception as e:
            logger.error(f"[ModelService] Error checking Ollama connection. Make sure Ollama is running. {e}")

    def generate(self, messages: list, tools: list = None):
        """
        Yields structured updates conforming to the strict output constraint:
        { "content": str, "tool_calls": list, "done": bool }
        """
        logger.info(f"[ModelService] Generating response using {self.model}...")
        
        try:
            response_stream = ollama.chat(
                model=self.model,
                messages=messages,
                tools=tools,
                stream=True,
                options={"num_predict": 1024, "temperature": 0.5, "num_ctx": 4096}
            )

            full_content = ""
            tool_calls = []

            for chunk in response_stream:
                msg = chunk.get("message", {})
                
                # Check for native tool calls in the stream
                if msg.get("tool_calls"):
                    # Parse the ollama.Message.ToolCall objects into strict dicts
                    parsed_calls = []
                    for tc in msg["tool_calls"]:
                        if hasattr(tc, 'function'):
                            parsed_calls.append({
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            })
                        else:
                            parsed_calls.append({
                                "name": tc.get("function", {}).get("name"),
                                "arguments": tc.get("function", {}).get("arguments", {})
                            })
                            
                    tool_calls = parsed_calls
                    
                    # When a tool call is detected, we yield it and terminate generation for this block
                    yield {
                        "content": full_content,
                        "tool_calls": tool_calls,
                        "done": True
                    }
                    return

                # Check for standard text content
                content_chunk = msg.get("content", "")
                if content_chunk:
                    full_content += content_chunk
                    yield {
                        "content": content_chunk,
                        "tool_calls": [],
                        "done": False
                    }
            
            # Yield final state when text generation completes naturally
            yield {
                "content": full_content,
                "tool_calls": tool_calls,
                "done": True
            }

        except Exception as e:
            logger.error(f"[ModelService] Ollama generation failed: {e}")
            yield {
                "content": f"System Error: {str(e)}",
                "tool_calls": [],
                "done": True
            }
