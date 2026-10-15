"""Smart Parking Lot Allocation and Billing System - Streamlit front end.

Run with:  streamlit run app.py
"""
import re
import base64
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from db import DBError

st.set_page_config(page_title="Smart Parking System", page_icon="🅿️", layout="wide")

PAGES = ["Dashboard", "Slot Search", "Find My Car", "Reservations", "Gate Entry / Exit",
         "Billing & Payments", "Passes", "Master Data", "Reports"]
PAGE_ICONS = {
    "Dashboard": "🏠",
    "Slot Search": "🔍",
    "Find My Car": "🚘",
    "Reservations": "📅",
    "Gate Entry / Exit": "🚧",
    "Billing & Payments": "💳",
    "Passes": "🎫",
    "Master Data": "🗂️",
    "Reports": "📊",
}
PAGE_SUBTITLES = {
    "Dashboard": "Your parking lot at a glance, with live space and revenue updates.",
    "Slot Search": "Find the right space by vehicle type, floor, zone, and availability.",
    "Find My Car": "Look up a parked vehicle and see its live location and fare.",
    "Reservations": "Hold spaces ahead of time and manage active reservations.",
    "Gate Entry / Exit": "Welcome vehicles in, record departures, and create bills.",
    "Billing & Payments": "Keep track of bills, balances, and payments.",
    "Passes": "Issue parking passes and check which ones are valid today.",
    "Master Data": "Manage customers, vehicles, spaces, and hourly tariffs.",
    "Reports": "Explore occupancy, usage, revenue, and operational reports.",
}
ASSET_DIR = Path(__file__).parent / "assets"
EMPTY_IMAGE = ASSET_DIR / "empty.svg"

st.markdown(
    """
    <style>
    :root {
        --navy: #0F1B2D;
        --blue: #1E5EFF;
        --amber: #FFC72C;
        --ink: #17243A;
        --muted: #66758B;
        --surface: #FFFFFF;
    }
    .stApp {
        background:
            radial-gradient(ellipse at 90% 0%, rgba(30,94,255,.08), transparent 34%),
            #F4F7FC;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(175deg, #0F1B2D 0%, #152944 100%);
    }
    [data-testid="stSidebar"] * { color: #F5F8FF; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        border-radius: 12px;
        padding: .38rem .6rem;
        transition: background .18s ease;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(255,255,255,.10);
    }
    [data-testid="stSidebar"] details {
        border: 1px solid rgba(255,255,255,.18);
        border-radius: 14px;
        background: rgba(255,255,255,.06);
    }
    .page-banner {
        padding: 1.45rem 1.8rem;
        border-radius: 22px;
        color: white;
        background: linear-gradient(115deg, #0F1B2D 0%, #1E5EFF 100%);
        box-shadow: 0 14px 34px rgba(15,27,45,.18);
        margin: .3rem 0 1.4rem;
    }
    .page-banner h1 { color: white; margin: 0; font-size: 2rem; }
    .page-banner p { color: #E2EAFE; margin: .35rem 0 0; }
    .hero-banner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 1.15rem 1.55rem;
        margin: .5rem 0 1.4rem;
        overflow: hidden;
        border-radius: 24px;
        background: linear-gradient(115deg, #0F1B2D, #1E5EFF);
        box-shadow: 0 15px 34px rgba(15,27,45,.2);
        color: white;
    }
    .hero-banner h1 { color: white; margin: 0; font-size: 2rem; white-space: nowrap; }
    .hero-banner p { color: #E5EDFF; margin: .35rem 0 0; font-size: 1.08rem; }
    .hero-banner img { width: min(38%, 300px); height: 145px; object-fit: contain; }
    .kpi-card {
        min-height: 120px;
        padding: 1rem 1.15rem;
        border-radius: 18px;
        background: white;
        border: 1px solid #E5EBF5;
        box-shadow: 0 8px 22px rgba(15,27,45,.07);
    }
    .kpi-icon { font-size: 1.45rem; }
    .kpi-value { color: #0F1B2D; font-size: 1.75rem; font-weight: 800; margin-top: .15rem; }
    .kpi-label { color: #66758B; font-size: .88rem; font-weight: 600; }
    [data-testid="stForm"] {
        border: 1px solid #E1E8F2;
        border-radius: 18px;
        padding: 1rem 1.15rem;
        background: rgba(255,255,255,.82);
        box-shadow: 0 7px 20px rgba(15,27,45,.055);
    }
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stButton"] button {
        border-radius: 11px;
        font-weight: 700;
        transition: transform .15s ease, box-shadow .15s ease;
    }
    [data-testid="stFormSubmitButton"] button:hover,
    [data-testid="stButton"] button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 14px rgba(30,94,255,.18);
    }
    .map-tile {
        min-height: 76px;
        padding: .7rem .5rem;
        border: 1px solid rgba(15,27,45,.10);
        border-radius: 13px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(15,27,45,.06);
        font-weight: 750;
    }
    .map-tile .vehicle-icon { font-size: 1.25rem; display: block; }
    .map-free { background: #E6F7EC; color: #176B37; }
    .map-occupied { background: #FDE9E8; color: #A12D2A; }
    .map-reserved { background: #FFF4D3; color: #825900; }
    .map-blocked { background: #EBEEF3; color: #5D6675; }
    .map-legend { display: flex; flex-wrap: wrap; gap: .65rem 1.1rem; margin: .5rem 0 1rem; }
    .map-legend span { font-size: .85rem; font-weight: 650; color: #44536A; }
    .map-dot { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .35rem; }
    .map-location { color: #24344B; font-weight: 750; margin: 1rem 0 .5rem; }
    .ticket-card, .pass-card {
        padding: 1.1rem 1.3rem;
        border: 1px solid #DDE6F3;
        border-left: 5px solid #1E5EFF;
        border-radius: 16px;
        background: white;
        box-shadow: 0 8px 22px rgba(15,27,45,.08);
        margin: .7rem 0 1rem;
    }
    .ticket-card h3, .pass-card h3 { margin: 0 0 .55rem; color: #0F1B2D; }
    .ticket-meta { color: #506078; line-height: 1.8; }
    </style>
    """,
    unsafe_allow_html=True,
)


def page_header(page):
    st.markdown(
        f"<div class='page-banner'><h1>{PAGE_ICONS[page]} {escape(page)}</h1>"
        f"<p>{escape(PAGE_SUBTITLES[page])}</p></div>",
        unsafe_allow_html=True,
    )


def floor_name(value):
    return {0: "Ground Floor", 1: "First Floor", 2: "Second Floor"}.get(
        int(value), f"Floor {value}"
    )


def zone_name(value):
    value = str(value)
    return value if value.startswith("Zone ") else f"Zone {value}"


def vehicle_label(value):
    return {
        "TWO_WHEELER": "🏍️ Two-Wheeler",
        "CAR": "🚗 Car",
        "SUV": "🚙 SUV",
    }.get(str(value).upper(), str(value))


def display_rows(rows):
    displayed = []
    for row in rows:
        item = dict(row)
        if "Floor" in item and item["Floor"] is not None:
            item["Floor"] = floor_name(item["Floor"])
        if "Zone" in item and item["Zone"] is not None:
            zone = zone_name(item["Zone"])
            item["Zone"] = (
                f"{item['Floor']} · {zone}" if "Floor" in item else zone
            )
        for column in ("Type", "Vehicle type"):
            if column in item and item[column] is not None:
                item[column] = vehicle_label(item[column])
        displayed.append(item)
    return displayed


