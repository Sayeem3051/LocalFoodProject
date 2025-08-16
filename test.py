import sqlite3
conn = sqlite3.connect("food_wastage.db")
print("Providers in DB:", conn.execute("SELECT * FROM providers").fetchall())
