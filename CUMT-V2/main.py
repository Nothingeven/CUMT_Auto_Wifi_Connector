import tkinter as tk
from tkinter import messagebox
import json, os, requests, threading, sys, time, subprocess
from datetime import datetime
import ctypes

# 基本配置
APP_NAME = "校园网自动登录工具"
APP_VERSION = "2.0.0    By NothingEven and Claude" 
DATA_DIR = "D:\\CampusLoginData"
CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials.json")
LOG_FILE = os.path.join(DATA_DIR, "login_log.txt")
MONITORING_INTERVAL = 30  # 秒

# 确保数据目录存在
if not os.path.exists(DATA_DIR):
    try: os.makedirs(DATA_DIR)
    except: pass

# 日志和通知功能
def log_message(message):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        print(message)
    except: pass

def show_notification(title, message):
    try:
        ps_cmd = f'powershell -command "& {{Add-Type -AssemblyName System.Windows.Forms; ' \
                 f'[System.Windows.Forms.MessageBox]::Show(\'{message}\', \'{title}\')}}"'
        subprocess.Popen(ps_cmd, shell=True)
    except: pass

# 工具函数
def is_auto_mode(): return "--auto" in sys.argv
def hide_console(): 
    try: ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except: pass
def show_console(): 
    try: ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)
    except: pass
# 凭证管理
def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_credentials(username, password, network_type, enable_monitoring):
    try:
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "username": username, "password": password, 
                "network_type": network_type, "enable_monitoring": enable_monitoring,
                "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, f)
        return True
    except: return False

