"""Database access layer for the Smart Parking Lot Allocation and Billing System.

All SQL is sent through mysql-connector-python with parameterised queries
(%s placeholders), so user input is never concatenated into SQL text.
"""
import re
from pathlib import Path

import mysql.connector
from mysql.connector import errorcode

import config

SCRIPT_PATH = Path(__file__).with_name("smart_parking.sql")

# Friendly messages for constraint names raised by the database.
CONSTRAINT_MESSAGES = {
    "chk_sess_time": "Exit time must be after the entry time.",
    "chk_res_time": "Reservation expiry must be after its start time.",
    "chk_payment_amount": "Payment amount must be greater than zero.",
    "chk_payment_mode": "Payment mode must be CASH, CARD, UPI or WALLET.",
    "chk_pass_dates": "Pass 'valid to' date must be after 'valid from'.",
    "chk_tariff_rate": "Hourly rate must be greater than zero.",
    "chk_bill_amount": "Bill amount cannot be negative.",
    "chk_facility_floors": "A facility must have at least one floor.",
    "chk_slot_status": "Invalid slot status.",
    "uq_active_slot": "This slot already has a vehicle parked (one active vehicle per slot).",
    "uq_active_vehicle": "This vehicle is already parked in another slot (one active slot per vehicle).",
    "uq_active_reservation_slot": "This slot already has an active reservation.",
    "uq_vehicle_reg": "A vehicle with this registration number already exists.",
    "uq_customer_phone": "A customer with this phone number already exists.",
    "uq_customer_email": "A customer with this email already exists.",
    "uq_slot": "This slot number already exists in the selected zone.",
    "uq_tariff": "A tariff for this vehicle type and date already exists.",
    "uq_sess_reservation": "This reservation has already been used for an entry.",
}


class DBError(Exception):
    """Database error carrying a user-readable message."""


def connect(database=True):
    """Open a connection using the settings in config.py.

    Raises DBError with a readable message when the settings are missing or
    the server cannot be reached; no fallback or sample data is substituted.
    """
    issues = config.problems()
    if issues:
        raise DBError("Database is not configured. " + " ".join(issues) +
                      " Set them as environment variables (Render) or in "
                      ".streamlit/secrets.toml (local). See README.md.")
    params = dict(host=config.DB_HOST, port=config.DB_PORT,
                  user=config.DB_USER, password=config.DB_PASSWORD,
                  connection_timeout=config.DB_CONNECT_TIMEOUT)
    params.update(config.ssl_params())
    if database:
        params["database"] = config.DB_NAME
    try:
        conn = mysql.connector.connect(**params)
        cur = conn.cursor()
        if config.ssl_required():
            cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            row = cur.fetchone()
            if not row or not row[1]:
                conn.close()
                raise DBError("PARKING_DB_SSL_MODE requires SSL, but the MySQL "
                              "connection is not encrypted.")
        if config.DB_TIME_ZONE:  # hosted MySQL usually runs on UTC
            cur.execute("SET time_zone = %s", (config.DB_TIME_ZONE,))
        cur.close()
        return conn
    except mysql.connector.Error as e:
        raise DBError(friendly(e)) from e


def friendly(err):
    """Convert a mysql.connector error into a readable message."""
    msg = getattr(err, "msg", str(err))
    for name, text in CONSTRAINT_MESSAGES.items():
        if name in msg:
            return text
    if getattr(err, "errno", None) == errorcode.ER_ROW_IS_REFERENCED_2:
        return "This record is used by other records and cannot be deleted."
    if getattr(err, "errno", None) == errorcode.ER_NO_REFERENCED_ROW_2:
        return "A referenced record does not exist."
    if getattr(err, "sqlstate", None) == "45000":   # SIGNAL from trigger/procedure
        return msg
    errno = getattr(err, "errno", None)
    if errno in (errorcode.CR_CONN_HOST_ERROR, errorcode.CR_UNKNOWN_HOST,
                 errorcode.CR_CONNECTION_ERROR, errorcode.CR_SERVER_LOST):
        return (f"Cannot reach the MySQL server at {config.DB_HOST}:{config.DB_PORT}. "
                "Check that the database is running and that PARKING_DB_HOST and "
                f"PARKING_DB_PORT are correct. ({msg})")
    if "CERTIFICATE_VERIFY_FAILED" in msg or "certificate verify failed" in msg:
        return ("The MySQL server's SSL certificate could not be verified. Check that "
                "PARKING_DB_SSL_CA (or PARKING_DB_SSL_CA_PEM) holds your provider's CA "
                "certificate, and use PARKING_DB_SSL_MODE=verify_ca unless the host name "
                "matches the certificate.")
    if errno == errorcode.ER_ACCESS_DENIED_ERROR:
        return ("MySQL rejected the username or password. Check PARKING_DB_USER and "
                "PARKING_DB_PASSWORD.")
    if errno == errorcode.ER_BAD_DB_ERROR:
        return (f"The database '{config.DB_NAME}' does not exist yet. Open Database setup "
                "in the sidebar and click Initialise database.")
    if errno == errorcode.ER_NO_SUCH_TABLE:
        return ("The database has no parking tables yet. Open Database setup in the "
                "sidebar and click Initialise database.")
    if errno == errorcode.ER_BINLOG_CREATE_ROUTINE_NEED_SUPER:
        return ("This MySQL server does not let this user create the project's triggers, "
                "function and stored procedures (binary logging is on and the user has no "
                "SUPER privilege). Ask the MySQL host to set "
                "log_bin_trust_function_creators = ON, then run the setup again.")
    return msg


