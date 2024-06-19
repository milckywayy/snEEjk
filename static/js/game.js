let snake = [];
let direction = "";
let nextDirection = "";
let apple = [];
let width = 0;
let height = 0;

const canvas = document.getElementById('game');
const context = canvas.getContext('2d');
let tile_size = 20;

const snake_body_color = "#FFD630";
const snake_head_color = "red";
const apple_color = "#FF8C00";

let lastFrameTime = 0;
const frameInterval = 70;

let score = 0;
let nickname = "test";

document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    socket.on('connect', () => {
        console.log('Connected to the server');
    });

    socket.on('initial_state', (data) => {
        const { valid_nickname, snake_init, direction_init, apple_init, score_init, tile_map_size_init } = data;
        gameSetup(valid_nickname, snake_init, direction_init, apple_init, score_init, tile_map_size_init);
        requestAnimationFrame(gameLoop);
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from the server');
    });

    socket.on('apple_eaten', (data) => {
        const { apple_update, new_score } = data;
        snake.push([...snake[snake.length - 1]]);
        apple = apple_update;
        score = parseInt(new_score);
    });

    socket.on('lost', (data) => {
        const { valid_nickname, snake_init, direction_init, apple_init, score_init, tile_map_size_init } = data;
        gameSetup(valid_nickname, snake_init, direction_init, apple_init, score_init, tile_map_size_init);
    });

    function gameSetup(valid_nickname, snake_init, direction_init, apple_init, score_init, tile_map_size_init) {
        nickname = valid_nickname;
        snake = snake_init;
        direction = direction_init;
        nextDirection = direction_init;
        apple = apple_init;
        score = score_init;
        width = tile_map_size_init[0];
        height = tile_map_size_init[1];

        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        document.addEventListener('keydown', handleKeydown);
        setupTouchControls();
    }

    function sendGameEvent(event) {
        socket.emit('game_event', event);
    }

    function gameLoop(timestamp) {
        if (timestamp - lastFrameTime >= frameInterval) {
            lastFrameTime = timestamp;
            eventLoop();
        }
        requestAnimationFrame(gameLoop);
    }

    function eventLoop() {
        direction = nextDirection;
        snakeMove();
        sendGameEvent({ type: 'MOVE', head: snake[0] });

        context.clearRect(0, 0, canvas.width, canvas.height);

        context.shadowColor = 'rgba(0,0,0,0)';
        drawSnake(snake);

        context.fillStyle = apple_color;
        context.shadowColor = apple_color;
        context.shadowBlur = 20;
        drawApple(apple);

        context.fillStyle = 'white';
        context.font = '18px Arial';
        context.fillText('Score: ' + score, 10, 20);
        context.fillText('Nickname: ' + nickname, 10, 40);
    }

    function handleKeydown(e) {
        const key = e.key.toLowerCase();
        if ((key === 'arrowleft' || key === 'a') && direction !== 'RIGHT') {
            nextDirection = 'LEFT';
        } else if ((key === 'arrowup' || key === 'w') && direction !== 'DOWN') {
            nextDirection = 'UP';
        } else if ((key === 'arrowright' || key === 'd') && direction !== 'LEFT') {
            nextDirection = 'RIGHT';
        } else if ((key === 'arrowdown' || key === 's') && direction !== 'UP') {
            nextDirection = 'DOWN';
        }
    }

    function resizeCanvas() {
        const margin = 0.15;
        const maxTileWidth = Math.floor((window.innerWidth * (1 - margin)) / width);
        const maxTileHeight = Math.floor((window.innerHeight * (1 - margin)) / height);
        tile_size = Math.min(maxTileWidth, maxTileHeight);

        canvas.width = width * tile_size;
        canvas.height = height * tile_size;
    }

    function fillTile([x, y], color) {
        const padding = 0.05 * tile_size;
        const innerTileSize = tile_size - 2 * padding;

        context.fillStyle = color;
        context.fillRect(
            x * tile_size + padding,
            y * tile_size + padding,
            innerTileSize,
            innerTileSize
        );
    }

    function drawSnake(body) {
        fillTile(body[0], snake_head_color);
        for (let i = 1; i < body.length; i++) {
            fillTile(body[i], snake_body_color);
        }
    }

    function snakeMove() {
        const head = { x: snake[0][0], y: snake[0][1] };

        if (direction === 'UP') head.y -= 1;
        else if (direction === 'DOWN') head.y += 1;
        else if (direction === 'LEFT') head.x -= 1;
        else if (direction === 'RIGHT') head.x += 1;

        if (head.x < 0) head.x = width - 1;
        else if (head.x >= width) head.x = 0;
        if (head.y < 0) head.y = height - 1;
        else if (head.y >= height) head.y = 0;

        snake.unshift([head.x, head.y]);
        snake.pop();
    }

    function drawApple(apple) {
        fillTile(apple, apple_color);
    }

    function setupTouchControls() {
        let touchStartX = 0;
        let touchStartY = 0;
        let touchEndX = 0;
        let touchEndY = 0;

        document.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
            touchStartY = e.changedTouches[0].screenY;
            e.preventDefault(); // Prevent scrolling
        });

        document.addEventListener('touchmove', (e) => {
            e.preventDefault(); // Prevent scrolling
        });

        document.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            touchEndY = e.changedTouches[0].screenY;
            handleGesture();
            e.preventDefault(); // Prevent scrolling
        });

        function handleGesture() {
            const diffX = touchEndX - touchStartX;
            const diffY = touchEndY - touchStartY;

            if (Math.abs(diffX) > Math.abs(diffY)) {
                // Horizontal swipe
                if (diffX > 0 && direction !== 'LEFT') {
                    nextDirection = 'RIGHT';
                } else if (diffX < 0 && direction !== 'RIGHT') {
                    nextDirection = 'LEFT';
                }
            } else {
                // Vertical swipe
                if (diffY > 0 && direction !== 'UP') {
                    nextDirection = 'DOWN';
                } else if (diffY < 0 && direction !== 'DOWN') {
                    nextDirection = 'UP';
                }
            }
        }
    }
});
