import sqlite3
import os

db_path = 'data/spbe_rag.db'
if not os.path.exists(db_path):
    print("DB not found at", db_path)
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE users ADD COLUMN hashed_password VARCHAR')
        c.execute('ALTER TABLE users ADD COLUMN roles VARCHAR DEFAULT "[]"')
        c.execute('ALTER TABLE users ADD COLUMN department VARCHAR')
        conn.commit()
        print('Columns added successfully')
    except Exception as e:
        print('Error or columns already exist:', e)

    try:
        c.execute('''
        CREATE TABLE IF NOT EXISTS token_blacklist (
            jti VARCHAR PRIMARY KEY,
            expires_at DATETIME NOT NULL
        )
        ''')
        conn.commit()
        print('TokenBlacklist table created')
    except Exception as e:
        print('Error creating table:', e)
    
    conn.close()
