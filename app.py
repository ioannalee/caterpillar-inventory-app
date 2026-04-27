import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# -----------------------------
# PAGE SETUP
# -----------------------------
st.set_page_config(page_title="Caterpillar Inventory App", layout="wide")
st.title("Caterpillar Inventory Policy App")

# -----------------------------
# GLOBAL ASSUMPTIONS
# -----------------------------
DOMESTIC_LEAD_TIME_WEEKS = 3
DOMESTIC_LEAD_TIME_STD = 0.3

# -----------------------------
# POLICY MAP
# -----------------------------
segment_policy = {
    "AX": {
        "model_type": "Continuous Review (EOQ)",
        "review_period_weeks": None,
        "service_level": 0.95,
        "z_value": 1.645,
    },
    "AY": {
        "model_type": "Continuous Review (EOQ)",
        "review_period_weeks": None,
        "service_level": 0.95,
        "z_value": 1.645,
    },
    "AZ": {
        "model_type": "Periodic Review",
        "review_period_weeks": 1,
        "service_level": 0.98,
        "z_value": 2.05,
    },
    "BX": {
        "model_type": "Periodic Review",
        "review_period_weeks": 2,
        "service_level": 0.95,
        "z_value": 1.645,
    },
    "BY": {
        "model_type": "Periodic Review",
        "review_period_weeks": 2,
        "service_level": 0.90,
        "z_value": 1.282,
    },
    "BZ": {
        "model_type": "Periodic Review",
        "review_period_weeks": 2,
        "service_level": 0.95,
        "z_value": 1.645,
    },
    "CX": {
        "model_type": "Periodic Review",
        "review_period_weeks": 4,
        "service_level": 0.90,
        "z_value": 1.282,
    },
    "CY": {
        "model_type": "Periodic Review",
        "review_period_weeks": 4,
        "service_level": 0.90,
        "z_value": 1.282,
    },
    "CZ": {
        "model_type": "Periodic Review",
        "review_period_weeks": 4,
        "service_level": 0.90,
        "z_value": 1.282,
    },
}

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
    "Holding Cost Rate",
    value=0.13,
    step=0.01,
    format="%.2f"
)

ordering_cost = st.sidebar.number_input(
    "Ordering Cost (S) for AX/AY",
    value=75.0,
    step=5.0
)

selected_segment = st.sidebar.selectbox(
    "Select Segment",
    sorted(model_df["segment"].dropna().unique())
)

# -----------------------------
# PREP MODEL DATA
# -----------------------------
model_df = model_df.copy()

# Override all lead times with domestic assumptions
model_df["avg_lead_time_weeks"] = DOMESTIC_LEAD_TIME_WEEKS
model_df["std_lead_time_weeks"] = DOMESTIC_LEAD_TIME_STD

# Add policy fields
model_df["model_type"] = model_df["segment"].map(
    lambda x: segment_policy.get(x, {}).get("model_type")
)
model_df["review_period_weeks"] = model_df["segment"].map(
    lambda x: segment_policy.get(x, {}).get("review_period_weeks")
)
model_df["service_level"] = model_df["segment"].map(
    lambda x: segment_policy.get(x, {}).get("service_level")
)
model_df["z_value"] = model_df["segment"].map(
    lambda x: segment_policy.get(x, {}).get("z_value")
)

# Recalculate safety stock using domestic lead time assumptions
model_df["safety_stock"] = model_df["z_value"] * np.sqrt(
    model_df["avg_lead_time_weeks"] * (model_df["std_weekly_demand"] ** 2) +
    (model_df["avg_weekly_demand"] ** 2) * (model_df["std_lead_time_weeks"] ** 2)
)

# Recalculate EOQ dynamically for AX and AY only
model_df["annual_demand"] = model_df["avg_weekly_demand"] * 52
model_df["holding_cost_per_unit"] = model_df["PT_VAL"] * holding_cost_rate

eoq_mask = (
    model_df["segment"].isin(["AX", "AY"])
    & model_df["annual_demand"].notna()
    & model_df["holding_cost_per_unit"].notna()
    & (model_df["holding_cost_per_unit"] > 0)
)

