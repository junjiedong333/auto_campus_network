"""校园网自动认证主脚本（标准库 only）.

门控：只有 以太网Up + Portal可达 + 外网不通 才 POST 登录。
热点+Mihomo 科学上网时静默 exit 0。
用法：
  python src/campus_auth.py --dry-run   # 只打印决策，不登录
  pythonw.exe src/campus_auth.py        # 计划任务调用
"""
import argparse
import http.client
import json
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from src.gate import decide
except ModuleNotFoundError:
    # 直接 python src/campus_auth.py 运行时 sys.path[0]=src，需补仓库根
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.gate import decide

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "auth.log"

PORTAL_HOST = "10.10.30.21"
PORTAL_URL = f"http://{PORTAL_HOST}/"
ETH_NAME = "以太网"
STATE_PATH = LOG_DIR / "state.json"
MIN_LOGIN_INTERVAL = 20  # 只压住同一次抖动里的连打；任务另有 IgnoreNew 防重叠
READY_WAIT = 25  # 插线事件可能早于网卡就绪，最长等这么多秒


def _run_ps_hidden(cmd: list, **kw) -> "subprocess.CompletedProcess":
    """无窗口跑 powershell（计划任务下不闪窗）。"""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("timeout", 15)
    if sys.platform == "win32":
        kw.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.run(cmd, **kw)


def should_attempt(last_ts: float, now: float, interval: int = MIN_LOGIN_INTERVAL) -> bool:
    """节流纯函数：距上次真实尝试不足间隔则跳过."""
    return (now - last_ts) >= interval


def _read_last_attempt() -> float:
    try:
        return float(json.loads(STATE_PATH.read_text(encoding="utf-8")).get("last_attempt", 0))
    except Exception:
        return 0.0


def _write_last_attempt(now: float) -> None:
    try:
        LOG_DIR.mkdir(exist_ok=True)
        STATE_PATH.write_text(json.dumps({"last_attempt": now}), encoding="utf-8")
    except Exception:
        pass


def is_eth_enabled(name: str = ETH_NAME) -> bool:
    """设置中是否启用：网卡存在且 Status 不是 Disabled（Up/Disconnected 都算启用）."""
    try:
        ps = f'(Get-NetAdapter -Name "{name}" -ErrorAction Stop).Status'
        out = _run_ps_hidden(["powershell", "-NoProfile", "-Command", ps])
        st = out.stdout.strip().lower()
        return st != "" and st != "disabled" and "不存在" not in st
    except Exception:
        return False


