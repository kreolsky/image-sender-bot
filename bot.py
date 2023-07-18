import os
import shutil
import time
import json
import logging
from telegram import Bot, Update
from telegram.utils.request import Request
from telegram.error import NetworkError
from telegram.ext import MessageHandler, Filters, Updater, CallbackContext, CommandHandler
from datetime import datetime, timedelta
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
os.chdir(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def restrict_access(func):
    def wrapper(self, update: Update, context: CallbackContext):
        if str(update.effective_user.id) not in self.config.USER_WHITELIST:
            logging.info(f"Blocked access for user {update.effective_user.id}")
            return
        return func(self, update, context)
    return wrapper

class Config:
    """Configuration class."""
    IMG_DIR = os.getenv('IMG_DIR', 'images')
    DONE_DIR = os.getenv('DONE_DIR', 'done')
    TIME_FILE = os.getenv('TIME_FILE', 'tmp/timer')
    LAST_FILENAME = os.getenv('LAST_FILENAME', 'tmp/last_filename')
    USER_WHITELIST = os.getenv('USER_WHITELIST', '').split(',')
    META_TAG = os.getenv('META_TAG', 'dream')
    SLEEP_INTERVAL_SECONDS = int(os.getenv('SLEEP_INTERVAL_SECONDS', 60))

    TOKEN = os.getenv('TOKEN')
    CHANNEL_NAME = os.getenv('CHANNEL_NAME')

    @property
    def COOLDOWN(self):
        load_dotenv(override=True)
        cooldown = int(os.getenv('COOLDOWN_MINUTES', 120)) * 60
        # logging.info(f"Cooldown update: {cooldown//60} minutes")
        return cooldown

class ImageHandler:
    """A class to handle image operations."""

    @staticmethod
    def get_image_metadata(filename, item=Config.META_TAG):
        with Image.open(filename) as im:
            metadata = json.dumps(im.info)

        if item in metadata:
            return metadata[item]

        return metadata

    @staticmethod
    def get_oldest_image(directory):
        images = (entry.path for entry in os.scandir(directory) if entry.is_file() and entry.name.endswith('.png'))
        return min(images, key=os.path.getmtime, default=None)


class MyBot:
    def __init__(self, token):
        self.request = Request(con_pool_size=8)
        self.bot = Bot(token, request=self.request)
        self.updater = Updater(bot=self.bot, use_context=True)
        self.config = Config()

        self.updater.dispatcher.add_handler(MessageHandler(~Filters.command, self.handle_bot_messages))  # Message handler for all messages that are not commands
        self.updater.dispatcher.add_handler(CommandHandler('instant', self.handle_instant_image))  # Command handler

    def run(self):
        self.updater.start_polling()

        try:
            while True:
                self.process_image()
                time.sleep(self.config.SLEEP_INTERVAL_SECONDS)
        except (KeyboardInterrupt, SystemExit):
            self.updater.stop()

    def send_image(self, filename):
        try:
            with open(filename, 'rb') as file:
                message = self.bot.send_photo(self.config.CHANNEL_NAME, photo=file)
        except NetworkError:
            logging.error("Network error when sending image")
            return  # If a network error occurred, simply try again

        self.save_last_filename(filename)
        self.update_last_time(datetime.now())

    def process_image(self):
        last_time = self.read_last_time()
        if datetime.now() - last_time < timedelta(seconds=self.config.COOLDOWN):
            return  # If cooldown is still ongoing

        filename = ImageHandler.get_oldest_image(self.config.IMG_DIR)
        if filename is None:
            return  # If no images in the folder

        self.send_image(filename)

    @restrict_access
    def handle_instant_image(self, update: Update, context: CallbackContext):
        if context.args:
            filename = os.path.join(self.config.IMG_DIR, context.args[0])
        else:
            filename = ImageHandler.get_oldest_image(self.config.IMG_DIR)

        logging.info(f"Command /instant received. Sending {filename}")
        if filename is None or not os.path.exists(filename):
            update.effective_message.reply_text("No image available.")
            return
        self.send_image(filename)

    def handle_bot_messages(self, update: Update, context: CallbackContext):
        message = update.effective_message
        if not os.path.isfile(self.config.LAST_FILENAME):
            return

        if message.forward_from_chat.username == self.config.CHANNEL_NAME.strip('@'):
            filename = self.get_last_filename()
            with open(filename, 'rb') as file:
                message.reply_document(file)
            message.reply_text(ImageHandler.get_image_metadata(filename))

            shutil.move(filename, os.path.join(self.config.DONE_DIR, os.path.basename(filename)))

    def read_last_time(self):
        if not os.path.exists(self.config.TIME_FILE):
            return datetime.now() - timedelta(seconds=self.config.COOLDOWN)
        try:
            with open(self.config.TIME_FILE, 'r') as f:
                timestamp = float(f.read())
        except Exception as e:
            logging.error(f"Error reading time from file: {e}")
        return datetime.fromtimestamp(timestamp)

    def update_last_time(self, last_time):
        try:
            with open(self.config.TIME_FILE, 'w') as f:
                f.write(str(last_time.timestamp()))
        except Exception as e:
            logging.error(f"Error updating time to file: {e}")

    def save_last_filename(self, filename):
        try:
            with open(self.config.LAST_FILENAME, 'w') as f:
                f.write(filename)
        except Exception as e:
            logging.error(f"Error saving last filename: {e}")

    def get_last_filename(self):
        try:
            with open(self.config.LAST_FILENAME, 'r') as f:
                filename = f.read().strip()
            os.remove(self.config.LAST_FILENAME)
            return filename
        except Exception as e:
            logging.error(f"Error getting last filename: {e}")

def main():
    bot = MyBot(Config.TOKEN)
    bot.run()

if __name__ == '__main__':
    main()
