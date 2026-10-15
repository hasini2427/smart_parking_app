import pytest


def test_defaults_without_credentials_report_missing(load_config):
    config, _ = load_config()
    assert config.DB_HOST == "localhost"
    assert config.DB_PORT == 3306
    assert config.DB_NAME == "smart_parking"
    assert config.DB_SSL_MODE == "preferred"
    assert config.ALLOW_DB_RESET is False
    problems = " ".join(config.problems())
    assert "PARKING_DB_USER" in problems and "PARKING_DB_PASSWORD" in problems


def test_no_credentials_have_defaults_in_source():
    import re
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "config.py").read_text()
    assert re.search(r'DB_USER = setting\("PARKING_DB_USER"\)\n', source)
    assert re.search(r'DB_PASSWORD = setting\("PARKING_DB_PASSWORD"\)\n', source)


def test_environment_overrides(load_config):
    config, _ = load_config(PARKING_DB_HOST="db.example.com", PARKING_DB_PORT="25060",
                            PARKING_DB_USER="parking_app", PARKING_DB_PASSWORD="x",
                            PARKING_DB_NAME="parking_prod", PARKING_ALLOW_DB_RESET="true")
    assert (config.DB_HOST, config.DB_PORT, config.DB_USER) == ("db.example.com", 25060, "parking_app")
    assert config.DB_NAME == "parking_prod"
    assert config.ALLOW_DB_RESET is True
    assert config.problems() == []


def test_invalid_database_name_rejected(load_config):
    config, _ = load_config(PARKING_DB_USER="u", PARKING_DB_PASSWORD="p",
                            PARKING_DB_NAME="bad-name; DROP")
    assert any("PARKING_DB_NAME" in p for p in config.problems())


def test_ssl_disabled(load_config):
    config, _ = load_config(PARKING_DB_USER="u", PARKING_DB_PASSWORD="p",
                            PARKING_DB_SSL_MODE="disabled")
    assert config.ssl_params() == {"ssl_disabled": True}
    assert config.ssl_required() is False


def test_ssl_ca_path_defaults_to_verify_ca(load_config, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n")
    config, _ = load_config(PARKING_DB_USER="u", PARKING_DB_PASSWORD="p",
                            PARKING_DB_SSL_CA=str(ca))
    assert config.DB_SSL_MODE == "verify_ca"
    assert config.ssl_params() == {"ssl_ca": str(ca), "ssl_verify_cert": True,
                                   "ssl_verify_identity": False}
    assert config.ssl_required() is True
    assert config.problems() == []


def test_ssl_ca_pem_text_written_to_file(load_config):
    pem = "-----BEGIN CERTIFICATE-----\\nABC\\n-----END CERTIFICATE-----"
    config, _ = load_config(PARKING_DB_USER="u", PARKING_DB_PASSWORD="p",
                            PARKING_DB_SSL_CA_PEM=pem, PARKING_DB_SSL_MODE="verify_identity")
    params = config.ssl_params()
    assert params["ssl_verify_identity"] is True
    with open(params["ssl_ca"]) as fh:
        assert fh.read() == "-----BEGIN CERTIFICATE-----\nABC\n-----END CERTIFICATE-----"


@pytest.mark.parametrize("env, needle", [
    ({"PARKING_DB_SSL_MODE": "verify_ca"}, "needs PARKING_DB_SSL_CA"),
    ({"PARKING_DB_SSL_MODE": "sometimes"}, "must be one of"),
    ({"PARKING_DB_SSL_CA": "/no/such/ca.pem"}, "was not found"),
])
def test_ssl_misconfiguration_reported(load_config, env, needle):
    config, _ = load_config(PARKING_DB_USER="u", PARKING_DB_PASSWORD="p", **env)
    assert any(needle in p for p in config.problems())
