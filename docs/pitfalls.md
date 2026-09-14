# 踩坑记录

## 1. 204 探测被 TUN/热点掩蔽 → 永远判断"已在线"

**现象**：网关明明回登录跳转，脚本却判 `already-online`，从不登录。
**根因**：`is_internet_ok` 量的是整机外网。TUN（默认路由 metric 0）或手机热点在时，
`generate_204` 真 204，与校园网关放行与否无关。
**解法**：门控改看网关回包内容（`classify_portal_html`），204 只做参考。
**证据**：路由表三条 metric 0 默认路由（Mihomo/以太网/WLAN 残留）+ 单出口对照组曾正常出现 `need-login`。

## 2. Mihomo 假 IP 段与校园真地址冲突

**现象**：`login.lsu.edu.cn` 解析结果每次都变（`198.18.0.69` → `.22` → `.15`），`:8443` SSL 握手失败。
**根因**：Mihomo 默认 fake-ip 段 `198.18.0.0/16` 恰好覆盖校园真地址，DNS 被劫持。
`route add` 绕行需要管理员权限，此路不通。
**解法**：TCP 直连 `10.10.30.21:8443` + SNI/Host 用域名（见技术细节第 3 节）。
脚本 POST 全走 IP，本不受影响；只有浏览器走域名才需要关 TUN。

## 3. 老 ePortal 的 TLS 要降级

**现象**：Python 默认上下文 `SSLV3_ALERT_HANDSHAKE_FAILURE`，而 schannel/curl 直连 IP 能通。
**根因**：设备证书/密码套件老，OpenSSL 默认 SECLEVEL 拒掉。
**解法**：`ctx.set_ciphers("ALL:@SECLEVEL=0")` + `minimum_version=TLSv1`（实际协商出 TLSv1.2/AES128-SHA256）。

## 4. 错抄 RSA：PKCS#1 vs Barrett，格式一样内容全错

**现象**：连败 6+ 次 `用户不存在或者密码错误`，浏览器同账号同密码一次就过。
**根因**：想当然写成 PKCS#1 v1.5（随机填充、大端整数），而 `security.js` 是 Barrett
教科书式 RSA（零填充、小端组块、无随机填充）。输出碰巧都是 256 位 hex，内容全错。
**关键证据**：浏览器密文与自家实现无法比对（随机填充每次不同）一度误导排查；
读完 `security.js` 发现是确定性加密后，用配置密码离线重算，与浏览器密文**逐字节一致**，
同时证伪了"密码录错"理论。
**教训**：第三方魔改加密必须读实现，不能按名字脑补；确定性算法优先找已知答案向量。

## 5. 漏拼 `>mac` 与单次编码

**现象**：同上，密码错。
**根因**：`login_bch.js` 提交的是 `password + ">" + mac`（mac 取自 index query），
且 `userId/password/service/queryString/encrypt` 全部双重 URL 编码。
**解法**：`_double_quote` + 从 query 实时取 mac（缺省 `111111111`，与 JS 一致）。

## 6. 登录成功回包 ≠ 网关放行

**现象**：`result=success` 但网页打不开（在线时再登一遍服务端也回 success，假阳性）。
**解法**：登录后必须复查——重取网关页分类 + `getOnlineUserInfo` + 204，三路证据；
`verify_login.py` 即为此而生。另连打两发会互顶会话，验证/回放脚本都只打单发。

## 7. 事件风暴互顶会话 + 弹窗

**现象**：网络抖动时任务被连网事件反复触发，连打登录互顶会话，网一直断，
captive-portal 弹窗跟着一直跳。
**解法**：登录尝试节流（20 秒）+ 任务 `IgnoreNew` 防重叠 + 登录后复验；
另 180 秒节流曾误伤正常插线登录，已回调。

## 8. 计划任务 `.ps1` 的两个坑

- 相对路径：管理员 PowerShell 默认在 `system32`，必须用绝对路径调 `-File`。
- UTF-8 无 BOM + 中文字符串在 PS 5.1 下报"字符串缺少终止符"：输出行改 ASCII + 文件存 UTF-8-SIG。

## 9. 终端粘贴带提示符

复制 `PS D:\...>` 整行（含提示符）粘回 PowerShell 会满屏报错（`PS` 被当成 `Get-Process`）。
只输命令本身。
