import json
import os
import re
import time
import random
import secrets
import hashlib
import base64
import argparse
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional
import urllib.parse
import urllib.request
import urllib.error

from curl_cffi import requests
import requests as std_requests # 专门用于 CPA 请求，避免代理冲突

# 引入 LuckMail SDK
from luckmail import LuckMailClient

# ==========================================
# 外部配置文件加载
# ==========================================
def load_external_config(config_path="config.json"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"错误: 找不到配置文件 '{config_path}'，程序无法启动！")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        raise RuntimeError(f"错误: 解析 config.json 失败: {e}")
    return config

CONFIG = load_external_config()

# 读取 LuckMail 配置
luckmail_cfg = CONFIG.get("luckmail_config", {})
LUCKMAIL_BASE_URL = luckmail_cfg.get("LUCKMAIL_BASE_URL", "https://mails.luckyous.com/")
LUCKMAIL_API_KEY = luckmail_cfg.get("LUCKMAIL_API_KEY", "")
LUCKMAIL_PROJECT_CODE = luckmail_cfg.get("LUCKMAIL_PROJECT_CODE", "openai")
LUCKMAIL_EMAIL_TYPE = luckmail_cfg.get("LUCKMAIL_EMAIL_TYPE", "ms_imap")
LUCKMAIL_DOMAIN = luckmail_cfg.get("LUCKMAIL_DOMAIN", "hotmail.com")

if not LUCKMAIL_API_KEY:
    raise ValueError("致命错误: config.json 中的 LUCKMAIL_API_KEY 不能为空！")

luckmail_client = LuckMailClient(base_url=LUCKMAIL_BASE_URL, api_key=LUCKMAIL_API_KEY)


# ==========================================
# CPA 系统：上传、查询与清理模块
# ==========================================

