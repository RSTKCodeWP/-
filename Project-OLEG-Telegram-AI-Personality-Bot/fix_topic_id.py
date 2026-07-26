#!/usr/bin/env python3
"""Fix missing columns in database tables."""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "./data/oleg.db")


def add_column_if_missing(cursor, table: str, column: str, col_type: str, default: str = None):
    """Add column to table if it doesn't exist."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    
    if column in columns:
        print(f"  ✓ {table}.{column} already exists")
        return False
    
    default_clause = f" DEFAULT {default}" if default else ""
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}")
    print(f"  + Added {table}.{column}")
    return True


def fix_database():
    """Fix all missing columns."""
    print(f"Connecting to database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    changes = False
    
    # Fix messages table
    print("\n[messages table]")
    if add_column_if_missing(cursor, "messages", "topic_id", "INTEGER"):
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_messages_topic_id ON messages(topic_id)")
        changes = True
    
    # Fix quotes table
    print("\n[quotes table]")
    if add_column_if_missing(cursor, "quotes", "dislikes_count", "INTEGER", "0"):
        changes = True
    
    # Create quote_votes table if missing
    print("\n[quote_votes table]")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quote_votes'")
    if cursor.fetchone():
        print("  ✓ quote_votes table already exists")
    else:
        cursor.execute("""
            CREATE TABLE quote_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vote_type VARCHAR(10) NOT NULL,
                created_at DATETIME,
                FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_quote_votes_quote_id ON quote_votes(quote_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_quote_votes_user_id ON quote_votes(user_id)")
        print("  + Created quote_votes table")
        changes = True
    
    if changes:
        conn.commit()
        print("\n✅ Database fixed!")
    else:
        print("\n✅ Database is up to date!")
    
    conn.close()


if __name__ == "__main__":
    fix_database()
