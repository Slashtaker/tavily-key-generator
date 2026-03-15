"""
Tavily 注册核心模块 - 简化版
"""
import os
import re
import time
import random
import string
import requests as std_requests
from curl_cffi import requests
from camoufox.sync_api import Camoufox

from config import EMAIL_API_URL, EMAIL_API_TOKEN, EMAIL_DOMAIN, DUCKMAIL_API_URL, DUCKMAIL_API_KEY, FIXED_PASSWORD

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────

LOCAL_SOLVER_URL = "http://127.0.0.1:5072"
TURNSTILE_SITEKEY = "0x4AAAAAAAQFNSW6xordsuIq"
_HERE = os.path.dirname(os.path.abspath(__file__))
_SAVE_FILE = os.path.join(_HERE, "accounts.txt")

def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def _save_account(email, password, api_key=None):
    with open(_SAVE_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{email},{password},{api_key or ''}\n")

# ──────────────────────────────────────────────
# 邮箱相关
# ──────────────────────────────────────────────

def create_email(provider="cloudflare"):
    """生成随机邮箱地址

    Args:
        provider: "cloudflare" 或 "duckmail"
    """
    username = f"tavily-{rand_str()}"
    password = FIXED_PASSWORD  # 使用固定密码

    if provider == "duckmail":
        # 获取 DuckMail 可用域名
        try:
            r = std_requests.get(
                f"{DUCKMAIL_API_URL}/domains",
                headers={"Authorization": f"Bearer {DUCKMAIL_API_KEY}"},
                timeout=10
            )
            if r.status_code == 200:
                domains = r.json()
                if domains and len(domains) > 0:
                    domain = domains[0].get('domain', 'duckmail.sbs')
                else:
                    domain = 'duckmail.sbs'
            else:
                domain = 'duckmail.sbs'
        except:
            domain = 'duckmail.sbs'

        email = f"{username}@{domain}"

        # 创建 DuckMail 账户
        try:
            r = std_requests.post(
                f"{DUCKMAIL_API_URL}/accounts",
                json={"address": email, "password": password},
                headers={"Authorization": f"Bearer {DUCKMAIL_API_KEY}"},
                timeout=10
            )
            if r.status_code == 201:
                print(f"✅ 邮箱: {email}")
                return email, password, provider
            else:
                print(f"⚠️  DuckMail 创建失败: {r.status_code}, 使用 Cloudflare")
                return create_email("cloudflare")
        except Exception as e:
            print(f"⚠️  DuckMail 错误: {e}, 使用 Cloudflare")
            return create_email("cloudflare")

    # Cloudflare Email Workers（默认）
    email = f"{username}@{EMAIL_DOMAIN}"
    print(f"✅ 邮箱: {email}")
    return email, password, "cloudflare"

def get_verification_link(email, password, provider, timeout=120):
    """等待验证邮件并提取验证链接

    Args:
        email: 邮箱地址
        password: 邮箱密码
        provider: "cloudflare" 或 "duckmail"
        timeout: 超时时间（秒）
    """
    print(f"⏳ 等待验证邮件（最多 {timeout} 秒）...", end="", flush=True)

    start_time = time.time()
    token = None

    # DuckMail 需要先获取 token
    if provider == "duckmail":
        try:
            r = std_requests.post(
                f"{DUCKMAIL_API_URL}/token",
                json={"address": email, "password": password},
                timeout=10
            )
            if r.status_code == 200:
                token = r.json().get('token')
            else:
                print(f"\n⚠️  DuckMail 认证失败: {r.status_code}")
                return None
        except Exception as e:
            print(f"\n⚠️  DuckMail 认证错误: {e}")
            return None

    while time.time() - start_time < timeout:
        try:
            if provider == "duckmail":
                # DuckMail API
                r = std_requests.get(
                    f"{DUCKMAIL_API_URL}/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )

                if r.status_code == 200:
                    messages = r.json()

                    for msg in messages:
                        subject = msg.get("subject", "").lower()
                        if "verify" in subject or "tavily" in subject:
                            # 获取完整邮件内容
                            msg_id = msg.get("id")
                            r_detail = std_requests.get(
                                f"{DUCKMAIL_API_URL}/messages/{msg_id}",
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=10
                            )

                            if r_detail.status_code == 200:
                                detail = r_detail.json()
                                html = detail.get("html", "")
                                text = detail.get("text", "")
                                content = html + " " + text

                                match = re.search(r'https://[^\s<>"]*verif[^\s<>"]*', content, re.IGNORECASE)
                                if match:
                                    verify_url = match.group(0)
                                    print(f"\n✅ 找到验证链接")
                                    return verify_url
            else:
                # Cloudflare Email Workers API
                r = std_requests.get(
                    f"{EMAIL_API_URL}/messages",
                    params={"address": email},
                    headers={"Authorization": f"Bearer {EMAIL_API_TOKEN}"},
                    timeout=10
                )

                if r.status_code == 200:
                    messages = r.json().get("messages", [])

                    for msg in messages:
                        subject = msg.get("subject", "").lower()
                        if "verify" in subject or "tavily" in subject.lower():
                            # 提取验证链接
                            html = msg.get("html", "")
                            text = msg.get("text", "")
                            content = html + " " + text

                            match = re.search(r'https://[^\s<>"]*verif[^\s<>"]*', content, re.IGNORECASE)
                            if match:
                                verify_url = match.group(0)
                                print(f"\n✅ 找到验证链接")
                                return verify_url

            time.sleep(5)
            print(".", end="", flush=True)

        except Exception as e:
            print(f"\n⚠️  检查邮件出错: {e}")
            time.sleep(5)

    print(f"\n❌ 验证邮件超时")
    return None

# ──────────────────────────────────────────────
# 浏览器验证
# ──────────────────────────────────────────────

def verify_with_browser(verify_url, session):
    """使用 Camoufox 处理验证链接并获取 API Key"""
    print("🌐 启动浏览器验证...")

    try:
        with Camoufox(headless=True) as browser:
            page = browser.new_page()

            # 转移 cookies
            cookies = []
            for name, value in session.cookies.items():
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": ".tavily.com",
                    "path": "/"
                })

            # 同时添加 auth.tavily.com 的 cookies
            for name, value in session.cookies.items():
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": ".auth.tavily.com",
                    "path": "/"
                })

            page.context.add_cookies(cookies)

            # 访问验证链接
            page.goto(verify_url, wait_until="networkidle", timeout=60000)

            # 等待跳转到主页
            page.wait_for_url("**/app.tavily.com/**", timeout=60000)

            # 等待页面完全加载
            time.sleep(5)

            # 访问主页获取 API Key
            print("🔑 获取 API Key...")
            page.goto("https://app.tavily.com/home", wait_until="networkidle")
            time.sleep(3)

            # 从页面 HTML 中提取 API Key
            html = page.content()
            # 匹配完整的 API Key 格式
            api_key_matches = re.findall(r'tvly-[a-zA-Z0-9_-]{50,}', html)

            if api_key_matches:
                # 取最长的那个（排除占位符）
                api_keys = [k for k in api_key_matches if k != "tvly-YOUR_API_KEY"]
                if api_keys:
                    api_key = max(api_keys, key=len)
                    browser.close()
                    print("✅ 浏览器验证完成")
                    return api_key

            browser.close()
            print("⚠️  未找到 API Key")
            return None

    except Exception as e:
        print(f"❌ 浏览器验证失败: {e}")
        return None

