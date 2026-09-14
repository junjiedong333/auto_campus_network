# Campus Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 插上网线/启用以太网后自动完成 10.10.30.21 Portal 认证，热点+Mihomo 时静默退出。

**Architecture:** Windows 计划任务事件触发 + Python 标准库脚本直调 Portal，脚本内二次门控防干扰。

**Tech Stack:** Python 3.10+ 标准库 (urllib, json, socket, subprocess), PowerShell (Get-NetAdapter, DPAPI, ScheduledTasks), pytest for tests.

## Global Constraints

- 仅监听/判断名为 `以太网` 的有线网卡，不碰 WLAN/Mihomo/VMware 虚拟网卡。
- 热点+Mihomo（WLAN Up + 以太网 Disabled + Portal 不可达）时必须静默 exit 0，不弹窗不断网。
- 密码不允许明文落盘，必须经 Windows DPAPI 加密后存 config.json。
- 不引入 requests/bs4 等第三方依赖，只用标准库，保证计划任务裸跑可用。
- Portal 地址固定 `http://10.10.30.21/`，运营商固定中国移动单选项，可配置覆盖。

---

### Task 1: 门控纯函数 + 单测

**Files:**
- Create: `src/gate.py`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: 无（纯函数，无 IO）
- Produces: `should_login(eth_up: bool, portal_reachable: bool, internet_ok: bool) -> bool`, `decide(reason) -> tuple[bool, str]`

- [x] **Step 1: Write the failing test**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Write minimal implementation**
- [x] **Step 4: Run test to verify it passes**

### Task 2: 主脚本门控 IO + 干跑模式

**Files:**
- Create: `src/campus_auth.py`
- Modify: `src/gate.py` (仅复用，不改签名)

**Interfaces:**
- Consumes: `src.gate.should_login/decide`
- Produces: `is_eth_up(name="以太网")->bool`, `is_portal_reachable(host="10.10.30.21")->bool`, `is_internet_ok()->bool`, `main(argv)->int`

- [x] **Step 1-4 done**：门控 IO + `--dry-run` 只打印决策不登录。

### Task 3: Portal 登录（ePortal 直调，最终实现）

**Files:**
- Modify: `src/campus_auth.py`
- Create: `config.example.json`
- Create: `tools/capture_portal.py`

实际逆向结论（见 docs/technical-details.md）：`10.10.30.21` 只是 328 字节跳转跳板，
真接口为 `POST https://login.lsu.edu.cn:8443/eportal/InterFace.do?method=login`，
字段 `userId/password/service/queryString/operatorPwd/operatorUserId/validcode/passwordEncrypt`，
密码算法为 Barrett 教科书式 RSA（`password+">"+mac` 反转后加密），service 取 `移动`。

- [x] ePortal 登录链 + RSA + 双重编码 + Cookie 会话 + 网关复验，真实 `login-ok`。

### Task 4: DPAPI 配置 + 计划任务注册

**Files:**
- Create: `setup_config.py`
- Create: `scripts/Register-CampusTask.ps1`
- Create: `.gitignore` (忽略 config.json, logs/, portal.html)

- [x] `setup_config.py` DPAPI 加密写 `config.json`；任务 `CampusAutoAuth`（连网事件 + 登录兜底）。
