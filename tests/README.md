# 测试文件说明

本目录包含所有测试脚本。

## 📋 测试分类

### 核心功能测试

#### 盘口数据测试

- `test_500_handicap.py` - 测试 500 彩票网盘口数据获取（主要）
- `test_handicap_api.py` - 测试盘口 API 接口
- `test_handicap_url.py` - 测试盘口 URL 可用性
- `test_html_handicap.py` - 测试 HTML 盘口解析

#### 比赛匹配测试

- `test_future_match.py` - 测试未来比赛匹配（标盘场次）
- `test_finished_matches.py` - 测试完场比赛数据
- `test_finished_detail.py` - 测试完场明细获取

#### 推荐引擎测试

- `test_recommendation_engine.py` - 测试推荐引擎完整流程
- `test_backtest.py` - 测试回测功能

### API 测试

- `test_web_api.py` - 测试 Web API 接口
- `test_api_response.py` - 测试 API 响应格式
- `test_detail_fetch.py` - 测试明细数据获取

### 自动化测试

- `test_automation.py` - 测试自动化脚本
- `test_login.py` - 测试登录功能
- `test_captcha.py` - 测试验证码处理
- `test_selenium_links.py` - 测试 Selenium 链接提取

### 数据解析测试

- `test_parse_saved_html.py` - 测试 HTML 解析
- `test_title_extraction.py` - 测试标题提取
- `test_columns.py` - 测试列格式
- `test_score_format.py` - 测试比分格式

### 修复验证测试

- `test_all_fixes.py` - 测试所有修复
- `test_fixes.py` - 测试特定修复
- `test_metadata_fix.py` - 测试元数据修复

### 完整流程测试

- `test_full_flow.py` - 测试完整工作流程
- `test_final.py` - 最终集成测试

### 工具测试

- `test_regex.py` - 测试正则表达式
- `test_url_direct.py` - 测试 URL 直接访问

## 🚀 运行测试

### 单个测试

```bash
python tests/test_500_handicap.py
```

### 重要测试组合

#### 1. 盘口功能测试

```bash
python tests/test_500_handicap.py
python tests/test_future_match.py
python tests/test_html_handicap.py
```

#### 2. 推荐引擎测试

```bash
python tests/test_recommendation_engine.py
python tests/test_backtest.py
```

#### 3. 完整流程测试

```bash
python tests/test_full_flow.py
python tests/test_web_api.py
```

## 📊 测试数据

测试过程中产生的数据：

- HTML 文件 → `../debug_html/`
- 调试日志 → 控制台输出
- 临时文件 → `../temp/`

## ⚠️ 注意事项

1. **网络依赖**

   - 大部分测试需要网络连接
   - 访问 500.com 和 bifaw.com

2. **测试数据**

   - 使用真实比赛数据
   - 确保日期在合理范围内
   - 注意 API 限流

3. **成功标准**
   - 完场比赛：90%+匹配成功率
   - 未来比赛：主流比赛 100%
   - 冷门比赛可能无盘口数据（正常）

## 🔧 调试技巧

1. **查看详细日志**

   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **检查保存的 HTML**

   - 查看 `debug_html/` 目录
   - 确认数据是否正确获取

3. **验证匹配结果**
   - 检查时间匹配
   - 检查联赛匹配
   - 验证球队名称

## 📝 添加新测试

创建新测试文件时：

1. 命名格式：`test_功能名称.py`
2. 包含文档字符串
3. 使用清晰的测试用例
4. 添加到本 README

---

**最后更新**: 2025-11-19
