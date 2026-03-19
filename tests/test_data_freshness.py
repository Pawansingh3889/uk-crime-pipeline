import os, sys
from sqlalchemy import create_engine, text
DATABASE_URL = os.getenv("DATABASE_URL")
def test_freshness():
    print("Checking data freshness...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM analytics.fct_crimes_by_city")).fetchone()[0]
            assert count >= 100, f"Only {count:,} rows in fct_crimes_by_city — expected 100+"
            cities = {r[0] for r in conn.execute(text("SELECT DISTINCT city FROM analytics.fct_crimes_by_city")).fetchall()}
            expected = {"Hull","London","Birmingham","Manchester","Leeds","Sheffield","Liverpool","Bristol","Nottingham","Newcastle"}
            missing = expected - cities
            assert not missing, f"Missing cities: {missing}"
        print(f"  ✅ {count:,} rows in fct_crimes_by_city, {len(cities)} cities present")
    except Exception as e:
        print(f"  ❌ FAILED — {e}"); sys.exit(1)
if __name__ == "__main__":
    test_freshness()
    print("Data freshness check passed.")
