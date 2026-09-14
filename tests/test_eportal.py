from src.campus_auth import (
    _cookie_header,
    _double_quote,
    _EPORTAL_COOKIES,
    _store_cookies,
    login_needed,
    rsa_encrypt_hex,
    should_attempt,
)


def test_throttle_blocks_frequent_attempts():
    assert should_attempt(0.0, 1000.0) is True
    assert should_attempt(900.0, 1000.0, interval=180) is False
    assert should_attempt(820.0, 1000.0, interval=180) is True


def test_unauthed_needs_login_even_if_204_online():
    # TUN/热点掩蔽场景：204 通但网关未放行，仍要登录
    need, reason = login_needed(True, "unauthed-redirect")
    assert need is True and reason == "need-login"


def test_authed_never_logs_in():
    need, _ = login_needed(True, "authed-success")
    assert need is False


def test_eth_down_never_logs_in():
    need, _ = login_needed(False, "unauthed-redirect")
    assert need is False


def test_unknown_state_silent_exit():
    need, reason = login_needed(True, "unknown")
    assert need is False and "unknown" in reason


def test_double_quote_matches_browser():
    # encodeURIComponent(encodeURIComponent('移动'))，浏览器发出的 service 编码
    assert _double_quote("移动") == "%25E7%25A7%25BB%25E5%258A%25A8"
    assert _double_quote("20230001") == "20230001"  # 纯数字不受影响


def test_cookie_jar_roundtrip():
    class FakeResp:
        def getheaders(self):
            return [("Set-Cookie", "JSESSIONID=ABC123; Path=/eportal; Secure; HttpOnly")]
    _EPORTAL_COOKIES.clear()
    _store_cookies(FakeResp())
    assert _cookie_header() == "JSESSIONID=ABC123"
    _EPORTAL_COOKIES.clear()


def test_rsa_output_format():
    # 用实测 pageInfo 公钥：1024-bit，输出应为 256 hex 字符；Barrett 方案无随机填充，确定性输出
    e = "10001"
    n = "94dd2a8675fb779e6b9f7103698634cd400f27a154afa67af6166a43fc26417222a79506d34cacc7641946abda1785b7acf9910ad6a0978c91ec84d40b71d2891379af19ffb333e7517e390bd26ac312fe940c340466b4a5d4af1d65c3b5944078f96a1a51a5a53e4bc302818b7c9f63c4a1b07bd7d874cef1c3d4b2f5eb7871"
    c1 = rsa_encrypt_hex("test123", e, n)
    c2 = rsa_encrypt_hex("test123", e, n)
    assert len(c1) == 256 and all(ch in "0123456789abcdef" for ch in c1)
    assert c1 == c2  # 无随机填充：相同输入必相同输出
    m1 = pow(int(c1, 16), int(e, 16), int(n, 16))
    assert m1 < int(n, 16)
