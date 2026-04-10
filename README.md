****
# 🚀 OpenAI 自动化注册引擎 (Auto-Registration Engine)

这是一个基于 Python 开发的全自动 OpenAI 账号注册与管理工具，集成 TLS 指纹绕过、LuckMail 邮箱接码、代理池轮询、CPA 云端守护补仓，支持 7×24 小时无人值守运行。

---

# ⚠️ 免责声明
本项目**仅用于技术研究与学习交流**。  
任何因使用本工具产生的法律责任、风险后果由使用者自行承担，开发者不承担任何责任。  
请遵守目标网站的服务条款（TOS）与当地法律法规。

---

# ✨ 核心特性
## 1. 🛡️ 智能风控绕过
- 基于 `curl_cffi` 完全模拟 Chrome TLS 指纹  
- 完美绕过 Cloudflare / Sentinel 人机验证  
- 降低高频风控拦截概率，大幅提升注册成功率  

## 2. 📧 多模式接码体系
### ✔ API 模式（LuckMail）
- 自动创建邮箱账号  
- 自动接收邮件、提取验证码  
- 支持自定义域名、邮箱类型、项目代号  

### ✔ 文本模式（阅后即焚）
- 支持 `email----token` 格式邮箱池  
- 使用后自动删除该行，防止重复使用  
- 适合批量注册场景  

## 3. 🤖 CPA 智能守护模式（核心）
自动实现：
1. 定期检测 CPA 云端账号有效性  
2. 清理失效账号  
3. 按目标库存自动补号  
4. 支持 7x24 持续挂机运行  
5. 自动间隔巡检、动态补仓  

配置项包括：
- 目标有效账号数量  
- 检测间隔  
- 是否开启自动补仓  
- 是否上传账号到 CPA 系统  

## 4. 🌐 代理池轮询
支持代理协议：
- http  
- socks5  
- socks5h  

特性：
- 自动切换代理  
- 自动过滤受限地区（CN / HK）  
- 支持代理账号密码格式  
- 保障注册 IP 多样性  

## 5. 📤 云端账号管理
- 自动注册成功后同步到 CPA  
- 支持远程统一管理  
- 便于批量调度、监控、库存管理  

---

# 🛠️ 环境要求
- Python 3.10 ~ 3.11  
- 支持 Windows / Linux  
- 依赖：`curl_cffi==0.13.0`、`requests`、`argparse`、`certifi`  

---

# 📦 快速部署
## 1. 文件结构
```
Auto-Registration-Engine/
├── main.py                # 主程序
├── config.json            # 配置文件
├── requirements.txt       # 依赖清单
├── proxies.txt            # 代理池
├── emails.txt（可选）     # 文本邮箱 token 池
├── tokens/（自动生成）
├── accounts.txt（自动生成）
└── run.log（后台运行产生）
```

## 2. 安装依赖
```bash
pip install -r requirements.txt
```

**requirements.txt 内容**
```txt
curl_cffi==0.13.0
requests
argparse
certifi
```

## 3. 配置 config.json
配置示例：
```json
{
  "luckmail_config": {
    "LUCKMAIL_BASE_URL": "https://mails.luckyous.com/",
    "LUCKMAIL_API_KEY": "ak_xxx",
    "LUCKMAIL_PROJECT_CODE": "openai",
    "LUCKMAIL_EMAIL_TYPE": "ms_imap",
    "LUCKMAIL_DOMAIN": "hotmail.com"
  },
  "runtime_config": {
    "proxy": "",
    "proxy_file": "proxies.txt",
    "proxy_scheme": "http",
    "times": 0,
    "max_success": 0,
    "sleep_min": 5,
    "sleep_max": 20,
    "email_token_file": "emails.txt"
  },
  "cpa_config": {
    "upload_cpa": true,
    "cpa_auth": "Bearer xxx",
    "cpa_url": "http://xxx",
    "maintain_enabled": true,
    "target_valid_count": 100,
    "check_interval_seconds": 600
  }
}
```

---

# 🚀 运行方式
## 方式 1：直接运行
```bash
python main.py
```

## 方式 2：命令行参数覆盖配置
```bash
# 使用文本邮箱池 + 开启守护模式 + 上传CPA
python main.py \
  --email-token-file emails.txt \
  --maintain-enabled \
  --upload-cpa

# 限制最多成功 10 个账号
python main.py --max-success 10

# 使用 socks5 代理
python main.py --proxy-scheme socks5
```

## 方式 3：Linux 后台长期运行
```bash
nohup python main.py > run.log 2>&1 < /dev/null &
```

查看实时日志：
```bash
tail -f run.log
```

停止程序：
```bash
pkill -f main.py
```

---

# 📄 文件格式说明
## 1. 邮箱 Token 文件（email----token）
```
user1@hotmail.com----tok_abc123
user2@hotmail.com----tok_xyz789
```
使用后自动删除该行。

## 2. 代理池文件 proxies.txt
```
127.0.0.1:7890
user:pass@1.1.1.1:8080
socks5://user:pass@ip:port
```

---

# 📁 输出文件
| 文件           | 说明                             |
| -------------- | -------------------------------- |
| tokens/        | 保存登录凭证 JSON                |
| accounts.txt   | 注册成功账号 email----password   |
| run.log        | 程序运行日志（后台模式）         |

---

# 🤖 守护模式工作逻辑
1. 读取 target_valid_count  
2. 从 CPA 获取当前有效账号数量  
3. 若不足 → 自动注册补号  
4. 达到目标后进入等待  
5. 按 check_interval_seconds 循环检查  

---

# ⭐ 贡献
欢迎提交：
- Issue  
- PR  
- 优化建议  

---

# ⭐ 支持项目
如果对你有帮助，欢迎点亮 Star ⭐
****

---

## 📄 相关文档与开源协议

- 📜 官方使用声明：[USE_DECLARATION.md](sslocal://flow/file_open?url=https%3A%2F%2Fgithub.com%2FMKA930%2FAuto-Registration-Engine%2Fblob%2Fmain%2FUSE_DECLARATION.md&flow_extra=eyJsaW5rX3R5cGUiOiJjb2RlX2ludGVycHJldGVyIn0=)
- ⚖️ 开源许可证：[LICENSE](sslocal://flow/file_open?url=https%3A%2F%2Fgithub.com%2FMKA930%2FAuto-Registration-Engine%2Fblob%2Fmain%2FLICENSE&flow_extra=eyJsaW5rX3R5cGUiOiJjb2RlX2ludGVycHJldGVyIn0=)