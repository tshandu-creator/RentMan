import datetime as dt
import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="My Properties",
                   page_icon="🏠", layout="centered")
st.markdown("<style>html{font-size:20px} .stButton button{width:100%;height:3rem}</style>",
            unsafe_allow_html=True)

# Secrets (.streamlit/secrets.toml): SUPABASE_URL, SUPABASE_KEY, APP_PASSWORD
db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Simple password gate
if not st.session_state.get("ok"):
    if st.text_input("Password", type="password") == st.secrets["APP_PASSWORD"]:
        st.session_state.ok = True
        st.rerun()
    st.stop()


def rows(table, select="*"):
    return pd.DataFrame(db.table(table).select(select).execute().data)


units = rows("units", "id, unit_name, monthly_rent, properties(id, name)")
if units.empty:
    units = pd.DataFrame(
        columns=["id", "unit_name", "monthly_rent", "properties", "label"])
else:
    units["label"] = units["properties"].apply(
        lambda p: p["name"]) + " - " + units["unit_name"]
tenants = rows(
    "tenants", "id, unit_id, full_name, monthly_rent, lease_end, is_active")
if tenants.empty:
    tenants = pd.DataFrame(
        columns=["id", "unit_id", "full_name", "monthly_rent", "lease_end", "is_active"])
cats = rows("expense_categories")
cats["label"] = cats["icon"] + " " + cats["name"]

page = st.radio("", ["🏠 Home", "💰 Rent received", "🧾 Money spent", "📊 Reports", "⚙️ Manage"],
                horizontal=True, label_visibility="collapsed")
if units.empty and page != "⚙️ Manage":
    st.info("Start in ⚙️ Manage: add a property, then a unit.")
    st.stop()

if page == "🏠 Home":
    month = dt.date.today().replace(day=1).isoformat()
    paid = rows("income").query(
        "for_month == @month")["tenant_id"].tolist() if len(rows("income")) else []
    active = tenants[tenants.is_active].copy()
    active["lease_end"] = pd.to_datetime(active["lease_end"]).dt.date
    for _, t in active.iterrows():
        unit = units[units.id == t.unit_id].iloc[0]
        days_left = (t.lease_end - dt.date.today()
                     ).days if pd.notna(t.lease_end) else None
        lease = "No end date" if days_left is None else ("🔴 Expired" if days_left < 0 else
                                                         "🟠 Ends soon" if days_left <= 60 else "🟢 Active")
        st.subheader(f"{unit.label}")
        st.write(f"{t.full_name} · R{t.monthly_rent:,.0f}/month · {lease}")
        st.write("✅ Paid this month" if t.id in paid else "❌ Not paid yet")

elif page == "💰 Rent received":
    with st.form("income", clear_on_submit=True):
        unit_label = st.selectbox("Which unit?", units["label"])
        unit = units[units.label == unit_label].iloc[0]
        tenant = tenants[(tenants.unit_id == unit.id) & tenants.is_active]
        amount = st.number_input("Amount (R)", min_value=0.0, step=100.0,
                                 value=float(tenant.monthly_rent.iloc[0]) if len(tenant) else 0.0)
        method = st.radio("How did they pay?", [
                          "Cash", "EFT", "Card"], horizontal=True)
        date = st.date_input("Date received", dt.date.today())
        if st.form_submit_button("Save") and amount > 0:
            db.table("income").insert({
                "unit_id": unit.id, "tenant_id": tenant.id.iloc[0] if len(tenant) else None,
                "amount": amount, "payment_method": method, "date_received": date.isoformat(),
                "for_month": date.replace(day=1).isoformat()}).execute()
            st.success("Saved ✅")

elif page == "🧾 Money spent":
    with st.form("expense", clear_on_submit=True):
        unit_label = st.selectbox("Which unit?", units["label"])
        unit = units[units.label == unit_label].iloc[0]
        cat_label = st.selectbox("What was it for?", cats["label"])
        amount = st.number_input("Amount (R)", min_value=0.0, step=50.0)
        date = st.date_input("Date", dt.date.today())
        note = st.text_input("Note (optional)")
        if st.form_submit_button("Save") and amount > 0:
            db.table("expenses").insert({
                "property_id": unit.properties["id"], "unit_id": unit.id,
                "category_id": int(cats[cats.label == cat_label].id.iloc[0]),
                "amount": amount, "date": date.isoformat(), "description": note}).execute()
            st.success("Saved ✅")

