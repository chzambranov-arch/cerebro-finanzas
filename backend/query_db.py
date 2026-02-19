import sqlite3

conn = sqlite3.connect('sql_app.db')
cursor = conn.cursor()

print("=== FOLDERS ===")
cursor.execute('SELECT id, name, user_id, initial_balance FROM folders')
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Name: {row[1]}, User: {row[2]}, Balance: {row[3]}")

print("\n=== ITEMS ===")
cursor.execute('SELECT id, folder_id, name, type, budget FROM items')
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Folder_ID: {row[1]}, Name: {row[2]}, Type: {row[3]}, Budget: {row[4]}")

conn.close()
