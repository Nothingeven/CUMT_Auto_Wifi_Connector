import os, sys, subprocess, urllib.request, tempfile
from pathlib import Path

APP_NAME = "CUMT_Auto_Wifi_Connector"
PYPI = "https://pypi.org/simple"
NEED_PY_MINOR = "3.12"

def sh(cmd, check=True, capture=False, cwd=None):
    print("> " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    if capture:
        return subprocess.check_output(cmd, text=True, cwd=cwd).strip()
    p = subprocess.run(cmd, cwd=cwd)
    if check and p.returncode != 0:
        raise SystemExit(f"命令失败（退出码 {p.returncode}）：{' '.join(map(str, cmd))}")
    return p.returncode

def find_python_minor(minor: str):
    try:
        exe = sh(["py", f"-{minor}", "-c", "import sys;print(sys.executable)"], capture=True)
        if exe and Path(exe).exists(): return Path(exe)
    except Exception:
        pass
    cands = [
        Path(os.environ.get("LOCALAPPDATA",""))/"Programs"/"Python"/f"Python{minor.replace('.','')}" / "python.exe",
        Path("C:/Program Files")/f"Python{minor.replace('.','')}" / "python.exe",
        Path(f"C:/Python{minor.replace('.','')}/python.exe"),
    ]
    for p in cands:
        if p.exists(): return p
    return None

def ensure_venv(base_py: Path, venv_dir: Path) -> Path:
    vpy = venv_dir/("Scripts" if os.name=="nt" else "bin")/("python.exe" if os.name=="nt" else "python3")
    if not vpy.exists():
        sh([str(base_py), "-m", "venv", str(venv_dir)])
    if not vpy.exists():
        raise SystemExit(f"创建虚拟环境失败：{vpy} 不存在")
    if sh([str(vpy), "-m", "pip", "--version"], check=False) != 0:
        sh([str(vpy), "-m", "ensurepip", "--upgrade"], check=False)
        if sh([str(vpy), "-m", "pip", "--version"], check=False) != 0:
            with tempfile.TemporaryDirectory() as td:
                gp = Path(td)/"get-pip.py"
                with urllib.request.urlopen("https://bootstrap.pypa.io/get-pip.py", timeout=60) as r, open(gp,"wb") as f:
                    f.write(r.read())
                sh([str(vpy), str(gp)])
    return vpy

def pip_install(py: Path, pkgs: list[str]):
    sh([str(py), "-m", "pip", "install", "--upgrade", "--no-cache-dir", "-i", PYPI, *pkgs])

def try_upx(exe: Path):
    try:
        sh(["upx", "-V"], check=False)
    except Exception:
        print("[提示] 未检测到 UPX（可选）。安装后体积可再降 10–30%。下载：https://upx.github.io/")
        return
    print("[UPX] 正在压缩可执行文件 ...")
    sh(["upx", "--best", "--lzma", str(exe)], check=False)

def main():
    proj = Path(__file__).resolve().parent
    os.chdir(proj)
    print(f"工作目录：{proj}")
    base_py = Path(sys.executable)
    if sys.version_info >= (3,13):
        print("[0] 当前 Python 为 3.13，尝试使用 Python 3.12 构建 ...")
        found = find_python_minor(NEED_PY_MINOR)
        if not found:
            raise SystemExit("未找到 Python 3.12。\n- 一键安装：winget install -e --id Python.Python.3.12\n- 或下载官网安装包：https://www.python.org/downloads/release/python-3126/\n安装后重跑本脚本。")
        base_py = found
        print(f"[0] 使用构建解释器：{found}")

    venv_dir = proj/".buildenv312"
    vpy = ensure_venv(base_py, venv_dir)

    # 安装完整 PySide6 + PyInstaller（不裁剪，让官方 hook 自动收齐 DLL）
    pip_install(vpy, ["pip", "setuptools", "wheel"])
    sh([str(vpy), "-m", "pip", "uninstall", "-y", "PySide6", "PySide6-Essentials", "PySide6-Addons"], check=False)
    pip_install(vpy, ["PySide6", "PyInstaller", "requests", "certifi"])

    main_py = proj/"main.py"
    if not main_py.exists():
        raise SystemExit(f"未找到入口脚本：{main_py}")
    icon = proj/"app.ico"
    version_file = proj/"version_info.txt"

    cmd = [
        str(vpy), "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--name", APP_NAME,
        "--clean", "--noconfirm",
    ]
    if icon.exists(): cmd += ["--icon", str(icon)]
    if version_file.exists(): cmd += ["--version-file", str(version_file)]
    cmd += [str(main_py)]
    sh(cmd)

    dist_exe = proj/"dist"/f"{APP_NAME}.exe"
    if not dist_exe.exists():
        raise SystemExit(f"未找到产物：{dist_exe}")

    try_upx(dist_exe)
    mb = round(dist_exe.stat().st_size/1024/1024, 2)
    print(f"[OK] 输出：{dist_exe}  大小：{mb} MB")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e, file=sys.stderr); sys.exit(1)
    except Exception as e:
        print("构建失败：", e, file=sys.stderr); sys.exit(1)