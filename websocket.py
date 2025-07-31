from extensions import socketio

@socketio.on('connect')
def on_connect():
    print("WebSocket client connected.")

@socketio.on('disconnect')
def on_disconnect():
    print("WebSocket client disconnected.")