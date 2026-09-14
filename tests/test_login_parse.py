from src.campus_auth import build_post_data, pick_credentials


def test_mobile_suffix_default():
    cfg = {
        "username": "20230001",
        "username_suffix": "@cmcc",
        "isp_value": "cmcc",
    }
    assert pick_credentials(cfg) == "20230001@cmcc"


def test_no_double_suffix():
    cfg = {"username": "20230001@cmcc", "username_suffix": "@cmcc"}
    assert pick_credentials(cfg) == "20230001@cmcc"


def test_build_post_data_override():
    cfg = {
        "username": "20230001",
        "password_plain": "x",
        "username_suffix": "@cmcc",
        "isp_value": "cmcc",
        "form_override": {
            "action": "/login",
            "fields": {"user": "{u}", "pass": "{p}"},
        },
    }
    u, p, data = build_post_data(cfg, "20230001@cmcc", "secret")
    assert data == {"user": "20230001@cmcc", "pass": "secret"}