def wait_for_eth_ready(name: str, timeout: int = READY_WAIT) -> bool:
    """插线事件常早于网卡就绪：轮询等 Up，超时才放弃."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_eth_up(name):
            return True
        time.sleep(2)
    return is_eth_up(name)


def log(msg: str) -> None:
    try:
        LOG_DIR.mkdir(exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass
    print(msg, flush=True)


def is_eth_up(name: str = ETH_NAME) -> bool:
    """仅判断指定有线网卡是否为 Up（禁用/断开/不存在一律 False），不碰 WLAN/Mihomo."""
    try:
        ps = f'(Get-NetAdapter -Name "{name}" -ErrorAction Stop).Status'
        out = _run_ps_hidden(["powershell", "-NoProfile", "-Command", ps])
        return out.stdout.strip().lower() == "up"
    except Exception:
        return False


def is_portal_reachable(host: str = PORTAL_HOST, port: int = 80, timeout: int = 5) -> bool:
    """HTTP 级可达判定：TCP 通但 HTTP 空回包（如热点+Mihomo 劫持）视为不可达."""
    import http.client

    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/")
        resp = conn.getresponse()
        # 任何 HTTP 状态（200/302/...）都算 Portal 活着；读一小段避免挂起
        try:
            resp.read(1024)
        except Exception:
            pass
        conn.close()
        return True
    except Exception:
        return False


def is_tun_active(name: str = "Mihomo") -> bool:
    """检测 TUN/代理虚拟网卡是否 Up。Up 时 ePortal 域名会被劫持到假 IP，8443 必失败."""
    try:
        ps = f'(Get-NetAdapter -Name "{name}" -ErrorAction Stop).Status'
        out = _run_ps_hidden(["powershell", "-NoProfile", "-Command", ps])
        return out.stdout.strip().lower() == "up"
    except Exception:
        return False


def is_internet_ok(timeout: int = 5) -> bool:
    """204 探测：任一成功即认为在线（已认证或在热点）。"""
    for url in (
        "http://www.gstatic.com/generate_204",
        "http://connect.rom.miui.com/generate_204",
    ):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                if r.status in (200, 204):
                    return True
        except Exception:
            continue
    return False


def decrypt_dpapi(enc: str) -> str:
    """DPAPI 解密 setup_config.py 生成的密文，仅本机本用户可解."""
    ps = (
        "$s = ConvertTo-SecureString -String $env:CFG_ENC; "
        "$b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); "
        "[Runtime.InteropServices.Marshal]::PtrToStringAuto($b)"
    )
    import os
    env = dict(os.environ)
    env["CFG_ENC"] = enc
    out = _run_ps_hidden(
        ["powershell", "-NoProfile", "-Command", ps], env=env,
    )
    return out.stdout.strip()


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"缺少 {path}，请先运行 python setup_config.py")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg.get("password_dpapi"):
        cfg["password"] = decrypt_dpapi(cfg["password_dpapi"])
    elif cfg.get("password_plain"):
        cfg["password"] = cfg["password_plain"]
    else:
        raise ValueError("config.json 缺少 password_dpapi/password_plain")
    if not cfg.get("username"):
        raise ValueError("config.json 缺少 username（学号）")
    return cfg


def pick_credentials(cfg: dict) -> str:
    u = cfg.get("username", "")
    suffix = cfg.get("username_suffix", "@cmcc")
    if suffix and not u.endswith(suffix):
        u = u + suffix
    return u


def build_post_data(cfg: dict, username_full: str, password: str):
    ov = cfg.get("form_override") or {}
    fields = dict(
        ov.get("fields", {"username": "{u}", "password": "{p}", "isp": cfg.get("isp_value", "cmcc")})
    )
    data = {}
    for k, v in fields.items():
        data[k] = v.replace("{u}", username_full).replace("{p}", password)
    return username_full, password, data


def classify_portal_html(html: str) -> str:
    """区分网关侧认证态：只看 10.10.30.21 回包内容，不依赖外网 204.

    - "unauthed-redirect": 328 字节跳转脚本（含 eportal/index.jsp），网关未放行
    - "authed-success": 成功页（含 success.jsp/getOnlineUserInfo），网关已放行
    - "unknown": 其他
    """
    if not html:
        return "unknown"
    if "eportal/index.jsp" in html and "top.self.location" in html:
        return "unauthed-redirect"
    if "getOnlineUserInfo" in html or "success.jsp" in html:
        return "authed-success"
    return "unknown"


EPORTAL_IP = "10.10.30.21"
EPORTAL_PORT = 8443
EPORTAL_HOST = "login.lsu.edu.cn:8443"  # SNI/Host 用域名，直连 IP，绕开 TUN 假 DNS


def _eportal_tls_ctx():
    """老 ePortal 只要旧 cipher，必须降 SECLEVEL，否则握手失败."""
    import ssl
    ctx = ssl._create_unverified_context()
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1
    except Exception:
        pass
    try:
        ctx.set_ciphers("ALL:@SECLEVEL=0")
    except Exception:
        pass
    return ctx


class _EportalConnection(http.client.HTTPSConnection):
    """TCP 直连 10.10.30.21:8443，TLS SNI 用域名."""

    def connect(self):
        import socket
        sock = socket.create_connection((EPORTAL_IP, EPORTAL_PORT), timeout=self.timeout)
        self.sock = _eportal_tls_ctx().wrap_socket(sock, server_hostname="login.lsu.edu.cn")


def _double_quote(s: str) -> str:
    """复刻 JS encodeURIComponent(encodeURIComponent(x))，登录页对各字段双重编码."""
    return urllib.parse.quote(urllib.parse.quote(s, safe=""), safe="")


_EPORTAL_COOKIES: dict = {}


def _store_cookies(resp) -> None:
    for _h, v in resp.getheaders():
        if _h.lower() == "set-cookie":
            pair = v.split(";", 1)[0]
            if "=" in pair:
                k, _, val = pair.partition("=")
                _EPORTAL_COOKIES[k.strip()] = val.strip()


def _cookie_header() -> str:
    return "; ".join(f"{k}={v}" for k, v in _EPORTAL_COOKIES.items())


def eportal_post(method: str, params: dict, timeout: int = 15, raw_body: str = None) -> dict:
    """POST /eportal/InterFace.do?method=X，返回 JSON dict.

    raw_body 非空时直接发送（登录接口各字段需浏览器式双重编码，urlencode 只编一次）。
    """
    body = raw_body.encode("utf-8") if raw_body is not None else urllib.parse.urlencode(params).encode("utf-8")
    conn = _EportalConnection(EPORTAL_IP, EPORTAL_PORT, timeout=timeout)
    headers = {
        "Host": EPORTAL_HOST,
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    if _EPORTAL_COOKIES:
        headers["Cookie"] = _cookie_header()
    conn.request(
        "POST", f"/eportal/InterFace.do?method={method}", body=body,
        headers=headers,
    )
    resp = conn.getresponse()
    raw = resp.read()
    _store_cookies(resp)
    conn.close()
    if resp.status != 200:
        raise RuntimeError(f"eportal {method} http={resp.status}")
    return json.loads(raw.decode("utf-8", errors="ignore"))


def rsa_encrypt_hex(pwd: str, e_hex: str, n_hex: str) -> str:
    """复刻 security.js RSAUtils.encryptedString（Barrett 教科书式 RSA）.

    注意：这不是 PKCS#1！逐字节对标 JS：
    - a[i] = charCodeAt（ASCII 与 UTF-8 一致）
    - 零填充到 chunkSize(=2*biHighIndex(m)，1024-bit 密钥为 126 字节)倍数
    - 每块内 digits[j] = a[2j] + (a[2j+1] << 8)，即小端整数，整块 powMod
    - 输出 hex（定长补齐，服务端按 BigInteger 解析，前导零无害）
    无随机填充：相同输入输出恒定，可与浏览器密文离线比对。
    """
    data = pwd[::-1].encode("utf-8")
    n = int(n_hex, 16)
    e = int(e_hex, 16)
    ndigits = (n.bit_length() + 15) // 16
    chunk = 2 * (ndigits - 1)
    if len(data) >= chunk:
        raise ValueError("password too long for RSA key")
    padded = data + b"\x00" * (chunk - len(data))
    m = int.from_bytes(padded, "little")
    c = pow(m, e, n)
    return format(c, "x").zfill(len(n_hex))


def fetch_portal_html(timeout: int = 10) -> str:
    with urllib.request.urlopen(PORTAL_URL, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gbk", "gb2312", "latin1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def get_portal_query(timeout: int = 10) -> str:
    """从 http://10.10.30.21/ 跳转脚本里抠出 ePortal queryString（未编码原串）."""
    html = fetch_portal_html(timeout)
    m = re.search(r"/eportal/index\.jsp\?([^'\"]+)", html)
    if not m:
        raise RuntimeError("portal 未返回 ePortal 跳转（可能已认证或结构变化）")
    return m.group(1)