# ──────────────────────────────────────────────
# Turnstile Solver
# ──────────────────────────────────────────────

def solve_turnstile(url):
    """调用本地 Solver 解析 Turnstile"""
    try:
        r = std_requests.get(
            f"{LOCAL_SOLVER_URL}/turnstile",
            params={"url": url, "sitekey": TURNSTILE_SITEKEY},
            timeout=10
        )
        
        if r.status_code != 200:
            print(f"❌ Solver 请求失败: {r.status_code}")
            return None
        
        task_id = r.json().get("taskId")
        if not task_id:
            print("❌ 未获取到 Task ID")
            return None
        
        # 轮询结果
        for _ in range(60):
            time.sleep(2)
            res = std_requests.get(
                f"{LOCAL_SOLVER_URL}/result",
                params={"id": task_id},
                timeout=10
            )
            
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "ready":
                    token = data.get("solution", {}).get("token")
                    if token:
                        return token
                elif data.get("status") == "CAPTCHA_FAIL":
                    print("❌ Turnstile 解析失败")
                    return None
        
        print("❌ Turnstile 超时")
        return None
        
    except Exception as e:
        print(f"❌ Solver 异常: {e}")
        return None

# ──────────────────────────────────────────────
# Tavily 注册
# ──────────────────────────────────────────────