model_df["eoq"] = np.nan
model_df.loc[eoq_mask, "eoq"] = np.sqrt(
    (2 * model_df.loc[eoq_mask, "annual_demand"] * ordering_cost) /
    model_df.loc[eoq_mask, "holding_cost_per_unit"]
)

# Reorder point for EOQ segments only
model_df["reorder_point"] = np.nan
rop_mask = model_df["segment"].isin(["AX", "AY"])
model_df.loc[rop_mask, "reorder_point"] = (
    model_df.loc[rop_mask, "avg_weekly_demand"] *
    DOMESTIC_LEAD_TIME_WEEKS
) + model_df.loc[rop_mask, "safety_stock"]

# Target inventory level for periodic-review segments only
model_df["target_inventory_level"] = np.nan
periodic_mask = ~model_df["segment"].isin(["AX", "AY"])
model_df.loc[periodic_mask, "target_inventory_level"] = (
    model_df.loc[periodic_mask, "avg_weekly_demand"] *
    (
        DOMESTIC_LEAD_TIME_WEEKS +
        model_df.loc[periodic_mask, "review_period_weeks"]
    )
) + model_df.loc[periodic_mask, "safety_stock"]

# Round for cleaner display
for col in [
    "avg_weekly_demand",
    "std_weekly_demand",
    "safety_stock",
    "target_inventory_level",
    "annual_demand",
    "holding_cost_per_unit",
    "eoq",
    "reorder_point",
]:
    if col in model_df.columns:
        model_df[col] = model_df[col].round(2)

segment_df = model_df[model_df["segment"] == selected_segment].copy()

# -----------------------------
# SECTION 1: DATA OVERVIEW
# -----------------------------
st.header("1. Data Overview")

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Ordering Cost Assumption", f"${ordering_cost:,.2f}")
col_b.metric("Holding Cost Rate", f"{holding_cost_rate:.2%}")
col_c.metric("Lead Time Assumption", f"{DOMESTIC_LEAD_TIME_WEEKS} weeks")
col_d.metric("Items in Segment", f"{segment_df['UPDATED PN'].nunique()}")

if selected_segment in ["AX", "AY"]:
    display_cols = [
        "UPDATED PN",
        "avg_weekly_demand",
        "std_weekly_demand",
        "safety_stock",
        "reorder_point",
        "eoq",
    ]
else:
    display_cols = [
        "UPDATED PN",
        "avg_weekly_demand",
        "std_weekly_demand",
        "safety_stock",
        "target_inventory_level",
        "review_period_weeks",
    ]

st.dataframe(
    segment_df[display_cols],
    use_container_width=True
)

# -----------------------------
# SECTION 2: SEGMENT POLICY
# -----------------------------
st.header("2. Segment Policy")

policy = segment_policy[selected_segment]

if policy["model_type"] == "Continuous Review (EOQ)":
    st.success(f"{selected_segment} uses a Continuous Review (EOQ) policy.")
    st.markdown(
        """
        **Policy logic**
        - Monitor inventory continuously
        - When **ending inventory** falls to or below the **reorder point**, place an order
        - Each order quantity is fixed at **EOQ**
        - Reorder Point = average demand during lead time + safety stock
        """
    )
else:
    st.info(f"{selected_segment} uses a Periodic Review policy.")
    st.markdown(
        f"""
        **Policy logic**
        - Review inventory every **{int(policy['review_period_weeks'])} week(s)**
        - At each review point, calculate **inventory position**
        - Order enough to raise inventory position to the **target inventory level**
        - Order Quantity = Target Inventory Level − Inventory Position
        """
    )

policy_summary = pd.DataFrame({
    "Segment": list(segment_policy.keys()),
    "Model": [segment_policy[s]["model_type"] for s in segment_policy],
    "Review Period (Weeks)": [segment_policy[s]["review_period_weeks"] for s in segment_policy],
    "Service Level": [segment_policy[s]["service_level"] for s in segment_policy],
})

