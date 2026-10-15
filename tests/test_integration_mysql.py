"""Business-rule tests against a real MySQL server.

Skipped unless PARKING_RUN_DB_TESTS=1. These tests WRITE to the database, so
point the PARKING_DB_* settings at a disposable, EMPTY test database only -
never at real data.
"""
import itertools
import os
import threading
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.skipif(os.getenv("PARKING_RUN_DB_TESTS") != "1",
                                reason="set PARKING_RUN_DB_TESTS=1 and PARKING_DB_* for a test MySQL")

NOW = datetime.now().replace(second=0, microsecond=0)
_seq = itertools.count(1)


@pytest.fixture(scope="module")
def db():
    import importlib
    import config
    import db as db_module
    importlib.reload(config)
    importlib.reload(db_module)
    db_module.initialise_database()
    return db_module


# ----------------------------------------------------------------- helpers
def type_id(db, type_name):
    return db.query("SELECT vehicle_type_id FROM VEHICLE_TYPE WHERE type_name = %s",
                    (type_name,))[0]["vehicle_type_id"]


def new_vehicle(db, type_name):
    """Create a test customer and vehicle of the given type; return vehicle_id."""
    n = next(_seq)
    cid = db.execute("INSERT INTO CUSTOMER (name, phone) VALUES (%s, %s)",
                     (f"Test Customer {n}", f"7{n:09d}"))
    return db.execute("INSERT INTO VEHICLE (customer_id, vehicle_type_id, reg_no) VALUES (%s, %s, %s)",
                      (cid, type_id(db, type_name), f"TS99ZZ{n:04d}"))


def customer_of(db, vehicle_id):
    return db.query("SELECT customer_id FROM VEHICLE WHERE vehicle_id = %s", (vehicle_id,))[0]["customer_id"]


def new_slot(db, type_name):
    return db.execute("INSERT INTO SLOT (zone_id, vehicle_type_id, slot_no) VALUES (1, %s, %s)",
                      (type_id(db, type_name), f"T-{next(_seq):02d}"))


def slot_status(db, slot_id):
    return db.query("SELECT status FROM SLOT WHERE slot_id = %s", (slot_id,))[0]["status"]


def enter(db, vehicle_id, when=NOW, reservation_id=None):
    return db.call("sp_vehicle_entry", (vehicle_id, reservation_id, when, 0))[3]


def leave(db, session_id, when):
    db.call("sp_close_session", (session_id, when))


def reserve(db, slot_id, vehicle_id, start=NOW, minutes=30):
    return db.execute("INSERT INTO RESERVATION (customer_id, slot_id, vehicle_id, start_time, expiry_time) "
                      "VALUES (%s, %s, %s, %s, %s)",
                      (customer_of(db, vehicle_id), slot_id, vehicle_id, start,
                       start + timedelta(minutes=minutes)))


