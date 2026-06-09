import asyncio
import websockets
import json

async def test_agent():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        print("Connected to Jarvis Backend!")
        
        # Send first request
        request1 = {
            "type": "user_message",
            "payload": {"text": "Open Brave for me"}
        }
        await websocket.send(json.dumps(request1))
        print("Sent request: Open Brave for me")
        
        # Listen for first sequence
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "final_response":
                print(f"[FINAL RESPONSE 1] {data.get('payload', {}).get('text')}")
                break
                
        # Send second request to test Memory injection
        request2 = {
            "type": "user_message",
            "payload": {"text": "Open Brave again"}
        }
        await websocket.send(json.dumps(request2))
        print("\nSent request: Open Brave again")
        
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "final_response":
                print(f"[FINAL RESPONSE 2] {data.get('payload', {}).get('text')}")
                break

if __name__ == "__main__":
    asyncio.run(test_agent())
