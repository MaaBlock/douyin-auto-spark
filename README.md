# 抖音火花自动续签工具 (Douyin Auto Spark)

🔥 抖音网页版自动续火花工具，支持 **GitHub Actions 每日全自动云端运行** 与 **本地定时挂机** 两种模式。

---

## ✨ 核心特性

- 🤖 **GitHub Actions 云端托管**：免开电脑、免服务器，每天定时自动执行两次续火花任务。
- 🎯 **智能模糊/精准匹配**：支持好友昵称精确与包含匹配，自动兼容昵称后的 Emoji 与勋章标识（例如：`好友2` 自动匹配 `好友2🏸`），并准确区分同名私聊与群聊。
- 📜 **自动滚动与会话检索**：如果目标会话排在列表靠后位置，脚本会自动滑动左侧边栏并持续检索目标。
- 📸 **运行截图云端归档**：GitHub Actions 每次执行完毕均会自动将发送界面的截图保存为 Actions Artifact，方便随时在网页端查看核验。
- 🛡️ **无感伪装与反爬防护**：内置反指纹探测、真实浏览器上下文、模拟真人随机打字延迟（Jitter）。
- 💻 **本地多模式支持**：支持 `--send`（单次立即发送）、`--schedule`（每日定时常驻）、`--login`（本地扫码登录）与 `--list`（会话列表查看）。

---

## 🚀 快速上手 (GitHub Actions 云端自动化)

### 1. 克隆/打开本仓库并安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 扫码登录并导出 Secret 凭据
运行凭证导出工具：
```bash
python get_cookies.py
```
1. 浏览器弹窗打开后，使用**手机抖音 App** 扫描二维码登录。
2. 登录成功进入聊天页面后，返回终端按下 **【回车键 (Enter)】**。
3. 工具会自动生成 `config_secret.json`。若本地安装并登录了 `gh` CLI，会自动同步到 GitHub Secrets。

### 3. 配置 GitHub Actions Secret (若手动配置)
1. 进入当前 GitHub 仓库页面，依次点击 **Settings** -> **Secrets and variables** -> **Actions**。
2. 点击 **New repository secret**：
   - **Name**: `DOUYIN_CONFIG`
   - **Secret**: 打开本地生成的 `config_secret.json`，复制其中的**全部内容**并粘贴进去。
3. 保存即可。

### 4. 自动运行与手动测试
- **自动定时**：GitHub Actions 默认在北京时间 **每天 08:30** 与 **20:30**（双重保险）自动运行。
- **手动触发测试**：前往 GitHub 仓库的 **Actions** 标签页 -> 点击左侧 **Douyin Spark Auto Renew** -> 点击右侧 **Run workflow** 即可立即触发一次运行。
- **查看截图证据**：在每次 Action 运行详情底部的 **Artifacts** 中，可下载 `spark-run-screenshots` 查看每次发送消息的实际截图。

---

## 💻 本地运行模式

除了云端 GitHub Actions，你也可以在本地电脑直接运行：

### 1. 立即执行一次
```bash
python douyin_spark.py --send
```

### 2. 启动每日定时常驻服务
```bash
python douyin_spark.py --schedule
```
> 默认在每天 08:30 自动执行（可在 `config.json` 中修改 `send_time`）。

### 3. 扫描并查看当前会话列表
```bash
python douyin_spark.py --list
```

---

## ⚙️ 配置文件说明 (`config.json`)

```json
{
  "targets": [
    "好友1",
    "好友2",
    "好友3",
    "好友4",
    "好友5",
    "好友6"
  ],
  "message": "续火花",
  "send_time": "08:30",
  "headless": false
}
```

- `targets`: 需要续火花的好友昵称或群聊名称列表。
- `message`: 发送的消息内容，默认为 `"续火花"`。
- `send_time`: 本地定时任务执行时间 (24小时制，如 `"08:30"`)。
- `headless`: 本地运行是否隐藏浏览器界面。

---

## ⚠️ 注意事项与常见问题

1. **Cookie 有效期**：抖音网页版 Cookie 通常有效期较长（数周至数月）。若 GitHub Actions 报错提示 Cookie 失效，只需在本地重新运行 `python get_cookies.py` 并更新 GitHub Secret 即可。
2. **安全隐私**：`config_secret.json` 包含登录凭证，已被 `.gitignore` 忽略，**切勿将凭证文件提交至公开 Git 仓库**。
