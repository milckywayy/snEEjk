import os
import re
import sqlite3
import logging
import ssl
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit
from game import game_setup, is_apple_eaten, eat_apple, check_collision, snake_move
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

# Customize logging format to include the current time
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SNAKE_SECRET_KEY', os.urandom(24))
socketio = SocketIO(app, async_mode='gevent')

if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

DATABASE = os.path.join(app.instance_path, 'scores.db')

GAME_TITLE = 'snEEjk'
VERSION = 'V2.0.5'


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            score INTEGER NOT NULL,
            nickname VARCHAR(20) NOT NULL
        )
        """)
        conn.commit()
        logger.info("Database initialized")


@app.route('/')
def login_screen():
    logger.info("Rendering login screen")
    return render_template('index.html', game_title=GAME_TITLE, game_version=VERSION)


@app.route('/hellopage')
def hello_screen():
    logger.info("Rendering hello screen")
    return render_template('hellopage.html', game_title=GAME_TITLE, game_version=VERSION)


@app.route('/highscores')
def highscores_screen():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT nickname, MAX(score) as score FROM scores GROUP BY nickname ORDER BY score DESC LIMIT 10')
        scores = cursor.fetchall()
    scores = [(nickname.encode('utf-8', errors='replace').decode('utf-8'), score) for nickname, score in scores]
    logger.info("Rendering highscores screen with scores: %s", scores)
    return render_template('highscores.html', game_title=GAME_TITLE, scores=scores, game_version=VERSION)


@app.route('/start_session', methods=['POST'])
def start_session():
    data = request.get_json()
    nickname = data.get('nickname', '')
    client_ip = request.remote_addr
    if not re.match(r'^[^<>/\\{}\[\]]{1,20}$', nickname):
        logger.warning("Invalid nickname attempt: %s(%s)", nickname, client_ip)
        return jsonify({'status': 'error', 'message': 'Invalid nickname'}), 400

    session['nickname'] = nickname
    session['invalid_score'] = False
    session['rapid_event_logged'] = False  # Initialize flag for rapid event logging
    logger.info("Session started for nickname: %s(%s)", nickname, client_ip)
    return jsonify({'status': 'success'}), 200


@app.route('/game_screen')
def game_screen():
    if 'nickname' not in session:
        logger.warning("Attempt to access game screen without valid session from IP: %s", request.remote_addr)
        return redirect(url_for('login_screen'))
    logger.info("Rendering game screen for nickname: %s(%s)", session['nickname'], request.remote_addr)
    return render_template('game.html', game_title=GAME_TITLE, game_version=VERSION)


def setup_for(event):
    nickname = session.get('nickname', 'Guest')
    client_ip = request.remote_addr
    snake, direction, map_size, apple, score = game_setup()
    session['snake'] = snake
    session['direction'] = direction
    session['apple'] = apple
    session['score'] = score
    session['tile_map_size'] = map_size
    session['start_time'] = datetime.now().timestamp()
    session['last_event_time'] = datetime.now().timestamp() - 1.0
    session['invalid_score'] = False
    session['rapid_event_logged'] = False
    logger.info("Game setup for event '%s' with nickname '%s(%s)'", event, nickname, client_ip)
    emit(event, {
        'valid_nickname': nickname,
        'snake_init': snake,
        'direction_init': direction.name,
        'apple_init': apple,
        'score_init': score,
        'tile_map_size_init': map_size
    })


@socketio.on('connect')
def handle_connect():
    nickname = session.get('nickname')
    client_ip = request.remote_addr
    logger.info(f"Client {nickname}({client_ip}) connected")
    setup_for('initial_state')


@socketio.on('disconnect')
def handle_disconnect():
    nickname = session.get('nickname')
    client_ip = request.remote_addr
    logger.info(f"Client {nickname}({client_ip}) disconnected")


@socketio.on('game_event')
def handle_game_event(data):
    client_ip = request.remote_addr
    current_event_time = datetime.now().timestamp()
    last_event_time = session.get('last_event_time', 0)

    if session['start_time'] > 1 and current_event_time - last_event_time < 0.04:
        if not session['rapid_event_logged']:
            logger.warning("Rapid event detected for nickname: %s(%s). Marking session for invalid scoring. %f",
                           session['nickname'], client_ip, current_event_time - last_event_time)
            session['rapid_event_logged'] = True
        session['invalid_score'] = True

    session['last_event_time'] = current_event_time

    if data['type'] == 'MOVE':
        snake = session['snake']
        apple = session['apple']
        new_head = data['head']

        if check_collision(snake):
            logger.info("Collision detected for nickname: %s(%s)", session['nickname'], client_ip)
            end_time = datetime.now().timestamp()
            duration = end_time - session['start_time']
            save_score(session['nickname'], session['score'], duration, client_ip)
            setup_for('lost')
            return

        snake_move(snake, new_head)

        if is_apple_eaten(new_head, apple):
            if session['score'] > 390:  # For cheaters
                setup_for('lost')
                return

            session['score'] += 1
            new_apple = eat_apple(snake)
            session['apple'] = new_apple
            logger.info("Apple eaten by nickname: %s(%s), new score: %d", session['nickname'], client_ip,
                        session['score'])
            emit('apple_eaten', {'apple_update': new_apple, 'new_score': session['score']})

        # Update snake position
        session['snake'] = snake
        emit('snake_update', {'snake_head_update': snake[0]})


def save_score(nickname, score, duration, client_ip):
    if session.get('invalid_score', False) or duration < score:
        logger.warning("Possible cheating detected for nickname: %s(%s). Score: %d, Duration: %.2f", nickname,
                       client_ip, score, duration)
        return
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scores (nickname, score) VALUES (?, ?)
        ''', (nickname, score))
        conn.commit()
    logger.info("Score saved for: %s(%s), score: %d", nickname, client_ip, score)


init_db()
if __name__ == '__main__':
    logger.info("Starting server")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('fullchain.pem', 'privkey.pem')

    http_server = pywsgi.WSGIServer(('0.0.0.0', 5050), app, handler_class=WebSocketHandler, ssl_context=context)
    http_server.serve_forever()
