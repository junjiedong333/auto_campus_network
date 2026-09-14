"""交互式生成 config.json，密码经 Windows DPAPI 加密，仅本机本用户可解密."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def dpapi_encrypt(plain: str) -> str:
    ps = (
        "$s = ConvertTo-SecureString -String $env:CFG_PLAIN -AsPlainText -Force; "
        "ConvertFrom-SecureString -SecureString $s"
    )
    import os
    env = dict(os.environ)
    env["CFG_PLAIN"] = plain
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, timeout=15, env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    enc = out.stdout.strip()
    if not enc:
        raise RuntimeError(f"DPAPI 加密失败: {out.stderr[:500]}")
    return enc


def main() -> None:
    print("=== 校园网配置生成（中国移动单运营商）===")
    username = input("学号: ").strip()
    if not username:
        raise SystemExit("学号不能为空")
    password = input("密码（回显）: ").strip()
    if not password:
        raise SystemExit("密码不能为空")
    suffix = input("账号后缀 [ePortal 不需要，直接回车]: ").strip() or ""
    isp = input("运营商标识 [默认 cmcc，直接回车]: ").strip() or "cmcc"
    service = input("ePortal 服务 [默认 移动，直接回车]: ").strip() or "移动"
    enc = dpapi_encrypt(password)
    cfg = {
        "username": username,
        "username_suffix": suffix,
        "isp_value": isp,
        "service": service,
        "password_dpapi": enc,
        "password_plain": "",
        "form_override": None,
    }
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {CONFIG_PATH}（DPAPI 加密，仅本机本用户可解）")


if __name__ == "__main__":
    main()
