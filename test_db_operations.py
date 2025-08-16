import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect("food_wastage.db")

print("=== DATABASE TEST ===")

# Check if tables exist
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"Tables in database: {tables}")

# Check food_listings table structure
try:
    cursor.execute("PRAGMA table_info(food_listings);")
    columns = cursor.fetchall()
    print(f"\nFood_listings table columns: {columns}")
except Exception as e:
    print(f"Error checking food_listings table: {e}")

# Check current data in food_listings
try:
    df = pd.read_sql_query("SELECT * FROM food_listings LIMIT 5", conn)
    print(f"\nCurrent food_listings data (first 5 rows):")
    print(df)
    print(f"Total rows in food_listings: {len(df)}")
except Exception as e:
    print(f"Error reading food_listings: {e}")

# Test adding a new record
print("\n=== TESTING ADD OPERATION ===")
try:
    # Add a test record
    test_data = (9999, "Test Food", 10, "2024-12-31", 1, "Test Provider", "Test Location", "Test Type", "Test Meal")
    conn.execute("""
    INSERT INTO food_listings (Food_ID, Food_Name, Quantity, Expiry_Date,
                               Provider_ID, Provider_Type, Location, Food_Type, Meal_Type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_data)
    conn.commit()
    print("✅ Test record added successfully!")
    
    # Verify the record was added
    df_after = pd.read_sql_query("SELECT * FROM food_listings WHERE Food_ID = 9999", conn)
    print(f"Verification - Found {len(df_after)} records with Food_ID = 9999")
    if len(df_after) > 0:
        print("✅ Record found in database!")
        print(df_after)
    
    # Clean up - remove test record
    conn.execute("DELETE FROM food_listings WHERE Food_ID = 9999")
    conn.commit()
    print("✅ Test record cleaned up!")
    
except Exception as e:
    print(f"❌ Error in add operation: {e}")

# Check providers table
print("\n=== CHECKING PROVIDERS TABLE ===")
try:
    df_providers = pd.read_sql_query("SELECT * FROM providers LIMIT 3", conn)
    print(f"Providers data (first 3 rows):")
    print(df_providers)
except Exception as e:
    print(f"Error reading providers: {e}")

conn.close()
print("\n=== TEST COMPLETE ===")
