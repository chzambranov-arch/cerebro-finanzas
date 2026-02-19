import sqlite3

conn = sqlite3.connect('sql_app.db')
cursor = conn.cursor()

# 1. Reset Balance for Folder 1 (CASA)
# The user's screenshot suggests the math was: Start 10k - 20k - 20k = -30k.
# So we reset it to 10,000.
cursor.execute('UPDATE folders SET initial_balance = 10000 WHERE id = 1')
print(f"Reset Folder 1 balance to 10000. Rows affected: {cursor.rowcount}")

# 2. Delete Sporadic Expenses for Folder 1
cursor.execute('DELETE FROM expenses WHERE folder_id = 1 AND item_id IS NULL')
print(f"Deleted sporadic expenses. Rows affected: {cursor.rowcount}")

conn.commit()
conn.close()
