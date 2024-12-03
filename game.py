import random
from enum import Enum


class Direction(Enum):
    LEFT = 'LEFT'
    UP = 'UP'
    RIGHT = 'RIGHT'
    DOWN = 'DOWN'


BOARD_WIDTH = 20
BOARD_HEIGHT = 20
START_SNAKE = [[5, 5], [4, 5], [3, 5], [2, 5]]
START_DIRECTION = Direction.RIGHT


def generate_apple_position(snake):
    while True:
        apple = [random.randint(0, BOARD_WIDTH - 1), random.randint(0, BOARD_HEIGHT - 1)]
        if apple not in snake:
            return apple


def game_setup():
    snake = START_SNAKE[:]
    direction = START_DIRECTION
    apple = generate_apple_position(snake)
    return snake, direction, (BOARD_WIDTH, BOARD_HEIGHT), apple, 0


def is_apple_eaten(head, apple):
    return head == apple


def eat_apple(snake):
    apple = generate_apple_position(snake)
    snake.append(snake[-1])

    return apple


def check_collision(snake):
    head = snake[0]
    return head in snake[1:]


def snake_move(snake, new_head):
    snake.insert(0, new_head)
    snake.pop()