def login_needed(eth_up: bool, portal_state: str) -> tuple:
    """网关侧门控纯函数：只看网关是否放行，不看 204（204 会被 TUN/热点掩蔽）."""
    if not eth_up:
        return False, "eth-down-silent-exit"
    if portal_state == "authed-success":
        return False, "already-online-silent-exit"
    if portal_state == "unauthed-redirect":
        return True, "need-login"
    return False, "portal-unknown-silent-exit"


def do_eportal_login(cfg: dict, query: str) -> tuple:
    """ePortal 登录：pageInfo 取公钥 → 密码拼 `>mac` 后 RSA 加密 → 双重编码 POST login."""
    _EPORTAL_COOKIES.clear()  # 新会话：与浏览器新开登录页一致，pageInfo 下发 JSESSIONID
    user_id = cfg.get("username", "")
    password = cfg.get("password", "")
    service = cfg.get("service", "移动")
    try:
        info = eportal_post("pageInfo", {"queryString": query})
    except Exception as e:
        return False, f"pageinfo-failed: {e}"
    encrypt = str(info.get("passwordEncrypt", "")).lower() == "true"
    mac = urllib.parse.parse_qs(query).get("mac", ["111111111"])[0]
    if encrypt:
        try:
            password = rsa_encrypt_hex(
                password + ">" + mac, info["publicKeyExponent"], info["publicKeyModulus"]
            )
        except Exception as e:
            return False, f"rsa-encrypt-failed: {e}"
    enc_flag = "true" if encrypt else "false"
    log(f"eportal mac={mac} service={service} user={user_id}")
    # 与 login_bch.js 完全一致：userId/password/service/queryString/encrypt 双重编码
    raw = (
        f"userId={_double_quote(user_id.strip())}"
        f"&password={_double_quote(password)}"
        f"&service={_double_quote(service)}"
        f"&queryString={_double_quote(query)}"
        f"&operatorPwd=&operatorUserId=&validcode="
        f"&passwordEncrypt={_double_quote(enc_flag)}"
    )
    try:
        res = eportal_post("login", {}, raw_body=raw)
    except Exception as e:
        return False, f"login-post-failed: {e}"
    log(f"login resp: {str(res)[:300]!r}")
    if str(res.get("result", "")).lower() == "success":
        return True, f"login-ok userIndex={res.get('userIndex')}"
    return False, f"login-rejected: {res.get('message', res)}"


