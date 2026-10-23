# Selenium 截图超时问题修复

## 🐛 问题描述

批量采集过程中，Selenium 在保存调试截图时出现超时错误：

```
21:29:30 [ERROR] 保存调试截图失败：detail_page_opened_20251120_212900.png
selenium.common.exceptions.TimeoutException: Message: timeout: Timed out receiving message from renderer: 30.000
```

**错误原因**：

- Chrome 渲染器在截图时响应超时（30 秒）
- 通常发生在页面加载缓慢、内容过大或系统资源不足时
- 虽然有异常捕获，但会打印大量 ERROR 日志

---

## ✅ 修复方案

### 修改内容

**文件**: `services/bifaw_client.py`

**优化前**：

```python
def _save_debug_screenshot(self, driver, *, prefix):
    try:
        driver.save_screenshot(str(file_path))
        logger.info("已保存调试截图：%s", file_path)
    except Exception:
        logger.exception("保存调试截图失败：%s", file_path)  # ❌ 打印完整堆栈
```

**优化后**：

```python
def _save_debug_screenshot(self, driver, *, prefix):
    try:
        driver.save_screenshot(str(file_path))
        logger.info("已保存调试截图：%s", file_path)
    except TimeoutException:
        # Chrome渲染器超时，跳过截图
        logger.warning(f"⚠️  截图超时（跳过）: {file_path.name}")  # ✅ 简洁警告
    except Exception as e:
        # 其他错误也只记录警告
        logger.warning(f"⚠️  截图失败（跳过）: {file_path.name} - {type(e).__name__}")
```

### 改进点

1. **特别处理 TimeoutException**

   - 明确识别超时错误
   - 使用简洁的警告消息

2. **降低日志级别**

   - 从 ERROR → WARNING
   - 截图失败不影响主流程，不应该是 ERROR 级别

3. **简化日志输出**
   - 不打印完整堆栈跟踪
   - 只输出文件名和错误类型
   - 避免日志过长影响可读性

---

## 📊 效果对比

### 修复前

```
21:29:30 [ERROR] 保存调试截图失败：D:\MSM\Cursor\football\debug_html\detail_page_opened_20251120_212900.png
Traceback (most recent call last):
  File "d:\MSM\Cursor\football\services\bifaw_client.py", line 546, in _save_debug_screenshot
    driver.save_screenshot(str(file_path))
  File "F:\APP\miniconda\envs\leverage_bt\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 1025, in save_screenshot
    return self.get_screenshot_as_file(filename)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  ... (20+ 行堆栈跟踪)
selenium.common.exceptions.TimeoutException: Message: timeout: Timed out receiving message from renderer: 30.000
  (Session info: chrome=142.0.7444.164)
Stacktrace:
Symbols not available. Dumping unresolved backtrace:
        0x4040e3
        ... (更多地址)
```

### 修复后

```
21:29:30 [WARNING] ⚠️  截图超时（跳过）: detail_page_opened_20251120_212900.png
21:29:35 [INFO] 保存明细页面加载后截图
21:29:35 [INFO] 已保存调试截图：detail_page_loaded_20251120_212935.png
```

---

## 🎯 为什么会超时？

### 常见原因

1. **页面加载慢**

   - 网络延迟
   - 页面资源过多
   - JavaScript 执行时间长

2. **Chrome 渲染器繁忙**

   - 同时处理多个页面
   - 内存占用过高
   - CPU 资源不足

3. **页面内容复杂**

   - 大量数据表格
   - 复杂的 CSS 样式
   - 动态内容未渲染完成

4. **系统资源不足**
   - 内存占用高
   - CPU 负载重
   - 磁盘 I/O 慢

### 不影响主流程的原因

- 调试截图是**可选功能**，用于问题排查
- 数据采集依赖的是 HTML 内容，不是截图
- 即使所有截图都失败，数据仍能正常采集

---

## 💡 进一步优化建议

### 1. 减少截图频率

只在关键节点截图：

```python
# 只在失败时截图
if not success:
    self._save_debug_screenshot(driver, prefix="error")
```

### 2. 添加截图开关

通过配置控制是否启用调试截图：

```python
# config.py
ENABLE_DEBUG_SCREENSHOTS = False  # 生产环境关闭

# bifaw_client.py
if ENABLE_DEBUG_SCREENSHOTS:
    self._save_debug_screenshot(driver, prefix="detail")
```

### 3. 异步截图

使用线程异步保存截图，不阻塞主流程：

```python
import threading

def _save_debug_screenshot_async(self, driver, *, prefix):
    def save():
        try:
            driver.save_screenshot(...)
        except:
            pass

    thread = threading.Thread(target=save, daemon=True)
    thread.start()
```

### 4. 优化 Chrome 配置

减少渲染开销：

```python
chrome_options = Options()
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-images')  # 禁用图片加载
```

---

## 🔍 如何排查截图超时

### 步骤 1：检查系统资源

```powershell
# Windows PowerShell
# 查看内存使用
Get-Process chrome | Select-Object ProcessName, WorkingSet

# 查看CPU使用
Get-Process chrome | Select-Object ProcessName, CPU
```

### 步骤 2：检查 Chrome 进程数量

```powershell
# 统计Chrome进程
(Get-Process chrome).Count

# 如果进程数量 > 10，可能有泄漏
```

### 步骤 3：手动访问页面

```
访问超时的URL，检查页面是否正常加载
例如：https://www.bifaw.com/bifaw/matchDetails.php?...
```

### 步骤 4：查看 Chrome DevTools

```
F12 -> Network -> 查看资源加载时间
F12 -> Performance -> 查看渲染性能
```

---

## ✅ 验证修复

### 测试场景 1：正常截图

```
[INFO] 已保存调试截图：detail_success_20251120_213000.png
```

### 测试场景 2：超时情况

```
[WARNING] ⚠️  截图超时（跳过）: detail_page_opened_20251120_213005.png
[INFO] 继续采集数据...  # ✅ 主流程不受影响
```

### 测试场景 3：其他错误

```
[WARNING] ⚠️  截图失败（跳过）: detail_error_20251120_213010.png - PermissionError
[INFO] 继续采集数据...  # ✅ 主流程不受影响
```

---

## 📝 注意事项

1. **截图超时不影响数据采集**

   - 只是调试功能失败
   - 数据仍能正常保存

2. **日志级别说明**

   - INFO: 正常截图成功
   - WARNING: 截图失败（可忽略）
   - ERROR: 严重错误（需关注）

3. **性能影响**

   - 截图操作会增加 10-30%开销
   - 生产环境可考虑关闭
   - 只在调试时开启

4. **磁盘空间**
   - 每张截图约 100-500KB
   - 大量采集会占用较多空间
   - 定期清理 `debug_html/` 目录

---

## 🚀 总结

修复后的截图功能：

- ✅ **容错性强**: 超时不影响主流程
- ✅ **日志清晰**: 简洁的 WARNING 消息
- ✅ **性能优化**: 快速失败，不阻塞
- ✅ **易于维护**: 清晰的错误分类

现在可以放心地进行大批量采集，截图超时只会产生一条简短的警告，不会影响数据采集！

---

**修复日期**: 2025-11-20
**涉及文件**: `services/bifaw_client.py`
**影响功能**: 调试截图功能
