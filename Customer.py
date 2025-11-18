import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from pymongo import MongoClient
import json

# ---------------------------
# Config
# ---------------------------
st.set_page_config(page_title="Customer Revenue & Churn Dashboard", layout="wide")
st.title("📊 Customer Revenue & Churn Intelligence Dashboard")

# ---------------------------
# MongoDB Connection
# ---------------------------
@st.cache_resource
def get_mongo_client():
    mongo_secrets = st.secrets["mongo"]
    client = MongoClient(mongo_secrets["uri"])
    return client[mongo_secrets["db_name"]]


def insert_to_mongo(df, collection_name):
    db = get_mongo_client()
    coll = db[collection_name]
    records = json.loads(df.to_json(orient="records"))
    coll.insert_many(records)


# ---------------------------
# Upload CSV File
# ---------------------------
uploaded_file = st.file_uploader("Upload your cleaned customer transaction CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.lower()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")

    if "revenue" not in df.columns:
        if "unit_price" in df.columns and "quantity" in df.columns:
            df["revenue"] = df["unit_price"] * df["quantity"]
        else:
            df["revenue"] = 0.0

    insert_to_mongo(df, st.secrets["mongo"]["collection_name"])
    st.success("🎉 Data uploaded and stored in MongoDB!")

    st.session_state["data"] = df


if "data" not in st.session_state:
    st.info("👆 Upload a CSV to begin exploring your data.")
    st.stop()

df = st.session_state["data"]


# ---------------------------
# Helper Functions
# ---------------------------
def build_customer_df(df):
    return (
        df.groupby("customer_id")
        .agg(
            customer_name=("customer_name", "first") if "customer_name" in df.columns else ("customer_id", "first"),
            total_revenue=("revenue", "sum"),
            last_order=("order_date", "max"),
            num_orders=("transaction_id", "count"),
            city=("city", "first"),
            segment=("segment", "first"),
            is_churned=("is_churned", "max") if "is_churned" in df.columns else (lambda _: False),
        )
        .reset_index()
    )


df_customer = build_customer_df(df)


# ---------------------------
# Filters
# ---------------------------
st.sidebar.header("Filters")
cities = st.sidebar.multiselect("City", df["city"].dropna().unique(), default=None)
segments = st.sidebar.multiselect("Segment", df["segment"].dropna().unique(), default=None)
date_range = st.sidebar.date_input(
    "Order Date Range",
    value=(df["order_date"].min(), df["order_date"].max()),
)

filtered_df = df.copy()
if cities:
    filtered_df = filtered_df[filtered_df["city"].isin(cities)]
if segments:
    filtered_df = filtered_df[filtered_df["segment"].isin(segments)]
if len(date_range) == 2:
    filtered_df = filtered_df[
        (filtered_df["order_date"] >= pd.to_datetime(date_range[0])) &
        (filtered_df["order_date"] <= pd.to_datetime(date_range[1]))
    ]

df_customer_filtered = build_customer_df(filtered_df)


# ---------------------------
# Dashboard Tabs
# ---------------------------
tab1, tab2 = st.tabs(["📈 Overview Dashboard", "🧑‍💼 Customer Explorer"])


# Overview
with tab1:
    st.subheader("📊 KPIs")

    total_revenue = filtered_df["revenue"].sum()
    churn_rate = df_customer_filtered["is_churned"].mean() * 100 if "is_churned" in df_customer_filtered.columns else 0
    avg_clv = df_customer_filtered["total_revenue"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Revenue", f"₹{total_revenue:,.2f}")
    col2.metric("Churn Rate", f"{churn_rate:.2f}%")
    col3.metric("Avg CLV", f"₹{avg_clv:,.2f}")

    st.markdown("---")
    st.subheader("Revenue Trend")

    revenue_trend = (
        filtered_df.set_index("order_date")
        .resample("M")["revenue"]
        .sum()
        .reset_index()
    )

    chart = alt.Chart(revenue_trend).mark_line(point=True).encode(
        x="order_date:T", y="revenue:Q", tooltip=["order_date:T", "revenue:Q"]
    )
    st.altair_chart(chart, use_container_width=True)


# Customer Explorer
with tab2:
    st.subheader("🔍 Search Customers")
    search_q = st.text_input("Search by name or email")

    customer_list = df_customer_filtered.copy()
    if search_q:
        mask = (
            customer_list["customer_name"].str.contains(search_q, case=False, na=False)
        )
        customer_list = customer_list[mask]

    st.dataframe(
        customer_list[["customer_id", "customer_name", "total_revenue", "city", "segment", "is_churned"]],
        use_container_width=True,
        height=300,
    )

    st.subheader("📂 Customer Profile")
    selected_customer = st.selectbox("Select Customer", customer_list["customer_id"].tolist())
    profile = customer_list[customer_list["customer_id"] == selected_customer].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Name", profile["customer_name"])
    col2.metric("Total Spent", f"₹{profile['total_revenue']:,.2f}")
    col3.metric("Orders", profile["num_orders"])

    if "last_order" in profile:
        st.metric("Last Active", str(profile["last_order"].date()))

    if "is_churned" in profile:
        st.metric("Churned?", "Yes" if profile["is_churned"] else "No")
