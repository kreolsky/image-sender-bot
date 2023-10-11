import os
import shutil
import time
import json
import logging
import pickle
import sqlite3
from telegram import Bot, Update, InputMediaPhoto
from telegram.utils.request import Request
from telegram.error import NetworkError
from telegram.ext import MessageHandler, Filters, Updater, CallbackContext, CommandHandler
from datetime import datetime, timedelta
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
os.chdir(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)

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
    TIMER_FILENAME = os.getenv('TIMER_FILENAME', 'tmp/timer')
    LAST_FILENAME = os.getenv('LAST_FILENAME', 'tmp/last_filename')
    DB_FILENAME = os.getenv('DB_FILENAME', 'tmp/image_metadata.db')
    USER_WHITELIST = os.getenv('USER_WHITELIST', '').split(',')
    META_TAG = os.getenv('META_TAG', 'Dream')
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
    def __init__(self, dir=Config.IMG_DIR):
        self.dir = dir

    def get_metadata(self, filename, item=Config.META_TAG):
        # Убедиться что пришло только имя файла
        filename = os.path.basename(filename)
        
        filename = os.path.join(self.dir, filename)
        with Image.open(filename) as im:
            metadata = im.info

        if item in metadata:
            return metadata[item]
        return metadata

    # ВЫНЕСТИ 'sd-metadata' в Config!
    def get_prompt(self, filename):
        metadata = self.get_metadata(filename, item='sd-metadata')
        return json.loads(metadata)['image']['prompt']

    def get_oldest_image(self):
        images = [os.path.join(self.dir, i) for i in self.get_all_images()]
        if images:
            min_images = min(images, key=os.path.getmtime, default=None)
            return os.path.basename(min_images)

    def get_all_images(self):
        return (i.name for i in os.scandir(self.dir) if i.is_file() and i.name.endswith('.png'))


class DataBaseHandler:
    def __init__(self):
        self.images = ImageHandler()

    def create_table(self):
        # Создать таблицу для хранения метаданных изображений
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS images (filename TEXT, prompt TEXT)')
            conn.commit()

    def get_connection(self):
        return sqlite3.connect(Config.DB_FILENAME)

    def add_images_prompt(self, data):
        # Добавить метаданные изображений в базу данных
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('INSERT INTO images (filename, prompt) VALUES (?, ?)', data)
            conn.commit()

    def get_image_group(self, filename):
        # Get all images with the same prompt
        prompt = self.images.get_prompt(filename)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT filename FROM images WHERE prompt = ?', (prompt,))
            images = [i[0] for i in cursor.fetchall()]
            return images

    def remove_images(self, filenames):
        # Удалить изображения из базы данных
        filenames = [(f,) for f in filenames]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('DELETE FROM images WHERE filename = ?', filenames)
            conn.commit()

    def sync_db(self):
        # Получить список всех файлов в директории IMG_DIR
        directory_files = self.images.get_all_images()

        # Получить список файлов из базы данных
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT filename FROM images')
            db_files = [r[0] for r in cursor.fetchall()]

        # Определить новые файлы, которые есть в директории, но отсутствуют в базе данных
        new_files = list(set(directory_files) - set(db_files))

        # Добавить новые файлы в базу данных
        files_metadata = []
        for filename in new_files:
            prompt = self.images.get_prompt(filename)
            files_metadata.append((filename, prompt))

        self.add_images_prompt(files_metadata)

        # Определить файлы, которые есть в базе данных, но отсутствуют в директории
        missing_files = list(set(db_files) - set(directory_files))

        # Удалить отсутствующие файлы из базы данных
        if missing_files:
            self.remove_images(missing_files)


