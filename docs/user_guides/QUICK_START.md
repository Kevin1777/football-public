# 快速开始 - 百度 OCR 自动登录

## ⚡ 快速配置（3 步完成）

### 步骤 1: 安装依赖

```bash
pip install python-dotenv requests
```

### 步骤 2: 配置 API 密钥

你的百度 OCR 配置信息：

- **AppID**: 7203771
- **API Key**: h20qCP8BxCm5DrsYBD3mn3jB
- **Secret Key**: PHNsMwFExSrxUhQfpgUgdgUQ5RMTylyJ

已自动为你创建了`.env`文件，包含以下内容：

```bash
BAIDU_OCR_ENABLED=1
BAIDU_OCR_API_KEY=h20qCP8BxCm5DrsYBD3mn3jB
BAIDU_OCR_SECRET_KEY=PHNsMwFExSrxUhQfpgUgdgUQ5RMTylyJ
```

### 步骤 3: 测试功能

```bash
python test_ocr_login.py
```

## 🎯 功能说明

系统现在会在以下情况自动触发 OCR 登录：

1. **请求明细时登录失效** → 自动 OCR 登录 → 继续请求
2. **批量采集时登录失效** → 自动 OCR 登录 → 继续采集
3. **定时任务时登录失效** → 自动 OCR 登录 → 继续任务

## 📝 使用示例

启动应用后，当登录状态失效时，你会看到：

```
[WARNING] ⚠️  检测到登录状态失效，尝试自动OCR登录...
[INFO] 🤖 开始自动OCR登录流程...
[INFO] 🔄 第 1/3 次尝试...
[INFO] 📷 正在获取验证码...
[INFO] 🔍 正在OCR识别验证码...
[INFO] ✅ OCR识别成功: 'abcd'
[INFO] 📝 正在提交登录...
[INFO] ✅ 自动登录成功！
[INFO] ✅ 自动登录成功，请重试请求
```

系统会自动完成登录，然后提示你重试之前失败的请求。

## 🔧 高级配置

查看完整文档：[OCR_AUTO_LOGIN.md](OCR_AUTO_LOGIN.md)

## ❓ 常见问题

**Q: 如何禁用自动登录？**
A: 修改`.env`文件，设置`BAIDU_OCR_ENABLED=0`

**Q: OCR 识别失败怎么办？**
A: 系统会自动重试 3 次，如果都失败会提示手动登录

**Q: 如何查看识别的验证码？**
A: 查看项目根目录下的`captcha.png`文件

**Q: API 调用次数有限制吗？**
A: 百度 OCR 免费版每月有调用次数限制，请注意使用情况

## 🎉 完成

现在你的系统已经具备自动登录能力！当检测到登录失效时会自动处理，无需人工干预。