def push_to_cliproxyapi(filename: str, token_json_str: str, auth_password: str, full_api_url: str) -> bool:
    """将注册成功的 Token 以文件形式直接上传到 CPA"""
    print(f"[*] 开始推送 Token 至: {full_api_url}")
    try:
        headers = {"Authorization": auth_password, "Accept": "*/*"}
        files = {"file": (filename, token_json_str.encode('utf-8'), "application/json")}
        resp = std_requests.post(full_api_url, headers=headers, files=files, proxies={"http": "", "https": ""}, timeout=15, verify=False)
        
        if resp.status_code in [200, 201]:
            print(f"[+] 推送成功! 状态码: {resp.status_code}")
            return True
        else:
            print(f"[-] 推送失败! 状态码: {resp.status_code}, 返回: {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"[-] 推送请求发生异常: {e}")
        return False
# ==========================================
# 新增: 通过 Token 获取验证码 API
# ==========================================
def get_code_by_token(token: str, base_url: str, timeout: int = 300, interval: float = 3.0) -> str:
    """轮询指定的 Token 接口获取验证码"""
    import time
    start_time = time.time()
    # 确保 URL 拼接正确
    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/v1/openapi/email/token/{token}/code"
    
    print(f"[*] 正在通过 API 轮询预设 Token 的验证码...")
    while time.time() - start_time < timeout:
        try:
            resp = std_requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0 and data.get("data", {}).get("has_new_mail"):
                    code = data.get("data", {}).get("verification_code")
                    if code:
                        return code
        except Exception as e:
            pass # 忽略网络请求错误，继续轮询
        time.sleep(interval)
    return ""

def check_and_clean_cpa(cpa_url: str, cpa_auth: str) -> int:
    """
    检查 CPA 云端的文件状态。
    1. 获取全部文件。
    2. 清理 status == "error" 或已触及使用限制 (usage limit reached) 的文件。
    3. 返回剩余 (健康) 的文件数量。
    返回 -1 代表获取失败。
    """
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": cpa_auth,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print(f"\n[*] 🛡️ [守护模式] 正在连接 CPA 系统，获取并清理失效/超限账号...")
    try:
        resp = std_requests.get(cpa_url, headers=headers, proxies={"http": "", "https": ""}, timeout=30)
        if resp.status_code != 200:
            print(f"[-] 获取 CPA 列表失败！状态码: {resp.status_code}, 返回: {resp.text[:100]}")
            return -1
            
        data = resp.json()
        files = data.get("files", [])
    except Exception as e:
        print(f"[-] 请求 CPA 文件列表时发生网络异常: {e}")
        return -1

    valid_count = 0
    error_files = []
    
    for f in files:
        status = f.get("status")
        status_msg = str(f.get("status_message", ""))
        
        if status == "error":
            # 状态是 error，但如果消息里包含限额提示，说明只是暂时没额度，不删除，记入有效库存
            if "The usage limit has been reached" in status_msg:
                valid_count += 1
            else:
                # 状态是 error 且没有限额提示，说明是真的失效号，加入清理列表
                error_files.append(f.get("name"))
        else:
            valid_count += 1
    """
     # 筛选失效文件与健康文件 原有逻辑（仅判断 status 字段）：
    for f in files:
        if f.get("status") == "error":
            error_files.append(f.get("name"))
        else:
            valid_count += 1     
    """                  
    if error_files:
        print(f"[*] 发现 {len(error_files)} 个异常(error 或达到限额)的文件，开始执行清理...")
        success_del = 0
        for name in error_files:
            if not name: continue
            try:
                del_resp = std_requests.delete(cpa_url, headers=headers, params={"name": name}, proxies={"http": "", "https": ""}, timeout=10)
                if del_resp.status_code in [200, 204]:
                    success_del += 1
                    print(f"  [+] 已删除: {name}")
                else:
                    print(f"  [-] 删除失败: {name} (HTTP {del_resp.status_code})")
            except Exception:
                pass
            time.sleep(0.2) # 防止并发过快
        print(f"[*] 清理任务结束。成功清除 {success_del} 个死号。")
    else:
        print(f"[*] CPA 云端状态良好，未发现失效账号。")

    print(f"[+] CPA 云端当前可用账号 (Valid): {valid_count} 个")
    return valid_count

# ==========================================
# OAuth 授权与核心算法函数
# ==========================================

AUTH_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_REDIRECT_URI = f"http://localhost:1455/auth/callback"
DEFAULT_SCOPE = "openid email profile offline_access"

def _b64url_no_pad(raw: bytes) -> str: return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
def _sha256_b64url_no_pad(s: str) -> str: return _b64url_no_pad(hashlib.sha256(s.encode("ascii")).digest())
def _random_state(nbytes: int = 16) -> str: return secrets.token_urlsafe(nbytes)
def _pkce_verifier() -> str: return secrets.token_urlsafe(64)

def _parse_callback_url(callback_url: str) -> Dict[str, Any]:
    candidate = callback_url.strip()
    if not candidate: return {"code": "", "state": "", "error": "", "error_description": ""}
    if "://" not in candidate:
        if candidate.startswith("?"): candidate = f"http://localhost{candidate}"
        elif any(ch in candidate for ch in "/?#") or ":" in candidate: candidate = f"http://{candidate}"
        elif "=" in candidate: candidate = f"http://localhost/?{candidate}"
    parsed = urllib.parse.urlparse(candidate)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    fragment = urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True)
    for key, values in fragment.items():
        if key not in query or not query[key] or not (query[key][0] or "").strip(): query[key] = values
    def get1(k: str) -> str: return (query.get(k, [""])[0] or "").strip()
    code, state, error, error_desc = get1("code"), get1("state"), get1("error"), get1("error_description")
    if code and not state and "#" in code: code, state = code.split("#", 1)
    return {"code": code, "state": state, "error": error, "error_description": error_desc}

def _jwt_claims_no_verify(id_token: str) -> Dict[str, Any]:
    if not id_token or id_token.count(".") < 2: return {}
    payload_b64 = id_token.split(".")[1]
    pad = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try: return json.loads(base64.urlsafe_b64decode((payload_b64 + pad).encode("ascii")).decode("utf-8"))
    except: return {}

def _decode_jwt_segment(seg: str) -> Dict[str, Any]:
    raw = (seg or "").strip()
    if not raw: return {}
    pad = "=" * ((4 - (len(raw) % 4)) % 4)
    try: return json.loads(base64.urlsafe_b64decode((raw + pad).encode("ascii")).decode("utf-8"))
    except: return {}

