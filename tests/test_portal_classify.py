from src.campus_auth import classify_portal_html


def test_redirect_script_is_unauthed():
    html = "<script>top.self.location.href='https://login.lsu.edu.cn:8443/eportal/index.jsp?wlanuserip=abc'</script>"
    assert classify_portal_html(html) == "unauthed-redirect"


def test_success_page_is_authed():
    html = "<html>success.jsp getOnlineUserInfo</html>"
    assert classify_portal_html(html) == "authed-success"


def test_garbage_is_unknown():
    assert classify_portal_html("") == "unknown"
    assert classify_portal_html("<html>hello</html>") == "unknown"
