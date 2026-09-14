"""单发验证：正式登录一次，紧接着用三路证据验放行（不再轻信 success).

用法（未认证窗口）：python tools/verify_login.py
恢复上网后把 logs/auth.log 尾部发给开发者。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.campus_auth import (  # noqa: E402
    classify_portal_html,
    do_eportal_login,
    eportal_post,
    fetch_portal_html,
    get_portal_query,
    is_eth_up,
    is_internet_ok,
    load_config,
    log,
)


def main() -> int:
    log("=== verify_login start ===")
    if not is_eth_up():
        log("ABORT: eth-down")
        return 2
    try:
        state0 = classify_portal_html(fetch_portal_html())
    except Exception as e:
        log(f"ABORT: portal-unreachable {e}")
        return 2
    log(f"before={state0}")
    if state0 != "unauthed-redirect":
        log("ABORT: not unauthed")
        return 0
    query = get_portal_query()
    cfg = load_config()
    ok, msg = do_eportal_login(cfg, query)
    log(f"login: {ok} {msg}")
    user_index = None
    if "userIndex=" in msg:
        user_index = msg.split("userIndex=")[-1].strip()
    time.sleep(3)
    # 证据1：服务端会话是否真实存在
    if user_index:
        try:
            info = eportal_post("getOnlineUserInfo", {"userIndex": user_index})
            log(f"online-info: result={info.get('result')} user={info.get('userName', info.get('userId'))}")
        except Exception as e:
            log(f"online-info error: {e}")
    # 证据2：网关回包是否翻成成功页
    try:
        state1 = classify_portal_html(fetch_portal_html())
    except Exception as e:
        state1 = f"fetch-failed {e}"
    log(f"after portal_state={state1}")
    # 证据3：204
    log(f"after internet_ok={is_internet_ok()}")
    log("=== verify_login end ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
