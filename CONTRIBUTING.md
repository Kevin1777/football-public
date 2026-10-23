# Contributing / 贡献指南

欢迎报告可复现问题、补充合成解析样例和提交小范围修复。维护者为 [@Kevin1777](https://github.com/Kevin1777)。问题和 Pull Request 在本仓库处理，目前没有固定响应时限。

## 准备环境

在独立的 Python 3.11 / 3.12 虚拟环境中运行：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m examples.offline_demo
python tools/check_public_release.py
```

默认测试不需要完整 Web / OCR 依赖。在线测试属于另外的验收流程，需要你自己的授权账号与配置，见 [TESTING.md](docs/TESTING.md)。

## 提交改动

1. 先描述可复现的问题、预期结果与运行环境。
2. 只修改相关模块；行为修复应补充能复现问题的测试。
3. 附上实际执行的检查及结果，明确未测试的部分。
4. 提交 Pull Request；用户可见的变化请同时更新文档或 CHANGELOG。

不要在 Issue、PR、截图、测试样例或日志中提交真实账号、密码、Token、Cookie、Webhook、个人联系方式或私有比赛数据。新样例应使用虚构名称并清楚标注来源。不要为了增加维护记录而拆分空提交、回填提交日期或编造用户反馈。

## English

Use an isolated Python 3.11 / 3.12 environment and run the commands above. Keep changes focused, include a reproducer for behavior fixes, and state exactly what was tested. Online integration checks require your own authorized accounts and are not part of the default suite. Never submit credentials or private data. Use synthetic fixtures and describe their provenance. The maintainer does not promise a fixed response time.
