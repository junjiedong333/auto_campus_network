"""校园网未认证态下运行：抓取 Portal 表单，指导补 config.json 的 form_override."""
import re
import sys
import urllib.request
from pathlib import Path

PORTAL_URL = "http://10.10.30.21/"


def main() -> int:
    print(f"GET {PORTAL_URL} ...")
    try:
        with urllib.request.urlopen(PORTAL_URL, timeout=10) as r:
            raw = r.read()
            print(f"HTTP {r.status} {len(raw)} bytes")
    except Exception as e:
        print(f"抓取失败（确认已启用以太网、断开热点/VPN、处于未认证态）: {e}")
        return 1
    for enc in ("utf-8", "gbk", "gb2312", "latin1"):
        try:
            html = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        html = raw.decode("utf-8", errors="ignore")
    out = Path("portal.html")
    out.write_bytes(raw)
    print(f"已保存 {out.resolve()}（发给开发者补字段）")
    for m in re.finditer(r"<form[^>]*>", html, re.I):
        print("FORM:", m.group(0)[:300])
    names = re.findall(r'name=["\']([^"\']+)["\']', html, re.I)
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    print("INPUT NAMES:", seen[:40])
    m = re.search(r"action=[\"']([^\"']+)[\"']", html, re.I)
    print("ACTION:", m.group(1) if m else "(未找到)")
    print("HTML HEAD:", html[:500].replace("\n", " ")[:500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
