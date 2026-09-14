"""离线裁决脚本：在校园网未认证态下一次跑完回放+正式登录，结果写入日志.

用法（断网窗口内）：
  1. 以太网保持启用，确认未认证（浏览器开 http://10.10.30.21/ 会跳登录页）
  2. 如需回放对比，把浏览器抓到的 login POST 之 password 值写入 replay_cipher.txt（可空）
  3. python tools/replay_offline.py
  4. 恢复上网后看 logs/auth.log
只读 + 最多两次登录 POST，不改任何配置。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.campus_auth import (  # noqa: E402
    _EPORTAL_COOKIES,
    _double_quote,
    classify_portal_html,
    do_eportal_login,
    eportal_post,
    fetch_portal_html,
    get_portal_query,
    is_eth_up,
    load_config,
    log,
)

REPLAY_CIPHER_FILE = Path(__file__).resolve().parent / "replay_cipher.txt"


def main() -> int:
    log("=== replay_offline start ===")
    if not is_eth_up():
        log("ABORT: eth-down")
        return 2
    try:
        html = fetch_portal_html()
    except Exception as e:
        log(f"ABORT: portal-unreachable {e}")
        return 2
    state = classify_portal_html(html)
    log(f"portal_state={state}")
    if state != "unauthed-redirect":
        log("ABORT: not unauthed (already online?)")
        return 0
    try:
        query = get_portal_query()
    except Exception as e:
        log(f"ABORT: no query {e}")
        return 2

    # 回放（可选）：浏览器原装密文 + 新会话 + 新 query，只验证传输/编码/会话层
    cipher = ""
    if REPLAY_CIPHER_FILE.exists():
        cipher = REPLAY_CIPHER_FILE.read_text(encoding="utf-8").strip()
    try:
        cfg_probe = load_config()
        username = cfg_probe.get("username", "")
        service = cfg_probe.get("service", "移动")
    except Exception as e:
        log(f"config-error: {e}")
        return 2
    if cipher:
        _EPORTAL_COOKIES.clear()
        try:
            eportal_post("pageInfo", {"queryString": query})
            raw = (
                "userId=" + _double_quote(username)
                + "&password=" + _double_quote(cipher)
                + "&service=" + _double_quote(service)
                + "&queryString=" + _double_quote(query)
                + "&operatorPwd=&operatorUserId=&validcode="
                + "&passwordEncrypt=" + _double_quote("true")
            )
            res = eportal_post("login", {}, raw_body=raw)
            log(f"replay resp: {str(res)[:300]!r}")
        except Exception as e:
            log(f"replay error: {e}")
        time.sleep(2)
    else:
        log("replay skipped (no tools/replay_cipher.txt)")

    # 正式：配置密码完整链路
    ok, msg = do_eportal_login(cfg_probe, query)
    log(f"official result: {ok} {msg}")
    log("=== replay_offline end ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