def _to_int(v: Any) -> int:
    try: return int(v)
    except: return 0

def _ssl_verify() -> bool: return os.getenv("OPENAI_SSL_VERIFY", "1").strip().lower() not in {"0", "false", "no", "off"}

def _normalize_proxy(proxy: Optional[str], scheme: str = "http") -> Optional[str]:
    raw = (proxy or "").strip()
    if not raw: return None
    if "://" in raw: return raw
    proxy_scheme = "socks5h" if scheme.lower() in {"socks5", "socks5h"} else "http"
    parts = raw.split(":")
    if len(parts) == 2: return f"{proxy_scheme}://{parts[0]}:{parts[1]}"
    if len(parts) == 4: return f"{proxy_scheme}://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return f"{proxy_scheme}://{raw}"

def _detect_proxy_info(session: requests.Session) -> tuple[Optional[str], Optional[str]]:
    ip_addr, loc = None, None
    try:
        ipv4_data = session.get("https://api4.ipify.org?format=json", timeout=20).json()
        ip_addr = str(ipv4_data.get("ip") or "").strip() or None
    except: pass
    try:
        trace = session.get("https://cloudflare.com/cdn-cgi/trace", timeout=25).text
        if m := re.search(r"^ip=(.+)$", trace, re.MULTILINE): ip_addr = m.group(1)
        if m := re.search(r"^loc=(.+)$", trace, re.MULTILINE): loc = m.group(1)
    except: pass
    return ip_addr, loc

def _post_with_retry(session: requests.Session, url: str, *, headers: Dict[str, Any], data: Any = None, json_body: Any = None, proxies: Any = None, timeout: int = 30, retries: int = 2) -> Any:
    last_error = None
    for attempt in range(retries + 1):
        try:
            if json_body is not None: return session.post(url, headers=headers, json=json_body, proxies=proxies, verify=_ssl_verify(), timeout=timeout)
            return session.post(url, headers=headers, data=data, proxies=proxies, verify=_ssl_verify(), timeout=timeout)
        except Exception as e:
            last_error = e
            if attempt >= retries: break
            time.sleep(2 * (attempt + 1))
    raise last_error or RuntimeError("Request failed without exception")

def _post_form(url: str, data: Dict[str, str], timeout: int = 30) -> Dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200: raise RuntimeError(f"Token 交换失败: {resp.status}")
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Token 交换失败: {exc.code}") from exc

def generate_password() -> str: return secrets.token_urlsafe(16)[:16] + "A1"

@dataclass(frozen=True)
class OAuthStart:
    auth_url: str
    state: str
    code_verifier: str
    redirect_uri: str

def generate_oauth_url(*, redirect_uri: str = DEFAULT_REDIRECT_URI, scope: str = DEFAULT_SCOPE) -> OAuthStart:
    state, code_verifier = _random_state(), _pkce_verifier()
    params = {
        "client_id": CLIENT_ID, "response_type": "code", "redirect_uri": redirect_uri,
        "scope": scope, "state": state, "code_challenge": _sha256_b64url_no_pad(code_verifier),
        "code_challenge_method": "S256", "prompt": "login",
        "id_token_add_organizations": "true", "codex_cli_simplified_flow": "true",
    }
    return OAuthStart(auth_url=f"{AUTH_URL}?{urllib.parse.urlencode(params)}", state=state, code_verifier=code_verifier, redirect_uri=redirect_uri)