with st.expander("Show policy table for all segments"):
    st.dataframe(policy_summary, use_container_width=True)

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

if selected_segment in ["AX", "AY"]:
    col4.metric("Reorder Point", f"{part_row['reorder_point']:.2f}")
    st.metric("EOQ", f"{part_row['eoq']:.2f}")
else:
    col4.metric("Target Inventory", f"{part_row['target_inventory_level']:.2f}")
    st.metric("Review Period (Weeks)", f"{int(part_row['review_period_weeks'])}")

# -----------------------------
# GRAPH 1: DEMAND
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
# SECTION 4: SIMULATION
# -----------------------------
st.header("4. Inventory Simulation")

sim_weeks = st.slider("Number of weeks to simulate", min_value=4, max_value=20, value=12)

default_start = float(
    part_row["reorder_point"] if selected_segment in ["AX", "AY"]
    else part_row["target_inventory_level"]
)

starting_inventory = st.number_input(
    "Starting inventory",
    min_value=0.0,
    value=default_start
)

st.write("This simulation uses the selected item's historical weekly demand pattern in sequence.")

sim_history = part_history.tail(sim_weeks).copy()

on_hand_inventory = float(starting_inventory)
lead_time = DOMESTIC_LEAD_TIME_WEEKS
open_orders = []
sim_rows = []

part_value = float(part_row["PT_VAL"]) if pd.notna(part_row["PT_VAL"]) else 0.0

if selected_segment in ["AX", "AY"]:
    reorder_point = float(part_row["reorder_point"])
    fixed_order_qty = float(part_row["eoq"])

    for i, (_, row) in enumerate(sim_history.iterrows()):
        demand = float(row["weekly_demand"])

        beginning_inventory = on_hand_inventory

        receipts = sum(qty for arrival_week, qty in open_orders if arrival_week == i)
        open_orders = [
            (arrival_week, qty)
            for arrival_week, qty in open_orders
            if arrival_week != i
        ]

        available_inventory = beginning_inventory + receipts
        ending_inventory = available_inventory - demand

        inventory_position = ending_inventory + sum(qty for _, qty in open_orders)

        order_qty = 0.0
        if inventory_position <= reorder_point:
            order_qty = fixed_order_qty
            arrival_week = i + lead_time
            open_orders.append((arrival_week, order_qty))
            inventory_position = ending_inventory + sum(qty for _, qty in open_orders)

        avg_inventory = (beginning_inventory + ending_inventory) / 2
        weekly_holding_cost = avg_inventory * part_value * holding_cost_rate / 52

        on_hand_inventory = ending_inventory

        sim_rows.append({
            "week_start": row["week_start"],
            "beginning_inventory": beginning_inventory,
            "receipts": receipts,
            "available_inventory": available_inventory,
            "demand": demand,
            "ending_inventory": ending_inventory,
            "inventory_position": inventory_position,
            "order_qty": order_qty,
            "control_level": reorder_point,
            "avg_inventory": avg_inventory,
            "weekly_holding_cost": weekly_holding_cost,
        })

else:
    target_level = float(part_row["target_inventory_level"])
    review_period = int(part_row["review_period_weeks"])

    for i, (_, row) in enumerate(sim_history.iterrows()):
        demand = float(row["weekly_demand"])

        beginning_inventory = on_hand_inventory

        receipts = sum(qty for arrival_week, qty in open_orders if arrival_week == i)
        open_orders = [
            (arrival_week, qty)
            for arrival_week, qty in open_orders
            if arrival_week != i
        ]

        available_inventory = beginning_inventory + receipts
        ending_inventory = available_inventory - demand

        inventory_position = ending_inventory + sum(qty for _, qty in open_orders)

        order_qty = 0.0
        is_review_week = ((i + 1) % review_period == 0)

        if is_review_week and inventory_position < target_level:
            order_qty = max(target_level - inventory_position, 0)
            arrival_week = i + lead_time
            open_orders.append((arrival_week, order_qty))
            inventory_position = ending_inventory + sum(qty for _, qty in open_orders)

        avg_inventory = (beginning_inventory + ending_inventory) / 2
        weekly_holding_cost = avg_inventory * part_value * holding_cost_rate / 52

        on_hand_inventory = ending_inventory

        sim_rows.append({
            "week_start": row["week_start"],
            "beginning_inventory": beginning_inventory,
            "receipts": receipts,
            "available_inventory": available_inventory,
            "demand": demand,
            "ending_inventory": ending_inventory,
            "inventory_position": inventory_position,
            "order_qty": order_qty,
            "control_level": target_level,
            "avg_inventory": avg_inventory,
            "weekly_holding_cost": weekly_holding_cost,
        })

