from app import app, socketio
import eventlet

from utils import read_config


if __name__ == '__main__':
    app_config = read_config()

    socketio.run(
        app,
        host=app_config['app_host'],
        port=app_config['app_port'],
        debug=False
    )