def submit_callback_url(*, callback_url: str, expected_state: str, code_verifier: str, redirect_uri: str = DEFAULT_REDIRECT_URI, account_email: str = "", account_password: str = "") -> str:
    cb = _parse_callback_url(callback_url)
    if cb["error"]: raise RuntimeError(f"OAuth 错误: {cb['error']}")
    if not cb["code"] or cb["state"] != expected_state: raise ValueError("回调参数不匹配或缺失")

    token_resp = _post_form(TOKEN_URL, {"grant_type": "authorization_code", "client_id": CLIENT_ID, "code": cb["code"], "redirect_uri": redirect_uri, "code_verifier": code_verifier})

    access_token = (token_resp.get("access_token") or "").strip()
    id_token = (token_resp.get("id_token") or "").strip()
    claims = _jwt_claims_no_verify(id_token)
    now = int(time.time())
    
    config = {
        "id_token": id_token, "access_token": access_token, "refresh_token": (token_resp.get("refresh_token") or "").strip(),
        "account_id": str((claims.get("https://api.openai.com/auth") or {}).get("chatgpt_account_id") or "").strip(),
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "email": str(claims.get("email") or "").strip(),
        "type": "codex", "expired": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + max(_to_int(token_resp.get("expires_in")), 0))),
    }
    if account_email: config["account_email"] = account_email
    if account_password: config["account_password"] = account_password

    return json.dumps(config, ensure_ascii=False, separators=(",", ":"))
# ==========================================
# 核心注册逻辑
# ==========================================

