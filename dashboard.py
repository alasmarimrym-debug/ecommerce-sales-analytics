
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# ----------------------------
# Page configuration
# ----------------------------
st.set_page_config(
    page_title="Sales Analytics",
    page_icon="📊",
    layout="wide",
)

st.title("Sales Analytics Dashboard")
st.caption("E-commerce sales performance and insights")


# ----------------------------
# Load data
# ----------------------------
DATA_FILE = Path(__file__).parent / "cleaned_sales.csv"


@st.cache_data
def load_data(file_path):
    return pd.read_csv(file_path)


if not DATA_FILE.exists():
    st.error(f"Data file not found: {DATA_FILE}")
    st.stop()

try:
    df = load_data(DATA_FILE)
except Exception as error:
    st.error(f"Could not read the CSV file: {error}")
    st.stop()

if df.empty:
    st.error("The CSV file contains no data.")
    st.stop()


# ----------------------------
# Detect column names
# ----------------------------
def find_column(candidates):
    normalized = {
        str(column).strip().lower().replace(" ", "_"): column
        for column in df.columns
    }

    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]

    return None


date_col = find_column([
    "order_date", "date", "orderdate", "sale_date", "transaction_date"
])

product_col = find_column([
    "product", "product_name", "item", "item_name"
])

category_col = find_column([
    "category", "product_category", "product_type"
])

quantity_col = find_column([
    "quantity", "qty", "units_sold"
])

price_col = find_column([
    "unit_price", "price", "product_price", "unitprice"
])

revenue_col = find_column([
    "revenue", "total_revenue", "sales_amount",
    "total_amount", "total_sales"
])

order_col = find_column([
    "order_id", "orderid", "transaction_id", "invoice_id"
])

region_col = find_column([
    "region", "country", "city", "location"
])


# ----------------------------
# Validate essential columns
# ----------------------------
if quantity_col is None:
    st.error(
        "Quantity column was not detected. "
        f"Available columns: {df.columns.tolist()}"
    )
    st.stop()

if revenue_col is None and price_col is None:
    st.error(
        "Neither a revenue column nor a unit price column was detected. "
        f"Available columns: {df.columns.tolist()}"
    )
    st.stop()


# ----------------------------
# Prepare data
# ----------------------------
df = df.copy()

df[quantity_col] = pd.to_numeric(
    df[quantity_col], errors="coerce"
)

if price_col is not None:
    df[price_col] = pd.to_numeric(
        df[price_col], errors="coerce"
    )

if revenue_col is not None:
    df[revenue_col] = pd.to_numeric(
        df[revenue_col], errors="coerce"
    )
    df["_revenue"] = df[revenue_col]
else:
    df["_revenue"] = df[quantity_col] * df[price_col]

df["_quantity"] = df[quantity_col]

if date_col is not None:
    df[date_col] = pd.to_datetime(
        df[date_col], errors="coerce"
    )

df = df.dropna(subset=["_revenue", "_quantity"])

if df.empty:
    st.error("No valid sales records remain after data preparation.")
    st.stop()


# ----------------------------
# Sidebar filters
# ----------------------------
st.sidebar.header("Filters")

filtered = df.copy()

if date_col is not None:
    valid_dates = df[date_col].dropna()

    if not valid_dates.empty:
        start_date = valid_dates.min().date()
        end_date = valid_dates.max().date()

        selected_dates = st.sidebar.date_input(
            "Order date range",
            value=(start_date, end_date),
            min_value=start_date,
            max_value=end_date,
        )

        if isinstance(selected_dates, (tuple, list)):
            if len(selected_dates) == 2:
                start, end = selected_dates
                filtered = filtered[
                    filtered[date_col].dt.date.between(start, end)
                ]
            elif len(selected_dates) == 1:
                filtered = filtered[
                    filtered[date_col].dt.date == selected_dates[0]
                ]

if category_col is not None:
    categories = sorted(
        filtered[category_col].dropna().astype(str).unique()
    )
    selected_categories = st.sidebar.multiselect(
        "Product category",
        categories,
        default=categories,
    )
    filtered = filtered[
        filtered[category_col].astype(str).isin(selected_categories)
    ]

if product_col is not None:
    products = sorted(
        filtered[product_col].dropna().astype(str).unique()
    )
    selected_products = st.sidebar.multiselect(
        "Product",
        products,
        default=products,
    )
    filtered = filtered[
        filtered[product_col].astype(str).isin(selected_products)
    ]

