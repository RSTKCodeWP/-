"""Fix database - add missing columns and tables."""
import sqlite3

# Прямое подключение к SQLite
conn = sqlite3.connect('data/oleg.db')
cursor = conn.cursor()

# Add dislikes_count column
try:
    cursor.execute('ALTER TABLE quotes ADD COLUMN dislikes_count INTEGER DEFAULT 0')
    conn.commit()
    print('Column dislikes_count added')
except Exception as e:
    print(f'Column may already exist: {e}')

# Create quote_votes table
try:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quote_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            vote_type VARCHAR(10) NOT NULL,
            created_at DATETIME,
            FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    print('Table quote_votes created')
except Exception as e:
    print(f'Table may already exist: {e}')

# Create indexes
try:
    cursor.execute('CREATE INDEX IF NOT EXISTS ix_quote_votes_quote_id ON quote_votes(quote_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS ix_quote_votes_user_id ON quote_votes(user_id)')
    conn.commit()
    print('Indexes created')
except Exception as e:
    print(f'Indexes may already exist: {e}')

conn.close()
print('Done!')
