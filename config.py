"""
Tavily 注册工具 - 配置文件
修改此文件以匹配你的环境
"""

# ──���────────── 邮箱配置 ─────────────
# Cloudflare Email Workers
EMAIL_API_URL = "https://mail.nashome.me"
EMAIL_API_TOKEN = "0e5ad283dc25405dfdeb47fbb876648ce95d9daadda92d4175a17e3e426c0d4b"
EMAIL_DOMAIN = "nashome.me"

# DuckMail
DUCKMAIL_API_URL = "https://api.duckmail.sbs"
DUCKMAIL_API_KEY = "dk_05d110d3bb873e617406f0946fb9e55f02f6ab926aeac06ac7419e9ac62d5d08"

# ───────────── 代理服务器配置（上传目标）─────────────
SERVER_URL = "https://tavily.hunters.works"
SERVER_ADMIN_PASSWORD = "Jelly120425"

# ───────────── 注册默认参数 ─────────────
DEFAULT_COUNT = 5                    # 默认注册数量
DEFAULT_DELAY = 10                   # 每次注册间隔（秒）
FIXED_PASSWORD = "Tavily2024!@"      # 固定密码（方便登录）
