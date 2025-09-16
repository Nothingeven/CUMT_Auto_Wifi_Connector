矿大云盘官方下载链接：https://pan.cumt.edu.cn/share/0c20d989143c155c6ad502c4ed   密码：cumt

GitHub开源链接：https://github.com/Nothingeven/CUMT_Auto_Wifi_Connector/

蓝奏云链接：https://wwwg.lanzouu.com/b014wpl1md   密码:cumt

更新要点汇总
    UI/体验
        天空玻璃更通透：天空淡蓝 SKY_BLUE(215,240,255)，透明度 SKY_ALPHA 从 0xE0→0xCC，整体更“玻璃感”。
        无边框圆角与毛玻璃：Win11 Acrylic 优先，失败自动降级到 Blur；增加圆角遮罩去黑边。
        自定义标题栏与托盘常驻，关闭时最小化到托盘。

    安全/数据
        DPAPI 加密保存密码：默认“用户范围”；解密兼容旧“机器范围”密文（向后兼容）。
        首次运行自动迁移旧版 D:\CampusLoginData\credentials.json 明文配置到新目录并加密保存。
        移除 D: 盘依赖，统一使用 LOCALAPPDATA 作为数据目录。
        配置“原子写”（临时文件 + replace），降低掉电/崩溃造成的配置损坏风险。

    启动与分发（大规模稳态）
        开机自启动：以 .lnk 方式注入“--auto”静默自启。
        单实例互斥锁，自动模式隐藏控制台窗口。
        错峰与退避抖动：自动模式按用户名哈希 0–12s 启动抖动；指数退避带 ±15% 抖动，避免洪峰冲击网关。
        仅校园网络策略：非校园场景自动休眠，节省无效请求。

    网络判定与自动登录（核心演进）
        成功判定增强：除 success/login_ok/中文提示外，若不确定立即做连通性校验，连通判定为 OK_ONLINE，避免“成功上网却提示失败”。
        网关域名跳转判断：访问网关根地址，识别 302 到 aXX.htm、携带 wlanuserip/ssid/eportal/login 等参数即判定为 captive（门户拦截）。
        外网导回/复位判定：对外网探测结果若出现被导回网关或连接复位（RST），结合网关可达，判定 captive。
        页面内跳转识别：识别 meta refresh / JS window.location 跳转，防止“无 302 但实际被拦截”漏检。
        多信号融合与阈值：综合网关跳转、外网导回、错误计数、可达性，加入去抖/迟滞（online→captive/offline 需连续两次确认）。
        手动登录复核：若初判 captive，短延迟复检一次；若复检 online 返回 OK_ONLINE_FINAL，减少误报。
        严格连通性与 DNS 劫持检测：
            严格探测集：要求 204 端点必须返回 204；微软/苹果连通性页进行内容匹配，防止“白名单/缓存”导致的假在线。
            随机 .invalid 域名 DNS 检测：若被解析或异常行为，作为 captive 的强信号。
        注销判定优化：注销后根据网关/外网状态返回“已注销（检测到门户拦截）/仍可用（网关延迟收敛或白名单）/当前离线”。

    兼容性与鲁棒性
        User-Agent 统一改为 ASCII，修复 requests 在发送中文 UA 时出现的 'latin-1' 编码报错。
        SSID 解析使用系统首选编码，避免 netsh 输出编码导致的解析失败。
        Win 特性调用全包裹降级：Acrylic/圆角失败不影响窗口正常显示。

    日志与诊断
        日志限长与截断：>2MB 自动保留末尾 256KB，避免占满磁盘。
        在线心跳：在线状态每 5 分钟打印心跳，证明监控线程仍在运行。
        可选“详细检测日志”：输出每条外网/严格探测样本与 DNS 检测结果，现场排障更高效。

    交互与提示
        统一错误码：OK、OK_ONLINE、OK_ONLINE_FINAL、E_NO_CRED、E_BAD_PASS、E_LIMIT、E_CAPTIVE、E_OFFLINE、E_TIMEOUT、E_REQUEST、E_UNKNOWN。
        通知冷却与等级：off/important/all，降低多人并发使用时的干扰。


————————————————————————————————————————————————————————————————————



Official download link for Minzu Cloud Drive: https://pan.cumt.edu.cn/share/0c20d989143c155c6ad502c4ed   Password: cumt
GitHub open-source link: https://github.com/Nothingeven/CUMT_Auto_Wifi_Connector/
LanZou Cloud Link: https://wwwg.lanzouu.com/b014wpl1md   Password: cumt