def run_together(funcs):
    """Start all callables at the same moment; return a list of (ok, result)."""
    barrier = threading.Barrier(len(funcs))
    results = [None] * len(funcs)

    def worker(i, fn):
        barrier.wait()
        try:
            results[i] = (True, fn())
        except Exception as e:  # noqa: BLE001
            results[i] = (False, str(e))
    threads = [threading.Thread(target=worker, args=(i, f)) for i, f in enumerate(funcs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


# ----------------------------------------------------------- initialisation
def test_database_objects_created(db):
    ok, message = db.database_ready()
    assert ok, message
    o = db.query(
        "SELECT (SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
        "        AND TABLE_TYPE = 'BASE TABLE') AS t, "
        "(SELECT COUNT(*) FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE()) AS v, "
        "(SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE()) AS tr, "
        "(SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE() "
        "        AND ROUTINE_TYPE = 'PROCEDURE') AS p, "
        "(SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE() "
        "        AND ROUTINE_TYPE = 'FUNCTION') AS f")[0]
    assert (o["t"], o["v"], o["tr"], o["p"], o["f"]) == (13, 3, 9, 3, 1)


def test_setup_never_wipes_existing_data(db):
    if db.config.ALLOW_DB_RESET:
        pytest.skip("PARKING_ALLOW_DB_RESET is true for this run")
    before = db.query("SELECT COUNT(*) AS n FROM PARKING_SESSION")[0]["n"]
    with pytest.raises(db.DBError, match="left untouched"):
        db.initialise_database()
    assert db.query("SELECT COUNT(*) AS n FROM PARKING_SESSION")[0]["n"] == before


# ------------------------------------------------------- allocation & entry
def test_auto_allocation_picks_free_matching_slot(db):
    sid = enter(db, new_vehicle(db, "SUV"))
    row = db.query("SELECT s.status, vt.type_name FROM PARKING_SESSION ps "
                   "JOIN SLOT s ON s.slot_id = ps.slot_id "
                   "JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = s.vehicle_type_id "
                   "WHERE ps.session_id = %s", (sid,))[0]
    assert row == {"status": "OCCUPIED", "type_name": "SUV"}
    leave(db, sid, NOW + timedelta(minutes=10))


def test_vehicle_cannot_be_parked_twice(db):
    new_slot(db, "CAR")
    vid = new_vehicle(db, "CAR")
    sid = enter(db, vid)
    with pytest.raises(db.DBError, match="already parked in another slot"):
        enter(db, vid)
    leave(db, sid, NOW + timedelta(minutes=5))


def test_slot_cannot_hold_two_vehicles(db):
    slot = new_slot(db, "CAR")
    v1, v2 = new_vehicle(db, "CAR"), new_vehicle(db, "CAR")
    s1 = db.execute("INSERT INTO PARKING_SESSION (slot_id, vehicle_id, entry_time) VALUES (%s, %s, %s)",
                    (slot, v1, NOW))
    with pytest.raises(db.DBError, match="Slot is not free"):
        db.execute("INSERT INTO PARKING_SESSION (slot_id, vehicle_id, entry_time) VALUES (%s, %s, %s)",
                   (slot, v2, NOW))
    # even if the status flag were wrong, the unique index still blocks it
    db.execute("UPDATE SLOT SET status = 'FREE' WHERE slot_id = %s", (slot,))
    with pytest.raises(db.DBError, match="one active vehicle per slot"):
        db.execute("INSERT INTO PARKING_SESSION (slot_id, vehicle_id, entry_time) VALUES (%s, %s, %s)",
                   (slot, v2, NOW))
    leave(db, s1, NOW + timedelta(minutes=1))


def test_slot_type_must_match_vehicle(db):
    slot = new_slot(db, "CAR")
    with pytest.raises(db.DBError, match="does not match vehicle type"):
        db.execute("INSERT INTO PARKING_SESSION (slot_id, vehicle_id, entry_time) VALUES (%s, %s, %s)",
                   (slot, new_vehicle(db, "TWO_WHEELER"), NOW))


def test_no_free_slot_gives_clear_error(db):
    suv = type_id(db, "SUV")
    blocked = [r["slot_id"] for r in db.query(
        "SELECT slot_id FROM SLOT WHERE status = 'FREE' AND vehicle_type_id = %s", (suv,))]
    for s in blocked:
        db.execute("UPDATE SLOT SET status = 'BLOCKED' WHERE slot_id = %s", (s,))
    try:
        with pytest.raises(db.DBError, match="No free compatible slot"):
            enter(db, new_vehicle(db, "SUV"))
    finally:
        for s in blocked:
            db.execute("UPDATE SLOT SET status = 'FREE' WHERE slot_id = %s", (s,))


def test_simultaneous_entries_never_share_a_slot(db):
    new_slot(db, "SUV")
    vehicles = [new_vehicle(db, "SUV") for _ in range(3)]
    results = run_together([lambda v=v: enter(db, v) for v in vehicles])
    sessions = [r for ok, r in results if ok]
    assert sessions
    slots = [db.query("SELECT slot_id FROM PARKING_SESSION WHERE session_id = %s", (s,))[0]["slot_id"]
             for s in sessions]
    assert len(set(slots)) == len(slots)
    for s in sessions:
        leave(db, s, NOW + timedelta(minutes=1))


# ------------------------------------------------------------ reservations
def test_reservation_conflict_and_cancel(db):
    slot = new_slot(db, "CAR")
    v1, v2 = new_vehicle(db, "CAR"), new_vehicle(db, "CAR")
    rid = reserve(db, slot, v1)
    assert slot_status(db, slot) == "RESERVED"
    with pytest.raises(db.DBError, match="not available for reservation"):
        reserve(db, slot, v2)
    db.execute("UPDATE RESERVATION SET status = 'CANCELLED' WHERE reservation_id = %s", (rid,))
    assert slot_status(db, slot) == "FREE"


def test_simultaneous_reservations_only_one_wins(db):
    slot = new_slot(db, "CAR")
    vehicles = [new_vehicle(db, "CAR") for _ in range(4)]
    results = run_together([lambda v=v: reserve(db, slot, v) for v in vehicles])
    assert sum(ok for ok, _ in results) == 1
    active = db.query("SELECT COUNT(*) AS n FROM RESERVATION WHERE slot_id = %s AND status = 'ACTIVE'",
                      (slot,))[0]["n"]
    assert active == 1


def test_reserved_entry_window_and_expiry(db):
    slot = new_slot(db, "CAR")
    vid = new_vehicle(db, "CAR")
    rid = reserve(db, slot, vid)
    with pytest.raises(db.DBError, match="not active or has expired"):
        enter(db, vid, NOW + timedelta(minutes=45), rid)          # arrives too late
    sid = enter(db, vid, NOW + timedelta(minutes=10), rid)        # arrives in time
    assert db.query("SELECT status FROM RESERVATION WHERE reservation_id = %s",
                    (rid,))[0]["status"] == "FULFILLED"
    leave(db, sid, NOW + timedelta(minutes=20))
    old = reserve(db, slot, vid, start=NOW - timedelta(hours=2), minutes=60)
    db.call("sp_expire_reservations", ())
    assert db.query("SELECT status FROM RESERVATION WHERE reservation_id = %s",
                    (old,))[0]["status"] == "EXPIRED"
    assert slot_status(db, slot) == "FREE"


# ----------------------------------------------------------------- billing
@pytest.mark.parametrize("minutes", [1, 59, 60, 90, 24 * 60 + 1])
def test_bill_equals_rate_times_minutes(db, minutes):
    sid = enter(db, new_vehicle(db, "CAR"))
    leave(db, sid, NOW + timedelta(minutes=minutes))
    bill = db.query("SELECT b.amount, t.rate_per_hour FROM BILL b JOIN TARIFF t "
                    "ON t.tariff_id = b.tariff_id WHERE b.session_id = %s", (sid,))[0]
    expected = round(float(bill["rate_per_hour"]) * minutes / 60, 2)
    assert float(bill["amount"]) == pytest.approx(expected, abs=0.005)


def test_latest_tariff_in_force_is_used(db):
    bike = type_id(db, "TWO_WHEELER")
    db.execute("INSERT INTO TARIFF (vehicle_type_id, rate_per_hour, effective_from) VALUES (%s, 12.00, %s)",
               (bike, (NOW - timedelta(days=1)).date()))
    db.execute("INSERT INTO TARIFF (vehicle_type_id, rate_per_hour, effective_from) VALUES (%s, 99.00, %s)",
               (bike, (NOW + timedelta(days=30)).date()))         # future rate must not apply
    sid = enter(db, new_vehicle(db, "TWO_WHEELER"))
    leave(db, sid, NOW + timedelta(minutes=60))
    assert float(db.query("SELECT amount FROM BILL WHERE session_id = %s", (sid,))[0]["amount"]) == 12.00


def test_session_cannot_be_billed_twice(db):
    sid = enter(db, new_vehicle(db, "CAR"))
    leave(db, sid, NOW + timedelta(minutes=30))
    with pytest.raises(db.DBError, match="already closed"):
        leave(db, sid, NOW + timedelta(minutes=40))
    results = run_together([lambda: leave(db, sid, NOW + timedelta(minutes=50))] * 2)
    assert not any(ok for ok, _ in results)
    assert db.query("SELECT COUNT(*) AS n FROM BILL WHERE session_id = %s", (sid,))[0]["n"] == 1


def test_simultaneous_exits_bill_once(db):
    sid = enter(db, new_vehicle(db, "CAR"))
    results = run_together([lambda: leave(db, sid, NOW + timedelta(minutes=30))] * 3)
    assert sum(ok for ok, _ in results) == 1
    assert db.query("SELECT COUNT(*) AS n FROM BILL WHERE session_id = %s", (sid,))[0]["n"] == 1


def test_failed_exit_rolls_back(db):
    sid = enter(db, new_vehicle(db, "CAR"))
    with pytest.raises(db.DBError, match="Exit time must be after the entry time"):
        leave(db, sid, NOW - timedelta(minutes=5))
    assert db.query("SELECT exit_time FROM PARKING_SESSION WHERE session_id = %s",
                    (sid,))[0]["exit_time"] is None               # still parked
    assert db.query("SELECT COUNT(*) AS n FROM BILL WHERE session_id = %s", (sid,))[0]["n"] == 0
    leave(db, sid, NOW + timedelta(minutes=1))


# ---------------------------------------------------------------- payments
def test_overpayment_rejected_including_simultaneous(db):
    sid = enter(db, new_vehicle(db, "CAR"))
    leave(db, sid, NOW + timedelta(minutes=60))
    bill = db.query("SELECT bill_id, amount FROM BILL WHERE session_id = %s", (sid,))[0]
    amount = float(bill["amount"])
    with pytest.raises(db.DBError, match="exceeds the outstanding balance"):
        db.execute("INSERT INTO PAYMENT (bill_id, amount_paid, mode) VALUES (%s, %s, 'UPI')",
                   (bill["bill_id"], amount + 1))

    def pay():
        return db.execute("INSERT INTO PAYMENT (bill_id, amount_paid, mode) VALUES (%s, %s, 'CASH')",
                          (bill["bill_id"], amount))
    results = run_together([pay, pay, pay])
    assert sum(ok for ok, _ in results) == 1
    status = db.query("SELECT amount_paid, balance FROM vw_bill_status WHERE bill_id = %s",
                      (bill["bill_id"],))[0]
    assert float(status["amount_paid"]) == amount and float(status["balance"]) == 0


def test_invalid_payment_mode_rejected(db):
    bill_id = db.query("SELECT bill_id FROM vw_bill_status WHERE balance > 0 LIMIT 1")[0]["bill_id"]
    with pytest.raises(db.DBError, match="Payment mode must be"):
        db.execute("INSERT INTO PAYMENT (bill_id, amount_paid, mode) VALUES (%s, 1, 'BITCOIN')", (bill_id,))


# ---------------------------------------------------- duplicates & security
def test_duplicate_registration_rejected(db):
    reg = db.query("SELECT reg_no FROM VEHICLE LIMIT 1")[0]["reg_no"]
    with pytest.raises(db.DBError, match="registration number already exists"):
        db.execute("INSERT INTO VEHICLE (customer_id, vehicle_type_id, reg_no) VALUES (1, 2, %s)", (reg,))


def test_sql_injection_is_treated_as_plain_text(db):
    before = db.query("SELECT COUNT(*) AS n FROM VEHICLE")[0]["n"]
    attack = "x' OR '1'='1'; DROP TABLE VEHICLE; -- "
    assert db.query("SELECT * FROM VEHICLE WHERE reg_no = %s", (attack,)) == []
    cid = db.execute("INSERT INTO CUSTOMER (name, phone) VALUES (%s, %s)", (attack, "6999999999"))
    assert db.query("SELECT name FROM CUSTOMER WHERE customer_id = %s", (cid,))[0]["name"] == attack
    assert db.query("SELECT COUNT(*) AS n FROM VEHICLE")[0]["n"] == before


def test_customer_with_vehicles_cannot_be_deleted(db):
    with pytest.raises(db.DBError, match="used by other records"):
        db.execute("DELETE FROM CUSTOMER WHERE customer_id = 1")


# ----------------------------------------------------------------- reports
def test_dashboard_figures_match_tables(db):
    counts = {r["status"]: r["n"] for r in db.query("SELECT status, COUNT(*) AS n FROM SLOT GROUP BY status")}
    occ = db.query("SELECT SUM(total_slots) AS t, SUM(occupied_slots) AS o, SUM(free_slots) AS f "
                   "FROM vw_zone_occupancy")[0]
    assert int(occ["t"]) == sum(counts.values())
    assert int(occ["o"]) == counts.get("OCCUPIED", 0)
    assert int(occ["f"]) == counts.get("FREE", 0)
    open_sessions = db.query("SELECT COUNT(*) AS n FROM PARKING_SESSION WHERE exit_time IS NULL")[0]["n"]
    assert counts.get("OCCUPIED", 0) == open_sessions
    assert db.query("SELECT COUNT(*) AS n FROM vw_free_slots")[0]["n"] == counts.get("FREE", 0)
    paid = float(db.query("SELECT COALESCE(SUM(amount_paid), 0) AS r FROM PAYMENT")[0]["r"])
    view_paid = float(db.query("SELECT COALESCE(SUM(amount_paid), 0) AS r FROM vw_bill_status")[0]["r"])
    assert paid == pytest.approx(view_paid)
    assert db.query("SELECT COUNT(*) AS n FROM vw_bill_status "
                    "WHERE ABS(balance - (amount - amount_paid)) > 0.001")[0]["n"] == 0


def test_report_queries_in_script_run(db):
    statements = db.split_script(db.SCRIPT_PATH.read_text(encoding="utf-8"))
    reports = [s for s in statements[statements.index(next(s for s in statements
               if s.upper().startswith("CREATE VIEW VW_BILL_STATUS"))) + 1:]
               if s.upper().startswith("SELECT")]
    assert len(reports) >= 7
    for sql in reports:
        db.query(sql)                                              # must not raise


def test_connection_uses_ssl_when_required(db):
    if not db.config.ssl_required():
        pytest.skip("PARKING_DB_SSL_MODE does not require SSL")
    assert db.query("SHOW SESSION STATUS LIKE 'Ssl_cipher'")[0]["Value"]
