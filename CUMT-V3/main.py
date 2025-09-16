# -*- coding: utf-8 -*-
"""
校园网自动登录助手 v3.0
作者: Nothingeven & Copilot
更新日期: 2025-09-15

关键改进：
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


"""

import os, sys, json, re, time, threading, subprocess, ctypes, base64, signal, random, locale, hashlib, tempfile, socket
from datetime import datetime, timedelta
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QPoint
from PySide6.QtGui import QAction, QIcon, QTextCursor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QRadioButton, QGroupBox, QCheckBox, QComboBox,
    QTextEdit, QSystemTrayIcon, QMenu, QFrame, QMessageBox, QStyle
)

import requests


# ----------------------------
# 基础信息与路径
# ----------------------------
APP_NAME = "校园网自动登录工具"
APP_VERSION = "3.0"
USER_AGENT = "CUMT-AutoLogin/3.0"  # ASCII-only
ORG_DATA_DIR = os.path.join(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"), "CampusLoginData")
APP_DATA_DIR = os.path.join(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"), "CUMT_Auto_Wifi_Connector")
DATA_DIR = APP_DATA_DIR if os.path.isdir(APP_DATA_DIR) or not os.path.isdir(ORG_DATA_DIR) else ORG_DATA_DIR
CONFIG_FILE = os.path.join(DATA_DIR, "settings.json")
LOG_FILE = os.path.join(DATA_DIR, "login_log.txt")
SINGLE_INSTANCE_MUTEX = "Global\\CUMT_Auto_Wifi_Connector_v3"
DEFAULT_PORTAL_BASE = "http://10.2.5.251:801/eportal/"
DEFAULT_GATEWAY_HOST = "10.2.5.251"
DEFAULT_SSID_HINTS = ["CUMT", "cumt", "校园网", "CUMT-"]

# 监控与通知
BASE_CHECK_INTERVAL = 5
MAX_CHECK_INTERVAL = 300
NETWORK_STABLE_GRACE = 20
NOTIFY_COOLDOWN = 180
ONLINE_HEARTBEAT_SECS = 300  # 在线心跳日志间隔

# 抖动配置
STARTUP_JITTER_MAX = 12
BACKOFF_JITTER_RATIO = 0.15

# 去抖阈值
STATE_CONFIRM_ONLINE_TO_OTHER = 2  # online -> (captive/offline) 需要 2 次确认
STATE_CONFIRM_OTHER_TO_ONLINE = 1  # (captive/offline) -> online 1 次即可

# 旧版（v2）兼容迁移位置
OLD_V2_DIR = r"D:\CampusLoginData"
OLD_V2_CRED = os.path.join(OLD_V2_DIR, "credentials.json")

# ----------------------------
# 工具：目录/日志/单实例
# ----------------------------
def ensure_dirs():
    try: os.makedirs(DATA_DIR, exist_ok=True)
    except Exception: pass

def _rotate_log_if_needed():
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 2 * 1024 * 1024:
            with open(LOG_FILE, "rb") as f:
                f.seek(-256 * 1024, os.SEEK_END)
                tail = f.read()
            with open(LOG_FILE, "wb") as f:
                f.write(b"[LOG ROTATED]\n")
                f.write(tail)
    except Exception:
        pass

def log_write(msg: str):
    ensure_dirs()
    _rotate_log_if_needed()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)

class SingleInstance:
    def __init__(self, name: str):
        self.name = name
        self.handle = None
    def acquire(self) -> bool:
        try:
            CreateMutex = ctypes.windll.kernel32.CreateMutexW
            GetLastError = ctypes.windll.kernel32.GetLastError
            self.handle = CreateMutex(None, ctypes.c_bool(True), self.name)
            return GetLastError() != 183
        except Exception:
            return True
    def release(self):
        try:
            if self.handle:
                ctypes.windll.kernel32.ReleaseMutex(self.handle)
                ctypes.windll.kernel32.CloseHandle(self.handle)
        except Exception:
            pass

# ----------------------------
# DPAPI 加解密（默认用户范围；解密兼容）
# ----------------------------
def dpapi_encrypt_user(plain: str) -> str:
    try:
        import ctypes, ctypes.wintypes as wt
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD), ("pbData", wt.LPBYTE)]
        data = plain.encode("utf-8")
        in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), wt.LPBYTE))
        out_blob = DATA_BLOB()
        CryptProtectData = ctypes.windll.crypt32.CryptProtectData
        res = CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob))
        if not res: return ""
        cipher = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return base64.b64encode(cipher).decode("ascii")
    except Exception:
        return ""

def dpapi_encrypt_machine(plain: str) -> str:
    try:
        import ctypes, ctypes.wintypes as wt
        CRYPTPROTECT_LOCAL_MACHINE = 0x4
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD), ("pbData", wt.LPBYTE)]
        data = plain.encode("utf-8")
        in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), wt.LPBYTE))
        out_blob = DATA_BLOB()
        CryptProtectData = ctypes.windll.crypt32.CryptProtectData
        res = CryptProtectData(ctypes.byref(in_blob), None, None, None, None, CRYPTPROTECT_LOCAL_MACHINE, ctypes.byref(out_blob))
        if not res: return ""
        cipher = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return base64.b64encode(cipher).decode("ascii")
    except Exception:
        return ""

def dpapi_decrypt_compat(cipher_b64: str) -> str:
    for _ in (0, 1):
        try:
            import ctypes, ctypes.wintypes as wt
            raw = base64.b64decode(cipher_b64)
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wt.DWORD), ("pbData", wt.LPBYTE)]
            in_blob = DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), wt.LPBYTE))
            out_blob = DATA_BLOB()
            CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
            res = CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob))
            if not res:
                continue
            plain = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return plain.decode("utf-8")
        except Exception:
            pass
    return ""

