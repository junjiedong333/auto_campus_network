# 校园网自动认证 Design

> 状态：已与用户确认，2026-09-14

**Goal:** 插网线/启用`以太网`后自动完成 `http://10.10.30.21` Web Portal 认证（学号+密码+中国移动）；`以太网`禁用/拔线、Wi-Fi 热点 + Mihomo 科学上网时绝不干扰。

## 实测现状（2026-09-14，本机）

- `以太网` (Realtek Gaming GbE) = Disabled
- `WLAN` = Up，连手机热点，IPv4 Internet
- `Mihomo` (Meta Tunnel) = Up，IPv4 Internet（科学上网中）
- `Test-Connection 10.10.30.21` 失败，`curl http://10.10.30.21/` 返回 `000` —— 热点+VPN 下 Portal 不可达，符合预期。
- 结论：需切回以太网未认证态才能抓包。代码必须先做门控，不可达则静默退出。

## Architecture

计划任务事件触发（无常驻进程）+ Python 脚本（仅标准库 `urllib`）直调 Portal。触发后脚本内二次门控：以太网 Up？Portal 可达？外网已通？三者决定是否 POST 登录。

## Components

1. `src/campus_auth.py` —— 唯一主逻辑：门控检查 → GET Portal 嗅探表单 → POST 登录 → 校验外网。`--dry-run` 只打印决策不登录。
2. `setup_config.py` —— 交互式生成 `config.json`，密码经 Windows DPAPI 加密，仅本机本用户可解密。
3. `tools/capture_portal.py` —— 校园网未认证态下运行，保存 `portal.html` + 解析出的 form/action/fields，供补齐移动运营商字段。
4. `scripts/Register-CampusTask.ps1` —— 注册计划任务：`NetworkProfile Operational 10000` + 登录/解锁兜底，动作为 `pythonw.exe src/campus_auth.py`。
5. `config.example.json` —— 配置模板。

## Data flow（防干扰门控）

```
事件触发 → 以太网 Status==Up? 否→exit 0
→ TCP 10.10.30.21:80 通? 否→exit 0（热点/VPN 中）
→ 外网已通(204探测)? 是→exit 0（已认证或在热点）
→ GET Portal → POST(学号+密码+移动标识) → 复查外网 → 写日志退出
```

## Error handling

- Portal 不可达/外网已通：静默 exit 0，不写错、不弹窗。
- 登录 POST 失败：重试 3 次间隔 3s，仍失败则保存响应片段到日志，exit 1。
- 配置缺失/DPAPI 解密失败：提示运行 `python setup_config.py`，exit 2。
- Portal 结构变化（找不到表单）：转储 HTML 前 4KB 到日志，exit 3，等待人工补 `form_override`。

## Testing

- `tests/test_gate.py`：纯函数单测（should_login 决策矩阵），无需硬件。
- 手动四态：以太网Up未认证→登录；已认证→退出；以太网Disabled→退出；热点+Mihomo→退出。用 `--dry-run` 先验决策。
- 抓包确认：中国移动字段值（需 `capture_portal` 输出确定）。

## Open item

Portal 表单字段名需用户切回校园网未认证态运行 `python tools/capture_portal.py` 后补齐 `config.json` 的 `form_override`。在此之前登录函数走“自动表单填充+可配置后缀”兼容模式。