def register(email, password, provider="cloudflare"):
    """
    注册 Tavily 账号
    返回: API Key 或 None
    """
    s = requests.Session(impersonate="chrome")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    # 1. 访问登录页
    r1 = s.get("https://app.tavily.com/sign-in", headers=headers)
    if r1.status_code != 200:
        print("❌ 无法访问登录页")
        return None
    
    # 提取 state
    state_m = re.search(r'state=([^"&]+)', r1.text)
    if not state_m:
        print("❌ 未找到 state")
        return None
    state = state_m.group(1)
    
    # 2. 第一次 Turnstile
    print("🔐 Turnstile (1/2)...")
    token1 = solve_turnstile(f"https://auth.tavily.com/u/login/identifier?state={state}")
    if not token1:
        return None
    print("✅ Turnstile OK")
    
    # 3. 提交邮箱
    r2 = s.post(
        f"https://auth.tavily.com/u/login/identifier?state={state}",
        data={
            "state": state,
            "username": email,
            "action": "default",
            "captcha": token1
        },
        headers=headers,
        allow_redirects=False
    )
    
    if r2.status_code != 302:
        print("❌ 邮箱提交失败")
        return None
    
    # 检查是否跳转到注册页
    loc = r2.headers.get('Location', '')
    if '/login/password' in loc:
        # 已有账号，切换到注册
        r2_text = s.get(f"https://auth.tavily.com{loc}", headers=headers).text
        signup_m = re.search(r'href="(/u/signup/identifier[^"]*)"', r2_text)
        if not signup_m:
            print("❌ 无法切换到注册页")
            return None
        
        signup_url = f"https://auth.tavily.com{signup_m.group(1)}"
        r2 = s.get(signup_url, headers=headers)
        
        # 重新提取 state
        state_m2 = re.search(r'name="state"\s+value="([^"]+)"', r2.text)
        if state_m2:
            state = state_m2.group(1)
        
        # 第二次 Turnstile
        print("🔐 Turnstile (2/2)...")
        token2 = solve_turnstile(signup_url)
        if not token2:
            return None
        print("✅ Turnstile OK")
        
        # 提交注册
        r3 = s.post(
            signup_url,
            data={
                "state": state,
                "email": email,
                "action": "default",
                "captcha": token2
            },
            headers=headers,
            allow_redirects=True
        )
    else:
        r3 = s.get(f"https://auth.tavily.com{loc}", headers=headers, allow_redirects=True)
    
    # 4. 到达密码页
    if '/password' not in r3.url:
        print(f"❌ 未到达密码页面: {r3.url}")
        return None
    
    # 第三次 Turnstile
    print("🔐 Turnstile (3/3)...")
    token3 = solve_turnstile(r3.url)
    if not token3:
        return None
    print("✅ Turnstile OK")
    
    # 提取 state 和 email
    state_m3 = re.search(r'name="state"\s+value="([^"]+)"', r3.text)
    if state_m3:
        state = state_m3.group(1)
    email_m = re.search(r'name="email"\s+value="([^"]*)"', r3.text)
    email_val = email_m.group(1) if email_m else email
    
    # 5. 提交密码
    r4 = s.post(
        r3.url,
        data={
            "state": state,
            "email": email_val,
            "password": password,
            "action": "default",
            "captcha": token3
        },
        headers=headers,
        allow_redirects=False
    )
    
    if r4.status_code != 302:
        print(f"❌ 密码提交失败 (状态码: {r4.status_code})")
        return None
    
    # 6. 跟随回调
    callback = r4.headers.get('Location', '')
    if callback.startswith('/'):
        callback = f"https://auth.tavily.com{callback}"

    r5 = s.get(callback, allow_redirects=True)

    if 'app.tavily.com' not in r5.url:
        print("❌ 登录失败")
        return None

    # 7. 检查账号状态
    print("检查账号状态...")
    r_account = s.get("https://app.tavily.com/api/account")

    if r_account.status_code == 403:
        account_data = r_account.json()
        if account_data.get('code') == 'email_not_verified':
            print("📧 需要邮件验证")
            verify_url = get_verification_link(email, password, provider, timeout=60)
            if not verify_url:
                print("❌ 未收到验证邮件")
                _save_account(email, password, None)
                return None

            # 使用浏览器处理验证链接并直接获取 API Key
            api_key = verify_with_browser(verify_url, s)
            if not api_key:
                print("❌ 验证失败或未获取到 API Key")
                _save_account(email, password, None)
                return None

            # 保存账号
            _save_account(email, password, api_key)
            print(f"🎉 注册成功")
            print(f"   邮箱: {email}")
            print(f"   密码: {password}")
            print(f"   Key : {api_key}")
            return api_key

    # 8. 获取 API Key
    api_key = get_api_key(s, email, password)
    
    if api_key:
        _save_account(email, password, api_key)
        print(f"🎉 注册成功")
        print(f"   邮箱: {email}")
        print(f"   密码: {password}")
        print(f"   Key : {api_key}")
        return api_key
    else:
        _save_account(email, password, None)
        print("⚠️  注册成功，未获取到 API Key")
        print(f"   邮箱: {email}")
        print(f"   密码: {password}")
        return "SUCCESS_NO_KEY"

def get_api_key(session, email, password):
    """获取 API Key（不创建新的）"""
    time.sleep(3)
    session.get("https://app.tavily.com/home")
    time.sleep(2)

    r_orgs = session.get("https://app.tavily.com/api/organizations")
    if r_orgs.status_code != 200:
        return None

    orgs = r_orgs.json()

    if not orgs:
        print("⚠️  没有找到组织")
        return None

    org_id = orgs[0].get('id') or orgs[0].get('oid')
    if not org_id:
        return None

    # 直接获取已有的 API Keys（不创建新的）
    r_keys = session.get(f"https://app.tavily.com/api/keys?oid={org_id}")
    if r_keys.status_code == 200:
        keys = r_keys.json()
        if keys and len(keys) > 0:
            return keys[0].get('key')

    print("⚠️  未找到 API Key")
    return None
