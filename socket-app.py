import socketio

# standard Python
with socketio.SimpleClient(logger=True, engineio_logger=True) as sio:
    sio.connect('http://127.0.0.1:8000')
    if sio.connected:
        sio.emit('socket', {'data': {'tipo':'lpr'}})

