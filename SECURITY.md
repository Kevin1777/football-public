# Security / 安全说明

## 报告问题

请通过仓库 Security 页面提供的私密漏洞报告入口（若可用）联系维护者。若入口不可用，可以先发不含复现敏感细节的 Issue，请维护者提供私密联系方式。不要在公开 Issue / PR 中粘贴可用的凭据、Cookie、Webhook 或个人数据。

报告应描述影响模块、适用版本、触发条件和可脱敏的复现步骤。维护者没有固定安全响应或修复时限。

## 运行边界

- 完整 Flask 应用包含文件和任务管理接口，目前没有完整认证层。仅在本机或隔离的可信网络运行。
- 首次配置使用 `.env.example` 和配置样例；真实配置由 `.gitignore` 排除。不要把示例文件改成可用凭据再提交。
- 完整应用会启动浏览器、写本地数据，并在启动时清理部分旧缓存。首次运行先使用新目录和独立环境。
- `requirements.txt` 为旧项目保留的完整依赖清单，尚未完成依赖安全升级；公开版不能被视为经过完整安全审计的互联网服务。
- 离线演示无需凭据、第三方请求或通知；适合先检查核心模块。

## Public source checks

CI scans tracked text files with detect-secrets and rejects tracked runtime credentials, cookies, databases, logs and virtual environments. It also parses tracked Python source. Automated scans reduce accidental disclosure but do not constitute a full application security audit. Review changes before publishing and rotate any credential that has been exposed.
