"""防干扰门控纯函数：只有 以太网Up + Portal可达 + 外网不通 才登录."""

def should_login(eth_up: bool, portal_reachable: bool, internet_ok: bool) -> bool:
    if not eth_up:
        return False
    if not portal_reachable:
        return False
    if internet_ok:
        return False
    return True


def decide(eth_up: bool, portal_reachable: bool, internet_ok: bool) -> tuple:
    ok = should_login(eth_up, portal_reachable, internet_ok)
    if not eth_up:
        return ok, "eth-down-silent-exit"
    if not portal_reachable:
        return ok, "portal-unreachable-silent-exit"
    if internet_ok:
        return ok, "already-online-silent-exit"
    return ok, "need-login"
