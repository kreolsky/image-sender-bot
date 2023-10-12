from bot import DataBaseHandler
from bot import ImageHandler

db = DataBaseHandler()
images = ImageHandler()

db.sync_db()

# image = '038964.ddd44f03.2733843441.postprocessed.png' # Есть группа
# image = '039020.f761f8aa.1634264166.postprocessed.png'

directory_files = images.get_all_images()
db_files = db.get_all_images()
new_files = [x for x in directory_files if x not in db_files]

print('Images in DIR:')
for i in directory_files:
    print(i)

print('Images in DB:')
for i in db_files:
    print(i)

print('New IMAGES')
print(new_files)


# print(*images.get_all_images())
# print(images.get_oldest_image())

# print(images.get_image_prompt(image))
# group_before = db.get_image_group(image)
# print(group_before)

# db.remove_images(group_before)

# group_after = db.get_image_group(image)
# print(group_after)