"""Migration script to add admin features support."""
import asyncio
import aiosqlite
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate():
    """Add last_activity column to users table."""
    db_path = "data/eft_helper.db"
    
    print("🔄 Миграция базы данных для админ панели...")
    
    async with aiosqlite.connect(db_path) as db:
        # Check if last_activity column exists
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "last_activity" not in column_names:
            print("   📝 Добавление колонки last_activity...")
            try:
                await db.execute("ALTER TABLE users ADD COLUMN last_activity INTEGER DEFAULT 0")
                await db.commit()
                print("   ✅ Колонка last_activity добавлена")
            except Exception as e:
                print(f"   ⚠️  Ошибка: {e}")
        else:
            print("   ✓ Колонка last_activity уже существует")
        
        # Update existing users with current timestamp
        from datetime import datetime
        current_timestamp = int(datetime.now().timestamp())
        
        async with db.execute("SELECT COUNT(*) FROM users WHERE last_activity = 0") as cursor:
            zero_count = (await cursor.fetchone())[0]
        
        if zero_count > 0:
            print(f"   📝 Обновление {zero_count} пользователей...")
            await db.execute(
                "UPDATE users SET last_activity = ? WHERE last_activity = 0",
                (current_timestamp,)
            )
            await db.commit()
            print("   ✅ Пользователи обновлены")
    
    print("✅ Миграция завершена успешно!")


if __name__ == "__main__":
    asyncio.run(migrate())
