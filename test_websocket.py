import socketio

# Create a Socket.IO client
sio = socketio.Client()

# Define the event when the connection is established
@sio.event
def connect():
    print("Connected to Nightscout server!")

# Define the event when a disconnect occurs
@sio.event
def disconnect():
    print("Disconnected from Nightscout server!")

# Listen for glucose values (sgvs)
@sio.on('sgv')
def on_sgv(data):
    print("Received sgv (sensor glucose value) event:", data)

@sio.on('notification')
def on_notification(data):
    print("Received notification event:", data)

# Listen for treatments (like insulin or carbs)
@sio.on('treatments')
def on_treatments(data):
    print("Received treatments event:", data)

# Listen for manual blood glucose (mbg)
@sio.on('dataUpdate')
def on_mbg(data):
    print("Received mbg (manual blood glucose) event:", data)

# Listen for device status updates
@sio.on('devicestatus')
def on_devicestatus(data):
    print("Received devicestatus event:", data)

# Catch all other events
@sio.on('*')
def catch_all(event, data):
    print(f"Received event: {event}, data: {data}")


# Define the URL of your Nightscout server
nightscout_url = 'https://glucose.fly.dev/'
nightscout_token = 'ledmatrix-95000395eef373f0'

# Connect to the Nightscout server with the token
sio.connect(nightscout_url, headers={'Authorization': f'Bearer {nightscout_token}'})

# Keep the connection open
sio.wait()

