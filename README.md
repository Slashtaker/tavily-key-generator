# Tavily 全自动注册工具

自动注册 Tavily 账号并获取 API Key，支持邮件验证的完整自动化工具。

## ✨ 核心特性

- 🚀 **零配置启动** - 自动创建虚拟环境并安装依赖
- 🔐 **本地 Turnstile Solver** - 免费稳定的验证码解决方案
- 📧 **邮件自动验证** - 使用 Cloudflare Email Workers 自动接收验证邮件
- 💾 **自动保存账号** - 格式兼容代理服务器直接导入
- 🎨 **交互式界面** - 简洁友好的命令行交互
- 🌐 **跨平台支持** - Windows / macOS / Linux

## 🚀 快速开始

### 一键运行

```bash
python3 run.py
```

就这么简单！脚本会自动：
1. 创建虚拟环境
2. 安装所有依赖
3. 下载浏览器
4. 启动 Turnstile Solver
5. 进入交互界面

### 使用流程

1. 运行 `python3 run.py`
2. 选择 `1` 开始注册
3. 输入注册数量（默认 5）
4. 输入间隔秒数（默认 10）
5. 选择是否上传到代理服务器
6. 等待注册完成

生成的账号保存在 `accounts.txt`，格式：
```
email,password,api_key
email,password,api_key
...
```

## 📁 项目结构

```
tavily-key-generator/
├── run.py                  # 主程序（一键启动）
├── tavily_core.py          # 注册核心逻辑
├── api_solver.py           # Turnstile Solver
├── config.py               # 配置文件
├── requirements.txt        # Python 依赖
├── browser_configs.py      # Solver 浏览器配置
├── db_results.py           # Solver 数据库
├── proxy/                  # 代理服务器（可选部署）
│   ├── server.py
│   ├── database.py
│   ├── key_pool.py
│   └── templates/
└── README.md
```

## ⚙️ 配置说明

编辑 `config.py` 自定义配置：

```python
# 邮箱配置（Cloudflare Email Workers）
EMAIL_API_URL = "https://mail.nashome.me"
EMAIL_API_TOKEN = "your-token"
EMAIL_DOMAIN = "nashome.me"

# 代理服务器配置（上传目标）
SERVER_URL = "https://tavily.hunters.works"
SERVER_ADMIN_PASSWORD = "your-password"

# 默认参数
DEFAULT_COUNT = 5      # 默认注册数量
DEFAULT_DELAY = 10     # 每次注册间隔（秒）
```

## 🔧 技术架构

- **HTTP 客户端**: curl_cffi（模拟真实浏览器 TLS 指纹）
- **验证码破解**: 本地 Turnstile Solver（Camoufox 浏览器自动化）
- **邮件接收**: Cloudflare Email Workers API
- **认证流程**: Auth0 Universal Login

## 📦 依赖说明

所有依赖会自动安装，无需手动操作：

- `curl_cffi` - HTTP 客户端（绕过 Cloudflare）
- `requests` - 标准 HTTP 库
- `quart` - 异步 Web 框架（Solver）
- `camoufox` - 反检测浏览器（Solver）
- `patchright` - Playwright 分支（Solver）
- `rich` - 终端美化（Solver）

## 🎯 代理服务器

项目内置代理服务器（`proxy/` 目录），支持：
- API Key 池管理
- 自动轮询使用
- 配额限制
- 使用统计
- Web 控制台

### 部署代理服务器

```bash
cd proxy/
docker compose up -d
```

访问 `http://localhost:9874` 进入管理控制台。

### 批量导入 API Key

在控制台中选择"批量导入"，粘贴 `accounts.txt` 内容即可。

## ⚠️ 注意事项

- 首次运行会下载 Camoufox 浏览器（约 200MB）
- Solver 启动需要 10-15 秒初始化时间
- 每个 API Key 有 1000 次免费调用额度（需要邮件验证激活）
- 建议批量注册时设置 10-15 秒延迟
- 邮件验证最多等待 120 秒

## 🐛 故障排查

**Solver 无法启动**：
```bash
# 检查端口占用
lsof -i :5072

# 手动清理进程
kill -9 $(lsof -ti :5072)
```

**注册失败**：
- 确认 Solver 正在运行（会显示"✅ Solver 已启动"）
- 检查网络连接
- 确认邮箱 API Token 有效

**邮件验证超时**：
- 检查 `config.py` 中的 `EMAIL_API_TOKEN` 是否正确
- 访问 https://mail.nashome.me 测试邮箱服务是否正常
- 增加等待时间（修改 `tavily_core.py` 中的 `timeout` 参数）

**虚拟环境问题**：
```bash
# 删除虚拟环境重新创建
rm -rf venv
python3 run.py
```

## 📄 输出文件

- `accounts.txt` - 账号信息（email,password,api_key）
- `venv/` - 虚拟环境（自动创建，已加入 .gitignore）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📜 许可证

MIT License