def query(sql, params=None):
    """Run a SELECT and return a list of dict rows."""
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        return cur.fetchall()
    except mysql.connector.Error as e:
        raise DBError(friendly(e)) from e
    finally:
        conn.close()


def execute(sql, params=None):
    """Run one INSERT/UPDATE/DELETE in a transaction; return lastrowid."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        conn.commit()
        return cur.lastrowid
    except mysql.connector.Error as e:
        conn.rollback()
        raise DBError(friendly(e)) from e
    finally:
        conn.close()


def call(proc, args):
    """Call a stored procedure; return its IN/OUT arguments."""
    conn = connect()
    try:
        cur = conn.cursor()
        result = cur.callproc(proc, args)
        conn.commit()
        return result
    except mysql.connector.Error as e:
        conn.rollback()
        raise DBError(friendly(e)) from e  # readable message
    finally:
        conn.close()


def split_script(text):
    """Split a MySQL script into statements, honouring DELIMITER lines."""
    statements, buf, delim = [], [], ";"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER"):
            delim = stripped.split()[1]
            continue
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        buf.append(line)
        if stripped.endswith(delim):
            stmt = "\n".join(buf).rstrip()
            stmt = stmt[: -len(delim)].strip()
            if stmt:
                statements.append(stmt)
            buf = []
    return statements


def _count(cur, sql, params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _check_can_create_routines(cur):
    """Stop before changing anything if the server will refuse triggers/procedures."""
    cur.execute("SELECT @@log_bin, @@log_bin_trust_function_creators, CURRENT_USER()")
    log_bin, trust, current = cur.fetchone()
    if not int(log_bin or 0) or int(trust or 0):
        return
    user, _, host = str(current).rpartition("@")
    grantee = f"'{user}'@'{host}'"
    has_super = _count(cur, "SELECT COUNT(*) FROM information_schema.USER_PRIVILEGES "
                            "WHERE GRANTEE = %s AND PRIVILEGE_TYPE = 'SUPER'", (grantee,))
    if not has_super:
        raise DBError(friendly(mysql.connector.Error(
            errno=errorcode.ER_BINLOG_CREATE_ROUTINE_NEED_SUPER, msg="")) +
            " Nothing was changed.")


def initialise_database():
    """Create the database objects and sample data from smart_parking.sql.

    Existing data is protected: if the database already contains tables, it
    is only dropped and rebuilt when PARKING_ALLOW_DB_RESET is true.
    """
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    conn = connect(database=False)
    try:
        cur = conn.cursor()
        name = config.DB_NAME  # validated in config.problems()
        exists = _count(cur, "SELECT COUNT(*) FROM information_schema.SCHEMATA "
                             "WHERE SCHEMA_NAME = %s", (name,)) > 0
        tables = _count(cur, "SELECT COUNT(*) FROM information_schema.TABLES "
                             "WHERE TABLE_SCHEMA = %s", (name,)) if exists else 0
        _check_can_create_routines(cur)
        if tables:
            if not config.ALLOW_DB_RESET:
                raise DBError(f"The database '{name}' already contains {tables} table(s), so "
                              "it was left untouched to protect existing data. To rebuild it, "
                              "set PARKING_ALLOW_DB_RESET=true (this deletes all data).")
            cur.execute(f"DROP DATABASE `{name}`")
            exists = False
        count = 0
        for stmt in split_script(text):
            if re.match(r"CREATE DATABASE\b", stmt, re.I) and exists:
                continue  # hosted databases are often pre-created
            if re.match(r"(CREATE DATABASE|USE)\b", stmt, re.I):
                stmt = re.sub(r"smart_parking", name, stmt)
            cur.execute(stmt)
            if cur.with_rows:
                cur.fetchall()
            count += 1
        conn.commit()
        return count
    except mysql.connector.Error as e:
        raise DBError(friendly(e)) from e
    finally:
        conn.close()


def database_ready():
    try:
        query("SELECT 1 FROM SLOT LIMIT 1")
        return True, ""
    except DBError as e:
        return False, str(e)
    except mysql.connector.Error as e:
        return False, friendly(e)