sim_df = pd.DataFrame(sim_rows)

# Round simulation table for cleaner display
display_sim_df = sim_df.copy()
for col in [
    "beginning_inventory",
    "receipts",
    "available_inventory",
    "demand",
    "ending_inventory",
    "inventory_position",
    "order_qty",
    "control_level",
    "avg_inventory",
    "weekly_holding_cost",
]:
    display_sim_df[col] = display_sim_df[col].round(2)

total_holding_cost = sim_df["weekly_holding_cost"].sum()
avg_ending_inventory = sim_df["ending_inventory"].mean()
total_ordered = sim_df["order_qty"].sum()
num_orders = (sim_df["order_qty"] > 0).sum()

col_h1, col_h2, col_h3, col_h4 = st.columns(4)
col_h1.metric("Total Simulated Holding Cost", f"${total_holding_cost:,.2f}")
col_h2.metric("Avg Ending Inventory", f"{avg_ending_inventory:,.2f}")
col_h3.metric("Total Ordered Qty", f"{total_ordered:,.2f}")
col_h4.metric("Number of Orders", f"{num_orders}")

st.dataframe(display_sim_df, use_container_width=True)

# -----------------------------
# GRAPH 2: INVENTORY OVER TIME
# -----------------------------
st.subheader("Simulated Inventory Over Time")

fig2, ax2 = plt.subplots()
ax2.plot(sim_df["week_start"], sim_df["ending_inventory"], marker="o", label="Ending Inventory")
ax2.plot(sim_df["week_start"], sim_df["inventory_position"], marker="o", linestyle="--", label="Inventory Position")
ax2.axhline(sim_df["control_level"].iloc[0], linestyle=":", label="Control Level")

if selected_segment in ["AX", "AY"]:
    ax2.set_title(f"EOQ Simulation for {selected_part}")
    ax2.legend(["Ending Inventory", "Inventory Position", "Reorder Point"])
else:
    ax2.set_title(f"Periodic Review Simulation for {selected_part}")
    ax2.legend(["Ending Inventory", "Inventory Position", "Target Inventory Level"])

ax2.set_xlabel("Week")
ax2.set_ylabel("Inventory")
plt.xticks(rotation=45)
plt.tight_layout()
st.pyplot(fig2)

# -----------------------------
# GRAPH 3: ORDER QUANTITY OVER TIME
# -----------------------------
st.subheader("Simulated Order Quantity Over Time")

fig3, ax3 = plt.subplots()
ax3.bar(sim_df["week_start"], sim_df["order_qty"])
ax3.set_title(f"Simulated Order Quantity for {selected_part}")
ax3.set_xlabel("Week")
ax3.set_ylabel("Order Quantity")
plt.xticks(rotation=45)
plt.tight_layout()
st.pyplot(fig3)

# -----------------------------
# GRAPH 4: HOLDING COST OVER TIME
# -----------------------------
st.subheader("Estimated Weekly Holding Cost Over Time")

fig4, ax4 = plt.subplots()
ax4.plot(sim_df["week_start"], sim_df["weekly_holding_cost"], marker="o")
ax4.set_title(f"Estimated Weekly Holding Cost for {selected_part}")
ax4.set_xlabel("Week")
ax4.set_ylabel("Holding Cost ($)")
plt.xticks(rotation=45)
plt.tight_layout()
st.pyplot(fig4)

