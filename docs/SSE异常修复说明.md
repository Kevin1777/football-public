# SSE 连接异常修复说明

## 🐛 问题描述

批量采集时，SSE（Server-Sent Events）流式连接在扫描阶段出现 `TypeError: network error` 异常，导致任务中断。

### 错误日志

```
[21:10:09] 📊 第一阶段：扫描 6 天
[21:10:09]   ✅ 2025-11-15: 51 场
[21:10:26]   ✅ 2025-11-16: 23 场
[21:10:44]   ✅ 2025-11-17: 18 场
[21:11:01]   ✅ 2025-11-18: 75 场
[21:11:18]   ✅ 2025-11-19: 4 场
[21:11:35] ❌ SSE连接异常: TypeError: network error
```

---

## 🔍 问题分析

### 根本原因

1. **网络请求异常未捕获**

   - `fetch_finished_matches()` 和 `fetch_daily_handicaps()` 网络调用失败
   - 异常直接传播到 SSE 生成器，导致流中断

2. **连接超时**

   - 长时间无数据推送
   - 浏览器或中间代理关闭连接

3. **客户端断开未处理**
   - 用户关闭页面或刷新
   - `GeneratorExit` 异常未正确处理

---

## ✅ 修复方案

### 1. 网络异常细粒度捕获

```python
# 修复前：网络异常直接抛出
matches = bifaw_client.fetch_finished_matches(...)

# 修复后：捕获并优雅降级
try:
    matches = bifaw_client.fetch_finished_matches(...)
except Exception as net_err:
    app.logger.error(f"获取比赛列表失败 {date_str}: {net_err}")
    yield f"data: {json.dumps({'type': 'scan_error', 'date': date_str, 'error': str(net_err)})}\n\n"
    date_match_map[date_str] = []
    continue  # 继续处理下一天
```

### 2. 盘口数据获取异常处理

```python
# 盘口获取失败时，使用原始比赛列表（不过滤）
try:
    daily_handicaps = lottery500_client.fetch_daily_handicaps(date_str, use_cache=False)
except Exception as handicap_err:
    app.logger.error(f"获取盘口数据失败 {date_str}: {handicap_err}")
    yield f"data: {json.dumps({'type': 'handicap_error', 'date': date_str, 'error': str(handicap_err)})}\n\n"
    date_match_map[date_str] = matches  # 降级：使用全部比赛
    continue
```

### 3. SSE 连接超时防护

添加心跳机制：

```python
scan_current_date += timedelta(days=1)

# 发送心跳，防止连接超时
yield f": heartbeat\n\n"
time_module.sleep(1)
```

### 4. 客户端断开处理

```python
except GeneratorExit:
    # 客户端断开连接（用户关闭页面等）
    app.logger.warning("SSE客户端断开连接")
except Exception as exc:
    app.logger.exception(f"SSE流异常: {exc}")
    error_type = type(exc).__name__
    error_msg = str(exc)

    # 特殊处理网络错误
    if 'network' in error_msg.lower() or 'connection' in error_msg.lower():
        error_msg = "网络连接异常，请检查网络或稍后重试"

    try:
        yield f"data: {json.dumps({'type': 'error', 'message': f'{error_type}: {error_msg}'})}\n\n"
    except:
        pass  # 连接已断开，忽略
```

### 5. SSE 响应头优化

```python
response = Response(stream_with_context(generate()), mimetype='text/event-stream')
response.headers['Cache-Control'] = 'no-cache'
response.headers['X-Accel-Buffering'] = 'no'  # 禁用nginx缓冲
response.headers['Connection'] = 'keep-alive'  # 保持连接
return response
```

---

## 📊 修复效果

### 修复前

- ❌ 网络错误导致整个流中断
- ❌ 后续日期无法继续处理
- ❌ 用户体验差（任务失败）

### 修复后

- ✅ 单个日期失败不影响其他日期
- ✅ 网络错误自动跳过并继续
- ✅ 前端收到详细错误信息
- ✅ 心跳防止连接超时
- ✅ 优雅处理客户端断开

---

## 🎯 新增错误类型

前端可以接收以下新的事件类型：

### `scan_error`

```json
{
  "type": "scan_error",
  "date": "2025-11-19",
  "error": "ConnectionError: 连接超时"
}
```

### `handicap_error`

```json
{
  "type": "handicap_error",
  "date": "2025-11-19",
  "error": "HTTPError: 500 服务器错误"
}
```

### 心跳注释

```
: heartbeat
```

（不会触发前端事件，只是保持连接活跃）

---

## 🔧 测试建议

### 测试场景 1: 网络不稳定

```bash
# 模拟网络延迟
# 预期：部分日期失败，其他正常完成
```

### 测试场景 2: 单个日期无数据

```bash
# 选择未来日期
# 预期：优雅跳过，不报错
```

### 测试场景 3: 用户中途关闭页面

```bash
# 开始采集后立即关闭页面
# 预期：后端日志记录 "SSE客户端断开连接"
```

### 测试场景 4: 长时间运行

```bash
# 采集7天以上数据
# 预期：连接不超时，心跳持续发送
```

---

## 💡 前端适配建议

### 处理新错误类型

```javascript
eventSource.addEventListener("message", (e) => {
  const data = JSON.parse(e.data);

  switch (data.type) {
    case "scan_error":
      console.warn(`扫描失败 ${data.date}: ${data.error}`);
      appendLog(`⚠️ ${data.date} 扫描失败: ${data.error}`);
      // 继续显示进度，不中断UI
      break;

    case "handicap_error":
      console.warn(`盘口数据失败 ${data.date}: ${data.error}`);
      appendLog(`⚠️ ${data.date} 盘口数据获取失败，使用全部比赛`);
      break;

    case "error":
      // 严重错误，终止任务
      console.error("任务失败:", data.message);
      appendLog(`❌ 任务失败: ${data.message}`);
      eventSource.close();
      break;
  }
});

// 处理连接错误
eventSource.onerror = (e) => {
  console.error("SSE连接错误:", e);
  appendLog("❌ 连接中断，请检查网络后重试");
  eventSource.close();
};
```

---

## 📝 注意事项

1. **网络异常是正常现象**

   - 外部 API 可能临时不可用
   - 修复后系统会自动降级处理
   - 不影响整体任务完成

2. **心跳频率**

   - 每天扫描后发送 1 次心跳
   - 防止 30 秒以上无数据时超时
   - 不会增加显著开销

3. **日志记录**

   - 所有异常都会记录到后端日志
   - 便于事后排查问题
   - 建议定期检查日志

4. **降级策略**
   - 盘口数据失败：使用全部比赛（不过滤）
   - 比赛列表失败：跳过该天
   - 保证最大容错性

---

## ✅ 总结

修复后的 SSE 流式采集具有：

- ✅ **容错性**: 单点失败不影响整体
- ✅ **稳定性**: 心跳防止超时
- ✅ **可观测性**: 详细错误日志
- ✅ **用户体验**: 前端收到明确反馈

可以安全地用于长时间、大批量的数据采集任务！

---

**修复日期**: 2025-11-20
**涉及文件**: `app.py` (SSE 流式采集路由)
**影响范围**: 批量日期区间采集功能