def status_style(value):
    return {
        "FREE": "background-color: #DDF4E5; color: #176B37; font-weight: 750;",
        "OCCUPIED": "background-color: #FDE1DF; color: #A12D2A; font-weight: 750;",
        "RESERVED": "background-color: #FFF0C2; color: #825900; font-weight: 750;",
        "BLOCKED": "background-color: #E7EAF0; color: #5D6675; font-weight: 750;",
    }.get(str(value).upper(), "")


# ---------------------------------------------------------------- helpers
def flash(kind, text):
    st.session_state["flash"] = (kind, text)


def show_flash():
    if "flash" in st.session_state:
        kind, text = st.session_state.pop("flash")
        getattr(st, kind)(text)


def table(rows, empty="No records found."):
    if rows:
        frame = pd.DataFrame(display_rows(rows))
        if "Status" in frame.columns:
            st.dataframe(
                frame.style.map(status_style, subset=["Status"]),
                hide_index=True,
                width="stretch",
            )
        else:
            st.dataframe(frame, hide_index=True, width="stretch")
    else:
        st.image(str(EMPTY_IMAGE), width=126)
        st.caption(empty)


def dt_input(label, key, default=None):
    default = default or datetime.now().replace(second=0, microsecond=0)
    c1, c2 = st.columns(2)
    d = c1.date_input(f"{label} date", default.date(), key=f"{key}_d")
    t = c2.time_input(f"{label} time", default.time(), key=f"{key}_t", step=60)
    return datetime.combine(d, t)


def options(rows, label_fn):
    """Map display label -> row for a selectbox."""
    return {label_fn(r): r for r in rows}


# ------------------------------------------------------------------ pages
def page_dashboard():
    hero_data = base64.b64encode((ASSET_DIR / "hero.svg").read_bytes()).decode("ascii")
    st.markdown(
        "<div class='hero-banner'><div><h1>🅿️ Smart Parking</h1>"
        "<p>Lot Allocation &amp; Billing System</p></div>"
        f"<img alt='Illustration of a multi-level car park' src='data:image/svg+xml;base64,{hero_data}'></div>",
        unsafe_allow_html=True,
    )
    show_flash()
    counts = {r["status"]: r["n"] for r in
              db.query("SELECT status, COUNT(*) AS n FROM SLOT GROUP BY status")}
    total = sum(counts.values())
    money = db.query(
        "SELECT COALESCE(SUM(amount_paid),0) AS collected, "
        "COALESCE(SUM(balance),0) AS outstanding FROM "
        "(SELECT b.bill_id, b.amount - COALESCE(SUM(p.amount_paid),0) AS balance, "
        " COALESCE(SUM(p.amount_paid),0) AS amount_paid "
        " FROM BILL b LEFT JOIN PAYMENT p ON p.bill_id = b.bill_id "
        " GROUP BY b.bill_id, b.amount) t")[0]
    kpis = [
        ("🅿️", total, "Total slots"),
        ("🟢", counts.get("FREE", 0), "Free"),
        ("🚗", counts.get("OCCUPIED", 0), "Occupied"),
        ("🟡", counts.get("RESERVED", 0), "Reserved"),
        ("💰", f"₹{money['collected']:.2f}", "Revenue collected"),
        ("🧾", f"₹{money['outstanding']:.2f}", "Outstanding"),
    ]
    for row_start in (0, 3):
        cards = st.columns(3)
        for column, (icon, value, label) in zip(cards, kpis[row_start:row_start + 3]):
           column.markdown(
               "<div class='kpi-card'>"
               f"<div class='kpi-icon'>{icon}</div>"
               f"<div class='kpi-value'>{escape(str(value))}</div>"
               f"<div class='kpi-label'>{escape(label)}</div></div>",
               unsafe_allow_html=True,
           )

    st.subheader("Live Parking Map")
    st.markdown(
        "<div class='map-legend'>"
        "<span><i class='map-dot' style='background:#36A66A'></i>Free</span>"
        "<span><i class='map-dot' style='background:#D94B45'></i>Occupied</span>"
        "<span><i class='map-dot' style='background:#E3A900'></i>Reserved</span>"
        "<span><i class='map-dot' style='background:#8993A2'></i>Blocked</span></div>",
        unsafe_allow_html=True,
    )
    slots = db.query(
        "SELECT fl.floor_no, z.zone_name, s.slot_no, vt.type_name, s.status "
        "FROM FLOOR fl JOIN ZONE z ON z.floor_id = fl.floor_id "
        "LEFT JOIN SLOT s ON s.zone_id = z.zone_id "
        "LEFT JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = s.vehicle_type_id "
        "ORDER BY fl.floor_no, z.zone_name, s.slot_no"
    )
    locations = {}
    for slot in slots:
        key = (slot["floor_no"], slot["zone_name"])
        locations.setdefault(key, []).append(slot)
    with st.container(border=True):
        if not locations:
           st.image(str(EMPTY_IMAGE), width=126)
           st.caption("No parking spaces have been added yet.")
        for (floor, zone), location_slots in locations.items():
           st.markdown(
               f"<div class='map-location'>{escape(floor_name(floor))} · "
               f"{escape(zone_name(zone))}</div>",
               unsafe_allow_html=True,
           )
           populated = [slot for slot in location_slots if slot["slot_no"] is not None]
           if not populated:
               st.caption("No slots in this zone yet.")
               continue
           tile_columns = st.columns(4)
           for index, slot in enumerate(populated):
               status_class = {
                   "FREE": "map-free",
                   "OCCUPIED": "map-occupied",
                   "RESERVED": "map-reserved",
                   "BLOCKED": "map-blocked",
               }.get(slot["status"], "map-blocked")
               vehicle_icon = {
                   "TWO_WHEELER": "🏍️",
                   "CAR": "🚗",
                   "SUV": "🚙",
               }.get(slot["type_name"], "🅿️")
               tile_columns[index % 4].markdown(
                   f"<div class='map-tile {status_class}' title='{escape(slot['status'])}'>"
                   f"<span class='vehicle-icon'>{vehicle_icon}</span>"
                   f"{escape(slot['slot_no'])}<br><small>{escape(slot['status'])}</small></div>",
                   unsafe_allow_html=True,
               )

    st.subheader("Occupancy by floor and zone")
    occ = db.query("SELECT floor_no AS Floor, zone_name AS Zone, total_slots AS Total, "
                  "occupied_slots AS Occupied, reserved_slots AS Reserved, "
                  "free_slots AS Free, occupancy_pct AS `Occupancy %` "
                  "FROM vw_zone_occupancy ORDER BY floor_no, zone_name")
    table(occ)

    st.subheader("Vehicles currently parked")
    table(db.query(
        "SELECT ps.session_id AS Session, v.reg_no AS Vehicle, vt.type_name AS Type, "
        "s.slot_no AS Slot, ps.entry_time AS `Entry time`, "
        "TIMESTAMPDIFF(MINUTE, ps.entry_time, NOW()) AS `Minutes parked` "
        "FROM PARKING_SESSION ps JOIN VEHICLE v ON v.vehicle_id = ps.vehicle_id "
        "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = v.vehicle_type_id "
        "JOIN SLOT s ON s.slot_id = ps.slot_id WHERE ps.exit_time IS NULL "
        "ORDER BY ps.entry_time"), "No vehicles are parked right now.")


