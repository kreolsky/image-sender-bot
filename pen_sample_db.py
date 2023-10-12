from bot import DataBaseHandler
from bot import ImageHandler

images = ImageHandler()
db = DataBaseHandler(images)

db.create_table()
db.sync_db()

db_files = db.get_all_images()
print('Images in DB:')
for i in db_files:
    print(i)

im = db_files[0]
print(f'prompt from db for {im}:')
print(db.get_prompt(im))
