import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import requests
import threading
import sys
import ctypes
import time
import subprocess
from datetime import datetime

# 当前时间和用户信息
CURRENT_DATE = "2025-03-01 10:15:23"
CURRENT_USER = "Nothingeven"

# 程序信息
APP_NAME = "校园网自动登录工具           开发者：Cos_Intel & Claude"
APP_VERSION = "1.0.0"
APP_AUTHORS = "Cos_Intel & Claude"

# 数据存储路径
DATA_DIR = "D:\\CampusLoginData"
CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials.json")
LOG_FILE = os.path.join(DATA_DIR, "login_log.txt")

# 确保数据目录存在
def ensure_data_directory():
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            log_message(f"已创建数据目录: {DATA_DIR}")
    except Exception as e:
        print(f"无法创建数据存储目录 {DATA_DIR}。将使用当前目录。错误信息: {str(e)}")
        return False
    return True

# 写入日志
def log_message(message):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        print(log_entry.strip())
    except Exception as e:
        print(f"写入日志失败: {str(e)}")

# 获取当前程序的可执行路径
def get_executable_path():
    """获取当前程序的可执行文件路径，适用于PyInstaller打包的程序"""
    if getattr(sys, 'frozen', False):
        # 如果是PyInstaller打包后的可执行文件
        return sys.executable
    else:
        # 如果是开发环境中的Python脚本
        try:
            import os.path
            return os.path.abspath(sys.argv[0])
        except:
            return sys.argv[0]

# 加载凭证
def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log_message(f"读取凭证失败: {str(e)}")
            return None
    return None

