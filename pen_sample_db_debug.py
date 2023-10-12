import sqlite3

# Создать базу
with sqlite3.connect("tmp/test.db") as connection:
    cursor = connection.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS mytable (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    age INTEGER)''')
    connection.commit()

print('>> База успешно создана')

with sqlite3.connect("tmp/test.db") as connection:
    cursor = connection.cursor()
    test_data = [
        ('Иван', 25),
        ('Мария', 30),
        ('Алексей', 22),
        ('Екатерина', 35),
        ('Петр', 28)
    ]

    cursor.executemany("INSERT INTO mytable (name, age) VALUES (?, ?)", test_data)
    connection.commit()

print('>> Записи добавлены')

print('>> Берем записи из базы...')
print('Людишки старше 25:')
with sqlite3.connect("tmp/test.db") as connection:
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM mytable WHERE age > 25")
    results = cursor.fetchall()
    for result in results:
        print(result[0])

print('>> База удалена')
with sqlite3.connect("tmp/test.db") as connection:
    cursor = connection.cursor()
    cursor.execute('''DROP TABLE mytable''')
    connection.commit()