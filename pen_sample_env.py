import os
import logging
import time
from dotenv import load_dotenv

os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

class Config:
    def __init__(self):
        load_dotenv()

    """Configuration class."""
    IMG_DIR = os.getenv('IMG_DIR', 'images')
    DONE_DIR = os.getenv('DONE_DIR', 'done')
    TIME_FILE = os.getenv('TIME_FILE', 'tmp/timer')
    LAST_FILENAME = os.getenv('LAST_FILENAME', 'tmp/last_filename')
    USER_WHITELIST = os.getenv('USER_WHITELIST', '').split(',')
    META_TAG = os.getenv('META_TAG', 'dream')

    TOKEN = os.getenv('TOKEN')
    CHANNEL_NAME = os.getenv('CHANNEL_NAME')

    @property
    def COOLDOWN(self):
        load_dotenv(override=True)
        cooldown = int(os.getenv('COOLDOWN_MINUTES', 120)) * 60
        logging.info(f"Cooldown update: {cooldown//60} minutes")
        return cooldown

config = Config()
while True:
    time.sleep(2)
    print(config.COOLDOWN)
