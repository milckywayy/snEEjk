import gevent.monkey
import json
import os


if os.path.exists('config/config.json'):
    with open('config/config.json', 'r') as file:
        app_config = json.load(file)
else:
    with open('config/default_config.json', 'r') as file:
        app_config = json.load(file)

gevent.monkey.patch_all()

worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'
workers = 1
bind = f"{app_config['app_host']}:{app_config['app_port']}"
