# Smart Parking Lot Allocation and Billing System

DBMS Project-Based Learning – Vishnu Hasini (25WU0101153)

A MySQL database with a Python (Streamlit) web application for slot search,
reservations, gate entry/exit with automatic slot allocation, duration-based
billing, passes, payments and reports.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit user interface |
| `db.py` | Database access: connections (with SSL), parameterised queries, procedure calls, safe database setup |
| `config.py` | Reads the database settings from environment variables or `.streamlit/secrets.toml` (no passwords in code) |
| `smart_parking.sql` | Complete database script for a NEW database (tables, triggers, procedures, views, sample data, report queries) |
| `migrations/` | Upgrade scripts for a database created with an earlier `smart_parking.sql` |
| `requirements.txt` | Python packages needed to run the app |
| `requirements-dev.txt` | Adds `pytest` for running the tests |
| `.env.example` | Names of the settings for Render (placeholders only) |
| `render.yaml` | Render Blueprint: Python runtime, build/start commands, settings |
| `.streamlit/secrets.toml.example` | Template for local settings |
| `.streamlit/config.toml` | App theme |
| `assets/` | Logo and illustrations |
| `tests/` | Automated tests |

## Settings

| Setting | Required | Example (placeholder) | Meaning |
|---------|----------|-----------------------|---------|
| `PARKING_DB_HOST` | yes | `your-mysql-host.example.com` | MySQL server host (default `localhost`) |
| `PARKING_DB_PORT` | yes | `3306` | MySQL port |
| `PARKING_DB_USER` | yes | `parking_app` | MySQL user (use a dedicated user, not `root`, in production) |
| `PARKING_DB_PASSWORD` | yes | `change-me` | Password of that user |
| `PARKING_DB_NAME` | no | `smart_parking` | Database name (letters, digits, `_`) |
| `PARKING_DB_SSL_MODE` | no | `verify_ca` | `disabled`, `preferred` (default), `required`, `verify_ca`, `verify_identity` |
| `PARKING_DB_SSL_CA` | for `verify_*` | `/etc/secrets/ca.pem` | Path to the provider's CA certificate |
| `PARKING_DB_SSL_CA_PEM` | alternative | `-----BEGIN CERTIFICATE-----...` | CA certificate text instead of a file |
| `PARKING_DB_TIME_ZONE` | no | `+05:30` | Session time zone (hosted MySQL usually runs on UTC) |
| `TZ` | no | `Asia/Kolkata` | Time zone of the app server (default dates and times) |
| `PARKING_ALLOW_DB_RESET` | no | `false` | When `true`, **Initialise database** may delete and rebuild an existing database |

Each value is read from an environment variable first, then from
`.streamlit/secrets.toml`. Never commit `.streamlit/secrets.toml` or `.env`;
both are listed in `.gitignore`.

If the settings are missing or the server cannot be reached, the app shows a
clear "Database not ready" message. It never substitutes sample or fake data.

## Run locally (Windows)

1. Install **MySQL Community Server 8.x** and make sure it is running.
2. Install **Python 3**, then in this folder run:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in
   your local MySQL user and password.
4. Start the app:
   ```
   streamlit run app.py
   ```
   It opens at http://localhost:8501.
5. First time only: in the sidebar open **Database setup**, tick the box and click
   **Initialise database**. This creates the `smart_parking` database with sample data.

You can also load the database with the MySQL client:
`mysql -u <user> -p < smart_parking.sql`

## Deploy on Render

### 1. Hosted MySQL database (done in your provider's dashboard)

Render does not host MySQL for this app, so use a hosted MySQL 8 service.

1. Create a MySQL 8 database named `smart_parking` (or note the name the provider gives).
2. Create a dedicated user (for example `parking_app`) with privileges on that
   database only: SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX,
   REFERENCES, CREATE VIEW, SHOW VIEW, TRIGGER, CREATE ROUTINE, ALTER ROUTINE,
   EXECUTE.
3. The project uses triggers, a stored function and stored procedures. Most hosted
   MySQL servers have binary logging on, so the server must allow these for a
   non-SUPER user: `log_bin_trust_function_creators = ON`. If it is off,
   **Initialise database** stops with a message saying so and changes nothing.
4. Download the provider's CA certificate (often `ca.pem`) if it offers one.

### 2. GitHub

The repository must contain the project files at its top level (`app.py`,
`requirements.txt`, ...), not a `.zip` file. Do not upload `.venv`,
`.streamlit/secrets.toml`, `.env` or any certificate/key files.

### 3. Render web service

**Easiest:** in Render choose **New → Blueprint**, select this repository and
Render reads `render.yaml` (Python runtime, build and start commands, settings).
It asks for the four secret values (host, port, user, password). Add a CA
certificate afterwards if your provider gives one (see below).

**Or by hand:** create a **Web Service** from the repository with:

| Field | Value |
|-------|-------|
| Language | `Python 3` |
| Branch | `main` |
| Root Directory | *(empty)* |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `streamlit run app.py --server.port ${PORT:-8501} --server.address 0.0.0.0 --server.headless true` |

Under **Environment**, add the settings from the table above (see `.env.example`).
If you have a CA certificate, add it under **Secret Files** as `ca.pem` and set
`PARKING_DB_SSL_CA=/etc/secrets/ca.pem` with `PARKING_DB_SSL_MODE=verify_ca`.
Keep `PARKING_ALLOW_DB_RESET=false`.

After the first successful deploy, open the site, go to **Database setup** and
click **Initialise database** once. It only fills an empty database; if tables
already exist it leaves them untouched.

## Updating an existing database

A database created with an earlier version of `smart_parking.sql` (before
October 2026) is missing three integrity rules. Upgrade it without losing data:

1. Back up: `mysqldump -h <host> -u <user> -p --routines --triggers smart_parking > backup.sql`
2. Run `mysql -h <host> -u <user> -p smart_parking < migrations/001_integrity_constraints.sql`
3. The three pre-check queries at the top of the file must return no rows. If
   one does, fix those records and run it again. Running it on an already
   upgraded database stops at the first statement ("Duplicate column") and
   changes nothing.

On your own laptop you can instead rebuild the sample database with
**Initialise database** (local `PARKING_ALLOW_DB_RESET=true`).

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

The database tests in `tests/test_integration_mysql.py` are skipped unless you
point the `PARKING_DB_*` settings at a disposable, empty test database and set
`PARKING_RUN_DB_TESTS=1`.

## Business rules enforced by MySQL

- One active vehicle per slot (unique index on a generated column + trigger)
- Slot / vehicle-type match (triggers)
- Exit time after entry time (CHECK constraint)
- Reservation expiry (CHECK, entry trigger, `sp_expire_reservations`)
- Tariff-based charges (`sp_close_session`: rate × minutes / 60, using the latest
  tariff effective on the entry date)
- One active slot per vehicle (unique index on generated column `active_vehicle_id`)
- One active reservation per slot (unique index on generated column `active_res_slot_id`)
- No double billing (`uq_bill_session`; `sp_close_session` only closes an open session)
- Payments can never exceed the bill (`trg_payment_bi` locks the bill row first)

Gate entry/exit run as stored-procedure transactions that roll back on any
error. The automated tests include simultaneous entries, reservations, exits
and payments to show these rules hold under concurrent requests.
