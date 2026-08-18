import os
import sys
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def build():
    print("==================================================")
    print("   Douyin Streak Setup - 桌面客户端 Release 打包   ")
    print("==================================================")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "DouyinStreakSetup",
        "--hidden-import", "PyQt5",
        "--hidden-import", "cryptography",
        "--hidden-import", "playwright",
        "--hidden-import", "requests",
        "--hidden-import", "config.model",
        "--hidden-import", "config.sanitizer",
        "--hidden-import", "douyin.provider",
        "--hidden-import", "douyin.session",
        "--hidden-import", "douyin.conversations",
        "--hidden-import", "douyin.sender",
        "--hidden-import", "douyin.playwright_provider",
        "--hidden-import", "github.client",
        "--hidden-import", "github.secrets",
        "--hidden-import", "github.instance",
        "--hidden-import", "setup.gui.style",
        "--hidden-import", "setup.gui.main_window",
        "setup/main.py"
    ]

    print(f"🚀 开始执行打包命令: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\n🎉 打包成功！")
        print("可执行程序路径: dist/DouyinStreakSetup.exe")
    else:
        print(f"\n❌ 打包失败，退出码: {res.returncode}")

if __name__ == "__main__":
    build()