# 开机自启动管理
def set_startup(enable=True):
    try:
        startup_folder = os.path.join(os.environ["APPDATA"], 
                                    r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
        
        if enable:
            ps_cmd = f'''
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]}"
            $Shortcut.Arguments = "--auto"
            $Shortcut.Save()
            '''
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        elif os.path.exists(shortcut_path):
            os.remove(shortcut_path)
        return True
    except: return False

def check_startup_enabled():
    shortcut_path = os.path.join(os.environ["APPDATA"], 
                               r"Microsoft\Windows\Start Menu\Programs\Startup",
                               f"{APP_NAME}.lnk")
    return os.path.exists(shortcut_path)

# 网络连接功能
def check_internet():
    try:
        # 针对Windows系统，使用静默方式执行ping命令
        if sys.platform.startswith('win'):
            # 使用CREATE_NO_WINDOW标志避免显示控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", "www.baidu.com"],
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # 针对Linux/Mac系统，重定向输出到/dev/null
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", "www.baidu.com"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
        
        # 如果返回码为0，说明ping成功
        return result.returncode == 0
        
    except Exception as e:
        log_message(f"网络检测出错: {str(e)}")
        return False

def campus_login(credentials):
    if not credentials: return False
    
    username = credentials.get("username", "")
    password = credentials.get("password", "")
    network_type = credentials.get("network_type", "1")
    
    if not username or not password: return False
    
    log_message(f"尝试登录 (用户: {username})")
    
    # 构建登录URL
    head = "http://10.2.5.251:801/eportal/?c=Portal&a=login&callback=&login_method=1&user_account="
    
    if network_type == '2': suffix = "@cmcc&user_password="
    elif network_type == '3': suffix = "@telecom&user_password="
    elif network_type == '4': suffix = "@unicom&user_password="
    else: suffix = "&user_password="
    
    try:
        response = requests.post(head + username + suffix + password, timeout=5)
        success = response.status_code == 200
        log_message("登录" + ("成功" if success else "失败"))
        return success
    except:
        log_message("登录请求发送失败")
        return False

def campus_logout():
    try:
        response = requests.post("http://10.2.5.251:801/eportal/?c=Portal&a=logout", timeout=5)
        return response.status_code == 200
    except: return False
# 系统托盘实现
class SimpleTray:
    def __init__(self, app):
        self.app = app
        self.create_tray()
        
    def create_tray(self):
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw
            
            # 创建简单图标
            image = Image.new('RGB', (64, 64), color=(52, 152, 219))
            draw = ImageDraw.Draw(image)
            draw.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
            
            # 菜单项和回调
            def on_show_window(icon, item):
                self.app.deiconify()
                self.app.lift()
                self.app.focus_force()
                
            def on_exit(icon, item):
                icon.stop()
                self.app.destroy()
            
            # 创建菜单
            menu = Menu(
                MenuItem('显示主窗口', on_show_window),
                MenuItem('退出程序', on_exit)
            )
            
            # 创建托盘图标
            self.icon = Icon("campus_login", image, "校园网登录工具", menu)
            threading.Thread(target=self.icon.run, daemon=True).start()
            return True
        except Exception as e:
            log_message(f"创建系统托盘图标失败: {str(e)}")
            return False
            
    def stop(self):
        try:
            if hasattr(self, 'icon'):
                self.icon.stop()
        except: pass

# 后台监控
class BackgroundMonitor:
    def __init__(self):
        self.active = False
        self.thread = None
        
    def start(self):
        if not self.active:
            self.active = True
            self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.thread.start()
            log_message("后台网络监控已启动")
    
    def stop(self):
        self.active = False
        log_message("后台网络监控已停止")
    
# 更新日期和用户信息
CURRENT_DATE = "2025-03-03 13:27:03"
CURRENT_USER = "Nothingeven"

# 更新的BackgroundMonitor类
class BackgroundMonitor:
    def __init__(self):
        self.active = False
        self.thread = None
        self.notification_shown = False  # 跟踪是否已显示通知
        
    def start(self):
        if not self.active:
            self.active = True
            self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.thread.start()
            log_message("后台网络监控已启动")
    
    def stop(self):
        self.active = False
        log_message("后台网络监控已停止")
    
    def monitor_loop(self):
        while self.active:
            time.sleep(5)
            try:
                if check_internet():
                    # 网络连接正常，重置通知标志
                    if self.notification_shown:
                        log_message("网络连接已恢复")
                        self.notification_shown = False
                else:
                    log_message("检测到网络断开，尝试重新连接")
                    success = campus_login(load_credentials())
                    
                    if success:
                        log_message("自动重连成功")
                        self.notification_shown = False  # 重连成功，重置通知标志
                    else:
                        log_message("自动重连失败")
                        # 只有在尚未显示通知时才显示
                        if not self.notification_shown:
                            show_notification(APP_NAME, "校园网断开，自动重连失败，请手动连接")
                            self.notification_shown = True  # 标记已显示通知
            except Exception as e:
                log_message(f"监控过程出错: {str(e)}")
                
            time.sleep(MONITORING_INTERVAL)
# UI界面类
class CampusNetLoginUI(tk.Tk):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("700x540")
        self.configure(bg="#f0f0f0")
        
        # 状态变量
        self.credentials = load_credentials()
        self.monitoring_active = False
        self.monitor = BackgroundMonitor()
        self.tray_icon = None
        
        # 创建UI
        self.create_widgets()
        self.center_window()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 如果需要最小化启动
        if start_minimized:
            self.create_tray_icon()
            self.withdraw()
            
        # 启动监控(如果启用)
        if self.credentials.get("enable_monitoring", False):
            self.start_monitoring()
    
    def center_window(self):
        self.update_idletasks()
        width, height = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_widgets(self):
        # 主内容区
        main_frame = tk.Frame(self, bg="white", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        tk.Label(main_frame, text="校园网登录设置", bg="white", 
               fg="#333333", font=("", 16)).pack(pady=(0, 20))
        
        # 账号
        tk.Label(main_frame, text="账号:", bg="white", anchor="w").pack(fill=tk.X)
        self.username_var = tk.StringVar(value=self.credentials.get("username", ""))
        tk.Entry(main_frame, textvariable=self.username_var, width=30).pack(fill=tk.X, pady=(0, 10))
        
        # 密码
        tk.Label(main_frame, text="密码:", bg="white", anchor="w").pack(fill=tk.X)
        self.password_var = tk.StringVar(value=self.credentials.get("password", ""))
        tk.Entry(main_frame, textvariable=self.password_var, show="●", width=30).pack(fill=tk.X, pady=(0, 10))
        
        # 网络类型
        tk.Label(main_frame, text="网络类型:", bg="white", anchor="w").pack(fill=tk.X)
        
        net_frame = tk.Frame(main_frame, bg="white")
        net_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.network_type = tk.StringVar(value=self.credentials.get("network_type", "1"))
        networks = [("校园网", "1"), ("移动", "2"), ("电信", "3"), ("联通", "4")]
        
        for i, (text, value) in enumerate(networks):
            tk.Radiobutton(net_frame, text=text, value=value, variable=self.network_type,
                         bg="white").pack(side=tk.LEFT, padx=5)
        
        # 选项区域
        options_frame = tk.LabelFrame(main_frame, text="选项", bg="white", padx=10, pady=10)
        options_frame.pack(fill=tk.X, pady=10)
        
        self.startup_var = tk.BooleanVar(value=check_startup_enabled())
        tk.Checkbutton(options_frame, text="开机自动登录", variable=self.startup_var,
                     bg="white").pack(anchor="w")
        
        self.monitoring_var = tk.BooleanVar(value=self.credentials.get("enable_monitoring", False))
        tk.Checkbutton(options_frame, text="启用自动重连", variable=self.monitoring_var,
                     bg="white").pack(anchor="w")
                     
        self.silent_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="关闭窗口时最小化到托盘", variable=self.silent_var,
                     bg="white").pack(anchor="w")
        
        # 状态区域
        self.status_var = tk.StringVar(value="就绪")
        status = tk.Label(main_frame, textvariable=self.status_var, bg="white", fg="#555555")
        status.pack(fill=tk.X, pady=10)
        
        # 按钮区域
        btn_frame = tk.Frame(main_frame, bg="white")
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.login_btn = tk.Button(btn_frame, text="保存并登录", bg="#4CAF50", fg="white",
                               command=self.save_and_login)
        self.login_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="注销", bg="#FF9800", fg="white",
                command=self.logout).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="清除", bg="#F44336", fg="white",
                command=self.clear_credentials).pack(side=tk.LEFT, padx=5)
        
        tray_btn = tk.Button(btn_frame, text="隐藏到托盘", bg="#2196F3", fg="white",
                          command=self.minimize_to_tray)
        tray_btn.pack(side=tk.RIGHT, padx=5)
        
    
    def create_tray_icon(self):
        if not self.tray_icon:
            self.tray_icon = SimpleTray(self)
    
    def minimize_to_tray(self):
        self.create_tray_icon()
        self.withdraw()  # 隐藏窗口
        if self.monitoring_var.get() and not self.monitoring_active:
            self.start_monitoring()
        show_notification(APP_NAME, "程序已最小化到系统托盘，将在后台监控网络")
    
    def save_and_login(self):
        username = self.username_var.get()
        password = self.password_var.get()
        network_type = self.network_type.get()
        enable_monitoring = self.monitoring_var.get()
        
        if not username or not password:
            messagebox.showerror("错误", "请输入账号和密码")
            return
        
        self.login_btn.config(state="disabled", text="登录中...")
        self.status_var.set("正在登录...")
        self.update()
        
        # 保存设置
        save_credentials(username, password, network_type, enable_monitoring)
        set_startup(self.startup_var.get())
        
        # 执行登录
        def do_login():
            credentials = {
                "username": username,
                "password": password,
                "network_type": network_type
            }
            success = campus_login(credentials)
            
            if success:
                self.after(0, lambda: self.status_var.set("登录成功!"))
                self.after(0, lambda: messagebox.showinfo("成功", "校园网已连接成功"))
                
                # 控制监控线程
                if enable_monitoring: 
                    self.start_monitoring()
                    # 询问是否最小化到托盘
                    if not is_auto_mode():
                        self.after(500, lambda: self.ask_minimize_to_tray())
                else: 
                    self.stop_monitoring()
                    if not is_auto_mode():
                        self.after(1500, self.destroy)
            else:
                self.after(0, lambda: self.status_var.set("登录失败"))
                self.after(0, lambda: messagebox.showerror("失败", "校园网连接失败"))
            
            self.after(0, lambda: self.login_btn.config(state="normal", text="保存并登录"))
        
        threading.Thread(target=do_login, daemon=True).start()
    
    def ask_minimize_to_tray(self):
        if self.monitoring_var.get():
            self.minimize_to_tray()
    
    def logout(self):
        self.status_var.set("正在注销...")
        threading.Thread(target=lambda: self.do_logout(), daemon=True).start()
    
    def do_logout(self):
        success = campus_logout()
        self.after(0, lambda: self.status_var.set("注销" + ("成功" if success else "失败")))
        self.after(0, lambda: messagebox.showinfo("注销", "校园网已断开连接" if success else "注销失败"))
    
    def clear_credentials(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                os.remove(CREDENTIALS_FILE)
                self.username_var.set("")
                self.password_var.set("")
                self.network_type.set("1")
                self.monitoring_var.set(False)
                self.status_var.set("已清除保存的信息")
                messagebox.showinfo("成功", "已清除账号信息")
            except:
                messagebox.showerror("错误", "清除信息失败")
        else:
            messagebox.showinfo("提示", "没有保存的账号信息")
    
    def start_monitoring(self):
        if not self.monitoring_active:
            self.monitor.start()
            self.monitoring_active = True
    
    def stop_monitoring(self):
        if self.monitoring_active:
            self.monitor.stop()
            self.monitoring_active = False
    
    def on_closing(self):
        if self.monitoring_active and self.silent_var.get():
            # 最小化到托盘而不是退出
            self.minimize_to_tray()
        else:
            if self.monitoring_active:
                if messagebox.askyesno("确认", "网络监控正在运行，确定要关闭吗？\n选择否将最小化到托盘"):
                    self.destroy()
                else:
                    self.minimize_to_tray()
            else:
                self.destroy()

# 主程序
def main():
    # 自动模式处理
    if is_auto_mode():
        hide_console()
        credentials = load_credentials()
        
        if credentials:
            success = campus_login(credentials)
            if success:
                log_message("自动登录成功")
                # 启动监控或退出
                if credentials.get("enable_monitoring", False):
                    app = CampusNetLoginUI(start_minimized=True)
                    app.mainloop()
                else:
                    show_notification(APP_NAME, "校园网已自动连接成功！")
            else:
                log_message("自动登录失败")
                show_notification(APP_NAME, "自动登录失败，请手动连接")
                app = CampusNetLoginUI()
                app.mainloop()
        else:
            log_message("未找到账号信息")
            show_notification(APP_NAME, "未找到保存的账号信息")
            app = CampusNetLoginUI()
            app.mainloop()
    else:
        # 手动模式
        app = CampusNetLoginUI()
        app.mainloop()

if __name__ == "__main__":
    main()