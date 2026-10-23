# 🎯 版本更新快速指南

## 📋 一句话总结

**只需修改 `version_config.py` 中的 `MODEL_VERSION`，所有地方自动更新！**

---

## 🚀 如何更新版本（3 步）

### 步骤 1：修改版本号

```python
# 编辑 version_config.py 第18行
MODEL_VERSION = "V3.0"  # 从 V2.0 改为 V3.0
```

### 步骤 2：添加版本历史

```python
# 在 VERSION_HISTORY 字典中添加新版本
"V3.0": {
    "name": "X1-JSON-V3.0",
    "description": "你的新功能描述",
    "release_date": "2025-12-01",
    "features": ["新特性1", "新特性2"],
    "performance": {...}
}
```

### 步骤 3：验证

```bash
python version_config.py       # 查看版本信息
python test_current_v2.py      # 测试是否生效
```

---

## 📊 已统一的位置

### ✅ 自动更新（无需手动修改）

| 文件                     | 位置     | 说明           |
| ------------------------ | -------- | -------------- |
| `x1_json_recommender.py` | Line 80  | V2 推荐成功    |
| `x1_json_recommender.py` | Line 118 | V2 不推荐      |
| `x1_json_recommender.py` | Line 847 | 批量回测格式   |
| `x1_json_recommender.py` | Line 857 | 批量回测不推荐 |

### ⚠️ 保持不变（故意的）

| 文件                     | 版本号           | 原因              |
| ------------------------ | ---------------- | ----------------- |
| `x1_json_recommender.py` | V1.0             | 错误处理/降级场景 |
| `handicap_engine_v2.py`  | X1-HANDICAP-V2.0 | 独立引擎          |
| `engine_v2.py`           | V2-DATA-DRIVEN   | 独立引擎          |

---

## 🎯 版本号结构

```
X1-JSON-V2.0
│   │   │  │
│   │   │  └─ 小版本号 (0)
│   │   └──── 大版本号 (2)
│   └──────── 引擎类型 (JSON)
└──────────── 项目代码 (X1)
```

---

## 📝 当前配置

```python
# version_config.py
MODEL_VERSION = "V2.0"              # 当前版本
MODEL_FULL_NAME = "X1-JSON-V2.0"   # 完整名称
ENGINE_NAME = "x1_json_v2"          # 引擎标识
```

---

## 🔧 使用示例

### 在代码中使用

```python
from version_config import MODEL_FULL_NAME, ENGINE_NAME

# ✅ 正确：自动跟随配置
result = {
    'version': MODEL_FULL_NAME,
    'engine': ENGINE_NAME
}

# ❌ 错误：硬编码
result = {
    'version': 'X1-JSON-V2.0',  # 难以维护
    'engine': 'x1_json_v2'
}
```

### 查看版本信息

```python
from version_config import get_version_info, print_version_info

# 获取版本信息
info = get_version_info()
print(info['description'])

# 打印详细信息
print_version_info()
```

---

## ✅ 验证清单

更新版本后检查：

- [x] `version_config.py` 中 `MODEL_VERSION` 已修改
- [x] `VERSION_HISTORY` 中添加了新版本记录
- [x] 运行 `python version_config.py` 显示正确
- [x] 运行 `python test_current_v2.py` 通过
- [x] Web API 返回正确版本号
- [x] 文档已更新（如有需要）

---

## 🎯 优势

### 之前（硬编码）

- ❌ 需要手动修改多个文件
- ❌ 容易遗漏某些位置
- ❌ 版本号不一致
- ❌ 难以维护

### 现在（统一管理）

- ✅ 只改一个地方
- ✅ 自动同步所有位置
- ✅ 版本号始终一致
- ✅ 易于维护

---

## 📞 故障排查

### 问题：提示 `NameError: name 'MODEL_FULL_NAME' is not defined`

**解决**：确认 `x1_json_recommender.py` 文件开头有导入语句：

```python
from version_config import MODEL_FULL_NAME, ENGINE_NAME
```

### 问题：版本号没有更新

**解决**：

1. 检查 `version_config.py` 是否保存
2. 重启 Python 进程或服务器
3. 清除 `__pycache__` 缓存

### 问题：测试失败

**解决**：

1. 检查 `version_config.py` 语法是否正确
2. 运行 `python version_config.py` 查看错误
3. 确认导入路径正确

---

**维护者**: Cascade AI  
**最后更新**: 2025-11-26  
**当前版本**: V2.0
