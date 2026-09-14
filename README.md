# 校园网自动认证（auto_campus_network）

插上网线 / 启用以太网后，自动完成深澜 ePortal Web 认证（`http://10.10.30.21` 跳转的 `login.lsu.edu.cn:8443` 登录页）；
用 Wi-Fi 热点 + 代理上网时绝不干扰、绝不弹窗。

- 平台：Windows 10/11 + Python 3.10+（**仅标准库**，计划任务裸跑无依赖）
- 触发：Windows 计划任务（连网事件 + 登录兜底），无常驻进程
- 实测：ePortal `InterFace.do?method=login` 真实 `login-ok`，21 项单测全过

## 快速开始

```powershell
# 1. 生成配置（学号+密码，密码经 Windows DPAPI 加密存 config.json，仅本机本用户可解）
python setup_config.py

# 2. 干跑验证决策（只打印，不登录）
python src/campus_auth.py --dry-run
# eth_up=True ... portal_state=unauthed-redirect need=need-login   -> 会登录
# eth_up=False ... need=eth-down-silent-exit                      -> 热点中，静默退出

# 3. 注册计划任务（管理员 PowerShell）
powershell -ExecutionPolicy Bypass -File "scripts\Register-CampusTask.ps1"
```

日常观察 `logs/auth.log`：出现 `need-login` + `login-ok` 即自动登上。

## 工作原理

```
计划任务事件 → 以太网 Up？否→静默退出
→ 取 http://10.10.30.21/ 回包分类：成功页=已放行退出 / 跳转脚本=未认证继续
→ 取 queryString → pageInfo 取 RSA 公钥 → 密码拼 `>mac` 反转+RSA 加密
→ POST InterFace.do?method=login（直连 10.10.30.21:8443，SNI/Host 用域名，绕开 TUN 假 DNS）
→ 复查网关翻页才算成功
```

关键设计：**门控看网关回包内容，不看 204 探测**（204 会被 TUN/热点掩蔽，见 docs/pitfalls.md）。

## 项目结构

```
src/campus_auth.py   主逻辑（门控 IO + ePortal 登录 + RSA）
src/gate.py          防干扰门控纯函数
setup_config.py      交互式生成 config.json（DPAPI 加密）
config.example.json  配置模板
scripts/Register-CampusTask.ps1  注册计划任务 CampusAutoAuth
tools/capture_portal.py   未认证态抓 Portal 跳转
tools/verify_login.py     单发登录 + 三重放行验证
tools/replay_offline.py   离线裁决（回放浏览器密文 + 正式链路）
tests/               pytest 单测（门控/RSA/编码/节流）
docs/                技术细节与踩坑记录
```

## 配置说明

`config.json`（`setup_config.py` 生成，**不要上传**，已在 `.gitignore`）：

| 字段 | 说明 |
|---|---|
| `username` | 学号原文（统一身份认证，不加后缀） |
| `service` | 运营商服务名，如 `移动`（中国移动校园宽带登录） |
| `password_dpapi` | DPAPI 密文 |
| `username_suffix` / `isp_value` | 旧版兼容字段，ePortal 路径不用 |

## 换密码 / 维护

```powershell
python setup_config.py                                  # 重输密码
schtasks /Change /TN CampusAutoAuth /DISABLE            # 暂停自动登录
schtasks /Change /TN CampusAutoAuth /ENABLE             # 恢复
python -m pytest tests/ -v                              # 跑单测
```
