import json
import os
import re
import logging
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit
from sqlalchemy import func, desc

from model import db, Score
from game import game_setup, is_apple_eaten, eat_apple, check_collision, snake_move
from usosapi import usosapi
from usosapi.usosapi import USOSAPISession, USOSAPIAuthorizationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SNAKE_SECRET_KEY', os.urandom(24))
socketio = SocketIO(app, async_mode='gevent')
# socketio = SocketIO(app, async_mode='eventlet')  # For windows

if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

GAME_TITLE = 'snEEjk'
VERSION = 'V2.2.0'

db.init_app(app)
with app.app_context():
    db.create_all()

with open('credentials/usos_api_credentials.json', 'r') as file:
    usosapi_credentials = json.load(file)

usosapi = USOSAPISession(
    usosapi_credentials['api_base_address'],
    usosapi_credentials['consumer_key'],
    usosapi_credentials['consumer_secret'],
    'email'
)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('usos_auth'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def home_screen():
    logger.info("Rendering login screen")
    return render_template('index.html', game_title=GAME_TITLE, game_version=VERSION)


@app.route('/login')
def login():
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')

    if oauth_token and oauth_verifier:
        try:
            usosapi.authorize(oauth_token, oauth_verifier)
            user_data = usosapi.fetch_from_service(
                'services/users/user',
                fields='id|first_name|last_name'
            )

            session['logged_in'] = True
            session['user'] = {
                'id': user_data['id'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name']
            }

            logging.info(f"User ({user_data['id']}) {user_data['first_name']} {user_data['last_name']} logged in")
            return redirect(url_for('home_screen'))

        except USOSAPIAuthorizationError:
            logger.info("Invalid oauth token")

    return render_template('index.html')


@app.route('/usos_auth')
def usos_auth():
    _, request_url = usosapi.get_auth_url(callback=url_for('login', _external=True))
    return redirect(request_url)


@app.route('/hellopage')
def hello_screen():
    logger.info("Rendering hello screen")
    return render_template('hellopage.html', game_title=GAME_TITLE, game_version=VERSION)


@app.route('/highscores')
def highscores_screen():
    scores = db.session.query(Score.nickname, func.max(Score.points).label('score')).group_by(Score.nickname).order_by(desc('score')).limit(10).all()

    scores = [(nickname.encode('utf-8', errors='replace').decode('utf-8'), points) for nickname, points in scores]
    logger.info("Rendering highscores screen with scores: %s", scores)
    return render_template('highscores.html', game_title=GAME_TITLE, scores=scores, game_version=VERSION)


@login_required
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
    session['apple_times'] = []  # Initialize list for apple collection times
    logger.info("Session started for nickname: %s(%s)", nickname, client_ip)
    return jsonify({'status': 'success'}), 200


@login_required
@app.route('/game_screen')
def game_screen():
    if 'nickname' not in session:
        logger.warning("Attempt to access game screen without valid session from IP: %s", request.remote_addr)
        return redirect(url_for('home_screen'))
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
    session['apple_times'] = []
    session['invalid_score'] = False
    logger.info(
        "Game setup for event '%s' for user '%s, %s'",
        event,
        f"{nickname} ({session['user']['id']} - {session['user']['first_name']} {session['user']['last_name']})",
        client_ip
    )
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

    if data['type'] == 'MOVE':
        snake = session['snake']
        apple = session['apple']
        new_head = data['head']

        if check_collision(snake):
            logger.info(
                "Collision detected for nickname: %s, %s",
                f"{session['nickname']} ({session['user']['id']} - {session['user']['first_name']} {session['user']['last_name']})",
                client_ip
            )
            end_time = datetime.now().timestamp()
            duration = end_time - session['start_time']
            save_score(session['nickname'], session['score'], duration, client_ip)
            setup_for('lost')
            return

        snake_move(snake, new_head)

        if is_apple_eaten(new_head, apple):
            session['apple_times'].append(current_event_time)

            # Calculate average time between collecting 5 apples
            if len(session['apple_times']) >= 5:
                times = session['apple_times'][-5:]
                average_time = (times[-1] - times[0]) / 4
                if average_time < 0.9:  # Arbitrary threshold for cheating
                    logger.warning(
                        "Possible cheating detected for nickname: %s, %s. Average time: %.2f seconds",
                       f"{session['nickname']} ({session['user']['id']} - {session['user']['first_name']} {session['user']['last_name']})",
                       client_ip,
                       average_time
                    )
                    session['invalid_score'] = True

                if session['score'] >= 396:
                    setup_for('lost')

            session['score'] += 1
            new_apple = eat_apple(snake)
            session['apple'] = new_apple
            logger.info(
                "Apple eaten by user: %s, %s, new score: %d",
                f"{session['nickname']} ({session['user']['id']} - {session['user']['first_name']} {session['user']['last_name']})",
                client_ip,
                session['score']
            )
            emit('apple_eaten', {'apple_update': new_apple, 'new_score': session['score']})

        # Update snake position
        session['snake'] = snake


def save_score(nickname, score, duration, client_ip):
    if session.get('invalid_score', False) or duration < score:
        logger.warning(
            "Possible cheating detected for nickname: %s, %s. Score: %d, Duration: %.2f",
           f"{nickname} ({session['user']['id']} - {session['user']['first_name']} {session['user']['last_name']})",
           client_ip,
           score,
           duration
        )
        return

    score = Score(
        points=score,
        nickname=nickname,
    )

    db.session.add(score)
    db.session.commit()

    logger.info(
        "Score saved for: %s, %s, score: %d",
        f"{nickname} ({session['user']['id']} - {session['user']['first_name']} {session['user']['last_name']})",
        client_ip,
        score.points
    )
