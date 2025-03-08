import os
import tempfile

# 当前日期和用户
CURRENT_DATE = "2025-03-15"
CURRENT_USER = "Nothingeven"

# 创建临时文件夹存放临时文件
temp_dir = tempfile.mkdtemp()
print(f"创建临时目录: {temp_dir}")

# 1. 创建简单的图标文件
icon_path="app_icon.ico"

# 2. 创建版本信息文件 - 使用UTF-8编码
version_file = os.path.join(temp_dir, "version_info.txt")
with open(version_file, "w", encoding="utf-8") as f:
    f.write("""
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 0, 0, 0),
    prodvers=(2, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'080404b0',
          [StringStruct(u'CompanyName', u'Nothingeven'),
           StringStruct(u'FileDescription', u'CUMT校园网自动登录助手 /Dear My Love C.K.'),
           StringStruct(u'FileVersion', u'2.0'),
           StringStruct(u'InternalName', u'CUMT_Auto_Wifi_Connector /Dear My Love C.K.'),
           StringStruct(u'LegalCopyright', u'(C) 2025 Nothingeven. 严禁用于商用，欢迎分享。 /Dear My Love C.K.'),
           StringStruct(u'OriginalFilename', u'CUMT校园网自动登录助手 v2.0.exe /Dear My Love C.K.'),
           StringStruct(u'ProductName', u'CUMT校园网自动登录助手 /Dear My Love C.K.'),
           StringStruct(u'ProductVersion', u'2.0'),
           StringStruct(u'Comments', u'CUMT校园网自动登录助手_v2.0.exe /Dear My Love C.K.')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
""")
print(f"创建版本信息文件: {version_file}")

# 3. 执行PyInstaller命令
source_file = "main.py"  # 替换为您的实际源文件名
cmd = f'pyinstaller --noconfirm --onefile --windowed --name "CUMT校园网自动登录助手 v2.0" --icon="{icon_path}" --version-file="{version_file}" "{source_file}"'

print("正在执行打包命令...")
print(cmd)
result = os.system(cmd)

# 4. 检查结果
if result == 0:
    print(f"\n✅ 打包成功! 输出文件: dist/校园网自动登录助手_v2.0.exe")
    print(f"📝 文件属性中已包含作者信息: {CURRENT_USER}")
    print(f"📝 版权声明: (C) 2025 {CURRENT_USER}. 严禁用于商用，欢迎分享。")
else:
    print(f"\n❌ 打包失败，错误代码: {result}")
    print("请确保已安装PyInstaller: pip install pyinstaller")
    print("并且源文件名称正确")

# 提醒查看属性
print("\n🔍 在Windows资源管理器中右键点击生成的EXE文件 -> 属性 -> 详细信息")
print("  可以看到作者、版权信息等设置")