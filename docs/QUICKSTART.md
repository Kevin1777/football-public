# 🚀 快速开始指南

## 📁 项目结构

```
football/
├── app.py                 # Flask 应用入口（控制器）
├── requirements.txt        # Python 依赖列表
├── README.md              # 项目说明
├── parser/                # 解析模块
│   ├── __init__.py
│   └── pdf_parser.py      # PDF 解析核心逻辑（在这里实现解析功能）
├── templates/             # HTML 模板
│   └── index.html         # 前端页面
└── uploads/               # 上传文件目录
```

## ⚡ 快速启动（3步）

### 1. 安装依赖

```bash
cd football
pip install -r requirements.txt
```

### 2. 运行应用

```bash
python app.py
```

### 3. 访问应用

打开浏览器访问：**http://localhost:5001**

## 📝 下一步：实现解析逻辑

### 在 `parser/pdf_parser.py` 中实现 `parse_bifa_pdf()` 函数

当前是占位函数：

```python
def parse_bifa_pdf(pdf_path):
    # TODO: 在这里实现PDF解析逻辑
    print(f"正在尝试解析: {pdf_path}")
    return None
```

### 示例实现框架

```python
def parse_bifa_pdf(pdf_path):
    """
    解析 PDF 文件并提取表格数据
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        pandas.DataFrame: 提取的表格数据
        或 None/错误信息: 如果解析失败
    """
    try:
        # 使用 pdfplumber 打开 PDF
        with pdfplumber.open(pdf_path) as pdf:
            # 提取所有表格
            all_tables = []
            for page in pdf.pages:
                tables = page.extract_tables()
                all_tables.extend(tables)
            
            # 转换为 DataFrame
            if all_tables:
                # 合并所有表格或选择第一个
                df = pd.DataFrame(all_tables[0])
                return df
            else:
                return None
                
    except Exception as e:
        return f"解析失败: {str(e)}"
```

## 🎯 工作流程

1. **用户上传 PDF** → `app.py` 接收文件
2. **保存到 uploads/** → `app.py` 保存文件
3. **调用解析函数** → `app.py` 调用 `parse_bifa_pdf()`
4. **返回结果** → `parser/pdf_parser.py` 返回 DataFrame
5. **显示表格** → `app.py` 渲染到前端

## 🔧 开发提示

- **解析逻辑**：在 `parser/pdf_parser.py` 中实现
- **前端样式**：在 `templates/index.html` 中修改
- **路由处理**：在 `app.py` 中修改
- **上传文件**：保存在 `uploads/` 目录

## 📚 相关文档

- `README.md` - 完整项目说明
- `requirements.txt` - 依赖列表