def page_slot_search():
    page_header("Slot Search")
    types = [r["type_name"] for r in db.query("SELECT type_name FROM VEHICLE_TYPE ORDER BY type_name")]
    floors = [r["floor_no"] for r in db.query("SELECT DISTINCT floor_no FROM FLOOR ORDER BY floor_no")]
    zones = [r["zone_name"] for r in db.query("SELECT DISTINCT zone_name FROM ZONE ORDER BY zone_name")]
    zone_rows = db.query(
        "SELECT DISTINCT fl.floor_no, z.zone_name FROM FLOOR fl "
        "JOIN ZONE z ON z.floor_id = fl.floor_id ORDER BY fl.floor_no, z.zone_name"
    )
    zone_map = {
        f"{floor_name(row['floor_no'])} · {zone_name(row['zone_name'])}": row["zone_name"]
        for row in zone_rows
        if row["zone_name"] in zones
    }
    with st.container(border=True):
        c = st.columns(4)
        vtype = c[0].selectbox("Vehicle type", ["All"] + [vehicle_label(t) for t in types])
        type_map = {vehicle_label(t): t for t in types}
        floor_options = {floor_name(f): f for f in floors}
        floor_label = c[1].selectbox("Floor", ["All"] + list(floor_options))
        zone_label = c[2].selectbox("Zone", ["All"] + list(zone_map))
        status = c[3].selectbox("Status", ["FREE", "All", "OCCUPIED", "RESERVED", "BLOCKED"])
    floor = floor_options.get(floor_label, "All")
    zone = zone_map.get(zone_label, "All")
    vtype = type_map.get(vtype, "All")

    sql = ("SELECT s.slot_no AS Slot, fl.floor_no AS Floor, z.zone_name AS Zone, "
           "vt.type_name AS `Vehicle type`, s.status AS Status "
           "FROM SLOT s JOIN ZONE z ON z.zone_id = s.zone_id "
           "JOIN FLOOR fl ON fl.floor_id = z.floor_id "
           "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = s.vehicle_type_id WHERE 1=1")
    params = []
    if vtype != "All":
        sql += " AND vt.type_name = %s"; params.append(vtype)
    if floor != "All":
        sql += " AND fl.floor_no = %s"; params.append(floor)
    if zone != "All":
        sql += " AND z.zone_name = %s"; params.append(zone)
    if status != "All":
        sql += " AND s.status = %s"; params.append(status)
    rows = db.query(sql + " ORDER BY fl.floor_no, z.zone_name, s.slot_no", params)
    st.caption(f"{len(rows)} slot(s) found")
    table(rows, "No slots match the selected filters.")


def page_find_my_car():
    page_header("Find My Car")
    with st.container(border=True):
        with st.form("find_my_car"):
            registration = st.text_input(
                "Vehicle registration number",
                placeholder="e.g. TS09AB1234",
            ).strip().upper()
            submitted = st.form_submit_button("Find my car", type="primary")

    if not submitted:
        return

    if not registration:
        st.image(str(EMPTY_IMAGE), width=160)
        st.info("Enter a vehicle registration number to find your car.")
        return

    rows = db.query(
        "SELECT v.reg_no, vt.type_name, s.slot_no, fl.floor_no, z.zone_name, "
        "ps.entry_time, TIMESTAMPDIFF(MINUTE, ps.entry_time, NOW()) AS minutes_parked, "
        "(SELECT t.rate_per_hour FROM TARIFF t "
        "WHERE t.vehicle_type_id = vt.vehicle_type_id "
        "AND t.effective_from <= DATE(ps.entry_time) "
        "ORDER BY t.effective_from DESC LIMIT 1) AS rate_per_hour "
        "FROM PARKING_SESSION ps "
        "JOIN VEHICLE v ON v.vehicle_id = ps.vehicle_id "
        "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = v.vehicle_type_id "
        "JOIN SLOT s ON s.slot_id = ps.slot_id "
        "JOIN ZONE z ON z.zone_id = s.zone_id "
        "JOIN FLOOR fl ON fl.floor_id = z.floor_id "
        "WHERE UPPER(v.reg_no) = %s AND ps.exit_time IS NULL "
        "ORDER BY ps.entry_time DESC LIMIT 1",
        (registration,),
    )
    if not rows:
        st.image(str(EMPTY_IMAGE), width=160)
        st.info(f"{registration} is not currently parked.")
        return

    car = rows[0]
    minutes = max(0, int(car["minutes_parked"]))
    hours, remaining_minutes = divmod(minutes, 60)
    duration = f"{hours}h {remaining_minutes}m"
    location = f"{floor_name(car['floor_no'])} · {zone_name(car['zone_name'])}"
    if car["rate_per_hour"] is None:
        fare = "Unavailable"
    else:
        fare = f"₹{float(car['rate_per_hour']) * minutes / 60:.2f}"

    with st.container(border=True):
        st.markdown(
            "<div class='ticket-card'><h3>🚘 Your car is parked</h3>"
            f"<div class='ticket-meta'><b>Vehicle:</b> {escape(car['reg_no'])} · "
            f"{escape(vehicle_label(car['type_name']))}<br>"
            f"<b>Location:</b> {escape(location)}<br>"
            f"<b>Slot:</b> {escape(car['slot_no'])}<br>"
            f"<b>Entry time:</b> {escape(car['entry_time'].strftime('%d-%m-%Y %H:%M'))}<br>"
            f"<b>Parked for:</b> {escape(duration)}<br>"
            f"<b>Fare so far:</b> {escape(fare)}</div></div>",
            unsafe_allow_html=True,
        )
        if car["rate_per_hour"] is None:
            st.warning("No applicable tariff was found for this parking session.")


