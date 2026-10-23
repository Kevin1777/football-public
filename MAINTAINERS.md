# Maintenance, provenance and evidence

## 维护者

- GitHub 账号：[@Kevin1777](https://github.com/Kevin1777)
- 公开仓库：[Kevin1777/football-public](https://github.com/Kevin1777/football-public)
- 职责：源码整理、配置与数据脱敏、文档、问题分流、测试和版本发布。
- 反馈入口：[Issues](https://github.com/Kevin1777/football-public/issues) 和 [Pull requests](https://github.com/Kevin1777/football-public/pulls)。

## 项目来源

本项目从维护者原有的私有 Football Data Service 整理而来。原应用启动标识为 `v2.1.3`；`version_config.py` 中的模型标签属于另一套内部版本编号，不能混同为公开发布版本。

2026-10-23 创建独立公开仓库和新的根提交，保留可发布的源码、测试及历史文档，剔除凭据、Cookie、运行数据库、日志、虚拟环境和第三方 PDF。没有导入旧 Git 历史，因此公开提交数量不能体现私有开发时长；也不宣称私有时期已经完成公开社区维护。

## 可核查的公开证据

| 证据 | 位置 | 能证明的范围 |
| --- | --- | --- |
| 安全整理后的根提交 | [a32c60f](https://github.com/Kevin1777/football-public/commit/a32c60fd0e237995951ffadc04b9afba72e15227) | 首次公开的源码内容 |
| 后续正常提交 | [Commits](https://github.com/Kevin1777/football-public/commits/main/) | 实际公开维护变更 |
| 自动检查 | [GitHub Actions](https://github.com/Kevin1777/football-public/actions/workflows/ci.yml) | 对应提交的离线核心测试、源码语法与发布内容检查 |
| 可复现演示 | [offline_demo.py](examples/offline_demo.py) 与 [合成输入](examples/matches.synthetic.json) | 核心模块在合成数据上的运行行为 |
| 公开版本说明 | [Releases](https://github.com/Kevin1777/football-public/releases) | 发布范围与已知限制 |
| 问题和改进 | [Issues](https://github.com/Kevin1777/football-public/issues) | 出现真实反馈后的处理记录；当前不预设用户数量 |

测试或 CI 不能证明预测准确率、实盘收益、线上采集可用性或外部项目的审批资格。Star、Fork、下载量和使用人数只在有实际可查数据时陈述，不编造或回填。

## Public record

Public maintenance starts on 2026-10-23. This repository has a fresh history because the private source contained runtime credentials and data. The maintainer is Kevin1777. Automated checks cover offline core behavior and public-source hygiene, not production operation or model performance. Release notes and commit history document actual changes; no historical community adoption is implied.
