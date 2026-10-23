# 版本更新指南

## 📋 概述

为了避免版本号硬编码导致的更新遗漏，现在所有版本号都统一在 `version_config.py` 中管理。

---

## 🎯 如何更新版本

### 步骤 1：修改版本配置文件

只需编辑 `version_config.py`：

```python
# 修改这一行即可更新所有地方的版本号
MODEL_VERSION = "V3.0"  # 例如：从 V2.0 升级到 V3.0
```

### 步骤 2：验证更新

```bash
# 运行测试验证版本是否正确
python version_config.py

# 应该看到：
# 🎯 当前模型版本: X1-JSON-V3.0
```

---

## 📁 已统一管理的文件

### ✅ 核心推荐引擎

- **文件**: `recommendation/x1_json_recommender.py`
- **位置**:
  - Line 72: `'version': MODEL_FULL_NAME`
  - Line 114: `'version': MODEL_FULL_NAME`
  - Line 847: `'version': MODEL_FULL_NAME, 'engine': ENGINE_NAME`
  - Line 857: `'version': MODEL_FULL_NAME`
- **状态**: ✅ 已统一

### ⚠️ 需要手动更新的文件

以下文件仍使用硬编码版本号，需要根据情况手动更新：

#### 1. 旧版引擎（V1 相关）

- `recommendation/x1_json_recommender.py` (V1.0 熔断和错误处理)
  - Line 668: `'version': 'X1-JSON-V1.0'` (熔断结果)
  - Line 704: `'version': 'X1-JSON-V1.0'` (低置信度)
  - Line 738: `'version': 'X1-JSON-V1.0'` (正常推荐)
  - Line 767: `'version': 'X1-JSON-V1.0'` (熔断错误)
  - Line 829: `'version': 'X1-JSON-V1.0'` (数据不足)
  - Line 920: `'version': 'X1-JSON-V1.0'` (旧格式)
  - Line 940: `'version': 'X1-JSON-V1.0'` (异常)
- **建议**: 保持 V1.0，因为这些是错误/降级场景

#### 2. 其他引擎

- `recommendation/engine_v2.py`
  - Line 136: `'version': 'V2-DATA-DRIVEN'`
  - Line 300: `'version': 'V2-DATA-DRIVEN'`
- **建议**: 独立版本号，不需要修改

- `recommendation/handicap_engine_v2.py`
  - Line 159: `'version': 'X1-HANDICAP-V2.0'`
- **建议**: 独立版本号，不需要修改

- `recommendation/handicap_engine_x1.py`
  - Line 167: `'version': 'X1-HANDICAP-V1.0'`
- **建议**: 独立版本号，不需要修改

#### 3. 测试和工具文件

- `test_current_v2.py` (Line 71, 78) - 测试脚本
- `test_api_v2.py` (Line 66) - 测试脚本
- `visualize_x1_accuracy.py` (Line 498) - 可视化工具
- `优化推荐引擎.py` (Line 329) - 优化工具
- **建议**: 测试脚本可以更新，工具脚本按需更新

---

## 🔧 版本号使用规范

### ✅ 正确做法

```python
# 导入版本配置
from version_config import MODEL_FULL_NAME, MODEL_VERSION, ENGINE_NAME

# 使用配置变量
result = {
    'version': MODEL_FULL_NAME,  # ✅ 正确：自动跟随配置
    'engine': ENGINE_NAME
}
```

### ❌ 错误做法

```python
# 硬编码版本号
result = {
    'version': 'X1-JSON-V2.0',  # ❌ 错误：难以维护
    'engine': 'x1_json_v2'
}
```

---

## 📊 版本更新影响范围

### 会自动更新的部分

- ✅ 推荐引擎返回的版本号
- ✅ API 响应中的版本号
- ✅ 日志中显示的版本号
- ✅ 前端展示的版本号（如果读取 API）

### 不会自动更新的部分

- ⚠️ 错误处理/降级场景中的 V1.0 版本号（故意保留）
- ⚠️ 独立引擎的版本号（如盘口引擎）
- ⚠️ 测试脚本中的硬编码检查

---

## 🎯 版本更新检查清单

更新版本时，请检查以下项目：

- [ ] 修改 `version_config.py` 中的 `MODEL_VERSION`
- [ ] 运行 `python version_config.py` 验证
- [ ] 运行 `python test_current_v2.py` 测试
- [ ] 检查 API 响应中的版本号
- [ ] 更新 `VERSION_HISTORY` 中的版本记录
- [ ] 更新相关文档（如 README）

---

## 📝 版本历史管理

在 `version_config.py` 中添加新版本记录：

```python
VERSION_HISTORY = {
    "V2.0": {
        "name": "X1-JSON-V2.0",
        "description": "数据驱动简化模型",
        # ...
    },
    "V3.0": {  # 新增版本记录
        "name": "X1-JSON-V3.0",
        "description": "机器学习增强模型",
        "release_date": "2025-12-01",
        "features": [
            "集成XGBoost模型",
            "自动特征工程",
            "在线学习能力"
        ],
        # ...
    }
}
```

---

## 🚀 快速更新示例

### 从 V2.0 升级到 V3.0

1. **编辑 version_config.py**

   ```python
   MODEL_VERSION = "V3.0"  # 改这一行
   ```

2. **添加版本历史**

   ```python
   VERSION_HISTORY = {
       # ... V2.0 记录 ...
       "V3.0": { /* 新版本信息 */ }
   }
   ```

3. **验证**

   ```bash
   python version_config.py
   python test_current_v2.py
   ```

4. **完成！** 🎉

---

## ⚠️ 注意事项

1. **不要直接修改推荐引擎代码中的版本号**

   - 所有 V2.0 相关版本号都已改为读取配置

2. **V1.0 版本号保留**

   - 错误处理和降级场景仍使用 V1.0
   - 这是故意的，便于区分正常推荐和异常情况

3. **独立引擎有独立版本**

   - 盘口引擎: X1-HANDICAP-V2.0
   - 数据驱动引擎: V2-DATA-DRIVEN
   - 它们不跟随主版本号

4. **测试脚本需要同步更新**
   - 如果测试脚本检查特定版本号
   - 记得同步修改测试期望值

---

**最后更新**: 2025-11-26  
**维护者**: Cascade AI  
**版本**: 1.0