elif page == "⚙️ Manage":
    props = rows("properties")
    with st.form("property", clear_on_submit=True):
        st.subheader("Add a property")
        name = st.text_input("Property name")
        address = st.text_input("Address")
        if st.form_submit_button("Save property") and name:
            db.table("properties").insert(
                {"name": name, "address": address}).execute()
            st.rerun()
    if not props.empty:
        with st.form("unit", clear_on_submit=True):
            st.subheader("Add a unit")
            prop_name = st.selectbox("Property", props["name"])
            unit_name = st.text_input("Unit name (for example, Unit 3)")
            rent = st.number_input(
                "Monthly rent (R)", min_value=0.0, step=100.0)
            if st.form_submit_button("Save unit") and unit_name:
                db.table("units").insert({"property_id": props[props.name == prop_name].id.iloc[0],
                                          "unit_name": unit_name, "monthly_rent": rent}).execute()
                st.rerun()
    if not units.empty:
        with st.form("tenant", clear_on_submit=True):
            st.subheader("Add a tenant")
            unit_label = st.selectbox("Unit", units["label"])
            full_name = st.text_input("Full name")
            phone = st.text_input("Phone number")
            rent = st.number_input(
                "Agreed rent (R)", min_value=0.0, step=100.0)
            start = st.date_input("Lease start", dt.date.today())
            end = st.date_input(
                "Lease end", dt.date.today() + dt.timedelta(days=365))
            if st.form_submit_button("Save tenant") and full_name:
                db.table("tenants").insert({
                    "unit_id": units[units.label == unit_label].id.iloc[0], "full_name": full_name,
                    "phone": phone, "monthly_rent": rent,
                    "lease_start": start.isoformat(), "lease_end": end.isoformat()}).execute()
                st.rerun()
        st.subheader("Tenant moved out")
        for _, t in tenants[tenants.is_active].iterrows():
            if st.button(f"{t.full_name} has moved out", key=t.id):
                db.table("tenants").update(
                    {"is_active": False}).eq("id", t.id).execute()
                st.rerun()
else:
    year = st.selectbox("Year", range(
        dt.date.today().year, dt.date.today().year - 5, -1))
    inc = rows("income", "date_received, amount, unit_id")
    exp = rows(
        "expenses", "date, amount, property_id, categories:expense_categories(name)")
    if inc.empty and exp.empty:
        st.info("Nothing logged yet.")
        st.stop()
    inc["month"] = pd.to_datetime(
        inc["date_received"]).dt.to_period("M").astype(str)
    exp["month"] = pd.to_datetime(exp["date"]).dt.to_period("M").astype(str)
    inc, exp = inc[inc.month.str.startswith(
        str(year))], exp[exp.month.str.startswith(str(year))]
    c1, c2, c3 = st.columns(3)
    c1.metric("Money in", f"R{inc.amount.sum():,.0f}")
    c2.metric("Money out", f"R{exp.amount.sum():,.0f}")
    c3.metric("Profit", f"R{inc.amount.sum() - exp.amount.sum():,.0f}")
    monthly = pd.concat([inc.assign(type="Money in"),
                        exp.assign(type="Money out")])
    st.plotly_chart(px.bar(monthly.groupby(["month", "type"], as_index=False).amount.sum(),
                           x="month", y="amount", color="type", barmode="group"),
                    use_container_width=True)
    st.plotly_chart(px.pie(exp.assign(cat=exp.categories.apply(lambda c: c["name"])),
                           names="cat", values="amount", title="Where the money went"),
                    use_container_width=True)
    inc = inc.merge(units[["id", "properties"]],
                    left_on="unit_id", right_on="id")
    inc["property"] = inc.properties.apply(lambda p: p["name"])
    exp["property"] = exp.property_id.map(
        {p["id"]: p["name"] for p in units.properties})
    net = inc.groupby("property").amount.sum().sub(
        exp.groupby("property").amount.sum(), fill_value=0)
    st.subheader("Profit per property")
    st.bar_chart(net)
