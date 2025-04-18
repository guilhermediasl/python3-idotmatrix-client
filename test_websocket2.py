import socketio

# Create a Socket.IO client instance
sio = socketio.AsyncClient()

nightscout_url = 'wss://glucose.fly.dev/socket.io/?token=ledmatrix-95000395eef373f0&EIO=4&transport=websocket'
@sio.event
async def connect():
    print("Connected to Nightscout WebSocket server")

@sio.event
async def disconnect():
    print("Disconnected from Nightscout WebSocket server")

@sio.on('notification')
async def on_notification(data):
    print('Notification received:', data)
    if 'title' in data and 'message' in data:
        print(f"Title: {data['title']}")
        print(f"Message: {data['message']}")
        if 'plugin' in data:
            print(f"Plugin: {data['plugin']['label']}")

async def main():
    await sio.connect(nightscout_url)
    await sio.wait()

# Run the asyncio event loop
import asyncio
asyncio.run(main())
