import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------
# PAGE SETUP
# -----------------------------
st.set_page_config(page_title="Caterpillar Inventory App", layout="wide")
st.title("Caterpillar Inventory Policy App")

# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data
def load_data():
    model_df = pd.read_excel("data/master_inventory_model.xlsx")
    weekly_full = pd.read_excel("data/weekly_demand_full.xlsx")
    weekly_full["week_start"] = pd.to_datetime(weekly_full["week_start"])
    return model_df, weekly_full

model_df, weekly_full = load_data()

# -----------------------------
# SIDEBAR INPUTS
# -----------------------------
st.sidebar.header("Controls")

holding_cost_rate = st.sidebar.number_input(
    "Holding Cost Rate", value=0.13, step=0.01, format="%.2f"
)
ordering_cost = st.sidebar.number_input(
    "Ordering Cost (S)", value=75.0, step=5.0
)

# -----------------------------
# DYNAMIC EOQ CALCULATION
# -----------------------------
model_df["annual_demand"] = model_df["avg_weekly_demand"] * 52
model_df["holding_cost_per_unit"] = model_df["PT_VAL"] * holding_cost_rate

mask = (
    model_df["segment"].isin(["AX", "AY"])
    & model_df["annual_demand"].notna()
    & model_df["holding_cost_per_unit"].notna()
    & (model_df["holding_cost_per_unit"] > 0)
)

model_df["eoq"] = model_df["eoq"].copy()
model_df.loc[mask, "eoq"] = (
    (2 * model_df.loc[mask, "annual_demand"] * ordering_cost)
    / model_df.loc[mask, "holding_cost_per_unit"]
) ** 0.5

selected_segment = st.sidebar.selectbox(
    "Select Segment",
    sorted(model_df["segment"].dropna().unique())
)

# Filter data
segment_df = model_df[model_df["segment"] == selected_segment].copy()

# -----------------------------
# SECTION 1: DATA OVERVIEW
# -----------------------------
st.header("1. Data Overview")

col_a, col_b = st.columns(2)
col_a.metric("Ordering Cost Assumption", f"${ordering_cost:,.2f}")
col_b.metric("Holding Cost Rate", f"{holding_cost_rate:.2%}")

st.write(f"Number of items in {selected_segment}: {segment_df['UPDATED PN'].nunique()}")

st.dataframe(
    segment_df[
        [
            "UPDATED PN",
            "avg_weekly_demand",
            "std_weekly_demand",
            "safety_stock",
            "target_inventory_level",
            "eoq",
        ]
    ],
    use_container_width=True,
)

# -----------------------------
# SECTION 2: SEGMENT POLICY
# -----------------------------
st.header("2. Segment Policy")

if selected_segment in ["AX", "AY"]:
    st.success("EOQ + Safety Stock Model")
else:
    st.info("Periodic Review + Safety Stock Model")

# -----------------------------
# SECTION 3: ITEM EXPLORER
# -----------------------------
st.header("3. Item Explorer")

selected_part = st.selectbox(
    "Select Item",
    sorted(segment_df["UPDATED PN"].dropna().unique())
)

part_row = segment_df[segment_df["UPDATED PN"] == selected_part].iloc[0]
part_history = (
    weekly_full[weekly_full["UPDATED PN"] == selected_part]
    .sort_values("week_start")
    .copy()
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Avg Weekly Demand", f"{part_row['avg_weekly_demand']:.2f}")
col2.metric("Std Dev", f"{part_row['std_weekly_demand']:.2f}")
col3.metric("Safety Stock", f"{part_row['safety_stock']:.2f}")
col4.metric("Target Inventory", f"{part_row['target_inventory_level']:.2f}")

if pd.notna(part_row["eoq"]):
    st.metric("EOQ", f"{part_row['eoq']:.2f}")

# -----------------------------
# DEMAND PLOT
# -----------------------------
st.subheader("Weekly Demand")

fig, ax = plt.subplots()
ax.plot(part_history["week_start"], part_history["weekly_demand"], marker="o")
ax.set_xlabel("Week")
ax.set_ylabel("Demand")
ax.set_title(f"Weekly Demand for {selected_part}")
plt.xticks(rotation=45)
plt.tight_layout()
st.pyplot(fig)

# -----------------------------
# SECTION 4: SIMPLE SIMULATION
# -----------------------------
st.header("4. Simple Inventory Simulation")

sim_weeks = st.slider("Number of weeks to simulate", min_value=4, max_value=12, value=12)
starting_inventory = st.number_input(
    "Starting inventory",
    min_value=0.0,
    value=float(part_row["target_inventory_level"])
)

st.write("This simulation uses the selected item's historical weekly demand pattern in sequence.")

sim_history = part_history.tail(sim_weeks).copy()

inventory = float(starting_inventory)
lead_time = int(round(part_row["avg_lead_time_weeks"]))
target_level = float(part_row["target_inventory_level"])

open_orders = []
sim_rows = []

for i, (_, row) in enumerate(sim_history.iterrows()):
    demand = float(row["weekly_demand"])

    # Receive any orders arriving this week
    receipts = sum(qty for arrival_week, qty in open_orders if arrival_week == i)
    inventory += receipts

    # Remove received orders from pipeline
    open_orders = [(arrival_week, qty) for arrival_week, qty in open_orders if arrival_week != i]

    beginning_inventory = inventory

    # Demand happens
    inventory -= demand

    # Inventory position = on hand + pipeline
    inventory_position = inventory + sum(qty for _, qty in open_orders)

    # Order-up-to-target policy
    order_qty = 0.0
    if inventory_position < target_level:
        order_qty = max(target_level - inventory_position, 0)
        arrival_week = i + lead_time
        open_orders.append((arrival_week, order_qty))

    ending_inventory = inventory

    sim_rows.append({
        "week_start": row["week_start"],
        "beginning_inventory": beginning_inventory,
        "demand": demand,
        "receipts": receipts,
        "inventory_position": inventory_position,
        "order_qty": order_qty,
        "ending_inventory": ending_inventory,
    })

sim_df = pd.DataFrame(sim_rows)

st.dataframe(sim_df, use_container_width=True)

fig2, ax2 = plt.subplots()
ax2.plot(sim_df["week_start"], sim_df["ending_inventory"], marker="o", label="Ending Inventory")
ax2.axhline(target_level, linestyle="--", label="Target Inventory")
ax2.set_title(f"Simulated Inventory for {selected_part}")
ax2.set_xlabel("Week")
ax2.set_ylabel("Inventory")
ax2.legend()
plt.xticks(rotation=45)
plt.tight_layout()
st.pyplot(fig2)