if region_col is not None:
    regions = sorted(
        filtered[region_col].dropna().astype(str).unique()
    )
    selected_regions = st.sidebar.multiselect(
        "Region",
        regions,
        default=regions,
    )
    filtered = filtered[
        filtered[region_col].astype(str).isin(selected_regions)
    ]


# ----------------------------
# KPI metrics
# ----------------------------
st.subheader("Key Performance Indicators")

total_revenue = filtered["_revenue"].sum()
total_units = filtered["_quantity"].sum()

if order_col is not None:
    total_orders = filtered[order_col].nunique()
else:
    # Without an order ID, rows are records, not necessarily unique orders.
    total_orders = len(filtered)

average_revenue = (
    total_revenue / total_orders if total_orders else 0
)

m1, m2, m3, m4 = st.columns(4)

m1.metric("Total Revenue", f"{total_revenue:,.2f}")
m2.metric("Units Sold", f"{total_units:,.0f}")
m3.metric(
    "Orders" if order_col else "Sales Records",
    f"{total_orders:,}",
)
m4.metric("Revenue per Order/Record", f"{average_revenue:,.2f}")

st.divider()

if filtered.empty:
    st.warning("No records match the selected filters.")
    st.stop()


# ----------------------------
# Revenue over time
# ----------------------------
if date_col is not None:
    time_data = filtered.dropna(subset=[date_col]).copy()

    if not time_data.empty:
        time_data["_period"] = (
            time_data[date_col].dt.to_period("M").astype(str)
        )

        revenue_time = (
            time_data.groupby("_period", as_index=False)["_revenue"]
            .sum()
            .sort_values("_period")
        )

        st.subheader("Revenue Over Time")

        fig_time = px.line(
            revenue_time,
            x="_period",
            y="_revenue",
            markers=True,
            labels={
                "_period": "Month",
                "_revenue": "Revenue",
            },
            title="Monthly Revenue",
        )
        fig_time.update_layout(
            hovermode="x unified",
            xaxis_title="Month",
            yaxis_title="Revenue",
        )
        st.plotly_chart(fig_time, use_container_width=True)


# ----------------------------
# Category and product analysis
# ----------------------------
left, right = st.columns(2)

with left:
    if category_col is not None:
        st.subheader("Revenue by Category")

        category_data = (
            filtered.groupby(category_col, as_index=False)["_revenue"]
            .sum()
            .sort_values("_revenue", ascending=False)
        )

        fig_category = px.bar(
            category_data,
            x=category_col,
            y="_revenue",
            color=category_col,
            text_auto=".2s",
            labels={
                category_col: "Category",
                "_revenue": "Revenue",
            },
        )
        fig_category.update_layout(showlegend=False)
        st.plotly_chart(fig_category, use_container_width=True)

with right:
    if product_col is not None:
        st.subheader("Top Products by Revenue")

        product_data = (
            filtered.groupby(product_col, as_index=False)["_revenue"]
            .sum()
            .sort_values("_revenue", ascending=False)
            .head(10)
            .sort_values("_revenue")
        )

        fig_products = px.bar(
            product_data,
            x="_revenue",
            y=product_col,
            orientation="h",
            labels={
                product_col: "Product",
                "_revenue": "Revenue",
            },
            text_auto=".2s",
        )
        st.plotly_chart(fig_products, use_container_width=True)


# ----------------------------
# Regional analysis
# ----------------------------
if region_col is not None:
    st.subheader("Revenue by Region")

    region_data = (
        filtered.groupby(region_col, as_index=False)["_revenue"]
        .sum()
        .sort_values("_revenue", ascending=False)
    )

    fig_region = px.bar(
        region_data,
        x=region_col,
        y="_revenue",
        color=region_col,
        labels={
            region_col: "Region",
            "_revenue": "Revenue",
        },
    )
    fig_region.update_layout(showlegend=False)
    st.plotly_chart(fig_region, use_container_width=True)


# ----------------------------
# Data table and download
# ----------------------------
with st.expander("View filtered data"):
    st.dataframe(filtered, use_container_width=True)

csv_data = filtered.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download filtered data as CSV",
    data=csv_data,
    file_name="filtered_sales.csv",
    mime="text/csv",
)

st.caption(
    "Dashboard source: cleaned_sales.csv | "
    "Figures reflect the currently selected filters."
)
