import sqlite3

# Connect to database file (creates it instantly if it doesn't exist)
conn = sqlite3.connect('mloc_db.db')
cur = conn.cursor()

# Create table matching your original project schema requirements safely for SQLite
cur.execute('''
CREATE TABLE IF NOT EXISTS saved_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL DEFAULT 'Untitled',
    language    TEXT NOT NULL DEFAULT 'python',
    code        TEXT NOT NULL,
    output      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')

# Insert sample row
cur.execute("INSERT INTO saved_codes (title, language, code, output) VALUES (?, ?, ?, ?)", 
            ('Hello World (Python)', 'python', 'print("Hello, World!")\nprint("Welcome to MLOC!")', 'Hello, World!\nWelcome to MLOC!'))

conn.commit()
conn.close()
print("🔥 Fresh database created successfully!")