# ----------------------------
# 配置 + 原子写 + 旧版迁移
# ----------------------------
DEFAULT_SETTINGS = {
    "username": "",
    "password_enc": "",
    "network_type": "1",
    "enable_monitoring": True,
    "run_on_startup": True,
    "only_on_campus": True,
    "campus_ssid_hints": DEFAULT_SSID_HINTS,
    "portal_base": DEFAULT_PORTAL_BASE,
    "notification_level": "important",
    "verbose_probe_log": False,   # 排障日志
    "last_login": ""
}

def atomic_write_json(path: str, data: dict) -> bool:
    ensure_dirs()
    try:
        d = json.dumps(data, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(prefix="cfg_", suffix=".json", dir=DATA_DIR)
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(d)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            if 'tmp' in locals() and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False

def load_settings() -> dict:
    ensure_dirs()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_SETTINGS.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(cfg: dict):
    return atomic_write_json(CONFIG_FILE, cfg)

def try_migrate_from_v2(cfg: dict) -> dict:
    try:
        if not os.path.exists(OLD_V2_CRED):
            return cfg
        with open(OLD_V2_CRED, "r", encoding="utf-8") as f:
            old = json.load(f)
        username = old.get("username") or ""
        password = old.get("password") or ""
        network_type = str(old.get("network_type", "1"))
        enable_monitoring = bool(old.get("enable_monitoring", True))
        if username and password:
            log_write("检测到旧版凭据，执行迁移")
            cfg["username"] = username
            cfg["password_enc"] = dpapi_encrypt_user(password) or dpapi_encrypt_machine(password) or ""
            cfg["network_type"] = network_type if network_type in ("1","2","3","4") else "1"
            cfg["enable_monitoring"] = enable_monitoring
            cfg["run_on_startup"] = True
            cfg["only_on_campus"] = True
            cfg["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_settings(cfg)
            log_write("旧版凭据迁移完成（已加密保存）")
        return cfg
    except Exception as e:
        log_write(f"迁移旧版凭据失败: {e}")
        return cfg

# ----------------------------
# 自启动
# ----------------------------
def set_startup(enable: bool):
    try:
        startup_folder = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
        if enable:
            ps_cmd = f'''
$W = New-Object -ComObject WScript.Shell
$S = $W.CreateShortcut("{shortcut_path}")
$S.TargetPath = "{sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]}"
$S.Arguments = "--auto"
$S.WorkingDirectory = "{os.path.dirname(sys.argv[0])}"
$S.Save()
'''
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
        return True
    except Exception as e:
        log_write(f"设置开机自启失败: {e}")
        return False

def check_startup_enabled() -> bool:
    try:
        path = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup", f"{APP_NAME}.lnk")
        return os.path.exists(path)
    except Exception:
        return False

# ----------------------------
# 网络与门户：SSID + 判定策略
# ----------------------------
def current_ssid() -> str:
    if not sys.platform.startswith("win"):
        return ""
    try:
        enc = locale.getpreferredencoding(False) or "utf-8"

        # 隐藏 netsh 子进程窗口的启动参数
        CREATE_NO_WINDOW = 0x08000000
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE

        # 直接调用系统 netsh.exe，避免 shell=True
        netsh_path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "netsh.exe")
        cmd = [netsh_path, "wlan", "show", "interfaces"]

        try:
            out = subprocess.check_output(
                cmd,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                startupinfo=si,
                creationflags=CREATE_NO_WINDOW,
                encoding=enc,
                errors="ignore",
            )
        except FileNotFoundError:
            # 兜底：如果上面的绝对路径异常，退回到 PATH 中的 netsh
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                startupinfo=si,
                creationflags=CREATE_NO_WINDOW,
                encoding=enc,
                errors="ignore",
            )

        m = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
        return (m.group(1).strip() if m else "")
    except Exception:
        return ""
    
def is_campus_env(cfg: dict) -> bool:
    ssid = current_ssid()
    for h in (cfg.get("campus_ssid_hints") or DEFAULT_SSID_HINTS):
        try:
            if h and h.lower() in ssid.lower():
                return True
        except Exception:
            pass
    try:
        base = cfg.get("portal_base") or DEFAULT_PORTAL_BASE
        r = requests.get(base, timeout=1)
        if r.status_code in (200, 302):
            return True
    except Exception:
        pass
    return False

# Captive URL 特征
CAPTIVE_HINT_PATTERNS = [
    r"/a\d+\.htm",            # a79.htm / aXX.htm
    r"wlanuserip=", r"ssid=", r"wlanacname=", r"nasip=",
    r"\beportal\b", r"\bportal\b", r"\bauth\b", r"login",
    r"ruijie",
]

