import sqlite3
conn = sqlite3.connect('backend/dev.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables in database:')
for t in tables:
    print(' -', t[0])
conn.close()
