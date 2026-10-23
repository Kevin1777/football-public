# Quick start / 快速开始

## 1. 不连接外站先体验

Python 3.11 / 3.12，无需安装依赖：

```bash
git clone https://github.com/Kevin1777/football-public.git
cd football-public
python -m examples.offline_demo
```

打开 `demo-output/index.html`。`results.json` 同时保存指标、主客评分、信号、过滤原因和结算。输入全为虚构，方向与比分预设；样例不调用完整 Web 应用，也不代表真实预测。

如浏览器不方便打开本地 HTML，可以仅在本机提供静态页面：

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory demo-output
```

访问 `http://127.0.0.1:8765`，按 Ctrl+C 退出。

## 2. 完整应用：Windows

完整依赖沿用旧项目版本，推荐在全新 Python 3.12 虚拟环境尝试。此安装流程尚未完成完整应用的公开验收。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item config/config.example.json config.json
Copy-Item config/wecom_config.example.json config/wecom_config.json
.\.venv\Scripts\python app.py
```

不需要激活虚拟环境，也不需要修改 PowerShell 执行策略。

## 3. 完整应用：Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
cp config/config.example.json config.json
cp config/wecom_config.example.json config/wecom_config.json
.venv/bin/python app.py
```

浏览器采集需要 Chrome / Chromium 和匹配的 WebDriver。可通过 `CHROME_BINARY`、`CHROMEDRIVER_PATH` 指定已安装程序；某些初始化路径可能尝试下载驱动，需要网络。

## 4. 配置与实际读取位置

| 本地文件 / 设置 | 用途 | 说明 |
| --- | --- | --- |
| `.env` | Flask 地址、调度器、通知和 OCR 可选变量 | 从 `.env.example` 复制；默认 `127.0.0.1:5002` |
| 根目录 `config.json` | 数据源账号 / 密码 | 从 `config/config.example.json` 复制；由 `services/bifaw_client.py` 读取 |
| `config/wecom_config.json` | 企业微信 Webhook | 从对应样例复制；通知模块也兼容根目录同名文件 |
| `DISABLE_SCHEDULER=true` | 首次检查时关闭后台调度和部分恢复服务 | 完整应用仍可能初始化本地目录、数据库并清理旧缓存 |
| `WECOM_WEBHOOK` / `WECOM_ALERT_WEBHOOK` | 通知配置 | 不同入口使用参数、配置文件或环境变量，分别检查相应模块 |

请在项目根目录启动。全新目录中先检查配置和页面，准备好自己的授权数据与通知目标后再启用调度。不要把真实配置提交到 Git。

## 5. 验证和排错

- `python -m pytest` 需要先安装 `requirements-dev.txt`；不需要完整采集依赖。
- 当前开发依赖与完整应用依赖分开；Python 3.13+ 对旧版 NumPy、Pandas、OCR 等可能没有匹配安装包，完整应用优先使用 3.11 / 3.12。
- 账号登录、验证码、网站页面结构和真实通知属于在线集成验收，目前不在 CI 范围内。
- 页面没有完整认证；不要直接暴露到互联网。启动会执行缓存清理，已有数据先备份。
- 反馈时提供系统、Python 版本、复现步骤和脱敏错误摘要；不要直接上传 Cookie 或完整日志。

See [README.en.md](../README.en.md) for the English overview and setup commands.