def _find_meta_or_js_redirect(html: str) -> str:
    try:
        h = html or ""
        m = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]*content=["\']\s*\d+\s*;\s*url=([^"\']+)["\']', h, re.I)
        if m:
            return m.group(1)
        m = re.search(r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', h, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""

def get_gateway_host(cfg: dict) -> str:
    try:
        parsed = urlparse(cfg.get("portal_base") or DEFAULT_PORTAL_BASE)
        if parsed.hostname:
            return parsed.hostname
    except Exception:
        pass
    return DEFAULT_GATEWAY_HOST

def gateway_reachable(cfg: dict, timeout: int = 2) -> bool:
    host = get_gateway_host(cfg)
    headers = {"User-Agent": USER_AGENT, "Cache-Control": "no-cache", "Pragma": "no-cache"}
    try:
        _ = requests.head(f"http://{host}/?_t={int(time.time()*1000)}", timeout=timeout, allow_redirects=False, headers=headers)
        return True
    except Exception:
        return False

# 网关重定向判定
def portal_redirection_state(cfg: dict, timeout: int = 3) -> (str, dict):
    host = get_gateway_host(cfg)
    base = f"http://{host}/?_t={int(time.time()*1000)}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    def looks_captive_url(url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        for p in CAPTIVE_HINT_PATTERNS:
            if re.search(p, u, re.I):
                return True
        return False

    try:
        r = requests.get(base, timeout=timeout, allow_redirects=False, headers=headers)
        loc = r.headers.get("Location") or r.headers.get("location") or ""
        if 300 <= r.status_code < 400 and looks_captive_url(loc):
            return "captive", {"via": "302", "location": loc}
        if r.status_code == 200:
            inner = _find_meta_or_js_redirect(r.text or "")
            if looks_captive_url(inner):
                return "captive", {"via": "html", "location": inner}
            return "logged_in", {"status": 200}
    except Exception:
        pass

    try:
        r2 = requests.get(base, timeout=timeout, allow_redirects=True, headers=headers)
        final_url = r2.url or ""
        if looks_captive_url(final_url) and (final_url.rstrip("/") != base.rstrip("/")):
            return "captive", {"via": "redir", "final_url": final_url}
        if r2.status_code == 200:
            return "logged_in", {"status": 200, "final_url": final_url}
    except Exception:
        pass

    return "unknown", {}

# 严格探测集：要求状态码/内容严格匹配，防止白名单/缓存“假在线”
STRICT_PROBES = [
    # 期望 204
    {"url": "http://www.gstatic.com/generate_204", "expect_status": 204},
    {"url": "http://connectivitycheck.gstatic.com/generate_204", "expect_status": 204},
    {"url": "http://connect.rom.miui.com/generate_204", "expect_status": 204},
    # 期望内容
    {"url": "http://www.msftconnecttest.com/connecttest.txt", "expect_status": 200, "expect_body": "Microsoft Connect Test"},
    {"url": "http://captive.apple.com/hotspot-detect.html", "expect_status": 200, "expect_body_contains": "Success"},
]

# 外网探测（严格判定 + 统计）
def strict_external_probe(cfg: dict, timeout: int = 3) -> dict:
    host = get_gateway_host(cfg).lower()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    def looks_captive(url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        if host and host in u:
            return True
        for p in CAPTIVE_HINT_PATTERNS:
            if re.search(p, u, re.I):
                return True
        return False

    ok_strict = redirects = errors = mismatches = 0
    samples = []
    ts = int(time.time()*1000)
    for p in STRICT_PROBES:
        u = f"{p['url']}?_t={ts}"
        try:
            r = requests.get(u, timeout=timeout, allow_redirects=True, headers=headers)
            final_url = r.url or ""
            if looks_captive(final_url) or r.status_code in (511, 401, 403):
                redirects += 1
                samples.append({"url": u, "final": final_url, "status": r.status_code, "type": "redir"})
                continue
            # 严格校验
            ok = (r.status_code == p.get("expect_status", 200))
            if ok and "expect_body" in p:
                ok = (p["expect_body"] in (r.text or ""))
            if ok and "expect_body_contains" in p:
                ok = (p["expect_body_contains"].lower() in (r.text or "").lower())
            if ok:
                ok_strict += 1
                samples.append({"url": u, "final": final_url, "status": r.status_code, "type": "ok"})
            else:
                mismatches += 1
                samples.append({"url": u, "final": final_url, "status": r.status_code, "type": "mismatch"})
        except (requests.Timeout, requests.ConnectionError) as e:
            errors += 1
            samples.append({"url": u, "final": "", "status": -1, "type": f"conn_err:{e.__class__.__name__}"})
        except Exception as e:
            errors += 1
            samples.append({"url": u, "final": "", "status": -2, "type": f"exc:{e.__class__.__name__}"})

    if cfg.get("verbose_probe_log", False):
        log_write(f"[StrictProbe] ok={ok_strict} redir={redirects} err={errors} mismatch={mismatches}")
        for s in samples:
            log_write(f"[StrictProbe] {s['type']} url={s['url']} -> {s['final']} status={s['status']}")
    return {"ok": ok_strict, "redirects": redirects, "errors": errors, "mismatches": mismatches}

# DNS 劫持/NXDOMAIN 检测：随机 .invalid 应当 NXDOMAIN；若解析出 IP 或超时（结合网关可达）判为 captive 信号
def dns_invalid_resolves_quick(timeout_sec: float = 0.8) -> dict:
    result = {"resolved": False, "timedout": False, "error": ""}
    domain = f"cp-{int(time.time()*1000)}.invalid"

    def worker():
        try:
            socket.getaddrinfo(domain, 80, family=socket.AF_INET)
            result["resolved"] = True
        except socket.gaierror as e:
            # NXDOMAIN 等均会抛出错误，这里视为未解析（期望行为）
            result["error"] = str(e)
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)
    if t.is_alive():
        result["timedout"] = True
    return result

def is_online_simple() -> bool:
    # 兜底通用：只要能访问百度 200 或某 204 端点 204 即认为在线
    urls = [
        "http://www.gstatic.com/generate_204",
        "http://connectivitycheck.gstatic.com/generate_204",
        "http://connect.rom.miui.com/generate_204",
        "http://www.baidu.com",
    ]
    headers = {"User-Agent": USER_AGENT, "Cache-Control": "no-cache", "Pragma": "no-cache"}
    for u in urls:
        try:
            r = requests.get(f"{u}?_t={int(time.time()*1000)}", timeout=2, allow_redirects=False, headers=headers)
            if r.status_code in (204, 200):
                if r.status_code == 204: return True
                if "baidu.com" in u: return True
        except Exception:
            pass
    return False

# 统一网络状态裁决顺序
def check_network_state(cfg: dict) -> str:
    """
    返回：online | captive | offline
    裁决优先级：
    1) 网关明确 captive（302/meta/JS/最终URL） => captive
    2) 严格探测：若被导回门户 => captive
    3) DNS 劫持：随机 .invalid 被解析 => captive
    4) 网关可达且 严格探测 ok==0 且 (errors+mismatches)>=2 => captive
    5) 严格探测 ok>=1 => online
    6) 兜底：通用连通性 => online，否则
    7) 网关不可达 => offline；否则 captive
    """
    st, _ = portal_redirection_state(cfg)         # captive | logged_in | unknown
    strict = strict_external_probe(cfg)
    dnsx = dns_invalid_resolves_quick()
    gw_ok = gateway_reachable(cfg)

    if st == "captive":
        return "captive"
    if strict["redirects"] >= 1:
        return "captive"
    if dnsx["resolved"]:
        if cfg.get("verbose_probe_log", False):
            log_write("[DNSX] 随机 .invalid 被解析为 IP（疑似DNS劫持），判定 captive")
        return "captive"
    if gw_ok and strict["ok"] == 0 and (strict["errors"] + strict["mismatches"]) >= 2:
        return "captive"
    if strict["ok"] >= 1:
        return "online"
    if is_online_simple():
        return "online"
    return "offline" if not gw_ok else "captive"

# ----------------------------
# 登录/注销（以网络状态为裁决）
# ----------------------------
def portal_login(cfg: dict) -> (bool, str, str):
    username = cfg.get("username", "").strip()
    network_type = cfg.get("network_type", "1")
    password_enc = cfg.get("password_enc", "")
    password = dpapi_decrypt_compat(password_enc) if password_enc else ""

    if not username or not password:
        return False, "E_NO_CRED", "未配置账号或密码"

    suffix = {
        "2": "@cmcc&user_password=",
        "3": "@telecom&user_password=",
        "4": "@unicom&user_password="
    }.get(network_type, "&user_password=")

    head = (cfg.get("portal_base") or DEFAULT_PORTAL_BASE).rstrip("/") + "/?c=Portal&a=login&callback=&login_method=1&user_account="
    url = head + requests.utils.quote(username) + suffix + requests.utils.quote(password)

    try:
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        r = requests.post(url, timeout=8, headers=headers)
        text = (r.text or "").strip()
        if not text and r.content:
            try:
                text = r.content.decode("utf-8", errors="ignore")
            except Exception:
                try:
                    text = r.content.decode("gbk", errors="ignore")
                except Exception:
                    text = ""

        def looks_success(t: str) -> bool:
            tt = (t or "").lower()
            pats = [
                r"success\s*[:=]\s*['\"]?\s*true\s*['\"]?",
                r"result\s*[:=]\s*['\"]?\s*1\s*['\"]?",
                r"code\s*[:=]\s*['\"]?\s*0\s*['\"]?",
                r"error\s*[:=]\s*['\"]?\s*0\s*['\"]?",
                r"login_ok",
                r"已连接|已登录|认证成功|登录成功|上网已开通",
                r"\bok\b",
                r"success",
            ]
            for p in pats:
                if re.search(p, tt, re.I):
                    return True
            return False

        if r.status_code == 200 and looks_success(text):
            return True, "OK", "登录成功"

        # 最终裁决：用网络状态决定；如不确定，短延迟后复检一次
        net = check_network_state(cfg)
        if net == "online":
            return True, "OK_ONLINE", "登录成功（连通性通过）"
        elif net == "captive":
            time.sleep(0.7)
            net2 = check_network_state(cfg)
            if net2 == "online":
                return True, "OK_ONLINE_FINAL", "登录成功（复检通过）"
            msg = ""
            try:
                m = re.search(r"msg\s*[:=]\s*['\"]([^'\"]+)['\"]", text)
                if m: msg = m.group(1)
            except Exception:
                pass
            if not msg:
                if "password" in text.lower() or "密码" in text:
                    return False, "E_BAD_PASS", "账号或密码错误"
                if "limit" in text.lower() or "并发" in text or "数量" in text:
                    return False, "E_LIMIT", "在线设备达到上限"
            return False, "E_CAPTIVE", msg or "仍处于门户拦截，需认证"
        else:
            return False, "E_OFFLINE", "网络离线，无法完成认证"

    except requests.Timeout:
        return False, "E_TIMEOUT", "登录请求超时"
    except Exception as e:
        return False, "E_REQUEST", f"登录请求失败: {e}"

def portal_logout(cfg: dict) -> (bool, str):
    try:
        base = (cfg.get("portal_base") or DEFAULT_PORTAL_BASE).rstrip("/")
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        _ = requests.post(base + "/?c=Portal&a=logout", timeout=8, headers=headers)
        # 注销后以网络状态说明现状
        net = check_network_state(cfg)
        if net == "captive":
            return True, "✅ 已注销（检测到门户拦截）"
        elif net == "online":
            return True, "⚠️ 注销请求已发出，但网络仍可用（网关可能延迟收敛/白名单）"
        else:
            return True, "✅ 已注销（当前离线）"
    except Exception as e:
        return False, f"注销失败: {e}"

# ----------------------------
# 高级材质（Acrylic/Blur）+ 圆角遮罩
# ----------------------------
def abgr(alpha, r, g, b) -> int:
    return ((alpha & 0xFF) << 24) | ((b & 0xFF) << 16) | ((g & 0xFF) << 8) | (r & 0xFF)

SKY_BLUE = (215, 240, 255)  # 更通透的天空蓝
SKY_ALPHA = 0xCC            # 更透明
SKY_ABGR = abgr(SKY_ALPHA, *SKY_BLUE)

def apply_acrylic_or_blur(hwnd, gradient_abgr: int = SKY_ABGR):
    if not sys.platform.startswith("win"):
        return
    try:
        from ctypes import wintypes as wt
        DWMWA_SYSTEMBACKDROP_TYPE = 38  # 3 = Acrylic
        DWMSBT_TRANSIENTWINDOW = 3
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wt.HWND(hwnd),
            ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
            ctypes.byref(ctypes.c_int(DWMSBT_TRANSIENTWINDOW)),
            ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass
    try:
        from ctypes import wintypes as wt
        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]
        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]
        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        ACCENT_ENABLE_BLURBEHIND = 3
        WCA_ACCENT_POLICY = 19

        accent = ACCENTPOLICY()
        accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.GradientColor = ctypes.c_uint(gradient_abgr)
        accent.AccentFlags = 2
        accent.AnimationId = 0

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.addressof(accent)

        ok = ctypes.windll.user32.SetWindowCompositionAttribute(wt.HWND(hwnd), ctypes.byref(data))
        if ok == 0:
            accent.AccentState = ACCENT_ENABLE_BLURBEHIND
            ctypes.windll.user32.SetWindowCompositionAttribute(wt.HWND(hwnd), ctypes.byref(data))
    except Exception:
        pass

