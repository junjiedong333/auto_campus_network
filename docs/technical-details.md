# 技术细节

## 1. 认证链路全貌

校园网关（`10.10.30.21:80`）本身只是 328 字节跳转跳板：

```html
<script>top.self.location.href='https://login.lsu.edu.cn:8443/eportal/index.jsp?wlanuserip=...&...&mac=...&t=wireless-v2&...'</script>
```

真登录页是深澜 ePortal（`login.lsu.edu.cn:8443/eportal/`），登录接口为
`POST /eportal/InterFace.do?method=login`，字段（见 `AuthInterFace.js`）：

```
userId / password / service / queryString / operatorPwd / operatorUserId / validcode / passwordEncrypt
```

- `userId`：学号原文（`pageInfo.domainName=false`，不加运营商后缀）。
- `service`：运营商服务名，本例 `移动`（`getServices` 返回 `serviceName=移动`，显示名"中国移动校园宽带登录"）。
- `queryString`：index.jsp 的查询串，**双重 URL 编码**后发送。
- `password`：见第 2 节。
- `operatorPwd/operatorUserId/validcode`：本场景为空（`pageInfo.validCodeUrl` 为空即无验证码）。

`AuthInterFace.init("./")` 说明接口基址与页面同目录，相对路径直调即可。

## 2. 密码加密：Barrett 教科书式 RSA（不是 PKCS#1）

`login_bch.js` 提交前：

```js
var passwordMac = password + ">" + macString;   // mac 取自 index query 的 mac 参数，缺省 "111111111"
password = encryptedPassword(passwordMac);      // 反转 + RSA
```

`security.js` 的 `RSAUtils.encryptedString` 是 Paul Johnston 式 Barrett 实现，
与标准 RSA 有三处本质不同：

1. **零填充**，无 PKCS#1 v1.5 随机填充；
2. 按 `digits[j] = a[2j] + (a[2j+1] << 8)` **小端组块**，整块一次 `powMod`；
3. 块大小 `chunkSize = 2 * biHighIndex(m)`（1024-bit 密钥为 126 字节），输出定宽 hex。

`src/campus_auth.py::rsa_encrypt_hex` 用纯标准库（`pow(m, e, n)` + `int.from_bytes(..., 'little')`）
逐字节复刻，并用浏览器真实密文做过**离线已知答案比对**（逐字节一致，见 `docs/pitfalls.md` 第 4 条）。

## 3. TUN 下直连：IP + SNI + Host 三件套

`login.lsu.edu.cn` 在 TUN 下会被劫持解析到 `198.18.0.x` 假 IP（Mihomo 默认 fake-ip 段恰与校园真地址段冲突），
直连域名必握手失败。做法：TCP 直连 `10.10.30.21:8443`，TLS SNI 用 `login.lsu.edu.cn`，
HTTP `Host: login.lsu.edu.cn:8443`。另老设备只认旧 cipher，TLS 上下文需
`set_ciphers("ALL:@SECLEVEL=0")` + 最低 TLSv1，否则 `SSLV3_ALERT_HANDSHAKE_FAILURE`。

## 4. 门控：看网关回包，不看 204

`classify_portal_html` 只看 `http://10.10.30.21/` 回包内容：

- 含 `eportal/index.jsp` 跳转脚本 → `unauthed-redirect`（未放行）
- 含 `getOnlineUserInfo`/`success.jsp` → `authed-success`（已放行）

`login_needed(eth_up, portal_state)`：仅"以太网 Up + 未放行"才登录。
204 探测只做参考日志——TUN/热点在时 204 恒通，会掩蔽真实未认证态。

## 5. 防风暴与静默

- 以太网非 Up（禁用/断开/不存在）秒退；已启用但未 Up（刚插线）最多等 25 秒网卡就绪。
- 真实登录尝试节流 20 秒；任务侧 `MultipleInstancesPolicy=IgnoreNew` 防重叠。
- 所有 `powershell` 子进程带 `CREATE_NO_WINDOW`，任务跑 `pythonw.exe`，全程无窗口。
- 登录后复查网关翻页才算成功；`logs/state.json` 记上次尝试时间。
