# 🔥 Douyin Streak (抖音火花自动续签实例管理器)

> 一个开源的个人自动化工具，帮助用户维护自己的聊天火花。  
> ✓ 用户本人扫码 · ✓ 私人云端部署 · ✓ 无需自备服务器 · ✓ 登录凭证不经过开发者服务器 · ✓ GitHub Actions 自动运行

---

## ⚡ 极速开始：下载 Windows 桌面客户端 (免配置环境)

💡 **最简使用方式**：
1. 前往 GitHub 仓库右侧 **[Releases 页面](../../releases)** 下载 `DouyinStreakSetup.exe` 单文件绿色客户端。
2. 双击打开运行，无需安装 Python 环境。
3. 跟随客户端向导完成登录与扫码，一键部署到属于您个人的 Private GitHub 实例中！

---

## 🖥️ 完整自助式部署流程

```text
打开 Douyin Streak Setup
        ↓
使用 GitHub 登录
        ↓
┌────────────────────────────┐
│ ⭐ 支持这个项目             │
│                            │
│ 这个工具免费开源，如果觉得  │
│ 有用，给项目点个 Star 吧    │
│                            │
│ [ ⭐ Star 并继续 ]          │
│ [ 跳过，直接部署 ]          │
└────────────────────────────┘
        ↓
自动创建 Private Instance 私有仓库
        ↓
扫码抖音
        ↓
读取好友 / 会话 / 群聊
        ↓
选择好友 / 群聊
        ↓
选择消息 / 发送策略
        ↓
配置执行时间
        ↓
自动部署 GitHub Actions
        ↓
自动化 Pre-flight 部署测试
        ↓
部署完成 🎉
```

---

## 🏗️ 架构设计

```text
Public 官方仓库 (MaaBlock/douyin-auto-spark)
        │
        ├── Setup 桌面安装器
        ├── Runner 执行引擎
        └── 自动版本更新
                │
                ↓
       Douyin Streak Setup
                │
                ↓
     创建用户 Private Instance (username/douyin-streak-instance)
                │
       ┌────────┴────────┐
       ↓                 ↓
   config.json       Actions Secrets
 (目标/策略/时间)     (DOUYIN_SESSION)
       │                 │
       └────────┬────────┘
                ↓
          GitHub Actions 定时无人值守
                ↓
        自动加载最新 Runner 运行
                ↓
            执行任务与归档截图
```

- **官方仓库永远是唯一 upstream**：当上游修复平台变更时，所有用户的私有实例每天自动拉取最新 Runner 运行，**用户无需手动同步 Fork**！
- **Zero Hosted User Session**：开发者服务器 0 存储用户 Cookie、0 好友数据、0 聊天记录，所有凭据仅存在于用户个人的私有 GitHub Secret 中。

---

## 🛠️ 开发者源码运行与打包

### 1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 启动桌面安装向导
```bash
python setup/main.py
```

### 3. 本地独立 Runner 测试
```bash
python -m runner.main --config config.json --test
```

### 4. 本地打包 Release 可执行程序 (`DouyinStreakSetup.exe`)
```bash
python build_exe.py
```
打包生成的可执行文件位于 `dist/DouyinStreakSetup.exe`。

---

## ⚠️ 免责声明 (Disclaimer)

- 本项目为个人自动化辅助工具，仅供学习交流与个人账户维护火花使用。
- **Third-party project. Not affiliated with Douyin / ByteDance.** (第三方开源项目，非抖音/字节跳动官方产品)。
- 禁止将本项目用于商业营销、批量群控、引流获客或任何违反平台服务条款之行为。
