import json


def test_example_config_valid():
    cfg = json.load(open("config.example.json", encoding="utf-8"))
    assert "username_suffix" in cfg and "isp_value" in cfg
    # ePortal userId 用统一身份认证学号原文，domainName=false，不加后缀
    assert cfg["username_suffix"] == ""
    assert cfg.get("service") == "移动"