# 保存凭证
def save_credentials(username, password, network_type):
    credentials = {
        "username": username,
        "password": password,
        "network_type": network_type,
        "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(credentials, f)
        log_message("凭证已保存")
        return True
    except Exception as e:
        log_message(f"保存凭证失败: {str(e)}")
        return False

# 自动登录函数
def auto_login(credentials):
    if not credentials:
        log_message("没有找到保存的凭证，需要打开设置界面")
        return False
    
    username = credentials.get("username", "")
    password = credentials.get("password", "")
    network_type = credentials.get("network_type", "1")
    
    if not username or not password:
        log_message("凭证不完整，需要打开设置界面")
        return False
    
    log_message(f"尝试使用保存的凭证自动登录 (用户: {username})")
    
    # 构建登录URL
    head_ = "http://10.2.5.251:801/eportal/?c=Portal&a=login&callback=&login_method=1&user_account="
    
    network_names = {"1": "校园网", "2": "移动", "3": "电信", "4": "联通"}
    
    if network_type == '2':
        fit_ = "@cmcc&user_password="
    elif network_type == '3':
        fit_ = "@telecom&user_password="
    elif network_type == '4':
        fit_ = "@unicom&user_password="
    else:  # 默认为校园网
        fit_ = "&user_password="
    
    url = head_ + username + fit_ + password
    
    try:
        log_message("发送登录请求...")
        response = requests.post(url, timeout=10)
        
        if response.status_code == 200:
            log_message(f"登录成功! 已连接到{network_names.get(network_type, '未知网络')}")
            return True
        else:
            log_message(f"登录失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        log_message(f"登录出错: {str(e)}")
        return False

# 注销校园网登录
def logout():
    logout_url = "http://10.2.5.251:801/eportal/?c=Portal&a=logout"
    try:
        log_message("发送注销请求...")
        response = requests.post(logout_url, timeout=10)
        
        if response.status_code == 200:
            log_message("注销成功！已断开校园网连接")
            return True
        else:
            log_message(f"注销失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        log_message(f"注销出错: {str(e)}")
        return False

# 设置开机自动启动
def set_startup(enable=True):
    try:
        # 获取当前可执行文件路径
        executable_path = get_executable_path()
        
        # 获取启动文件夹路径
        startup_folder = os.path.join(
            os.environ["APPDATA"],
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
        
        if enable:
            # 创建带参数的快捷方式（添加--auto参数以指示自动登录模式）
            if not os.path.exists(shortcut_path) or True:  # 总是更新快捷方式，确保路径正确
                create_shortcut(executable_path, shortcut_path, params="--auto")
                log_message(f"已在启动文件夹中创建快捷方式: {shortcut_path}")
                log_message(f"目标: {executable_path} --auto")
            return True
        else:
            # 删除快捷方式
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                log_message(f"已从启动文件夹中删除快捷方式: {shortcut_path}")
            return True
    except Exception as e:
        log_message(f"设置启动文件夹失败: {str(e)}")
        return False

# 检查开机自启动状态
def check_startup_enabled():
    startup_folder = os.path.join(
        os.environ["APPDATA"],
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
    
    return os.path.exists(shortcut_path)

# 创建快捷方式
def create_shortcut(target, shortcut_path, params=""):
    try:
        # 使用PowerShell创建快捷方式
        powershell_command = f'''
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{target}"
        $Shortcut.Arguments = "{params}"
        $Shortcut.Save()
        '''
        
        # 执行PowerShell命令
        subprocess.run(["powershell", "-Command", powershell_command], 
                       capture_output=True, text=True, check=True)
        
        return True
    except Exception as e:
        log_message(f"创建快捷方式失败: {str(e)}")
        return False

# 隐藏控制台窗口
def hide_console():
    if sys.platform.startswith('win'):
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass

# 显示控制台窗口
def show_console():
    if sys.platform.startswith('win'):
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)
        except:
            pass

# UI界面类
class CampusNetLoginUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("680x650")  # 高度稍增以容纳作者信息
        self.configure(bg="#f0f0f0")
        self.minsize(680, 650)  # 最小尺寸也调整
        
        # 配置全局字体
        self.title_font = ("微软雅黑", 18)
        self.normal_font = ("微软雅黑", 13)
        self.button_font = ("微软雅黑", 13, "bold")
        
        # 读取凭证
        self.credentials = load_credentials() or {}
        
        # 创建界面
        self.create_widgets()
        
        # 设置窗口居中
        self.center_window()
        
    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def create_widgets(self):
        # 顶部标题
        title_frame = tk.Frame(self, bg="#f0f0f0", pady=20)
        title_frame.pack(fill=tk.X)
        
        title_label = tk.Label(
            title_frame, 
            text="校园网登录设置", 
            font=("微软雅黑", 24, "bold"),
            bg="#f0f0f0", 
            fg="#2c3e50"
        )
        title_label.pack()
        
        # 主内容区
        main_frame = tk.Frame(self, bg="#ffffff", padx=40, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=(0, 30))
        
        # 添加阴影效果（简单模拟）
        shadow_frame = tk.Frame(self, bg="#dddddd")
        shadow_frame.place(in_=main_frame, x=5, y=5, relwidth=1, relheight=1)
        main_frame.lift()
        
        # 账号框
        username_label = tk.Label(
            main_frame, 
            text="账号",
            font=self.normal_font, 
            bg="#ffffff", 
            anchor="w"
        )
        username_label.pack(fill=tk.X, pady=(0, 5))
        
        self.username_var = tk.StringVar(value=self.credentials.get("username", ""))
        self.username_entry = tk.Entry(
            main_frame, 
            textvariable=self.username_var,
            font=self.normal_font,
            bg="#f9f9f9",
            relief="solid",
            bd=1
        )
        self.username_entry.pack(fill=tk.X, ipady=8, pady=(0, 20))
        
        # 密码框
        password_label = tk.Label(
            main_frame, 
            text="密码", 
            font=self.normal_font, 
            bg="#ffffff", 
            anchor="w"
        )
        password_label.pack(fill=tk.X, pady=(0, 5))
        
        self.password_var = tk.StringVar(value=self.credentials.get("password", ""))
        self.password_entry = tk.Entry(
            main_frame, 
            textvariable=self.password_var,
            font=self.normal_font,
            show="●",
            bg="#f9f9f9",
            relief="solid",
            bd=1
        )
        self.password_entry.pack(fill=tk.X, ipady=8, pady=(0, 20))
        
        # 网络类型选择
        network_label = tk.Label(
            main_frame, 
            text="网络类型", 
            font=self.normal_font, 
            bg="#ffffff", 
            anchor="w"
        )
        network_label.pack(fill=tk.X, pady=(0, 10))
        
        # 网络类型框架
        network_frame = tk.Frame(main_frame, bg="#ffffff")
        network_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 网络类型单选按钮
        self.network_type = tk.StringVar(value=self.credentials.get("network_type", "1"))
        
        networks = [
            ("校园网", "1"), 
            ("移动", "2"), 
            ("电信", "3"), 
            ("联通", "4")
        ]
        
        for i, (text, value) in enumerate(networks):
            rb = tk.Radiobutton(
                network_frame,
                text=text,
                value=value,
                variable=self.network_type,
                font=self.normal_font,
                bg="#ffffff",
                activebackground="#f0f0f0",
                padx=15,
                pady=5
            )
            rb.grid(row=0, column=i, padx=10)
        
        # 开机自启动选项
        startup_frame = tk.Frame(main_frame, bg="#ffffff")
        startup_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.startup_var = tk.BooleanVar(value=check_startup_enabled())
        startup_check = tk.Checkbutton(
            startup_frame,
            text="开机自动启动（电脑开机后自动连接校园网）",
            variable=self.startup_var,
            font=self.normal_font,
            bg="#ffffff",
            activebackground="#ffffff"
        )
        startup_check.pack(side=tk.LEFT)
        
        # 数据存储信息标签
        info_frame = tk.Frame(main_frame, bg="#ffffff")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        info_label = tk.Label(
            info_frame,
            text=f"数据保存位置: {DATA_DIR}",
            font=("微软雅黑", 10),
            bg="#ffffff",
            fg="#888888"
        )
        info_label.pack(side=tk.LEFT)
        
        # 按钮区域
        button_frame = tk.Frame(main_frame, bg="#ffffff")
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # 保存并登录按钮
        self.save_login_button = tk.Button(
            button_frame,
            text="保存并登录",
            font=self.button_font,
            bg="#2980b9",
            fg="#ffffff",
            activebackground="#3498db",
            activeforeground="#ffffff",
            relief="flat",
            padx=20,
            pady=10,
            width=12,
            cursor="hand2",
            command=self.save_and_login
        )
        self.save_login_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 注销按钮
        self.logout_button = tk.Button(
            button_frame,
            text="注销登录",
            font=self.button_font,
            bg="#f39c12",
            fg="#ffffff",
            activebackground="#f1c40f",
            activeforeground="#ffffff",
            relief="flat",
            padx=20,
            pady=10,
            width=10,
            cursor="hand2",
            command=self.perform_logout
        )
        self.logout_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 清除按钮
        clear_button = tk.Button(
            button_frame,
            text="清除信息",
            font=self.button_font,
            bg="#e74c3c",
            fg="#ffffff",
            activebackground="#c0392b",
            activeforeground="#ffffff",
            relief="flat",
            padx=20,
            pady=10,
            width=10,
            cursor="hand2",
            command=self.clear_credentials
        )
        clear_button.pack(side=tk.LEFT)
        
        # 作者信息框
        author_frame = tk.Frame(main_frame, bg="#f9f9f9", relief="solid", bd=1)
        author_frame.pack(fill=tk.X, pady=(20, 0))
        
        author_label = tk.Label(
            author_frame,
            text=f"作者: {APP_AUTHORS}",
            font=("微软雅黑", 11),
            bg="#f9f9f9",
            fg="#2c3e50",
            padx=15,
            pady=8
        )
        author_label.pack(side=tk.LEFT)
        
        version_label = tk.Label(
            author_frame,
            text=f"版本: v{APP_VERSION}",
            font=("微软雅黑", 11),
            bg="#f9f9f9",
            fg="#2c3e50",
            padx=15,
            pady=8
        )
        version_label.pack(side=tk.RIGHT)
        
        # 状态栏
        status_frame = tk.Frame(self, bg="#f0f0f0")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_var = tk.StringVar(value="请输入或修改登录信息")
        status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("微软雅黑", 10),
            bg="#f0f0f0",
            fg="#555555"
        )
        status_label.pack(side=tk.LEFT, padx=40)
        
        # 用户信息
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            username = CURRENT_USER
        except:
            username = "Nothingeven"
        
        user_info = f"用户: {username} | 日期: {current_date}"
        user_label = tk.Label(
            status_frame,
            text=user_info,
            font=("微软雅黑", 10),
            bg="#f0f0f0",
            fg="#555555"
        )
        user_label.pack(side=tk.RIGHT, padx=40)
    
    def clear_credentials(self):
        """清除保存的凭证"""
        if os.path.exists(CREDENTIALS_FILE):
            try:
                os.remove(CREDENTIALS_FILE)
                self.username_var.set("")
                self.password_var.set("")
                self.network_type.set("1")
                self.status_var.set("已清除保存的账号信息")
                messagebox.showinfo("成功", "已清除保存的账号信息")
                log_message("用户已清除保存的账号信息")
            except Exception as e:
                error_msg = f"清除信息失败: {str(e)}"
                self.status_var.set(error_msg)
                messagebox.showerror("错误", error_msg)
                log_message(error_msg)
        else:
            self.status_var.set("没有找到保存的账号信息")
            messagebox.showinfo("提示", "没有找到保存的账号信息")

    def perform_logout(self):
        """执行注销操作"""
        self.logout_button.config(state=tk.DISABLED, text="正在注销...", bg="#95a5a6")
        self.status_var.set("正在注销校园网登录...")
        
        # 在新线程中执行注销
        threading.Thread(target=self._perform_logout, daemon=True).start()
    
    def _perform_logout(self):
        """实际执行注销的线程函数"""
        try:
            success = logout()
            
            if success:
                self.after(0, lambda: self.status_var.set("注销成功! 已断开校园网连接"))
                self.after(0, lambda: messagebox.showinfo("注销成功", "已成功断开校园网连接"))
            else:
                self.after(0, lambda: self.status_var.set("注销失败"))
                self.after(0, lambda: messagebox.showwarning("注销失败", "尝试断开校园网连接失败，可能您未登录或网络已断开"))
        except Exception as e:
            error_msg = f"注销出错: {str(e)}"
            self.after(0, lambda: self.status_var.set(error_msg))
            self.after(0, lambda: messagebox.showerror("注销错误", error_msg))
        
        # 恢复按钮状态
        self.after(0, lambda: self.logout_button.config(
            state=tk.NORMAL, 
            text="注销登录", 
            bg="#f39c12"
        ))
    
    def save_and_login(self):
        """保存设置并登录"""
        # 获取登录信息
        username = self.username_var.get()
        password = self.password_var.get()
        network_type = self.network_type.get()
        
        # 检查输入
        if not username or not password:
            self.status_var.set("错误: 用户名和密码不能为空")
            messagebox.showerror("输入错误", "用户名和密码不能为空")
            return
        
        # 禁用按钮并更改文字
        self.save_login_button.config(state=tk.DISABLED, text="正在登录...", bg="#95a5a6")
        self.status_var.set("保存设置并登录...")
        
        # 保存设置
        save_credentials(username, password, network_type)
        
        # 设置开机自启动
        set_startup(self.startup_var.get())
        
        # 在新线程中执行登录
        threading.Thread(target=self._perform_login, daemon=True).start()
    
    def _perform_login(self):
        """实际执行登录的线程函数"""
        username = self.username_var.get()
        password = self.password_var.get()
        network_type = self.network_type.get()
        
        # 构建登录URL
        head_ = "http://10.2.5.251:801/eportal/?c=Portal&a=login&callback=&login_method=1&user_account="
        
        network_names = {"1": "校园网", "2": "移动", "3": "电信", "4": "联通"}
        
        if network_type == '2':
            fit_ = "@cmcc&user_password="
        elif network_type == '3':
            fit_ = "@telecom&user_password="
        elif network_type == '4':
            fit_ = "@unicom&user_password="
        else:  # 默认为校园网
            fit_ = "&user_password="
        
        url = head_ + username + fit_ + password
        
        try:
            response = requests.post(url, timeout=10)
            
            if response.status_code == 200:
                success_msg = f"登录成功! 已连接到{network_names.get(network_type, '未知网络')}"
                log_message(success_msg)
                
                # 创建成功消息详情
                detail_msg = success_msg + "\n\n"
                if self.startup_var.get():
                    detail_msg += "• 电脑开机后将自动连接校园网"
                
                # 更新UI并关闭窗口
                self.after(0, lambda: self.status_var.set(success_msg))
                self.after(0, lambda: messagebox.showinfo("登录成功", detail_msg))
                self.after(1000, self.destroy)  # 1秒后关闭窗口
            else:
                error_msg = f"登录失败，状态码: {response.status_code}"
                log_message(error_msg)
                
                self.after(0, lambda: self.status_var.set(error_msg))
                self.after(0, lambda: messagebox.showerror("登录失败", error_msg))
                self.after(0, lambda: self.save_login_button.config(
                    state=tk.NORMAL, 
                    text="保存并登录", 
                    bg="#2980b9"
                ))
        except Exception as e:
            error_msg = f"连接错误: {str(e)}"
            log_message(error_msg)
            
            self.after(0, lambda: self.status_var.set(error_msg))
            self.after(0, lambda: messagebox.showerror("连接错误", error_msg))
            self.after(0, lambda: self.save_login_button.config(
                state=tk.NORMAL, 
                text="保存并登录", 
                bg="#2980b9"
            ))

def main():
    # 确保数据目录存在
    ensure_data_directory()
    
    # 检查命令行参数
    is_auto_mode = "--auto" in sys.argv
    
    # 记录启动方式和执行路径
    executable_path = get_executable_path()
    if is_auto_mode:
        log_message(f"系统自动启动模式 (路径: {executable_path})")
    else:
        log_message(f"手动启动模式 (路径: {executable_path})")
    
    # 加载凭证
    credentials = load_credentials()
    
    # 如果是自动模式且有凭证，尝试自动登录
    if is_auto_mode and credentials:
        hide_console()  # 隐藏控制台
        success = auto_login(credentials)
        if success:
            log_message("自动登录成功，程序将在3秒后退出")
            time.sleep(3)
            return
        else:
            log_message("自动登录失败，将显示UI设置界面")
            show_console()  # 登录失败时显示控制台
    
    # 显示UI界面
    show_console()  # 确保控制台可见（用于调试）
    app = CampusNetLoginUI()
    app.mainloop()

if __name__ == "__main__":
    main()