def run(proxy: Optional[str], pre_email: Optional[str] = None, pre_token: Optional[str] = None) -> tuple:
    proxies: Any = None
    if proxy:
        proxies = {"http": proxy, "https": proxy}

    s = requests.Session(proxies=proxies, impersonate="chrome")

    try:
        ip_addr, loc = _detect_proxy_info(s)
        print(f"[*] 当前代理出口 IP: {ip_addr or '未知'}, 地区: {loc or '未知'}")
        if loc in ["CN", "HK"]:
            raise RuntimeError("代理地区不支持 (CN/HK)")
    except Exception as e:
        print(f"[警告] 网络检查失败，尝试继续执行: {e}")

    # === 新增判断：是否使用了预设的 Token 和 Email ===
    if pre_email and pre_token:
        email = pre_email
        order_no = "pre_assigned"
        print(f"[*] 读取到预设数据 | 邮箱: {email} | Token: {pre_token[:6]}***")
    else:
        print("[*] 通过 LuckMail 创建接码订单...")
        try:
            order = luckmail_client.user.create_order(
                project_code=LUCKMAIL_PROJECT_CODE,
                email_type=LUCKMAIL_EMAIL_TYPE,
                domain=LUCKMAIL_DOMAIN,
            )
            email = order.email_address
            order_no = order.order_no
            print(f"[*] 订单号: {order_no} | 分配邮箱: {email}")
        except Exception as e:
            print(f"[错误] LuckMail 创建订单失败: {e}")
            return None, "", ""

    password = generate_password()
    oauth = generate_oauth_url()

    try:
        resp = s.get(oauth.auth_url, timeout=15)
        did = s.cookies.get("oai-did")
        print(f"[*] 设备 ID: {did}")

        sen_req_body = f'{{"p":"","id":"{did}","flow":"authorize_continue"}}'
        sen_resp = requests.post(
            "https://sentinel.openai.com/backend-api/sentinel/req",
            headers={"origin": "https://sentinel.openai.com", "referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html?sv=20260219f9f6", "content-type": "text/plain;charset=UTF-8"},
            data=sen_req_body, proxies=proxies, impersonate="chrome", timeout=15,
        )

        if sen_resp.status_code != 200:
            print(f"[错误] Sentinel 异常拦截: {sen_resp.status_code}")
            return None, email, password

        sen_token = sen_resp.json()["token"]
        sentinel = f'{{"p": "", "t": "", "c": "{sen_token}", "id": "{did}", "flow": "authorize_continue"}}'

        signup_resp = s.post(
            "https://auth.openai.com/api/accounts/authorize/continue",
            headers={"referer": "https://auth.openai.com/create-account", "accept": "application/json", "content-type": "application/json", "openai-sentinel-token": sentinel},
            data=f'{{"username":{{"value":"{email}","kind":"email"}},"screen_hint":"signup"}}',
        )

        print(f"[*] 提交密码...")
        pwd_resp = s.post(
            "https://auth.openai.com/api/accounts/user/register",
            headers={"referer": "https://auth.openai.com/create-account/password", "accept": "application/json", "content-type": "application/json", "openai-sentinel-token": sentinel},
            data=json.dumps({"password": password, "username": email}), proxies=proxies,
        )

        if pwd_resp.status_code != 200:
            print(f"[!] 密码拒绝: {pwd_resp.text[:200]}")
            return None, email, password

        try: register_continue = pwd_resp.json().get("continue_url", "")
        except: register_continue = ""

        otp_url = register_continue if register_continue else "https://auth.openai.com/api/accounts/email-otp/send"
        s.post(otp_url, headers={"referer": "https://auth.openai.com/create-account/password", "accept": "application/json", "content-type": "application/json", "openai-sentinel-token": sentinel})

        print(f"[*] 等待验证码...")
        code = ""

        # === 新增判断：如果是预设的 Token，使用新接口轮询 ===
        if pre_token:
            code = get_code_by_token(pre_token, LUCKMAIL_BASE_URL, timeout=300, interval=3.0)
            if code:
                print(f"[*] 收到验证码: {code}")
            else:
                print(f"[!] 预设 Token 轮询失败未能获取验证码")
        else:
            # 原有的 SDK 轮询逻辑
            code_result = luckmail_client.user.wait_for_code(order_no=order_no, timeout=300, interval=3.0)
            if code_result.status == "success" and code_result.verification_code:
                code = code_result.verification_code
                print(f"[*] 收到验证码: {code}")
            else:
                print(f"[!] 轮询失败: {code_result}")

        # 如果首次没获取到，触发重发机制
        if not code:
            print(f"[!] 首次未获取验证码，触发重发机制...")
            for _ in range(2):
                s.post("https://auth.openai.com/api/accounts/passwordless/send-otp", headers={"referer": "https://auth.openai.com/create-account/password", "accept": "application/json", "content-type": "application/json"})
                
                if pre_token:
                    code = get_code_by_token(pre_token, LUCKMAIL_BASE_URL, timeout=120, interval=3.0)
                    if code:
                        print(f"[*] 重试成功获取: {code}")
                        break
                else:
                    try:
                        new_order = luckmail_client.user.create_order(project_code=LUCKMAIL_PROJECT_CODE, email_type=LUCKMAIL_EMAIL_TYPE, domain=LUCKMAIL_DOMAIN, specified_email=email)
                        new_code_result = luckmail_client.user.wait_for_code(order_no=new_order.order_no, timeout=120, interval=3.0)
                        if new_code_result.status == "success" and new_code_result.verification_code:
                            code = new_code_result.verification_code
                            print(f"[*] 重试成功获取: {code}")
                            break
                    except: pass

        if not code:
            print("[!] 彻底未能获取 OTP 验证码")
            return None, email, password

        code_resp = s.post(
            "https://auth.openai.com/api/accounts/email-otp/validate",
            headers={"referer": "https://auth.openai.com/email-verification", "accept": "application/json", "content-type": "application/json"},
            data=f'{{"code":"{code}"}}',
        )
        print(f"[*] 验证码校验状态: {code_resp.status_code}")

        rand_name = f"{random.choice(['James', 'John', 'Robert', 'Mary', 'Linda'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown'])}"
        rand_birth = f"{random.randint(1985, 2004)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        create_account_resp = s.post(
            "https://auth.openai.com/api/accounts/create_account",
            headers={"referer": "https://auth.openai.com/about-you", "accept": "application/json", "content-type": "application/json"},
            data=json.dumps({"name": rand_name, "birthdate": rand_birth}),
        )
        if create_account_resp.status_code != 200:
            print(create_account_resp.text)
            return None, email, password

        print("[*] 账户创建成功，准备重新登录抓取 Token...")
        login_oauth = generate_oauth_url()
        s.get(login_oauth.auth_url, proxies=proxies, timeout=15)
        login_did = s.cookies.get("oai-did") or did
        
        login_sen_resp = requests.post("https://sentinel.openai.com/backend-api/sentinel/req", headers={"origin": "https://sentinel.openai.com", "referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html?sv=20260219f9f6", "content-type": "text/plain;charset=UTF-8"}, data=f'{{"p":"","id":"{login_did}","flow":"authorize_continue"}}', proxies=proxies, impersonate="chrome", timeout=15)
        if login_sen_resp.status_code != 200: return None, email, password
        login_sentinel = f'{{"p": "", "t": "", "c": "{login_sen_resp.json()["token"]}", "id": "{login_did}", "flow": "authorize_continue"}}'

        login_email_resp = s.post("https://auth.openai.com/api/accounts/authorize/continue", headers={"referer": "https://auth.openai.com/sign-in", "accept": "application/json", "content-type": "application/json", "openai-sentinel-token": login_sentinel}, data=f'{{"username":{{"value":"{email}","kind":"email"}},"screen_hint":"login"}}', proxies=proxies)
        if login_email_resp.status_code != 200: return None, email, password
        login_page = (login_email_resp.json().get("page") or {}).get("type", "")

        if login_page == "login_password":
            pwd_resp = s.post("https://auth.openai.com/api/accounts/password/verify", headers={"referer": "https://auth.openai.com/log-in/password", "accept": "application/json", "content-type": "application/json", "openai-sentinel-token": login_sentinel}, data=json.dumps({"password": password}), proxies=proxies)
            if pwd_resp.status_code != 200: return None, email, password
            login_page = (pwd_resp.json().get("page") or {}).get("type", "")

        if "otp" in login_page or "verification" in login_page:
            try: s.post("https://auth.openai.com/api/accounts/passwordless/send-otp", headers={"referer": "https://auth.openai.com/log-in/password", "accept": "application/json", "content-type": "application/json"}, proxies=proxies, verify=_ssl_verify(), timeout=10)
            except: pass
            
            code_resp = _post_with_retry(s, "https://auth.openai.com/api/accounts/email-otp/validate", headers={"referer": "https://auth.openai.com/email-verification", "accept": "application/json", "content-type": "application/json", "openai-sentinel-token": login_sentinel}, json_body={"code": code}, proxies=proxies, timeout=30, retries=2)
            if code_resp.status_code != 200: return None, email, password

        auth_cookie = s.cookies.get("oai-client-auth-session")
        if not auth_cookie: return None, email, password

        auth_json = _decode_jwt_segment(auth_cookie.split(".")[0])
        workspaces = auth_json.get("workspaces") or []
        if not workspaces: return None, email, password
        workspace_id = str((workspaces[0] or {}).get("id") or "").strip()

        select_resp = s.post("https://auth.openai.com/api/accounts/workspace/select", headers={"referer": "https://auth.openai.com/sign-in-with-chatgpt/codex/consent", "content-type": "application/json"}, data=f'{{"workspace_id":"{workspace_id}"}}')
        if select_resp.status_code != 200: return None, email, password

        continue_url = str((select_resp.json() or {}).get("continue_url") or "").strip()
        if not continue_url: return None, email, password

        current_url = continue_url
        for _ in range(6):
            final_resp = s.get(current_url, allow_redirects=False, timeout=15)
            location = final_resp.headers.get("Location") or ""
            if final_resp.status_code not in [301, 302, 303, 307, 308] or not location: break
            next_url = urllib.parse.urljoin(current_url, location)
            if "code=" in next_url and "state=" in next_url:
                token_j = submit_callback_url(callback_url=next_url, code_verifier=login_oauth.code_verifier, redirect_uri=login_oauth.redirect_uri, expected_state=login_oauth.state, account_email=email, account_password=password)
                return token_j, email, password
            current_url = next_url

        return None, email, password

    except Exception as e:
        print(f"[错误] 运行时发生错误: {e}")
        return None, "", ""

