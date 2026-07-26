"""Clean old weapons without tarkov_id from database."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")

print("=" * 60)
print("  Очистка устаревших данных из БД")
print("=" * 60)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Count before
c.execute("SELECT COUNT(*) FROM weapons")
total_before = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM weapons WHERE tarkov_id IS NULL")
old_weapons = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM modules WHERE tarkov_id IS NULL")
old_modules = c.fetchone()[0]

print(f"\n📊 Текущее состояние:")
print(f"  Оружие всего: {total_before}")
print(f"  Оружие без tarkov_id (удалить): {old_weapons}")
print(f"  Модули без tarkov_id (удалить): {old_modules}")

if old_weapons == 0 and old_modules == 0:
    print("\n✅ Нет устаревших записей для удаления")
    conn.close()
    sys.exit(0)

print(f"\n⚠️  Будет удалено:")
print(f"  - {old_weapons} устаревших оружий")
print(f"  - {old_modules} устаревших модулей")

response = input("\nПродолжить? (yes/no): ").strip().lower()

if response != "yes":
    print("❌ Отменено")
    conn.close()
    sys.exit(0)

print("\n🗑️  Удаление устаревших записей...")

# Delete old weapons
c.execute("DELETE FROM weapons WHERE tarkov_id IS NULL")
deleted_weapons = c.rowcount

# Delete old modules
c.execute("DELETE FROM modules WHERE tarkov_id IS NULL")
deleted_modules = c.rowcount

conn.commit()

# Count after
c.execute("SELECT COUNT(*) FROM weapons")
total_after = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM modules")
modules_after = c.fetchone()[0]

print(f"\n✅ Удаление завершено:")
print(f"  Удалено оружий: {deleted_weapons}")
print(f"  Удалено модулей: {deleted_modules}")
print(f"  Осталось оружий: {total_after}")
print(f"  Осталось модулей: {modules_after}")

print("\n💡 Рекомендуется запустить синхронизацию:")
print("  .venv\\Scripts\\python.exe scripts/sync_tarkov_data.py")

conn.close()
