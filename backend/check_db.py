import sqlite3
conn = sqlite3.connect('sql_app.db')
c = conn.cursor()

print("=== ITEMS ===")
for r in c.execute('SELECT id, name, folder_id FROM items').fetchall():
    print(f"  id={r[0]} name={r[1]} folder_id={r[2]}")

print("\n=== EXPENSES ===")
for r in c.execute('SELECT id, item_id, description, amount, user_id FROM expenses').fetchall():
    print(f"  id={r[0]} item_id={r[1]} desc={r[2]} amount={r[3]} user_id={r[4]}")

conn.close()