Update Highlights Summary
    UI/Experience
        Enhanced sky transparency: Sky color adjusted to SKY_BLUE(215,240,255), transparency SKY_ALPHA increased from 0xE0 to 0xCC for a more “glass-like” effect.
        Borderless Rounded Corners & Frosted Glass: Prioritizes Win11 Acrylic; automatically falls back to Blur if unavailable. Added rounded corner masks to eliminate black borders.
        Customizable Title Bar & System Tray Residency: Minimizes to tray when closed.

    Security/Data
        DPAPI Encrypted Password Storage: Default “User Scope”; decryption compatible with legacy “Machine Scope” ciphertext (backward compatible).
        First-run auto-migration of legacy plaintext credentials from D:\CampusLoginData\credentials.json to new encrypted directory.
Removed D: drive dependency; unified data directory to LOCALAPPDATA.
Implemented “atomic write” (temp file + replace) to reduce configuration corruption risks from power loss/crashes.

    Launch & Distribution (Large-Scale Steady State)
        Auto-start on boot: Injects “--auto” silently via .lnk for silent startup.
        Single-instance mutex lock; hides console window in auto mode.
        Off-peak scheduling & evasive jitter: Auto mode applies 0–12s startup jitter based on username hash; exponential backoff with ±15% jitter prevents gateway overload during traffic spikes.
        Campus Network Only Policy: Auto-hibernates outside campus networks to reduce redundant requests.

Network Verification & Auto-Login (Core Evolution)
*   Enhanced Success Verification: Beyond success/login_ok/Chinese prompts, performs immediate connectivity checks if uncertain. Connectivity is marked as OK_ONLINE to prevent “failed” prompts despite successful internet access.
        Gateway Domain Redirect Detection: Accesses the gateway root address; identifies 302 redirects to aXX.htm with parameters like wlanuserip/ssid/eportal/login as captive portal interception.
        External Network Redirect/Reset Detection: If external network probes show redirection back to the gateway or connection reset (RST), combined with gateway reachability, it is identified as captive portal.
        Intra-page Redirect Detection: Identifies meta refresh or JS window.location redirects to prevent false negatives where “no 302 exists but actual interception occurs.”
        Multi-signal Fusion & Thresholding: Integrates gateway redirects, external network redirection, error counts, and reachability with debouncing/hysteresis (online→captive/offline requires two consecutive confirmations).
        Manual Login Verification: If initially classified as captive, perform a short-delay recheck; if recheck confirms online, return OK_ONLINE_FINAL to reduce false positives.
Strict Connectivity and DNS Hijacking Detection:
- Strict probe set: Requires 204 endpoints to return 204 responses; performs content matching on Microsoft/Apple connectivity pages to prevent “whitelist/cache” false positives.
            Random .invalid domain DNS checks: If resolved or exhibits abnormal behavior, serves as a strong captive signal.
Optimized logout determination: After logout, returns “Logged out (detected portal interception)/Still accessible (gateway delay convergence or whitelist)/Currently offline” based on gateway/external network status.

    Compatibility and Robustness
        Unified User-Agent to ASCII, fixing ‘latin-1’ encoding errors when sending Chinese UAs via requests.
        SSID parsing uses system default encoding to prevent failures caused by netsh output encoding.
        Full wrapper downgrade for Win feature calls: Acrylic/rounded corners failure does not affect normal window display.

    Logging and Diagnostics
        Log size limit and truncation: Automatically preserves the last 256KB for logs exceeding 2MB to prevent disk space exhaustion.
        Online heartbeat: Prints a heartbeat every 5 minutes to confirm the monitoring thread remains active.
        Optional “Detailed Diagnostic Log”: Outputs results for each external network/strict probe sample and DNS check, enabling more efficient on-site troubleshooting.

    Interaction & Notifications
        Unified Error Codes: OK, OK_ONLINE, OK_ONLINE_FINAL, E_NO_CRED, E_BAD_PASS, E_LIMIT, E_CAPTIVE, E_OFFLINE, E_TIMEOUT, E_REQUEST, E_UNKNOWN.
        Notification Cooling & Priority: off/important/all. Reduces interference during concurrent multi-user operations.
Interaction and Prompts Unified Error Codes: OK, OK_ONLINE, OK_ONLINE_FINAL, E_NO_CRED, E_BAD_PASS, E_LIMIT, E_CAPTIVE, E_OFFLINE, E_TIMEOUT, E_REQUEST, E_UNKNOWN. Notification Cooling and Priority Levels: off/important/all, reducing disruption during multi-user concurrency.
