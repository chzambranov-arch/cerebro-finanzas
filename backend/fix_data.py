
from app.database import SessionLocal
from app.models.models import User
from app.models.budget import Category, Budget
from app.models.finance import Expense

db = SessionLocal()
user_id = 2 # Christian

print("Normalizing categories for Christian...")

# 1. Normalize sections to UPPERCASE
cats = db.query(Category).filter(Category.user_id == user_id).all()
for c in cats:
    old_sec = c.section
    new_sec = c.section.strip().upper()
    if old_sec != new_sec:
        print(f"  ID {c.id}: [{old_sec}] -> [{new_sec}]")
        c.section = new_sec

# 2. Normalize category names (strip and maybe title case?)
for c in cats:
    old_name = c.name
    new_name = c.name.strip()
    if old_name != new_name:
        print(f"  ID {c.id}: Name change '{old_name}' -> '{new_name}'")
        c.name = new_name

db.commit()

# 3. Consolidate duplicates (Section + Name)
cats = db.query(Category).filter(Category.user_id == user_id).all()
seen = {} # (section, name) -> Category
to_delete = []

for c in cats:
    key = (c.section, c.name.lower())
    if key in seen:
        master = seen[key]
        print(f"  Merging ID {c.id} into ID {master.id} (Section: {c.section}, Name: {c.name})")
        # Sum budgets
        master.budget += c.budget
        to_delete.append(c)
    else:
        seen[key] = c

for c in to_delete:
    # First update expenses pointing to the one being deleted (if they were exactly matching)
    # Actually expenses have strings, so we just need to make sure the master exists.
    db.delete(c)

db.commit()

# 4. Normalize Expenses
expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
for e in expenses:
    if e.section: e.section = e.section.strip().upper()
    if e.category: e.category = e.category.strip()

db.commit()
print("Done!")
db.close()
