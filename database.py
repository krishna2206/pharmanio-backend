import sqlite3

DB_FILE = "pharmacies.db"


def init_db():
    """Initialize the database with all necessary tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pharmacies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            latitude REAL,
            longitude REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_id) REFERENCES cities (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS on_duty_pharmacies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            pharmacy_ids TEXT,  -- JSON array of pharmacy IDs
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pharmacies_city_id ON pharmacies(city_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pharmacies_coordinates ON pharmacies(latitude, longitude)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pharmacies_name ON pharmacies(name)")
    
    conn.commit()
    conn.close()
