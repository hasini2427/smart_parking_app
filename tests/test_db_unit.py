import re

import mysql.connector
import pytest
from mysql.connector import errorcode


def test_script_splits_into_expected_objects(load_config):
    _, db = load_config()
    stmts = db.split_script(db.SCRIPT_PATH.read_text(encoding="utf-8"))
    def count(pattern):
        return sum(1 for s in stmts if re.match(pattern, s, re.I))
    assert count(r"CREATE DATABASE") == 1
    assert count(r"CREATE TABLE") == 13
    assert count(r"CREATE TRIGGER") == 9
    assert count(r"CREATE FUNCTION") == 1
    assert count(r"CREATE PROCEDURE") == 3
    assert count(r"CREATE (OR REPLACE )?VIEW") == 3
    assert not any(s.upper().startswith("DELIMITER") for s in stmts)


def test_connect_without_settings_gives_clear_error(load_config):
    _, db = load_config()
    with pytest.raises(db.DBError) as info:
        db.connect()
    message = str(info.value)
    assert "not configured" in message and "PARKING_DB_USER" in message


def test_database_ready_reports_missing_settings(load_config):
    _, db = load_config()
    ok, message = db.database_ready()
    assert ok is False and "not configured" in message


def test_unreachable_server_gives_clear_error(load_config):
    _, db = load_config(PARKING_DB_HOST="127.0.0.1", PARKING_DB_PORT="1",
                        PARKING_DB_USER="u", PARKING_DB_PASSWORD="p",
                        PARKING_DB_CONNECT_TIMEOUT="3")
    with pytest.raises(db.DBError) as info:
        db.connect()
    assert "Cannot reach the MySQL server at 127.0.0.1:1" in str(info.value)


@pytest.mark.parametrize("errno, needle", [
    (errorcode.ER_ACCESS_DENIED_ERROR, "username or password"),
    (errorcode.ER_BAD_DB_ERROR, "does not exist yet"),
    (errorcode.ER_BINLOG_CREATE_ROUTINE_NEED_SUPER, "log_bin_trust_function_creators"),
])
def test_friendly_messages(load_config, errno, needle):
    _, db = load_config(PARKING_DB_USER="u", PARKING_DB_PASSWORD="p")
    err = mysql.connector.Error(msg="raw server text", errno=errno)
    assert needle in db.friendly(err)


def test_constraint_message_kept(load_config):
    _, db = load_config()
    err = mysql.connector.Error(msg="Check constraint 'chk_sess_time' is violated.", errno=3819)
    assert db.friendly(err) == "Exit time must be after the entry time."


def test_certificate_failure_message(load_config):
    _, db = load_config(PARKING_DB_USER="u", PARKING_DB_PASSWORD="p")
    err = mysql.connector.Error(msg="Lost connection, [SSL: CERTIFICATE_VERIFY_FAILED] x", errno=2055)
    assert "PARKING_DB_SSL_CA" in db.friendly(err)
