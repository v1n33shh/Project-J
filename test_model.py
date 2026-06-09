import sys
import json
from backend.core.logger import logger
from backend.model.service import ModelService

def run_test():
    logger.info("Initializing Model Service Test...")
    model = ModelService(primary_model="qwen2.5:7b")
    
    # Define native tool schema
    tools = [{
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open a desktop application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string"}
                },
                "required": ["app_name"]
            }
        }
    }]
    
    logger.info("\n--- TEST 1: Standard Chat Streaming ---")
    messages = [{"role": "user", "content": "Say 'hello world' in 3 words."}]
    final_output = None
    
    # We expect a stream of text chunks
    for chunk in model.generate(messages, tools=tools):
        # We can see partial chunks here if we want to print them to console without newline
        if not chunk["done"]:
            sys.stdout.write(chunk["content"])
            sys.stdout.flush()
        else:
            final_output = chunk
            print("")
            
    logger.info(f"Test 1 Complete. Output structure: {json.dumps(final_output, indent=2)}")
    
    logger.info("\n--- TEST 2: Native Tool Call Detection ---")
    messages_tool = [{"role": "user", "content": "Can you open Brave for me?"}]
    final_tool_output = None
    
    for chunk in model.generate(messages_tool, tools=tools):
        # Qwen 2.5 usually sends the tool call in the final chunk instantly
        if chunk["done"]:
            final_tool_output = chunk
            
    logger.info(f"Test 2 Complete. Tool Call Structure: {json.dumps(final_tool_output, indent=2)}")

if __name__ == "__main__":
    run_test()
