import gevent.monkey
gevent.monkey.patch_all()

worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'
workers = 1
bind = '0.0.0.0:5050'
certfile = 'fullchain.pem'
keyfile = 'privkey.pem'