# -----------------------------
# SECTION 5: SENSITIVITY ANALYSIS
# -----------------------------
st.header("5. Sensitivity Analysis")

st.write(
    "This section shows how estimated holding cost changes under different carrying cost assumptions. "
    "For AX and AY items, it also shows how EOQ changes under different ordering cost assumptions."
)

# Holding cost sensitivity
holding_rate_options = [0.08, 0.10, 0.13, 0.15, 0.20]

holding_sensitivity_rows = []

for rate in holding_rate_options:
    temp_df = sim_df.copy()
    temp_df["sensitivity_holding_cost"] = (
        temp_df["avg_inventory"] * part_value * rate / 52
    )

    holding_sensitivity_rows.append({
        "holding_cost_rate": rate,
        "total_simulated_holding_cost": temp_df["sensitivity_holding_cost"].sum(),
        "avg_weekly_holding_cost": temp_df["sensitivity_holding_cost"].mean(),
    })

holding_sensitivity_df = pd.DataFrame(holding_sensitivity_rows)
holding_sensitivity_df["holding_cost_rate"] = holding_sensitivity_df["holding_cost_rate"].apply(lambda x: f"{x:.0%}")
holding_sensitivity_df["total_simulated_holding_cost"] = holding_sensitivity_df["total_simulated_holding_cost"].round(2)
holding_sensitivity_df["avg_weekly_holding_cost"] = holding_sensitivity_df["avg_weekly_holding_cost"].round(2)

st.subheader("Holding Cost Sensitivity")
st.dataframe(holding_sensitivity_df, use_container_width=True)

fig5, ax5 = plt.subplots()
ax5.bar(
    holding_sensitivity_df["holding_cost_rate"],
    holding_sensitivity_df["total_simulated_holding_cost"]
)
ax5.set_title(f"Holding Cost Sensitivity for {selected_part}")
ax5.set_xlabel("Annual Holding Cost Rate")
ax5.set_ylabel("Total Simulated Holding Cost ($)")
plt.tight_layout()
st.pyplot(fig5)

# EOQ sensitivity only applies to AX and AY
if selected_segment in ["AX", "AY"]:
    st.subheader("EOQ Sensitivity")

    ordering_cost_options = [50, 75, 100, 125, 150]

    eoq_sensitivity_rows = []

    annual_demand = float(part_row["avg_weekly_demand"]) * 52
    holding_cost_per_unit = part_value * holding_cost_rate

    for s in ordering_cost_options:
        if holding_cost_per_unit > 0:
            eoq_value = np.sqrt((2 * annual_demand * s) / holding_cost_per_unit)
        else:
            eoq_value = np.nan

        eoq_sensitivity_rows.append({
            "ordering_cost": s,
            "eoq": eoq_value,
        })

    eoq_sensitivity_df = pd.DataFrame(eoq_sensitivity_rows)
    eoq_sensitivity_df["eoq"] = eoq_sensitivity_df["eoq"].round(2)

    st.dataframe(eoq_sensitivity_df, use_container_width=True)

    fig6, ax6 = plt.subplots()
    ax6.plot(eoq_sensitivity_df["ordering_cost"], eoq_sensitivity_df["eoq"], marker="o")
    ax6.set_title(f"EOQ Sensitivity to Ordering Cost for {selected_part}")
    ax6.set_xlabel("Ordering Cost ($)")
    ax6.set_ylabel("EOQ")
    plt.tight_layout()
    st.pyplot(fig6)

else:
    st.info(
        "EOQ sensitivity is only shown for AX and AY segments because those are the segments using the continuous review EOQ policy."
    )

# -----------------------------
# VALIDATION NOTE
# -----------------------------
st.subheader("Validation Note")
st.info(
    "This app currently simulates inventory behavior using historical weekly demand patterns "
    "and assumes all items are domestic with a fixed 3-week lead time. "
    "Estimated holding cost is based on simulated average weekly inventory, part value, "
    "and the selected annual holding cost rate. "
    "A full validation against actual historical inventory levels and actual historical replenishment "
    "records would require an additional dataset containing observed on-hand inventory and actual orders."
)