import os, sys
from sqlalchemy import create_engine, text
DATABASE_URL = os.getenv("DATABASE_URL")
def test_freshness():
    print("Checking data freshness...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM raw.crimes")).fetchone()[0]
            assert count >= 1000, f"Only {count:,} rows — expected 1,000+"
            cities = {r[0] for r in conn.execute(text("SELECT DISTINCT city FROM raw.crimes")).fetchall()}
            expected = {"Hull","London","Birmingham","Manchester","Leeds","Sheffield","Liverpool","Bristol","Nottingham","Newcastle"}
            assert not expected - cities, f"Missing cities: {expected - cities}"
        print(f"  ✅ {count:,} rows, all 10 cities present")
    except Exception as e:
        print(f"  ❌ FAILED — {e}"); sys.exit(1)
if __name__ == "__main__":
    test_freshness()
    print("Data freshness check passed.")
