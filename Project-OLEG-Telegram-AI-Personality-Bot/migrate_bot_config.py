#!/usr/bin/env python3
"""
Миграция: добавление колонок pvp_accept_timeout и persona в bot_configs.

Запуск внутри контейнера:
    python migrate_bot_config.py

Или через docker:
    docker exec <container_name> python migrate_bot_config.py
"""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "/app/data/oleg.db")

# Для локального запуска
if not os.path.exists(DB_PATH):
    DB_PATH = "app/data/oleg.db"
if not os.path.exists(DB_PATH):
    DB_PATH = "data/oleg.db"

print(f"Using database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Добавляем pvp_accept_timeout
try:
    cursor.execute("ALTER TABLE bot_configs ADD COLUMN pvp_accept_timeout INTEGER DEFAULT 120")
    print("✅ Added: pvp_accept_timeout")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⏭️  Exists: pvp_accept_timeout")
    else:
        print(f"❌ Error: {e}")

# Добавляем persona
try:
    cursor.execute("ALTER TABLE bot_configs ADD COLUMN persona VARCHAR(20) DEFAULT 'oleg'")
    print("✅ Added: persona")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("⏭️  Exists: persona")
    else:
        print(f"❌ Error: {e}")

conn.commit()
conn.close()

print("\n✅ Migration complete!")