def page_reservations():
    page_header("Reservations")
    show_flash()
    customers = db.query("SELECT customer_id, name, phone FROM CUSTOMER ORDER BY name")
    vehicles = db.query("SELECT v.vehicle_id, v.reg_no, v.vehicle_type_id, vt.type_name "
                        "FROM VEHICLE v JOIN VEHICLE_TYPE vt "
                        "ON vt.vehicle_type_id = v.vehicle_type_id ORDER BY v.reg_no")

    st.subheader("New reservation")
    if not customers or not vehicles:
        st.warning("Add customers and vehicles in Master Data first.")
    else:
        cust = options(customers, lambda r: f"{r['name']} ({r['phone']})")
        veh = options(vehicles, lambda r: f"{r['reg_no']} - {vehicle_label(r['type_name'])}")
        c1, c2 = st.columns(2)
        cust_label = c1.selectbox("Customer", list(cust))
        veh_label = c2.selectbox("Vehicle", list(veh))
        vehicle = veh[veh_label]
        all_slots = st.checkbox("Show all free slots (not only those matching the vehicle type)")
        sql = ("SELECT s.slot_id, s.slot_no, vt.type_name FROM SLOT s JOIN VEHICLE_TYPE vt "
               "ON vt.vehicle_type_id = s.vehicle_type_id WHERE s.status = 'FREE'")
        params = []
        if not all_slots:
            sql += " AND s.vehicle_type_id = %s"; params.append(vehicle["vehicle_type_id"])
        slots = db.query(sql + " ORDER BY s.slot_no", params)
        if not slots:
            st.warning("No free slot is available for this vehicle type.")
        else:
            slot_map = options(slots, lambda r: f"{r['slot_no']} ({vehicle_label(r['type_name'])})")
            with st.container(border=True), st.form("new_res"):
                slot_label = st.selectbox("Slot", list(slot_map))
                start = dt_input("Start", "res_start")
                hold = st.number_input("Hold slot for (minutes)", 5, 240, 30, step=5)
                if st.form_submit_button("Create reservation", type="primary"):
                    expiry = start + timedelta(minutes=int(hold))
                    try:
                        rid = db.execute(
                            "INSERT INTO RESERVATION (customer_id, slot_id, vehicle_id, "
                            "start_time, expiry_time) VALUES (%s, %s, %s, %s, %s)",
                            (cust[cust_label]["customer_id"], slot_map[slot_label]["slot_id"],
                             vehicle["vehicle_id"], start, expiry))
                        flash("success", f"Reservation #{rid} created. Slot "
                              f"{slot_map[slot_label]['slot_no']} is held until {expiry:%d-%m-%Y %H:%M}.")
                        st.rerun()
                    except DBError as e:
                        st.error(f"Reservation rejected: {e}")

    st.subheader("Cancel a reservation / run expiry check")
    active = db.query("SELECT r.reservation_id, v.reg_no, s.slot_no, r.expiry_time "
                      "FROM RESERVATION r JOIN VEHICLE v ON v.vehicle_id = r.vehicle_id "
                      "JOIN SLOT s ON s.slot_id = r.slot_id WHERE r.status = 'ACTIVE' "
                      "ORDER BY r.reservation_id")
    c1, c2 = st.columns(2)
    with c1:
        if active:
            act = options(active, lambda r: f"#{r['reservation_id']} - {r['reg_no']} - slot {r['slot_no']}")
            pick = st.selectbox("Active reservation", list(act))
            if st.button("Cancel reservation"):
                try:
                    db.execute("UPDATE RESERVATION SET status = 'CANCELLED' "
                               "WHERE reservation_id = %s AND status = 'ACTIVE'",
                               (act[pick]["reservation_id"],))
                    flash("success", f"Reservation {pick.split(' ')[0]} cancelled; slot released.")
                    st.rerun()
                except DBError as e:
                    st.error(str(e))
        else:
            st.caption("No active reservations.")
    with c2:
        st.write("Mark all overdue active reservations as EXPIRED and release their slots.")
        if st.button("Run expiry check"):
            before = db.query("SELECT COUNT(*) AS n FROM RESERVATION WHERE status = 'EXPIRED'")[0]["n"]
            db.call("sp_expire_reservations", ())
            after = db.query("SELECT COUNT(*) AS n FROM RESERVATION WHERE status = 'EXPIRED'")[0]["n"]
            flash("success", f"Expiry check complete: {after - before} reservation(s) expired.")
            st.rerun()

    st.subheader("All reservations")
    table(db.query(
        "SELECT r.reservation_id AS ID, c.name AS Customer, v.reg_no AS Vehicle, "
        "s.slot_no AS Slot, r.start_time AS Start, r.expiry_time AS Expiry, r.status AS Status "
        "FROM RESERVATION r JOIN CUSTOMER c ON c.customer_id = r.customer_id "
        "JOIN VEHICLE v ON v.vehicle_id = r.vehicle_id JOIN SLOT s ON s.slot_id = r.slot_id "
        "ORDER BY r.reservation_id DESC"))


