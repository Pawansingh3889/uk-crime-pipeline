import streamlit as st
import pandas as pd
import plotly.express as px
import time
from sqlalchemy import create_engine, text


def get_db_url():
    """Build DATABASE_URL from secrets — supports both single URL and individual fields."""
    try:
        # Try single DATABASE_URL first
        return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    try:
        # Build from individual fields
        host = st.secrets["POSTGRES_HOST"]
        port = st.secrets.get("POSTGRES_PORT", "5432")
        db   = st.secrets["POSTGRES_DB"]
        user = st.secrets["POSTGRES_USER"]
        pw   = st.secrets["POSTGRES_PASSWORD"]
        return f"postgresql://{user}:{pw}@{host}:{port}/{db}?sslmode=require"
    except Exception:
        return "postgresql://postgres:crimes123@localhost:5432/crime_db"


st.set_page_config(page_title="UK Crime Pipeline", page_icon="🔍", layout="wide")


def _create_engine_with_retry():
    """Create engine with retry logic for Neon cold starts."""
    db_url = get_db_url()
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 30},
    )
    # Neon free tier suspends after inactivity — first connect wakes it up
    for attempt in range(3):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise
    return engine


@st.cache_data(ttl=300)
def load_data():
    engine = _create_engine_with_retry()
    monthly  = pd.read_sql("SELECT * FROM analytics.fct_monthly_trend", engine)
    by_city  = pd.read_sql("SELECT * FROM analytics.fct_crimes_by_city", engine)
    hotspots = pd.read_sql("SELECT * FROM analytics.fct_crime_hotspots", engine)
    engine.dispose()
    return monthly, by_city, hotspots


try:
    monthly, by_city, hotspots = load_data()
except Exception as e:
    st.error(f"Database connection failed — the Neon database may be suspended. Try refreshing in 30 seconds.")
    st.caption(f"Error: {type(e).__name__}")
    st.stop()

st.title("🔍 UK Crime Analytics Dashboard")
st.caption("Live data from Police UK API · 10 cities · 6 months · 99,675 incidents")

total    = monthly["total_crimes"].sum()
cities   = monthly["city"].nunique()
months   = monthly["month"].nunique()
unsolved = monthly["unsolved"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Incidents",     f"{total:,.0f}")
c2.metric("Cities Covered",      f"{cities}")
c3.metric("Months Covered",      f"{months}")
c4.metric("Under Investigation", f"{unsolved:,.0f}")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Monthly crime trend by city")
    city_filter = st.multiselect(
        "Filter cities",
        options=sorted(monthly["city"].unique()),
        default=["Hull", "Manchester", "Birmingham"],
    )
    filtered = monthly[monthly["city"].isin(city_filter)] if city_filter else monthly
    fig = px.line(filtered.sort_values("month"), x="month", y="total_crimes",
                  color="city", markers=True,
                  labels={"total_crimes": "Total incidents", "month": "Month"})
    fig.update_layout(height=350, margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Total crimes by city")
    city_totals = monthly.groupby("city")["total_crimes"].sum().reset_index()
    city_totals = city_totals.sort_values("total_crimes", ascending=True)
    fig2 = px.bar(city_totals, x="total_crimes", y="city", orientation="h",
                  color="total_crimes", color_continuous_scale="Reds",
                  labels={"total_crimes": "Total incidents", "city": "City"})
    fig2.update_layout(height=350, margin=dict(t=10), showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("Crime category breakdown")

col3, col4 = st.columns([1, 2])

with col3:
    selected_city = st.selectbox(
        "Select city",
        options=sorted(by_city["city"].unique()),
        index=list(sorted(by_city["city"].unique())).index("Hull")
    )

with col4:
    city_cats = (by_city[by_city["city"] == selected_city]
                 .groupby("category")["crime_count"].sum().reset_index()
                 .sort_values("crime_count", ascending=False).head(10))
    fig3 = px.bar(city_cats, x="crime_count", y="category", orientation="h",
                  color="crime_count", color_continuous_scale="Blues",
                  labels={"crime_count": "Incidents", "category": "Crime type"})
    fig3.update_layout(height=350, margin=dict(t=10), showlegend=False)
    st.plotly_chart(fig3, use_container_width=True)

st.divider()
st.subheader("Top crime hotspots")

hotspot_city = st.selectbox(
    "Select city for hotspots",
    options=sorted(hotspots["city"].unique()),
    key="hotspot_city"
)

city_hotspots = (hotspots[hotspots["city"] == hotspot_city]
                 .sort_values("incident_count", ascending=False)
                 .head(20).reset_index(drop=True))
city_hotspots.index += 1

st.dataframe(
    city_hotspots[["street_name", "category", "incident_count"]],
    use_container_width=True,
    column_config={
        "street_name":    st.column_config.TextColumn("Street"),
        "category":       st.column_config.TextColumn("Crime type"),
        "incident_count": st.column_config.NumberColumn("Incidents", format="%d"),
    }
)

st.caption("Data source: Police UK API · Pipeline: Python → PostgreSQL → dbt → Streamlit")