from bot import Config
from bot import logging
import pickle
import os

def save_sent_imagess(filenames):
    if not isinstance(filenames, list):
        filenames = [filenames]

    try:
        with open(Config.LAST_FILENAME, 'wb') as f:
            pickle.dump(filenames, f)
    except Exception as e:
        logging.error(f"Error saving last filenames: {e}")

def get_sent_images():
    try:
        with open(Config.LAST_FILENAME, 'rb') as f:
            filenames = pickle.load(f)
        os.remove(Config.LAST_FILENAME)
        return filenames
    except Exception as e:
        logging.error(f"Error getting last filenames: {str(e)}")

# filenames = ['038974.37f0e5eb.3349772249.postprocessed.png', 'artgerm.png', 'conrad roset.png']
# save_sent_imagess(filenames)

image = get_sent_images()
print(image)