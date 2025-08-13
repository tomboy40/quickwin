# Confluence Automation Script

这个Python脚本可以自动化创建Confluence页面，并处理CSV数据。脚本仅使用Python标准库，无需安装第三方依赖。

## 功能特性

- ✅ **Confluence REST API集成** - 使用基本认证连接到Confluence服务器
- ✅ **CSV数据处理** - 读取和处理CSV文件，支持数据过滤和格式化
- ✅ **条件单元格格式化** - 根据Impact/Risk列的值自动应用颜色格式
- ✅ **可折叠部分** - 将标准变更放在可折叠的部分中
- ✅ **Confluence存储格式** - 生成正确的XHTML格式内容
- ✅ **错误处理和日志** - 完整的错误处理和调试日志

## 系统要求

- Python 3.6+
- 仅使用Python标准库（无第三方依赖）
- 访问Confluence服务器的权限

## 安装和设置

### 1. 下载脚本

将以下文件下载到您的工作目录：
- `confluence_automation.py` - 主脚本
- `test_confluence_automation.py` - 测试脚本

### 2. 准备CSV文件

确保您的CSV文件名为 `extracted_output.csv`，并包含以下列：

| 列名 | 描述 | 示例 |
|------|------|------|
| Change ID | 变更ID | CHG001 |
| Summary | 变更摘要 | Database maintenance window |
| Assignee | 负责人 | John Smith |
| Impact | 影响级别 | High/Medium/Low/Critical |
| Risk | 风险级别 | High/Medium/Low/Critical/Moderate |
| Date | 日期 | 2025-01-18 |
| Tags | 标签 | Call_out 或其他值 |

### 3. 设置环境变量

设置Confluence认证信息：

**Windows (PowerShell):**
```powershell
$env:CONFLUENCE_USERNAME = "your_username"
$env:CONFLUENCE_PASSWORD = "your_password"
```

**Windows (Command Prompt):**
```cmd
set CONFLUENCE_USERNAME=your_username
set CONFLUENCE_PASSWORD=your_password
```

**Linux/Mac:**
```bash
export CONFLUENCE_USERNAME="your_username"
export CONFLUENCE_PASSWORD="your_password"
```

## 使用方法

### 运行主脚本

```bash
python confluence_automation.py
```

### 运行测试脚本

在实际使用前，建议先运行测试脚本验证功能：

```bash
python test_confluence_automation.py
```

测试脚本会：
- 验证CSV文件读取和处理
- 测试HTML生成和格式化
- 生成测试输出文件 `test_output.html`
- 不会连接到实际的Confluence服务器

## 配置选项

在 `confluence_automation.py` 文件顶部，您可以修改以下配置：

```python
# 配置常量
CONFLUENCE_BASE_URL = "https://htc.tw.com"  # Confluence服务器URL
PARENT_PAGE_ID = "123456"                   # 父页面ID
CSV_FILENAME = "extracted_output.csv"       # CSV文件名
```

## 输出说明

### 页面标题格式

脚本会自动生成页面标题：`Weekend Change Note - [当前周的周六日期]`

例如：`Weekend Change Note - 2025-01-18`

### 表格组织

脚本会根据Tags列的值创建两个表格：

1. **Critical Changes (Call Out Required)** - 显示Tags="Call_out"的行
   - 正常显示，不可折叠
   - 用于需要特别关注的重要变更

2. **Standard Changes** - 显示其他Tags值的行
   - 放在可折叠部分中
   - 用于常规变更

### 条件格式化

对于Impact和Risk列，脚本会自动应用颜色格式：

- 🔴 **红色背景**: High, Critical
- 🟠 **橙色背景**: Medium, Moderate  
- 🟢 **绿色背景**: 其他值（Low, Normal等）

### 新增列

脚本会自动添加两个新列：
- **Implement status** - 实施状态（空白，供手动填写）
- **Comment (Mandatory)** - 评论（必填），其中"Mandatory"显示为红色

## 故障排除

### 常见错误

1. **认证失败**
   ```
   Authentication failed. Please check your credentials.
   ```
   - 检查环境变量是否正确设置
   - 验证用户名和密码是否正确

2. **CSV文件未找到**
   ```
   CSV file not found: extracted_output.csv
   ```
   - 确保CSV文件在当前工作目录中
   - 检查文件名是否正确

3. **缺少必需列**
   ```
   Missing required columns: ['Tags']
   ```
   - 检查CSV文件是否包含所有必需的列
   - 确保列名完全匹配（区分大小写）

4. **SSL连接错误**
   ```
   SSL: UNEXPECTED_EOF_WHILE_READING
   ```
   - 检查网络连接
   - 验证Confluence服务器URL是否正确
   - 可能需要配置代理或SSL设置

### 调试

脚本会生成详细的日志文件 `confluence_automation.log`，包含：
- 执行步骤的详细信息
- 错误消息和堆栈跟踪
- API请求和响应信息

## 安全注意事项

- 🔒 **不要在代码中硬编码密码**
- 🔒 **使用环境变量存储敏感信息**
- 🔒 **定期更换密码**
- 🔒 **确保日志文件不包含敏感信息**

## 示例输出

运行成功后，您会看到类似以下的输出：

```
2025-08-14 00:07:56,478 - INFO - Starting Confluence automation script
2025-08-14 00:07:56,478 - INFO - Successfully read 7 rows from extracted_output.csv
2025-08-14 00:07:56,478 - INFO - Filtered data: 3 Call_out rows, 4 other rows
2025-08-14 00:07:56,478 - INFO - Creating page: Weekend Change Note - 2025-08-16
2025-08-14 00:07:59,228 - INFO - Successfully created page: Weekend Change Note - 2025-08-16
2025-08-14 00:07:59,228 - INFO - Page ID: 789012
2025-08-14 00:07:59,228 - INFO - Page URL: /pages/viewpage.action?pageId=789012
```

## 技术细节

### 使用的Python标准库模块

- `urllib.request` - HTTP请求
- `urllib.parse` - URL编码
- `json` - JSON数据处理
- `csv` - CSV文件处理
- `base64` - 基本认证编码
- `html` - HTML转义
- `logging` - 日志记录
- `datetime` - 日期处理
- `os` - 环境变量

### Confluence Storage Format

脚本生成的内容使用Confluence Storage Format (XHTML)，包括：
- 标准HTML表格标签
- Confluence特定的宏（如expand宏）
- 内联样式用于条件格式化

## 许可证

此脚本仅供内部使用，请遵守您组织的软件使用政策。