def page_gate():
    page_header("Gate Entry / Exit")
    show_flash()
    entry_ticket = st.session_state.pop("entry_ticket", None)
    if entry_ticket:
        st.markdown(
            "<div class='ticket-card'><h3>🎟️ Entry Ticket</h3>"
            f"<div class='ticket-meta'><b>Vehicle:</b> {escape(entry_ticket['vehicle'])} · "
            f"{escape(entry_ticket['type'])}<br>"
            f"<b>Slot:</b> {escape(entry_ticket['slot'])}<br>"
            f"<b>Location:</b> {escape(entry_ticket['location'])}<br>"
            f"<b>Entry time:</b> {escape(entry_ticket['time'])}</div></div>",
            unsafe_allow_html=True,
        )
    exit_receipt = st.session_state.get("exit_receipt")
    if exit_receipt:
        st.markdown(
            "<div class='ticket-card'><h3>🧾 Parking Receipt</h3>"
            f"<div class='ticket-meta'><b>Vehicle:</b> {escape(exit_receipt['vehicle'])}<br>"
            f"<b>Bill:</b> #{escape(str(exit_receipt['bill_no']))}<br>"
            f"<b>Slot:</b> {escape(exit_receipt['slot'])} · "
            f"{escape(exit_receipt['location'])}<br>"
            f"<b>Entry:</b> {escape(exit_receipt['entry_time'])}<br>"
            f"<b>Exit:</b> {escape(exit_receipt['exit_time'])}<br>"
            f"<b>Parking duration:</b> {escape(str(exit_receipt['minutes']))} minutes<br>"
            f"<b>Rate:</b> ₹{escape(str(exit_receipt['rate']))}/hour<br>"
            f"<b>Amount:</b> ₹{escape(str(exit_receipt['amount']))}</div></div>",
            unsafe_allow_html=True,
        )
        receipt_html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Smart Parking Receipt</title><style>"
            "body{font:16px Arial,sans-serif;background:#f4f7fc;color:#0f1b2d;padding:32px}"
            ".receipt{max-width:560px;margin:auto;background:#fff;border-radius:18px;"
            "padding:28px;box-shadow:0 8px 24px #0f1b2d20;border-top:7px solid #1e5eff}"
            "h1{margin-top:0;color:#1e5eff}.line{display:flex;justify-content:space-between;"
            "gap:20px;padding:10px 0;border-bottom:1px solid #e5ebf5}"
            ".label{color:#66758b}.amount{font-size:1.25rem;font-weight:bold}"
            ".thanks{text-align:center;margin-top:24px;color:#1e5eff;font-weight:bold}"
            "</style></head><body><main class='receipt'><h1>🅿️ Smart Parking</h1>"
            "<p>Parking Receipt</p>"
            f"<div class='line'><span class='label'>Bill number</span>"
            f"<strong>#{escape(str(exit_receipt['bill_no']))}</strong></div>"
            f"<div class='line'><span class='label'>Vehicle</span>"
            f"<strong>{escape(exit_receipt['vehicle'])}</strong></div>"
            f"<div class='line'><span class='label'>Slot</span>"
            f"<strong>{escape(exit_receipt['slot'])}</strong></div>"
            f"<div class='line'><span class='label'>Location</span>"
            f"<strong>{escape(exit_receipt['location'])}</strong></div>"
            f"<div class='line'><span class='label'>Entry time</span>"
            f"<strong>{escape(exit_receipt['entry_time'])}</strong></div>"
            f"<div class='line'><span class='label'>Exit time</span>"
            f"<strong>{escape(exit_receipt['exit_time'])}</strong></div>"
            f"<div class='line'><span class='label'>Minutes</span>"
            f"<strong>{escape(str(exit_receipt['minutes']))}</strong></div>"
            f"<div class='line'><span class='label'>Rate per hour</span>"
            f"<strong>₹{escape(str(exit_receipt['rate']))}</strong></div>"
            f"<div class='line amount'><span>Amount</span>"
            f"<strong>₹{escape(str(exit_receipt['amount']))}</strong></div>"
            "<p class='thanks'>Thank you for parking with us</p>"
            "</main></body></html>"
        )
        st.download_button(
            "Download receipt",
            data=receipt_html,
            file_name=f"parking-receipt-{exit_receipt['bill_no']}.html",
            mime="text/html",
            key="download_parking_receipt",
        )
    entry_tab, exit_tab = st.tabs(["Vehicle entry", "Vehicle exit & billing"])

    with entry_tab:
        vehicles = db.query("SELECT v.vehicle_id, v.reg_no, vt.type_name, v.vehicle_type_id "
                            "FROM VEHICLE v JOIN VEHICLE_TYPE vt "
                            "ON vt.vehicle_type_id = v.vehicle_type_id ORDER BY v.reg_no")
        veh = options(vehicles, lambda r: f"{r['reg_no']} - {vehicle_label(r['type_name'])}")
        veh_label = st.selectbox("Vehicle", list(veh), key="entry_vehicle")
        vehicle = veh[veh_label]
        res_rows = db.query("SELECT r.reservation_id, s.slot_no, r.expiry_time FROM RESERVATION r "
                            "JOIN SLOT s ON s.slot_id = r.slot_id "
                            "WHERE r.vehicle_id = %s AND r.status = 'ACTIVE'", (vehicle["vehicle_id"],))
        res_map = {"Walk-in (no reservation)": None}
        res_map.update({f"Reservation #{r['reservation_id']} - slot {r['slot_no']} "
                        f"(expires {r['expiry_time']:%d-%m %H:%M})": r for r in res_rows})
        res_label = st.selectbox("Reservation", list(res_map))
        reservation = res_map[res_label]
        mode = "Automatic"
        if reservation is None:
            mode = st.radio("Slot allocation", ["Automatic", "Manual"], horizontal=True,
                            help="Automatic picks the first free slot that matches the vehicle type.")
        manual_slot = None
        if mode == "Manual":
            slots = db.query("SELECT s.slot_id, s.slot_no, vt.type_name, s.status FROM SLOT s "
                             "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = s.vehicle_type_id "
                             "ORDER BY s.slot_no")
            sm = options(slots, lambda r: f"{r['slot_no']} - "
                                           f"{vehicle_label(r['type_name'])} - {r['status']}")
            manual_slot = sm[st.selectbox("Slot", list(sm))]
        entry_time = dt_input("Entry", "entry")
        if st.button("Record entry", type="primary"):
            parked = db.query("SELECT s.slot_no FROM PARKING_SESSION ps JOIN SLOT s "
                              "ON s.slot_id = ps.slot_id WHERE ps.vehicle_id = %s "
                              "AND ps.exit_time IS NULL", (vehicle["vehicle_id"],))
            if parked:
                st.error(f"Entry rejected: {vehicle['reg_no']} is already parked in slot "
                         f"{parked[0]['slot_no']}.")
            else:
                try:
                    if manual_slot:
                        sid = db.execute("INSERT INTO PARKING_SESSION (slot_id, vehicle_id, entry_time) "
                                         "VALUES (%s, %s, %s)",
                                         (manual_slot["slot_id"], vehicle["vehicle_id"], entry_time))
                    else:
                        out = db.call("sp_vehicle_entry",
                                      (vehicle["vehicle_id"],
                                       reservation["reservation_id"] if reservation else None,
                                       entry_time, 0))
                        sid = out[3]
                    info = db.query("SELECT s.slot_no, fl.floor_no, z.zone_name FROM PARKING_SESSION ps "
                                    "JOIN SLOT s ON s.slot_id = ps.slot_id JOIN ZONE z ON z.zone_id = s.zone_id "
                                    "JOIN FLOOR fl ON fl.floor_id = z.floor_id WHERE ps.session_id = %s",
                                    (sid,))[0]
                    st.session_state["entry_ticket"] = {
                        "vehicle": vehicle["reg_no"],
                        "type": vehicle_label(vehicle["type_name"]),
                        "slot": info["slot_no"],
                        "location": f"{floor_name(info['floor_no'])} · {zone_name(info['zone_name'])}",
                        "time": entry_time.strftime("%d-%m-%Y %H:%M"),
                    }
                    flash("success", f"Entry recorded for {vehicle['reg_no']}: session #{sid}, "
                          f"slot {info['slot_no']} (floor {info['floor_no']}, zone {info['zone_name']}).")
                    st.rerun()
                except DBError as e:
                    st.error(f"Entry rejected: {e}")

    with exit_tab:
        open_rows = db.query("SELECT ps.session_id, v.reg_no, s.slot_no, ps.entry_time, "
                             "fl.floor_no, z.zone_name, "
                             "(SELECT t.rate_per_hour FROM TARIFF t "
                             "WHERE t.vehicle_type_id = vt.vehicle_type_id "
                             "AND t.effective_from <= DATE(ps.entry_time) "
                             "ORDER BY t.effective_from DESC LIMIT 1) AS rate_per_hour "
                             "FROM PARKING_SESSION ps JOIN VEHICLE v ON v.vehicle_id = ps.vehicle_id "
                             "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = v.vehicle_type_id "
                             "JOIN SLOT s ON s.slot_id = ps.slot_id "
                             "JOIN ZONE z ON z.zone_id = s.zone_id "
                             "JOIN FLOOR fl ON fl.floor_id = z.floor_id "
                             "WHERE ps.exit_time IS NULL "
                             "ORDER BY ps.entry_time")
        if not open_rows:
            st.info("No vehicles are parked right now.")
        else:
            om = options(open_rows, lambda r: f"Session #{r['session_id']} - {r['reg_no']} - slot "
                                              f"{r['slot_no']} (in {r['entry_time']:%d-%m %H:%M})")
            pick = om[st.selectbox("Parked vehicle", list(om))]
            exit_time = dt_input("Exit", "exit")
            minutes = max(0, int((exit_time - pick["entry_time"]).total_seconds() // 60))
            fare_columns = st.columns(3)
            fare_columns[0].metric("Minutes parked", minutes)
            if pick["rate_per_hour"] is None:
                fare_columns[1].metric("Rate per hour", "Unavailable")
                fare_columns[2].metric("Estimated charge", "Unavailable")
                st.warning("No applicable tariff was found for this parking session.")
            else:
                rate = float(pick["rate_per_hour"])
                estimate = rate * minutes / 60
                fare_columns[1].metric("Rate per hour", f"₹{rate:.2f}")
                fare_columns[2].metric("Estimated charge", f"₹{estimate:.2f}")
            if st.button("Record exit & generate bill", type="primary"):
                try:
                    db.call("sp_close_session", (pick["session_id"], exit_time))
                    bill = db.query(
                        "SELECT b.bill_id, b.amount, t.rate_per_hour, "
                        "TIMESTAMPDIFF(MINUTE, ps.entry_time, ps.exit_time) AS minutes, "
                        "ps.entry_time, ps.exit_time, s.slot_no, fl.floor_no, z.zone_name "
                        "FROM BILL b JOIN TARIFF t ON t.tariff_id = b.tariff_id "
                        "JOIN PARKING_SESSION ps ON ps.session_id = b.session_id "
                        "JOIN SLOT s ON s.slot_id = ps.slot_id "
                        "JOIN ZONE z ON z.zone_id = s.zone_id "
                        "JOIN FLOOR fl ON fl.floor_id = z.floor_id "
                        "WHERE b.session_id = %s", (pick["session_id"],))[0]
                    st.session_state["exit_receipt"] = {
                        "bill_no": bill["bill_id"],
                        "vehicle": pick["reg_no"],
                        "slot": bill["slot_no"],
                        "location": f"{floor_name(bill['floor_no'])} · {zone_name(bill['zone_name'])}",
                        "entry_time": bill["entry_time"].strftime("%d-%m-%Y %H:%M"),
                        "exit_time": bill["exit_time"].strftime("%d-%m-%Y %H:%M"),
                        "minutes": bill["minutes"],
                        "rate": bill["rate_per_hour"],
                        "amount": bill["amount"],
                    }
                    flash("success", f"Exit recorded for {pick['reg_no']}. Bill #{bill['bill_id']}: "
                          f"{bill['minutes']} min at ₹{bill['rate_per_hour']}/hour = ₹{bill['amount']}.")
                    st.rerun()
                except DBError as e:
                    st.error(f"Exit rejected: {e}")


def page_billing():
    page_header("Billing & Payments")
    show_flash()
    outstanding = db.query("SELECT bill_id, reg_no, amount, amount_paid, balance "
                           "FROM vw_bill_status WHERE balance > 0 ORDER BY bill_id")
    st.subheader("Record a payment")
    if not outstanding:
        st.info("All bills are fully paid.")
    else:
        bm = options(outstanding, lambda r: f"Bill #{r['bill_id']} - {r['reg_no']} - "
                                            f"balance ₹{r['balance']}")
        bill = bm[st.selectbox("Bill", list(bm))]
        with st.container(border=True), st.form("pay"):
            c1, c2 = st.columns(2)
            amount = c1.number_input("Amount (₹)", min_value=0.0,
                                     value=float(bill["balance"]), step=1.0, format="%.2f")
            mode = c2.selectbox("Payment mode", ["CASH", "CARD", "UPI", "WALLET"])
            paid_at = dt_input("Paid", "paid")
            if st.form_submit_button("Record payment", type="primary"):
                if amount > float(bill["balance"]):
                    st.error(f"Payment rejected: amount exceeds the outstanding balance "
                             f"of ₹{bill['balance']}.")
                else:
                    try:
                        pid = db.execute("INSERT INTO PAYMENT (bill_id, amount_paid, mode, paid_at) "
                                         "VALUES (%s, %s, %s, %s)",
                                         (bill["bill_id"], amount, mode, paid_at))
                        flash("success", f"Payment #{pid} of ₹{amount:.2f} ({mode}) recorded "
                              f"against bill #{bill['bill_id']}.")
                        st.rerun()
                    except DBError as e:
                        st.error(f"Payment rejected: {e}")

    st.subheader("Bills")
    only_due = st.checkbox("Show outstanding bills only")
    sql = ("SELECT bill_id AS Bill, session_id AS Session, reg_no AS Vehicle, amount AS Amount, "
           "amount_paid AS Paid, balance AS Balance FROM vw_bill_status")
    table(db.query(sql + (" WHERE balance > 0" if only_due else "") + " ORDER BY bill_id"))
    st.subheader("Payment history")
    table(db.query("SELECT payment_id AS Payment, bill_id AS Bill, amount_paid AS Amount, "
                   "mode AS Mode, paid_at AS `Paid at` FROM PAYMENT ORDER BY paid_at DESC"))


def page_passes():
    page_header("Passes")
    show_flash()
    customers = db.query("SELECT customer_id, name, phone FROM CUSTOMER ORDER BY name")
    vehicles = db.query("SELECT vehicle_id, reg_no FROM VEHICLE ORDER BY reg_no")
    st.subheader("Issue a pass")
    with st.container(border=True), st.form("pass"):
        cust = options(customers, lambda r: f"{r['name']} ({r['phone']})")
        veh = options(vehicles, lambda r: r["reg_no"])
        c1, c2 = st.columns(2)
        cl = c1.selectbox("Pass holder", list(cust))
        vl = c2.selectbox("Vehicle", list(veh))
        c3, c4 = st.columns(2)
        vf = c3.date_input("Valid from", date.today())
        vt = c4.date_input("Valid to", date.today() + timedelta(days=30))
        if st.form_submit_button("Issue pass", type="primary"):
            if vt <= vf:
                st.error("Pass rejected: 'valid to' must be after 'valid from'.")
            else:
                try:
                    pid = db.execute("INSERT INTO PASS (customer_id, vehicle_id, valid_from, valid_to) "
                                     "VALUES (%s, %s, %s, %s)",
                                     (cust[cl]["customer_id"], veh[vl]["vehicle_id"], vf, vt))
                    flash("success", f"Pass #{pid} issued for {vl}, valid {vf:%d-%m-%Y} to {vt:%d-%m-%Y}.")
                    st.rerun()
                except DBError as e:
                    st.error(f"Pass rejected: {e}")

    st.subheader("Check pass validity")
    reg = st.text_input("Vehicle registration number").strip().upper()
    if reg:
        rows = db.query("SELECT pa.pass_id AS Pass, c.name AS Holder, pa.valid_from AS `Valid from`, "
                        "pa.valid_to AS `Valid to` FROM PASS pa JOIN VEHICLE v ON v.vehicle_id = pa.vehicle_id "
                        "JOIN CUSTOMER c ON c.customer_id = pa.customer_id WHERE v.reg_no = %s "
                        "AND CURDATE() BETWEEN pa.valid_from AND pa.valid_to", (reg,))
        if rows:
            st.success(f"{reg} has a valid pass today.")
            pass_row = rows[0]
            st.markdown(
                "<div class='pass-card'><h3>🎫 Valid Parking Pass</h3>"
                f"<div class='ticket-meta'><b>Pass:</b> #{escape(str(pass_row['Pass']))}<br>"
                f"<b>Holder:</b> {escape(str(pass_row['Holder']))}<br>"
                f"<b>Valid:</b> {escape(str(pass_row['Valid from']))} – "
                f"{escape(str(pass_row['Valid to']))}</div></div>",
                unsafe_allow_html=True,
            )
            table(rows)
        else:
            st.warning(f"No pass valid today for {reg}.")

    st.subheader("All passes")
    table(db.query(
        "SELECT pa.pass_id AS Pass, c.name AS Holder, v.reg_no AS Vehicle, "
        "pa.valid_from AS `Valid from`, pa.valid_to AS `Valid to`, "
        "CASE WHEN CURDATE() BETWEEN pa.valid_from AND pa.valid_to THEN 'VALID' "
        "WHEN CURDATE() < pa.valid_from THEN 'UPCOMING' ELSE 'EXPIRED' END AS Status "
        "FROM PASS pa JOIN CUSTOMER c ON c.customer_id = pa.customer_id "
        "JOIN VEHICLE v ON v.vehicle_id = pa.vehicle_id ORDER BY pa.pass_id"))


PHONE_RE = re.compile(r"^[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
REG_RE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}$")


def page_master():
    page_header("Master Data")
    show_flash()
    t_cust, t_veh, t_slot, t_tariff = st.tabs(["Customers", "Vehicles", "Slots", "Tariffs"])

    with t_cust:
        with st.container(border=True), st.form("cust"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name").strip()
            phone = c2.text_input("Phone (10 digits)").strip()
            email = c3.text_input("Email (optional)").strip()
            if st.form_submit_button("Add customer", type="primary"):
                if not name:
                    st.error("Name is required.")
                elif not PHONE_RE.match(phone):
                    st.error("Enter a valid 10-digit mobile number.")
                elif email and not EMAIL_RE.match(email):
                    st.error("Enter a valid email address.")
                else:
                    try:
                        cid = db.execute("INSERT INTO CUSTOMER (name, phone, email) VALUES (%s, %s, %s)",
                                         (name, phone, email or None))
                        flash("success", f"Customer #{cid} ({name}) added.")
                        st.rerun()
                    except DBError as e:
                        st.error(f"Customer not added: {e}")
        customers = db.query("SELECT customer_id, name, phone, email FROM CUSTOMER ORDER BY customer_id")
        table([{"ID": r["customer_id"], "Name": r["name"], "Phone": r["phone"],
                "Email": r["email"]} for r in customers])
        if customers:
            cm = options(customers, lambda r: f"#{r['customer_id']} {r['name']}")
            st.markdown("**Update or delete a customer**")
            pick = cm[st.selectbox("Customer", list(cm), key="cust_pick")]
            c1, c2 = st.columns(2)
            new_phone = c1.text_input("New phone", pick["phone"], key=f"np{pick['customer_id']}")
            new_email = c2.text_input("New email", pick["email"] or "", key=f"ne{pick['customer_id']}")
            b1, b2, b3 = st.columns([1, 1, 2])
            if b1.button("Update"):
                if not PHONE_RE.match(new_phone.strip()):
                    st.error("Enter a valid 10-digit mobile number.")
                elif new_email.strip() and not EMAIL_RE.match(new_email.strip()):
                    st.error("Enter a valid email address.")
                else:
                    try:
                        db.execute("UPDATE CUSTOMER SET phone = %s, email = %s WHERE customer_id = %s",
                                   (new_phone.strip(), new_email.strip() or None, pick["customer_id"]))
                        flash("success", f"Customer #{pick['customer_id']} updated.")
                        st.rerun()
                    except DBError as e:
                        st.error(f"Update rejected: {e}")
            confirm = b3.checkbox("Confirm delete")
            if b2.button("Delete"):
                if not confirm:
                    st.warning("Tick 'Confirm delete' first.")
                else:
                    try:
                        db.execute("DELETE FROM CUSTOMER WHERE customer_id = %s", (pick["customer_id"],))
                        flash("success", f"Customer #{pick['customer_id']} deleted.")
                        st.rerun()
                    except DBError as e:
                        st.error(f"Delete rejected: {e}")

    with t_veh:
        customers = db.query("SELECT customer_id, name FROM CUSTOMER ORDER BY name")
        types = db.query("SELECT vehicle_type_id, type_name FROM VEHICLE_TYPE ORDER BY type_name")
        with st.container(border=True), st.form("veh"):
            cm = options(customers, lambda r: r["name"])
            tm = options(types, lambda r: vehicle_label(r["type_name"]))
            c1, c2, c3 = st.columns(3)
            owner = c1.selectbox("Owner", list(cm))
            vtype = c2.selectbox("Vehicle type", list(tm))
            reg = c3.text_input("Registration no. (e.g. TS09AB1234)").strip().upper().replace(" ", "")
            if st.form_submit_button("Add vehicle", type="primary"):
                if not REG_RE.match(reg):
                    st.error("Enter a valid registration number, e.g. TS09AB1234.")
                else:
                    try:
                        vid = db.execute("INSERT INTO VEHICLE (customer_id, vehicle_type_id, reg_no) "
                                         "VALUES (%s, %s, %s)",
                                         (cm[owner]["customer_id"], tm[vtype]["vehicle_type_id"], reg))
                        flash("success", f"Vehicle #{vid} ({reg}) added.")
                        st.rerun()
                    except DBError as e:
                        st.error(f"Vehicle not added: {e}")
        table(db.query("SELECT v.vehicle_id AS ID, v.reg_no AS `Reg. no.`, vt.type_name AS Type, "
                       "c.name AS Owner FROM VEHICLE v JOIN VEHICLE_TYPE vt "
                       "ON vt.vehicle_type_id = v.vehicle_type_id JOIN CUSTOMER c "
                       "ON c.customer_id = v.customer_id ORDER BY v.vehicle_id"))

    with t_slot:
        zones = db.query("SELECT z.zone_id, fl.floor_no, z.zone_name FROM ZONE z "
                         "JOIN FLOOR fl ON fl.floor_id = z.floor_id ORDER BY fl.floor_no, z.zone_name")
        types = db.query("SELECT vehicle_type_id, type_name FROM VEHICLE_TYPE ORDER BY type_name")
        with st.container(border=True), st.form("slot"):
            zm = options(
                zones,
                lambda r: f"{floor_name(r['floor_no'])} · {zone_name(r['zone_name'])}",
            )
            tm = options(types, lambda r: vehicle_label(r["type_name"]))
            c1, c2, c3 = st.columns(3)
            zone = c1.selectbox("Zone", list(zm))
            vtype = c2.selectbox("Vehicle type", list(tm))
            slot_no = c3.text_input("Slot number (e.g. A-04)").strip().upper()
            if st.form_submit_button("Add slot", type="primary"):
                if not slot_no:
                    st.error("Slot number is required.")
                else:
                    try:
                        db.execute("INSERT INTO SLOT (zone_id, vehicle_type_id, slot_no) VALUES (%s, %s, %s)",
                                   (zm[zone]["zone_id"], tm[vtype]["vehicle_type_id"], slot_no))
                        flash("success", f"Slot {slot_no} added.")
                        st.rerun()
                    except DBError as e:
                        st.error(f"Slot not added: {e}")
        slots = db.query("SELECT s.slot_id, s.slot_no, s.status FROM SLOT s ORDER BY s.slot_no")
        st.markdown("**Block or unblock a slot** (only free or blocked slots)")
        sm = options([r for r in slots if r["status"] in ("FREE", "BLOCKED")],
                     lambda r: f"{r['slot_no']} ({r['status']})")
        if sm:
            c1, c2 = st.columns([2, 1])
            pick = sm[c1.selectbox("Slot", list(sm))]
            new_status = "FREE" if pick["status"] == "BLOCKED" else "BLOCKED"
            if c2.button(f"Set {new_status}"):
                db.execute("UPDATE SLOT SET status = %s WHERE slot_id = %s AND status IN ('FREE','BLOCKED')",
                           (new_status, pick["slot_id"]))
                flash("success", f"Slot {pick['slot_no']} set to {new_status}.")
                st.rerun()

    with t_tariff:
        types = db.query("SELECT vehicle_type_id, type_name FROM VEHICLE_TYPE ORDER BY type_name")
        with st.container(border=True), st.form("tariff"):
            tm = options(types, lambda r: vehicle_label(r["type_name"]))
            c1, c2, c3 = st.columns(3)
            vtype = c1.selectbox("Vehicle type", list(tm))
            rate = c2.number_input("Rate per hour (₹)", min_value=0.0, value=20.0, step=1.0)
            eff = c3.date_input("Effective from", date.today())
            if st.form_submit_button("Add tariff", type="primary"):
                try:
                    db.execute("INSERT INTO TARIFF (vehicle_type_id, rate_per_hour, effective_from) "
                               "VALUES (%s, %s, %s)", (tm[vtype]["vehicle_type_id"], rate, eff))
                    flash("success", f"Tariff for {tm[vtype]['type_name']} "
                          f"(₹{rate:.2f}/hour from {eff:%d-%m-%Y}) added.")
                    st.rerun()
                except DBError as e:
                    st.error(f"Tariff not added: {e}")
        table(db.query("SELECT t.tariff_id AS ID, vt.type_name AS `Vehicle type`, "
                       "t.rate_per_hour AS `Rate / hour`, t.effective_from AS `Effective from` "
                       "FROM TARIFF t JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = t.vehicle_type_id "
                       "ORDER BY vt.type_name, t.effective_from"))


REPORTS = {
    "Occupancy": (
        "SELECT floor_no AS Floor, zone_name AS Zone, total_slots AS Total, "
        "occupied_slots AS Occupied, reserved_slots AS Reserved, free_slots AS Free, "
        "occupancy_pct AS `Occupancy %` FROM vw_zone_occupancy ORDER BY floor_no, zone_name",
        ("Zone", "Occupancy %")),
    "Peak hours": (
        "SELECT HOUR(entry_time) AS `Hour of day`, COUNT(*) AS Entries FROM PARKING_SESSION "
        "GROUP BY HOUR(entry_time) ORDER BY `Hour of day`",
        ("Hour of day", "Entries")),
    "Parking duration": (
        "SELECT vt.type_name AS `Vehicle type`, COUNT(*) AS Sessions, "
        "ROUND(AVG(TIMESTAMPDIFF(MINUTE, ps.entry_time, ps.exit_time)), 1) AS `Avg minutes`, "
        "MIN(TIMESTAMPDIFF(MINUTE, ps.entry_time, ps.exit_time)) AS `Min minutes`, "
        "MAX(TIMESTAMPDIFF(MINUTE, ps.entry_time, ps.exit_time)) AS `Max minutes` "
        "FROM PARKING_SESSION ps JOIN VEHICLE v ON v.vehicle_id = ps.vehicle_id "
        "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = v.vehicle_type_id "
        "WHERE ps.exit_time IS NOT NULL GROUP BY vt.type_name",
        ("Vehicle type", "Avg minutes")),
    "Pass usage": (
        "SELECT pa.pass_id AS Pass, c.name AS Holder, v.reg_no AS Vehicle, "
        "pa.valid_from AS `Valid from`, pa.valid_to AS `Valid to`, "
        "COUNT(ps.session_id) AS `Sessions used` FROM PASS pa "
        "JOIN CUSTOMER c ON c.customer_id = pa.customer_id "
        "JOIN VEHICLE v ON v.vehicle_id = pa.vehicle_id "
        "LEFT JOIN PARKING_SESSION ps ON ps.vehicle_id = pa.vehicle_id "
        "AND DATE(ps.entry_time) BETWEEN pa.valid_from AND pa.valid_to "
        "GROUP BY pa.pass_id, c.name, v.reg_no, pa.valid_from, pa.valid_to",
        None),
    "Violations - unpaid bills": (
        "SELECT bill_id AS Bill, session_id AS Session, reg_no AS Vehicle, amount AS Amount, "
        "amount_paid AS Paid, balance AS Balance FROM vw_bill_status WHERE balance > 0",
        None),
    "Violations - expired unused reservations": (
        "SELECT r.reservation_id AS Reservation, c.name AS Customer, v.reg_no AS Vehicle, "
        "s.slot_no AS Slot, r.expiry_time AS Expired FROM RESERVATION r "
        "JOIN CUSTOMER c ON c.customer_id = r.customer_id "
        "JOIN VEHICLE v ON v.vehicle_id = r.vehicle_id JOIN SLOT s ON s.slot_id = r.slot_id "
        "WHERE r.status = 'EXPIRED' AND NOT EXISTS (SELECT 1 FROM PARKING_SESSION ps "
        "WHERE ps.reservation_id = r.reservation_id)",
        None),
    "Free slots": (
        "SELECT slot_no AS Slot, floor_no AS Floor, zone_name AS Zone, type_name AS `Vehicle type` "
        "FROM vw_free_slots ORDER BY floor_no, zone_name, slot_no",
        None),
    "Revenue": (
        "SELECT DATE(p.paid_at) AS Date, vt.type_name AS `Vehicle type`, "
        "SUM(p.amount_paid) AS Revenue FROM PAYMENT p JOIN BILL b ON b.bill_id = p.bill_id "
        "JOIN PARKING_SESSION ps ON ps.session_id = b.session_id "
        "JOIN VEHICLE v ON v.vehicle_id = ps.vehicle_id "
        "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = v.vehicle_type_id "
        "GROUP BY DATE(p.paid_at), vt.type_name ORDER BY Date, `Vehicle type`",
        ("Vehicle type", "Revenue")),
}


REPORT_PRESENTATION = {
    "Occupancy": ("🅿️", "See how spaces are being used across every floor and zone."),
    "Peak hours": ("⏱️", "Spot the busiest arrival times from recorded entries."),
    "Parking duration": ("🚘", "Compare parking-session lengths by vehicle type."),
    "Pass usage": ("🎫", "Review pass holders and sessions during each pass period."),
    "Violations - unpaid bills": ("⚠️", "Find bills that still have an outstanding balance."),
    "Violations - expired unused reservations": (
        "⏰", "Find expired reservations that were never used."
    ),
    "Free slots": ("🟢", "Browse spaces that are currently available."),
    "Revenue": ("💰", "Track collected payments by date and vehicle type."),
}


def page_reports():
    page_header("Reports")
    name = st.selectbox("Report", list(REPORTS))
    icon, description = REPORT_PRESENTATION[name]
    st.markdown(f"### {icon} {name}")
    st.caption(description)
    sql, chart = REPORTS[name]
    rows = db.query(sql)
    table(rows, "This report has no rows for the current data.")
    report_csv = pd.DataFrame(display_rows(rows)).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Download as CSV",
        data=report_csv,
        file_name=f"{name.lower().replace(' ', '-').replace('/', '-')}.csv",
        mime="text/csv",
        key=f"download_report_{name}",
    )
    if rows and chart:
        df = pd.DataFrame(display_rows(rows))
        x, y = chart
        df[y] = pd.to_numeric(df[y])
        st.bar_chart(df.groupby(x, as_index=False)[y].sum(), x=x, y=y, color="#1E5EFF")
    with st.expander("SQL used for this report"):
        st.code(sql, language="sql")


# ------------------------------------------------------------------- main
def main():
    st.sidebar.image(str(ASSET_DIR / "logo.svg"), width=112)
    st.sidebar.title("Smart Parking")
    st.sidebar.caption("Lot Allocation & Billing System")
    default = st.query_params.get("page", "Dashboard")
    page_labels = [f"{PAGE_ICONS[page]} {page}" for page in PAGES]
    label_to_page = dict(zip(page_labels, PAGES))
    page = label_to_page[st.sidebar.radio(
        "Go to",
        page_labels,
        index=PAGES.index(default) if default in PAGES else 0,
    )]

    ok, err = db.database_ready()
    with st.sidebar.expander("Database setup"):
        st.write("Create the database (tables, rules, procedures, views and sample data) "
                 "from smart_parking.sql. If the database already has tables, they are only "
                 "replaced when PARKING_ALLOW_DB_RESET is true; otherwise nothing is changed.")
        sure = st.checkbox("I understand existing data will be reset")
        if st.button("Initialise database", disabled=not sure):
            try:
                n = db.initialise_database()
                flash("success", f"Database initialised ({n} SQL statements executed).")
                st.rerun()
            except Exception as e:  # noqa: BLE001 - show any setup failure
                st.error(f"Setup failed: {db.friendly(e)}")

    if not ok:
        page_header(page)
        st.title("Smart Parking Lot Allocation & Billing System")
        show_flash()
        st.error(f"Database not ready: {err}")
        st.write("Check the database settings (PARKING_DB_HOST, PARKING_DB_PORT, "
                 "PARKING_DB_USER, PARKING_DB_PASSWORD, PARKING_DB_NAME) described in "
                 "README.md. If the database is new and empty, open **Database setup** in "
                 "the sidebar and click **Initialise database**.")
        return

    try:
        {
            "Dashboard": page_dashboard,
            "Slot Search": page_slot_search,
            "Find My Car": page_find_my_car,
            "Reservations": page_reservations,
            "Gate Entry / Exit": page_gate,
            "Billing & Payments": page_billing,
            "Passes": page_passes,
            "Master Data": page_master,
            "Reports": page_reports,
        }[page]()
    except DBError as e:
        st.error(f"Database error: {e}")


main()
