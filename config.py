"""Database connection settings.

Nothing secret is stored in this file. Every value is read, in this order, from:
  1. an environment variable (used on Render), or
  2. .streamlit/secrets.toml (used on your own laptop; never commit it), or
  3. the safe default shown below.

See .env.example and .streamlit/secrets.toml.example for the setting names.
"""
import os
import re
import tempfile


def _from_secrets(name):
    """Read a value from Streamlit secrets, if a secrets file exists."""
    try:
        import streamlit as st
        value = st.secrets.get(name)
    except Exception:  # no secrets file, or not running under Streamlit
        return None
    return None if value is None else str(value)


def setting(name, default=""):
    value = os.getenv(name)
    if value is None or value == "":
        value = _from_secrets(name)
    if value is None or value == "":
        return default
    return value


def _flag(name, default=False):
    return setting(name, "true" if default else "false").strip().lower() in ("1", "true", "yes", "on")


DB_HOST = setting("PARKING_DB_HOST", "localhost")
DB_PORT = int(setting("PARKING_DB_PORT", "3306"))
DB_USER = setting("PARKING_DB_USER")
DB_PASSWORD = setting("PARKING_DB_PASSWORD")
DB_NAME = setting("PARKING_DB_NAME", "smart_parking")
DB_CONNECT_TIMEOUT = int(setting("PARKING_DB_CONNECT_TIMEOUT", "10"))

# Optional session time zone, e.g. "+05:30". Hosted MySQL servers usually
# run on UTC, so set this to show Indian times.
DB_TIME_ZONE = setting("PARKING_DB_TIME_ZONE")

# SSL / TLS for hosted MySQL.
#   PARKING_DB_SSL_MODE:   disabled | preferred (default) | required | verify_ca | verify_identity
#   PARKING_DB_SSL_CA:     path to the provider's CA certificate file (e.g. a Render Secret File)
#   PARKING_DB_SSL_CA_PEM: the CA certificate text itself (alternative to the file path)
DB_SSL_CA = setting("PARKING_DB_SSL_CA")
DB_SSL_CA_PEM = setting("PARKING_DB_SSL_CA_PEM")
DB_SSL_MODE = setting("PARKING_DB_SSL_MODE",
                      "verify_ca" if (DB_SSL_CA or DB_SSL_CA_PEM) else "preferred").strip().lower()

# "Initialise database" may only DROP an existing database when this is true.
# Keep it false on Render so real data can never be wiped by accident.
ALLOW_DB_RESET = _flag("PARKING_ALLOW_DB_RESET", False)

SSL_MODES = ("disabled", "preferred", "required", "verify_ca", "verify_identity")


def problems():
    """Return a list of configuration problems (empty when the settings are usable)."""
    issues = []
    missing = [name for name, value in (("PARKING_DB_USER", DB_USER),
                                        ("PARKING_DB_PASSWORD", DB_PASSWORD)) if not value]
    if missing:
        issues.append("Missing setting(s): " + ", ".join(missing) + ".")
    if not re.fullmatch(r"[A-Za-z0-9_]+", DB_NAME or ""):
        issues.append("PARKING_DB_NAME may only contain letters, digits and underscores.")
    if DB_SSL_MODE not in SSL_MODES:
        issues.append("PARKING_DB_SSL_MODE must be one of: " + ", ".join(SSL_MODES) + ".")
    if DB_SSL_MODE in ("verify_ca", "verify_identity") and not (DB_SSL_CA or DB_SSL_CA_PEM):
        issues.append(f"PARKING_DB_SSL_MODE={DB_SSL_MODE} needs PARKING_DB_SSL_CA or PARKING_DB_SSL_CA_PEM.")
    if DB_SSL_CA and not os.path.isfile(DB_SSL_CA):
        issues.append("The CA certificate file named in PARKING_DB_SSL_CA was not found.")
    return issues


_ca_temp_path = None


def _ca_file():
    """Path of the CA certificate, writing PARKING_DB_SSL_CA_PEM to a temp file if needed."""
    global _ca_temp_path
    if DB_SSL_CA:
        return DB_SSL_CA
    if _ca_temp_path is None:
        pem = DB_SSL_CA_PEM.replace("\\n", "\n")
        handle = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
        with handle:
            handle.write(pem)
        _ca_temp_path = handle.name
    return _ca_temp_path


def ssl_params():
    """mysql-connector-python keyword arguments for the chosen SSL mode."""
    if DB_SSL_MODE == "disabled":
        return {"ssl_disabled": True}
    if DB_SSL_MODE in ("verify_ca", "verify_identity"):
        return {"ssl_ca": _ca_file(), "ssl_verify_cert": True,
                "ssl_verify_identity": DB_SSL_MODE == "verify_identity"}
    return {}  # preferred / required: TLS is negotiated when the server offers it


def ssl_required():
    return DB_SSL_MODE in ("required", "verify_ca", "verify_identity")
