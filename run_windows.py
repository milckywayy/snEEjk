from waitress import serve
from gevent import monkey
from app import app
import json
import os


if os.path.exists('config/config.json'):
    with open('config/config.json', 'r') as file:
        app_config = json.load(file)
else:
    with open('config/default_config.json', 'r') as file:
        app_config = json.load(file)


monkey.patch_all()
serve(
    app,
    host=app_config['app_host'],
    port=app_config['app_port'],
    threads=2,
    backlog=2048,
    channel_timeout=120,
    connection_limit=2000,
)