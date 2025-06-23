import gevent.monkey

from utils import read_config


app_config = read_config()

gevent.monkey.patch_all()

worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'
workers = app_config['workers']
bind = f"{app_config['app_host']}:{app_config['app_port']}"
