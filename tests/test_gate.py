from src.gate import should_login


def test_only_eth_up_and_portal_and_no_internet_logs_in():
    assert should_login(True, True, False) is True


def test_eth_down_never_logs_in():
    assert should_login(False, True, False) is False
    assert should_login(False, False, False) is False


def test_hotspot_vpn_silent_exit():
    # 当前实测态：以太网 Disabled + Portal 不可达 + 外网通 = 热点科学上网
    assert should_login(False, False, True) is False


def test_already_authed_exit():
    assert should_login(True, True, True) is False


def test_portal_unreachable_exit():
    assert should_login(True, False, False) is False