def do_login(cfg: dict, retries: int = 3) -> tuple:
    username_full = pick_credentials(cfg)
    password = cfg["password"]
    ov = cfg.get("form_override") or {}
    action = ov.get("action", "/")
    post_url = urllib.parse.urljoin(PORTAL_URL, action)

    try:
        html = fetch_portal_html()
    except Exception as e:
        return False, f"get-portal-failed: {e}"
    log(f"portal html head: {html[:200]!r}")

    _, _, data = build_post_data(cfg, username_full, password)
    body = urllib.parse.urlencode(data).encode("utf-8")
    last_err = ""
    for i in range(1, retries + 1):
        try:
            req = urllib.request.Request(post_url, data=body, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = r.read()[:4096]
            log(f"login POST #{i} http={r.status} resp_head={resp[:200]!r}")
            time.sleep(2)
            if is_internet_ok():
                return True, f"login-ok-after-{i}-tries"
            last_err = f"POST#{i} ok but internet still down"
        except Exception as e:
            last_err = f"POST#{i} failed: {e}"
            log(last_err)
            time.sleep(3)
    return False, last_err


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印决策，不登录")
    ap.add_argument("--eth-name", default=ETH_NAME)
    args = ap.parse_args(argv)

    # 门槛1：以太网必须 Up。禁用/不存在秒退；已启用但未 Up（刚插线）则等一轮
    if not is_eth_up(args.eth_name):
        if not is_eth_enabled(args.eth_name):
            log(f"eth_up=False need=eth-down-silent-exit")
            return 0
        if not wait_for_eth_ready(args.eth_name):
            log(f"eth_up=False need=eth-down-silent-exit")
            return 0
    eth_up = True
    portal = is_portal_reachable()
    internet = is_internet_ok()
    tun = is_tun_active()
    ok, reason = decide(eth_up, portal, internet)
    # 网关侧信号（不受 TUN/热点 204 掩蔽影响），作为主决策依据
    portal_state = "unknown"
    query = ""
    if portal:
        try:
            html = fetch_portal_html()
            portal_state = classify_portal_html(html)
            if portal_state == "unauthed-redirect":
                query = get_portal_query()
        except Exception as e:
            log(f"portal-read-failed: {e}")
    need, need_reason = login_needed(eth_up, portal_state)
    log(f"eth_up={eth_up} portal_reachable={portal} internet_ok={internet} tun_active={tun} portal_state={portal_state} decision={reason} need={need_reason}")

    if args.dry_run:
        return 0
    if not need:
        return 0  # 防干扰：静默退出
    # 门槛2：节流——距上次真实尝试不足间隔则跳过，防事件风暴互顶会话
    now = time.time()
    if not should_attempt(_read_last_attempt(), now):
        log(f"throttled-skip interval={MIN_LOGIN_INTERVAL}s")
        return 0
    _write_last_attempt(now)
    try:
        cfg = load_config()
    except Exception as e:
        log(f"config-error: {e}")
        return 2
    success, msg = do_eportal_login(cfg, query)
    log(f"login result: {success} {msg}")
    if success:
        # 登录后复验：网关必须翻成成功页，否则视为未真正放行
        time.sleep(3)
        try:
            state_after = classify_portal_html(fetch_portal_html())
        except Exception as e:
            state_after = f"fetch-failed {e}"
        log(f"post-login portal_state={state_after}")
        return 0 if state_after == "authed-success" else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
