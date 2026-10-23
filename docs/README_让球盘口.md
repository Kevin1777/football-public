# 让球盘口数据获取功能

> 从 500 彩票网获取比赛的让球盘口（亚洲盘）数据

## 🎯 快速开始

### 1. 启动服务

```bash
python app.py
```

### 2. 获取单场比赛盘口

```python
import requests

response = requests.post(
    "http://127.0.0.1:5001/api/handicap/match",
    json={
        "home_team": "曼联",
        "away_team": "利物浦"
    }
)

data = response.json()["data"]
print(f"盘口: {data['current_handicap_str']} ({data['current_handicap']})")
```

### 3. 批量获取

```python
response = requests.post(
    "http://127.0.0.1:5001/api/handicap/batch",
    json={
        "matches": [
            {"home_team": "曼联", "away_team": "利物浦"},
            {"home_team": "切尔西", "away_team": "阿森纳"}
        ]
    }
)
```

## 📊 盘口说明

| 表示   | 数值 | 含义            |
| ------ | ---- | --------------- |
| 球半   | 1.5  | 主队让 1.5 球   |
| 平手   | 0.0  | 不让球          |
| 受半球 | -0.5 | 主队受让 0.5 球 |

**规则**：

- 正数 = 主队让球
- 负数 = 主队受让（客队让主队）

## 🔧 API 端点

| 端点                   | 功能               |
| ---------------------- | ------------------ |
| `/api/handicap/match`  | 一站式获取（推荐） |
| `/api/handicap/batch`  | 批量获取           |
| `/api/handicap/search` | 仅搜索比赛 ID      |
| `/api/handicap/data`   | 仅获取盘口数据     |

## 📚 文档

- [快速开始指南](./让球盘口快速开始.md) - 5 分钟上手
- [详细文档](./让球盘口数据获取说明.md) - 完整 API 说明
- [功能总结](./让球盘口功能实现总结.md) - 实现细节

## 🧪 测试

```bash
# 运行测试脚本
python test_handicap_api.py

# 运行示例脚本
python 获取比赛盘口示例.py
```

## 💡 使用示例

### 与必发数据集成

```python
# 获取必发比赛列表
matches = requests.get("http://127.0.0.1:5001/api/bifaw/matches").json()["matches"]

# 为每场比赛获取盘口
for match in matches:
    handicap = requests.post(
        "http://127.0.0.1:5001/api/handicap/match",
        json={"home_team": match["home"], "away_team": match["away"]}
    ).json()

    if handicap["success"]:
        print(f"{match['home']} vs {match['away']}: {handicap['data']['current_handicap_str']}")
```

## ⚠️ 注意事项

1. **球队名称**：使用简短常用名称（如"曼联"而非"曼彻斯特联"）
2. **日期格式**：YYYY-MM-DD（如 2025-11-18）
3. **主客队**：务必区分，影响盘口正负号

## 🐛 问题排查

**找不到比赛？**

- 检查球队名称（尝试简化）
- 确认比赛日期
- 查看生成的 debug 文件

**盘口数值异常？**

- 查看`debug_500_handicap_*.txt`文件
- 确认博彩公司 ID（默认 3=澳门盘）

## 📦 依赖

无需额外安装，使用现有依赖：

- requests
- Flask

## 🎉 功能特点

- ✅ 自动盘口解析（支持中文和数值）
- ✅ 批量处理
- ✅ 多家博彩公司支持
- ✅ 盘口历史记录
- ✅ 主客队自动识别
- ✅ 调试文件自动生成

---

**需要帮助？** 查看详细文档或运行测试脚本。
