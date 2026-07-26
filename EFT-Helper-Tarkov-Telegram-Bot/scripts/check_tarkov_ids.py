"""Check tarkov_id in weapons database."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("=== Проверка tarkov_id в БД ===\n")

# Check AK weapons
c.execute("SELECT name_ru, tarkov_id FROM weapons WHERE name_ru LIKE '%АК%' LIMIT 5")
print("АК оружие:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1] or 'НЕТ ID'}")

print("\n")

# Check M4 weapons
c.execute("SELECT name_ru, tarkov_id FROM weapons WHERE name_en LIKE '%M4%' LIMIT 5")
print("M4 оружие:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1] or 'НЕТ ID'}")

print("\n")

# Count weapons with tarkov_id
c.execute("SELECT COUNT(*) FROM weapons WHERE tarkov_id IS NOT NULL")
total_with_id = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM weapons")
total = c.fetchone()[0]

print(f"Всего оружия: {total}")
print(f"С tarkov_id: {total_with_id}")
print(f"Без tarkov_id: {total - total_with_id}")

conn.close()