# ==========================================
# 批量执行控制器 (封装核心注册循环)
# ==========================================
def run_batch_registration(target_success: int, args) -> int:
    sleep_min = max(1, args.sleep_min)
    sleep_max = max(sleep_min, args.sleep_max)
    
    count = 0           
    success_count = 0   
    fail_count = 0      

    while True:
        if target_success > 0 and success_count >= target_success:
            print(f"\n[信息] 🎉 已达到本次设定的目标成功数量 ({target_success} 个)！退出注册循环。")
            break
            
        pre_email, pre_token = None, None
        
        # === 新增：动态从文件读取并消耗顶部的账号 (阅后即焚) ===
        if args.email_token_file:
            if not os.path.exists(args.email_token_file):
                print(f"\n[警告] 找不到指定的文件: {args.email_token_file}，停止运行。")
                break
                
            with open(args.email_token_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            # 过滤出有内容的行
            valid_lines = [l for l in lines if l.strip() and "----" in l]
            
            if not valid_lines:
                print(f"\n[信息] 预设的 {args.email_token_file} 文件已全部处理完毕或为空，停止当前批量任务。")
                break
                
            # 提取第一行并分割
            current_line = valid_lines.pop(0).strip()
            parts = current_line.split("----", 1)
            pre_email, pre_token = parts[0].strip(), parts[1].strip()
            
            # 将剩下的行写回文件，防止守护模式重复读取失效数据
            with open(args.email_token_file, "w", encoding="utf-8") as f:
                f.writelines([l + "\n" for l in valid_lines])
                
            print(f"[*] 成功从文件提取数据 | 邮箱: {pre_email} | 剩余库存: {len(valid_lines)} 条")

        count += 1
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> 开始执行注册流程 (当前批次第 {count} 次尝试) <<<")

        is_success = False

        try:
            proxy = _normalize_proxy(args.proxy, args.proxy_scheme)
            if not proxy:
                try:
                    fps = [p.strip() for p in open(args.proxies_file, "r", encoding="utf-8") if p.strip() and not p.strip().startswith("#")]
                    if fps:
                        proxy = _normalize_proxy(fps[(count - 1) % len(fps)], args.proxy_scheme)
                except: pass

            print(f"[*] 使用代理: {proxy or '直连'}")
            
            # ⚠️ 这里非常关键：必须将 pre_email 和 pre_token 传给 run 函数
            token_json, generated_ema, generated_pwd = run(proxy, pre_email, pre_token)

            if token_json:
                is_success = True
                try:
                    fname_email = json.loads(token_json).get("email", "unknown").replace("@", "_")
                except Exception:
                    fname_email = "unknown"

                file_name = f"token_{fname_email}_{int(time.time())}.json"
                token_dir = os.getenv("TOKEN_OUTPUT_DIR", "tokens")
                os.makedirs(token_dir, exist_ok=True)
                file_path = os.path.join(token_dir, file_name)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(token_json)

                print(f"[*] 成功! Token 已保存至: {file_path}")
                
                if args.upload_cpa:
                    push_to_cliproxyapi(file_name, token_json, args.cpa_auth, args.cpa_url)

            else:
                print("[-] 注册/获取 Token 失败。")

            # 保存账户凭据
            if generated_ema and generated_pwd:
                with open("accounts.txt", "a", encoding="utf-8") as af:
                    af.write(f"{generated_ema}----{generated_pwd}\n")

        except Exception as e:
            print(f"[错误] 发生未捕获异常: {e}")

        # 统计
        if is_success: success_count += 1
        else: fail_count += 1

        print(f"\n=============================================")
        print(f"📊 本批次状态: 尝试={count} | 成功={success_count} | 失败={fail_count} | 目标={target_success if target_success>0 else '无限制'}")
        print(f"=============================================")
        
        # 注册成功一轮后，判断是否跳出
        if target_success > 0 and success_count >= target_success:
            print(f"[信息] 🎉 已达到设定的目标成功数量 ({target_success} 个)！")
            break

        # 如果是非守护模式下的强制循环次数限制（如果是文本文件模式，则以消耗完毕为止优先）
        if not args.maintain_enabled and not args.email_token_file and args.times > 0 and count >= args.times:
            print("[信息] 达到了最大运行次数上限，安全退出。")
            break

        wait_time = random.randint(sleep_min, sleep_max)
        print(f"[*] 休息 {wait_time} 秒后开启下一次...")
        time.sleep(wait_time)

    return success_count


# ==========================================
# 主入口
# ==========================================
def main() -> None:
    runtime_cfg = CONFIG.get("runtime_config", {})
    cpa_cfg = CONFIG.get("cpa_config", {})

    parser = argparse.ArgumentParser(description="OpenAI 自动注册引擎 (LuckMail接码 + 智能补仓守护模式)")
    parser.add_argument("--proxy", default=runtime_cfg.get("proxy"), help="代理地址")
    parser.add_argument("--proxies-file", default=runtime_cfg.get("proxy_file", "proxies.txt"), help="代理池")
    parser.add_argument("--proxy-scheme", default=runtime_cfg.get("proxy_scheme", "http"), choices=["http", "socks5", "socks5h"])
    parser.add_argument("--times", type=int, default=runtime_cfg.get("times", 0), help="普通模式下最大循环次数")
    parser.add_argument("--max-success", type=int, default=runtime_cfg.get("max_success", 0), help="普通模式下最大成功注册数量")
    parser.add_argument("--sleep-min", type=int, default=runtime_cfg.get("sleep_min", 5), help="最短等待秒数")
    parser.add_argument("--sleep-max", type=int, default=runtime_cfg.get("sleep_max", 30), help="最长等待秒数")
    
    # 新增: 文本模式配置 (读取 config.json)
    parser.add_argument("--email-token-file", type=str, default=runtime_cfg.get("email_token_file", ""), help="包含 email----token 的 txt 文本文件路径")
    
    # CPA 参数配置
    parser.add_argument("--upload-cpa", action="store_true", default=cpa_cfg.get("upload_cpa", False), help="上传到 CPA")
    parser.add_argument("--cpa-auth", type=str, default=cpa_cfg.get("cpa_auth", "Bearer Crm@2020"), help="CPA Auth")
    parser.add_argument("--cpa-url", type=str, default=cpa_cfg.get("cpa_url", "http://127.0.0.1:8317/v0/management/auth-files"), help="CPA URL")
    
    # 守护模式配置
    parser.add_argument("--maintain-enabled", action="store_true", default=cpa_cfg.get("maintain_enabled", False), help="开启智能守护补仓模式")

    args = parser.parse_args()
    if not args.upload_cpa and cpa_cfg.get("upload_cpa"): args.upload_cpa = True
    if not args.maintain_enabled and cpa_cfg.get("maintain_enabled"): args.maintain_enabled = True

    print("\n=============================================")
    print("🚀 OpenAI 自动化引擎启动")
    if args.email_token_file:
        print(f"[*] 接码模式: 预设 Token 文本轮询模式 ({args.email_token_file})")
    else:
        print(f"[*] 接码模式: LuckMail API 创建模式 ({LUCKMAIL_DOMAIN})")
    print(f"[*] CPA 上传: {'✅ 启用' if args.upload_cpa else '❌ 禁用'}")
    
    # ---------------- 守护模式逻辑 ----------------
    if args.maintain_enabled:
        if args.email_token_file:
            print("[警告] 守护模式下不建议使用一次性的 Token 文本文件，如果文件耗尽，补仓任务将停止。")
            
        target_valid = cpa_cfg.get("target_valid_count", 100)
        check_interval = cpa_cfg.get("check_interval_seconds", 600)
        
        print(f"[*] 运行模式: 🛡️ CPA 守护补仓模式")
        print(f"[*] 目标库存: {target_valid} 个")
        print(f"[*] 检测间隔: {check_interval} 秒")
        print("=============================================\n")

        while True:
            valid_count = check_and_clean_cpa(args.cpa_url, args.cpa_auth)
            
            if valid_count < 0:
                print(f"[*] ⚠️ 网络异常，获取状态失败。等待 {check_interval} 秒后重试...")
                time.sleep(check_interval)
                continue
                
            if valid_count >= target_valid:
                print(f"[*] ✅ 当前库存充足 ({valid_count}/{target_valid})，无需注册。休眠 {check_interval} 秒...")
                time.sleep(check_interval)
                continue
                
            need_to_register = target_valid - valid_count
            print(f"[*] 📉 库存不足 ({valid_count}/{target_valid})，触发自动补货，目标: {need_to_register} 个！")
            
            run_batch_registration(need_to_register, args)
            
            print(f"\n[*] 🏁 本轮补仓任务结束。等待 {check_interval} 秒后进行下一轮库存复检...")
            time.sleep(check_interval)

    # ---------------- 普通模式逻辑 ----------------
    else:
        print(f"[*] 运行模式: ⚡ 普通循环注册模式")
        print("=============================================\n")
        run_batch_registration(args.max_success, args)


if __name__ == "__main__":
    main()