def enable_round_corners(hwnd):
    if not sys.platform.startswith("win"):
        return
    try:
        from ctypes import wintypes as wt
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wt.HWND(hwnd),
            ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
            ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass

# ----------------------------
# 通知（托盘消息 + 冷却）
# ----------------------------
class Notifier(QObject):
    def __init__(self, tray: QSystemTrayIcon, level: str):
        super().__init__()
        self.tray = tray
        self.level = level
        self.last = datetime.min
        self.cooldown = timedelta(seconds=NOTIFY_COOLDOWN)

    def should(self) -> bool:
        return self.level != "off"

    def _cool_ok(self) -> bool:
        return datetime.now() - self.last >= self.cooldown

    def notify(self, title: str, message: str, important=False):
        if not self.should(): return
        if self.level == "important" and not important: return
        if not self._cool_ok() and not important: return
        self.last = datetime.now()
        try:
            if self.tray and self.tray.isVisible():
                self.tray.showMessage(title, message, QSystemTrayIcon.Information, 5000)
            else:
                ps = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$Template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$Xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($Template)
($Xml.GetElementsByTagName("text"))[0].AppendChild($Xml.CreateTextNode("{title}")) > $null
($Xml.GetElementsByTagName("text"))[1].AppendChild($Xml.CreateTextNode("{message}")) > $null
$Toast = [Windows.UI.Notifications.ToastNotification]::new($Xml)
$Notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{APP_NAME}")
$Notifier.Show($Toast)
'''
                subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

# ----------------------------
# 后台监控（QThread + 指数退避 + 抖动 + 去抖）
# ----------------------------
def with_jitter(base: int, ratio: float = BACKOFF_JITTER_RATIO) -> int:
    if base <= 1: return base
    delta = int(base * ratio)
    return max(1, base + random.randint(-delta, delta))

class MonitorWorker(QObject):
    status = Signal(str)
    log = Signal(str)
    notify = Signal(str, str, bool)

    def __init__(self, cfg_getter):
        super().__init__()
        self._get_cfg = cfg_getter
        self._active = False
        self._paused = False
        self._cur_interval = BASE_CHECK_INTERVAL
        self._last_state = None
        self._pending_state = None
        self._confirm_count = 0
        self._last_change = datetime.min
        self._last_heartbeat = datetime.min

    def start(self):
        self._active = True

    def stop(self):
        self._active = False

    def pause(self):
        self._paused = True
        self.status.emit("监控已暂停")
        self.log.emit("监控已暂停")

    def resume(self):
        self._paused = False
        self.status.emit("监控已恢复")
        self.log.emit("监控已恢复")

    def _confirm_and_get_state(self, raw_state: str) -> str:
        threshold = 1
        if self._last_state == "online" and raw_state in ("captive", "offline"):
            threshold = STATE_CONFIRM_ONLINE_TO_OTHER
        elif (self._last_state in ("captive", "offline")) and raw_state == "online":
            threshold = STATE_CONFIRM_OTHER_TO_ONLINE
        else:
            threshold = 1

        if raw_state != self._last_state:
            if raw_state == self._pending_state:
                self._confirm_count += 1
            else:
                self._pending_state = raw_state
                self._confirm_count = 1
            if self._confirm_count >= threshold:
                self._last_state = raw_state
                self._pending_state = None
                self._confirm_count = 0
        return self._last_state or raw_state

    def run(self):
        self.start()
        while self._active:
            if self._paused:
                time.sleep(1)
                continue
            cfg = self._get_cfg()
            if cfg.get("only_on_campus", True) and not is_campus_env(cfg):
                self.status.emit("非校园网络，监控休眠")
                self._cur_interval = MAX_CHECK_INTERVAL
                time.sleep(10)
                continue
            try:
                raw_state = check_network_state(cfg)
                state = self._confirm_and_get_state(raw_state)
                now = datetime.now()

                if state == "online":
                    if self._last_change == datetime.min or self._last_state != "online":
                        self.status.emit("网络正常 ✅")
                        self.log.emit("网络在线（网关+严格探测通过）")
                        self.notify.emit(APP_NAME, "网络在线 ✅", False)
                        self._last_change = now
                        self._last_heartbeat = now
                    if (now - self._last_heartbeat).total_seconds() >= ONLINE_HEARTBEAT_SECS:
                        self.log.emit("在线心跳（监控运行中）")
                        self._last_heartbeat = now
                    self._cur_interval = with_jitter(BASE_CHECK_INTERVAL)
                    if (now - self._last_change).total_seconds() > NETWORK_STABLE_GRACE:
                        self._cur_interval = min(60, with_jitter(self._cur_interval * 2))
                else:
                    if state == "captive":
                        if self._last_state != "captive":
                            self.status.emit("检测到门户拦截，尝试认证…")
                            self.log.emit("门户拦截（captive），尝试自动认证")
                            self.notify.emit(APP_NAME, "检测到门户拦截，自动登录中…", False)
                    else:
                        if self._last_state != "offline":
                            self.status.emit("网络离线，尝试认证…")
                            self.log.emit("网络离线（offline），尝试自动认证")
                            self.notify.emit(APP_NAME, "网络离线，尝试自动重连…", False)

                    ok, code, msg = portal_login(cfg)
                    if ok:
                        self.status.emit("自动登录成功 ✅")
                        self.log.emit(f"自动登录成功（{code}）")
                        self.notify.emit(APP_NAME, "自动登录成功 ✅", False)
                        self._cur_interval = with_jitter(BASE_CHECK_INTERVAL)
                        self._last_change = now
                    else:
                        self.status.emit(f"自动登录失败: {msg} ({code})")
                        self.log.emit(f"自动登录失败: {msg} ({code})")
                        self.notify.emit(APP_NAME, f"自动登录失败: {msg}", True)
                        self._cur_interval = min(MAX_CHECK_INTERVAL, max(with_jitter(self._cur_interval * 2), BASE_CHECK_INTERVAL))

                time.sleep(self._cur_interval)
            except Exception as e:
                self.log.emit(f"监控出错: {e}")
                time.sleep(min(with_jitter(self._cur_interval * 2), MAX_CHECK_INTERVAL))

# ----------------------------
# 自定义标题栏（无边框窗口控制）
# ----------------------------
class TitleBar(QFrame):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._mouse_pos = QPoint()
        self.setFixedHeight(42)
        self.setStyleSheet("""
#TitleBar {
  background: rgba(215, 240, 255, 90);
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
}
QPushButton#tb {
  background: rgba(255,255,255,200);
  border: 1px solid rgba(0,0,0,0.06);
  padding: 5px 10px;
  border-radius: 8px;
  color: #1A1A1A;
}
QPushButton#tb:hover {
  background: rgba(255,255,255,235);
}
QLabel { color: #103654; }
""")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)
        icon_label = QLabel("🌤️")
        icon_label.setFixedWidth(28)
        icon_label.setAlignment(Qt.AlignCenter)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:15px; font-weight:600;")
        lay.addWidget(icon_label)
        lay.addWidget(title_label)
        lay.addStretch(1)
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("tb")
        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("tb")
        self.btn_min.setFixedWidth(36)
        self.btn_close.setFixedWidth(36)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_close)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._mouse_pos = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._mouse_pos)
            e.accept()

# ----------------------------
# 主窗口（一体式淡蓝毛玻璃 + 深色文本）
# ----------------------------
class MainWindow(QMainWindow):
    RADIUS = 16

    def __init__(self, auto_mode=False, start_silent=False):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(860, 620)
        self.setMinimumSize(720, 480)

        # 无边框 + 透明绘制
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.auto_mode = auto_mode

        # 数据
        self.cfg = load_settings()
        # 首次迁移旧版凭据（若存在）
        self.cfg = try_migrate_from_v2(self.cfg)
        if self.cfg.get("run_on_startup", True) != check_startup_enabled():
            set_startup(self.cfg.get("run_on_startup", True))

        # 外层布局（留边用于圆角阴影）
        container = QWidget(self)
        cont_layout = QVBoxLayout(container)
        cont_layout.setContentsMargins(12, 12, 12, 12)

        # 自定义标题栏
        self.titlebar = TitleBar(self, f"{APP_NAME} v{APP_VERSION}")
        self.titlebar.btn_min.clicked.connect(self.showMinimized)
        self.titlebar.btn_close.clicked.connect(self.quit_app)
        cont_layout.addWidget(self.titlebar)

        # 一体式“天蓝毛玻璃”主体
        self.chrome = QFrame(self)
        self.chrome.setObjectName("Chrome")
        self.chrome.setStyleSheet("""
#Chrome {
  background: rgba(215, 240, 255, 120); /* 一体式天空淡蓝半透明，更“淡” */
  border-bottom-left-radius: 16px;
  border-bottom-right-radius: 16px;
}
#Chrome QLabel { color: #111; font-size: 14px; }
#Chrome QCheckBox, #Chrome QRadioButton { color: #111; font-size: 14px; }
#Chrome QGroupBox {
  color: #0F2F4A;
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 10px;
  margin-top: 12px;
}
#Chrome QGroupBox::title {
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 4px;
}
#Chrome QLineEdit, #Chrome QTextEdit {
  background: rgba(255,255,255,235);
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 8px;
  padding: 6px 8px;
  color: #111;
}
#Chrome QPushButton {
  background: #1E88E5;
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 8px 14px;
}
#Chrome QPushButton:hover { background: #1976D2; }
#Chrome QPushButton:disabled { background: #90CAF9; color: #f5f5f5; }
""")
        chrome_layout = QVBoxLayout(self.chrome)
        chrome_layout.setContentsMargins(20, 16, 20, 16)
        cont_layout.addWidget(self.chrome, 1)

        # 内容直接铺在 chrome 上
        title = QLabel("校园网登录设置", self.chrome)
        title.setStyleSheet("font-size: 20px; font-weight: 600; color:#0F2F4A;")
        chrome_layout.addWidget(title)

        # 账号行
        row_user = QHBoxLayout()
        row_user.addWidget(QLabel("账号:", self.chrome))
        self.ed_user = QLineEdit(self.cfg.get("username", ""), self.chrome)
        self.ed_user.setPlaceholderText("输入校园网账号")
        row_user.addWidget(self.ed_user, 1)
        chrome_layout.addLayout(row_user)

        # 密码行
        row_pass = QHBoxLayout()
        row_pass.addWidget(QLabel("密码:", self.chrome))
        self.ed_pass = QLineEdit("", self.chrome)
        self.ed_pass.setEchoMode(QLineEdit.Password)
        self.ed_pass.setPlaceholderText("输入密码（留空不修改）")
        row_pass.addWidget(self.ed_pass, 1)
        chrome_layout.addLayout(row_pass)

        # 网络类型
        gb_type = QGroupBox("网络类型", self.chrome)
        hl_type = QHBoxLayout(gb_type)
        self.rb_type_1 = QRadioButton("校园网", gb_type)
        self.rb_type_2 = QRadioButton("移动", gb_type)
        self.rb_type_3 = QRadioButton("电信", gb_type)
        self.rb_type_4 = QRadioButton("联通", gb_type)
        for w in (self.rb_type_1, self.rb_type_2, self.rb_type_3, self.rb_type_4):
            hl_type.addWidget(w)
        t = self.cfg.get("network_type", "1")
        {"1": self.rb_type_1, "2": self.rb_type_2, "3": self.rb_type_3, "4": self.rb_type_4}.get(t, self.rb_type_1).setChecked(True)
        chrome_layout.addWidget(gb_type)

        # 选项
        gb_opt = QGroupBox("选项", self.chrome)
        vl_opt = QVBoxLayout(gb_opt)
        self.cb_startup = QCheckBox("开机自启动（静默）", gb_opt)
        self.cb_startup.setChecked(self.cfg.get("run_on_startup", True))
        self.cb_monitor = QCheckBox("启用后台自动重连", gb_opt)
        self.cb_monitor.setChecked(self.cfg.get("enable_monitoring", True))
        self.cb_verbose = QCheckBox("详细检测日志（排障用）", gb_opt)
        self.cb_verbose.setChecked(self.cfg.get("verbose_probe_log", False))
        hl_opt1 = QHBoxLayout()
        hl_opt1.addWidget(self.cb_startup)
        hl_opt1.addWidget(self.cb_monitor)
        hl_opt1.addWidget(self.cb_verbose)
        hl_opt1.addStretch(1)
        vl_opt.addLayout(hl_opt1)

        hl_opt2 = QHBoxLayout()
        hl_opt2.addWidget(QLabel("通知级别:", gb_opt))
        self.cb_notify = QComboBox(gb_opt)
        self.cb_notify.addItems(["off", "important", "all"])
        self.cb_notify.setCurrentText(self.cfg.get("notification_level", "important"))
        hl_opt2.addWidget(self.cb_notify)
        hl_opt2.addStretch(1)
        vl_opt.addLayout(hl_opt2)
        chrome_layout.addWidget(gb_opt)

        # 状态
        self.lb_status = QLabel("就绪", self.chrome)
        self.lb_status.setStyleSheet("color:#223;")
        chrome_layout.addWidget(self.lb_status)

        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("✓ 保存并登录", self.chrome)
        self.btn_logout = QPushButton("注销", self.chrome)
        self.btn_clear = QPushButton("清除账号", self.chrome)
        self.btn_tray = QPushButton("最小化到托盘", self.chrome)
        for b in (self.btn_save, self.btn_logout, self.btn_clear, self.btn_tray):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        chrome_layout.addLayout(btn_row)

        # 日志
        gb_log = QGroupBox("最近日志", self.chrome)
        vl_log = QVBoxLayout(gb_log)
        self.logview = QTextEdit(self.chrome)
        self.logview.setReadOnly(True)
        vl_log.addWidget(self.logview)
        chrome_layout.addWidget(gb_log, 1)

        self.setCentralWidget(container)

        # 托盘
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QApplication.style().standardIcon(QStyle.SP_ComputerIcon))
        tray_menu = QMenu()
        act_show = QAction("显示窗口", self, triggered=self.show_and_focus)
        act_pause = QAction("暂停监控", self)
        act_resume = QAction("继续监控", self)
        act_exit = QAction("退出", self, triggered=self.quit_app)
        tray_menu.addAction(act_show)
        tray_menu.addAction(act_pause)
        tray_menu.addAction(act_resume)
        tray_menu.addSeparator()
        tray_menu.addAction(act_exit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda r: (self.show_and_focus() if r == QSystemTrayIcon.Trigger else None))
        self.tray.setVisible(True)

        # 通知器
        self.notifier = Notifier(self.tray, self.cfg.get("notification_level", "important"))

        # 监控线程
        self.worker = MonitorWorker(lambda: self.cfg)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.set_status)
        self.worker.log.connect(self.append_log)
        self.worker.notify.connect(lambda t, m, imp: self.notifier.notify(t, m, imp))

        # 事件
        self.btn_save.clicked.connect(self.on_save_login)
        self.btn_logout.clicked.connect(self.on_logout)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_tray.clicked.connect(self.minimize_to_tray)
        act_pause.triggered.connect(self.worker.pause)
        act_resume.triggered.connect(self.worker.resume)

        # 应用 Acrylic + 圆角 + 形状遮罩
        QTimer.singleShot(100, self.apply_material)

        # 开机静默逻辑
        if start_silent or (auto_mode and self.cfg.get("enable_monitoring", True)):
            self.hide()

        if self.cfg.get("enable_monitoring", True):
            self.start_monitor()

        self.refresh_log()

    # 材质与形状
    def apply_material(self):
        hwnd = int(self.winId())
        apply_acrylic_or_blur(hwnd, SKY_ABGR)
        enable_round_corners(hwnd)
        self.update_mask()

    def update_mask(self):
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect.adjusted(1, 1, -1, -1), self.RADIUS, self.RADIUS)
        poly = path.toFillPolygon().toPolygon()
        region = QRegion(poly)
        self.setMask(region)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.update_mask()

    # 状态与日志
    def set_status(self, text: str):
        self.lb_status.setText(text)

    def refresh_log(self):
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    content = f.read()[-8000:]
                self.logview.setPlainText(content)
                self.logview.moveCursor(QTextCursor.End)
        except Exception:
            pass
        QTimer.singleShot(3000, self.refresh_log)

    def append_log(self, text: str):
        log_write(text)
        self.refresh_log()

    # 控制
    def start_monitor(self):
        if not self.thread.isRunning():
            self.thread.start()
            self.append_log("后台监控已启动")

    def stop_monitor(self):
        if self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait(1000)
            self.append_log("后台监控已停止")

    def minimize_to_tray(self):
        self.hide()
        self.notifier.notify(APP_NAME, "已最小化到托盘，在后台监控网络 ✅", False)

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # 交互
    def on_save_login(self):
        user = self.ed_user.text().strip()
        passwd_new = self.ed_pass.text()
        if not user and not passwd_new and not self.cfg.get("password_enc"):
            QMessageBox.information(self, "提示", "请输入账号和密码")
            return

        self.cfg["username"] = user
        if passwd_new:
            enc = dpapi_encrypt_user(passwd_new) or dpapi_encrypt_machine(passwd_new)
            if not enc:
                QMessageBox.critical(self, "错误", "密码加密失败，请重试")
                return
            self.cfg["password_enc"] = enc

        nt = "1"
        if self.rb_type_2.isChecked(): nt = "2"
        elif self.rb_type_3.isChecked(): nt = "3"
        elif self.rb_type_4.isChecked(): nt = "4"
        self.cfg["network_type"] = nt

        self.cfg["enable_monitoring"] = self.cb_monitor.isChecked()
        self.cfg["run_on_startup"] = self.cb_startup.isChecked()
        self.cfg["verbose_probe_log"] = self.cb_verbose.isChecked()
        self.cfg["only_on_campus"] = True
        self.cfg["notification_level"] = self.cb_notify.currentText()
        self.cfg["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        save_settings(self.cfg)
        set_startup(self.cfg.get("run_on_startup", True))
        self.notifier.level = self.cfg.get("notification_level", "important")

        self.set_status("正在登录…")
        self.btn_save.setEnabled(False)
        def task():
            ok, code, msg = portal_login(self.cfg)
            if ok:
                self.set_status("登录成功 ✅")
                self.notifier.notify(APP_NAME, "登录成功 ✅", False)
                log_write(f"手动登录成功（{code}）")
                if self.cfg.get("enable_monitoring", True):
                    self.worker.resume()
                    self.start_monitor()
                else:
                    self.worker.pause()
            else:
                self.set_status(f"登录失败: {msg} ({code})")
                self.notifier.notify(APP_NAME, f"登录失败: {msg}", True)
                log_write(f"手动登录失败: {msg} ({code})")
            self.btn_save.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()

    def on_logout(self):
        self.set_status("正在注销…")
        def task():
            ok, msg = portal_logout(self.cfg)
            self.set_status(msg)
            log_write(msg)
        threading.Thread(target=task, daemon=True).start()

    def on_clear(self):
        if QMessageBox.question(self, "确认", "确定清除保存的账号信息吗？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.cfg["username"] = ""
            self.cfg["password_enc"] = ""
            save_settings(self.cfg)
            self.ed_user.setText("")
            self.ed_pass.setText("")
            self.set_status("已清除账号信息 ✅")
            log_write("账号信息已清除")

    def closeEvent(self, e):
        if self.cfg.get("enable_monitoring", True):
            e.ignore()
            self.minimize_to_tray()
        else:
            e.accept()

    def quit_app(self):
        try: self.stop_monitor()
        except Exception: pass
        try: self.tray.hide()
        except Exception: pass
        QApplication.quit()

# ----------------------------
# 入口
# ----------------------------
def is_auto_mode(): return "--auto" in sys.argv
def hide_console():
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

def main():
    ensure_dirs()
    inst = SingleInstance(SINGLE_INSTANCE_MUTEX)
    if not inst.acquire():
        sys.exit(0)

    signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))

    cfg = load_settings()
    # 自动模式：错峰启动抖动（基于用户名哈希）
    startup_delay = 0
    if is_auto_mode():
        seed = (cfg.get("username") or str(time.time())).encode("utf-8")
        h = int(hashlib.sha1(seed).hexdigest()[:6], 16)
        startup_delay = h % (STARTUP_JITTER_MAX + 1)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if is_auto_mode():
        hide_console()
        if startup_delay:
            time.sleep(startup_delay)
        if not cfg.get("username") or not cfg.get("password_enc"):
            log_write("自动模式：未找到账号信息，退出")
            inst.release(); sys.exit(0)
        if cfg.get("only_on_campus", True) and not is_campus_env(cfg):
            log_write("自动模式：非校园网络环境，静默退出")
            inst.release(); sys.exit(0)
        win = MainWindow(auto_mode=True, start_silent=True)
        if not cfg.get("enable_monitoring", True):
            ok, code, msg = portal_login(cfg)
            if ok:
                log_write(f"自动登录成功（无监控） ✅（{code}）")
            else:
                log_write(f"自动登录失败（无监控）: {msg} ({code})")
        sys.exit(app.exec())

    win = MainWindow(auto_mode=False, start_silent=False)
    win.show()
    try:
        sys.exit(app.exec())
    finally:
        inst.release()

if __name__ == "__main__":
    main()