class MyBot:
    def __init__(self, token):
        self.request = Request(con_pool_size=8)
        self.bot = Bot(token, request=self.request)
        self.updater = Updater(bot=self.bot, use_context=True)
        self.config = Config()
        self.db = DataBaseHandler()
        self.images = ImageHandler()

        # Message handler for all messages that are not commands
        self.updater.dispatcher.add_handler(MessageHandler(~Filters.command, self.handle_bot_messages))  
        # Command "/instant" handler
        self.updater.dispatcher.add_handler(CommandHandler('instant', self.handle_instant_image))
        # Sync db
        self.db.sync_db()

    def run(self):
        self.updater.start_polling()

        try:
            while True:
                self.process_image()
                time.sleep(self.config.SLEEP_INTERVAL_SECONDS)
        except (KeyboardInterrupt, SystemExit):
            self.updater.stop()

    def send_images(self, filename):
        images_to_send = self.db.get_image_group(filename)
        logging.info(f"Images group based on '{filename}': '{', '.join(images_to_send)}'")

        try:
            media_group = []
            for filename in images_to_send:
                filepath = os.path.join(self.config.IMG_DIR, filename)
                with open(filepath, 'rb') as file:
                    media_group.append(InputMediaPhoto(media=file))

            # Отправка всех фотографий как одно сообщение
            self.bot.send_media_group(self.config.CHANNEL_NAME, media_group)

        except NetworkError as e:
            logging.error(f"Network error when sending images: {str(e)}")
            return  # If a network error occurred, simply try again

        self.save_sent_images(images_to_send)
        self.update_last_time(datetime.now())

    def process_image(self):
        last_time = self.get_last_time()
        if datetime.now() - last_time < timedelta(seconds=self.config.COOLDOWN):
            return  # If cooldown is still ongoing

        filename = self.images.get_oldest_image()
        if filename is None:
            return  # If no images in the folder

        self.send_images(filename)

    @restrict_access
    def handle_instant_image(self, update: Update, context: CallbackContext):
        if context.args:
            filename = os.path.join(self.config.IMG_DIR, context.args[0])
        else:
            filename = self.images.get_oldest_image()

        logging.info(f"Command /instant received. Sending {filename}")
        if filename is None or not os.path.exists(filename):
            update.effective_message.reply_text("No image available.")
            return

        self.send_images(filename)

    def handle_bot_messages(self, update: Update, context: CallbackContext):
        message = update.effective_message
        if not os.path.isfile(self.config.LAST_FILENAME):
            return

        if message.forward_from_chat.username == self.config.CHANNEL_NAME.strip('@'):
            sent_images = self.get_sent_images()
            filepath = os.path.join(self.config.IMG_DIR, sent_images[0])
            with open(filepath, 'rb') as file:
                message.reply_document(file)
            message.reply_text(self.images.get_metadata(filepath))
            # metadata = json.dumps(ImageHandler.get_metadata(filename))
            # logging.info(metadata.strip('"'))
            # message.reply_text(f'```{metadata}```', parse_mode='MarkdownV2')

            # Move sent images to DONE_DIR
            logging.info(f"Files to move: '{', '.join(sent_images)}'")
            for f in sent_images:
                path_from = os.path.join(self.config.IMG_DIR, f)
                path_to = os.path.join(self.config.DONE_DIR, f)
                shutil.move(path_from, path_to)

            self.db.sync_db()

    def get_last_time(self):
        if not os.path.exists(self.config.TIMER_FILENAME):
            return datetime.now() - timedelta(seconds=self.config.COOLDOWN)
        try:
            with open(self.config.TIMER_FILENAME, 'r') as f:
                timestamp = float(f.read())
        except Exception as e:
            logging.error(f"Error reading time from file: {str(e)}")
        return datetime.fromtimestamp(timestamp)

    def update_last_time(self, last_time):
        try:
            with open(self.config.TIMER_FILENAME, 'w') as f:
                f.write(str(last_time.timestamp()))
        except Exception as e:
            logging.error(f"Error updating time to file: {str(e)}")

    def save_sent_images(self, filenames):
        if not isinstance(filenames, list):
            filenames = [filenames, ]

        try:
            with open(self.config.LAST_FILENAME, 'wb') as f:
                pickle.dump(filenames, f)
        except Exception as e:
            logging.error(f"Error saving last filenames: {str(e)}")

    def get_sent_images(self):
        try:
            with open(self.config.LAST_FILENAME, 'rb') as f:
                filenames = pickle.load(f)
            os.remove(self.config.LAST_FILENAME)
            return filenames
        except Exception as e:
            logging.error(f"Error getting last filenames: {str(e)}")


if __name__ == '__main__':
    bot = MyBot(Config.TOKEN)
    bot.run()
