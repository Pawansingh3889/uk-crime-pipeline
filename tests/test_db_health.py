import os, sys
from sqlalchemy import create_engine, text
DATABASE_URL = os.getenv("DATABASE_URL")
def test_db():
    print("Checking database...")
    if not DATABASE_URL: print("  ❌ DATABASE_URL not set"); sys.exit(1)
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).fetchone()[0] == 1
            count = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='analytics'")).fetchone()[0]
            assert count >= 3, f"Expected 3+ analytics tables, found {count}"
        print("  ✅ Database OK")
    except Exception as e:
        print(f"  ❌ FAILED — {e}"); sys.exit(1)
if __name__ == "__main__":
    test_db()
    print("Database health check passed.")
