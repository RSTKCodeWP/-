import sqlite3

conn = sqlite3.connect('data/oleg.db')
try:
    conn.execute('ALTER TABLE chats ADD COLUMN persona VARCHAR(50) DEFAULT "oleg"')
    conn.commit()
    print('✓ Column persona added to chats table')
except sqlite3.OperationalError as e:
    if 'duplicate column name' in str(e):
        print('✓ Column persona already exists')
    else:
        print(f'✗ Error: {e}')
finally:
    conn.close()
