import json
import os


def read_config():
    if os.path.exists('config/config.json'):
        with open('config/config.json', 'r') as file:
            return json.load(file)
    else:
        with open('config/default_config.json', 'r') as file:
            return json.load(file)
