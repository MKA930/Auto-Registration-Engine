# 🚀 OpenAI 自动化注册引擎 (Auto-Registration Engine)

这是一个基于 Python 编写的高效、自动化的 OpenAI 账号注册与管理脚本。本项目集成了自动化人机验证绕过、LuckMail 邮箱接码、代理池轮询以及独特的 **CPA 守护补仓模式**，能够实现账号的全自动注册、状态监控与库存管理。

⚠️ **免责声明**：本项目仅供技术交流与学习使用。请遵守目标网站的使用条款（TOS）。因使用本脚本产生的任何后果由使用者自行承担。

---

## ⚠️ 免责声明

本项目仅用于 **技术研究与学习交流**，请务必遵守目标网站的服务条款（TOS）。
因使用本项目产生的任何风险与后果，均由使用者自行承担。

---

## ✨ 核心特性

### 🛡️ 风控绕过

* 基于 `curl_cffi` 模拟真实 Chrome TLS 指纹
* 有效降低 Cloudflare / Sentinel 风控拦截

### 📧 接码模式

* **API 自动建单**

  * 本项目对接 LuckMail 邮箱平台自动获取邮箱与验证码，欢迎体验，地址：https://mails.luckyous.com/727273B1
* **文本模式（阅后即焚）**

  * 使用 `email----token` 文件
  * 使用后自动删除，避免重复使用

### 🤖 智能守护模式（核心）

* 自动检测 CPA 云端账号状态
* 自动清理失效账号
* 按目标库存 **自动补号**
* 支持 7x24 持续挂机运行

### 🌐 代理池支持

* 支持：

  * `http`
  * `socks5`
  * `socks5h`
* 自动轮询代理
* 自动规避不支持地区（CN/HK）

### 📤 云端上报

* 自动上传账号到 CPA 系统
* 实现远程统一管理

---

## 🛠️ 环境准备

### Python 版本

```
Python 3.10+
```

### 安装依赖

```bash
pip install curl_cffi requests argparse
```

> ⚠️ 如果使用 LuckMail 私有 SDK，请确保模块已正确安装或放置。

---

## ⚙️ 配置文件（config.json）

程序启动时会自动读取 `config.json`

---

### 1️⃣ luckmail_config（接码配置）

| 字段                    | 示例                                                         | 说明          |
| --------------------- | ---------------------------------------------------------- | ----------- |
| LUCKMAIL_BASE_URL     | [https://mails.luckyous.com/](https://mails.luckyous.com/) | API 地址      |
| LUCKMAIL_API_KEY      | ak_xxx                                                     | API Key（必填） |
| LUCKMAIL_PROJECT_CODE | openai                                                     | 项目代号        |
| LUCKMAIL_EMAIL_TYPE   | ms_imap                                                    | 邮箱类型        |
| LUCKMAIL_DOMAIN       | hotmail.com                                                | 邮箱域名        |

---

### 2️⃣ runtime_config（运行配置）

| 字段               | 示例          | 说明         |
| ---------------- | ----------- | ---------- |
| proxy            | ""          | 单代理        |
| proxy_file       | proxies.txt | 代理池文件      |
| proxy_scheme     | http        | 协议         |
| times            | 0           | 最大循环（0=无限） |
| max_success      | 0           | 成功数上限      |
| sleep_min        | 5           | 最小休眠       |
| sleep_max        | 20          | 最大休眠       |
| email_token_file | 1.txt       | 文本邮箱池      |

---

### 3️⃣ cpa_config（守护模式）

| 字段                     | 示例                       | 说明     |
| ---------------------- | ------------------------ | ------ |
| upload_cpa             | true                     | 上传开关   |
| cpa_auth               | Bearer xxx               | 鉴权     |
| cpa_url                | [http://xxx](http://xxx) | API 地址 |
| maintain_enabled       | true                     | 守护模式   |
| target_valid_count     | 100                      | 目标库存   |
| check_interval_seconds | 600                      | 检查间隔   |

---

## 🚀 使用方法

### ✅ 方式一：直接运行

```bash
python main.py
```

---

### ✅ 方式二：命令行参数

```bash
# 使用文本邮箱池 + 守护模式 + 上传CPA
python main.py \
  --email-token-file emails.txt \
  --maintain-enabled \
  --upload-cpa

# 普通模式：注册10个号
python main.py --max-success 10 --proxy-scheme socks5
```

---

## 📄 数据文件格式

### 📧 邮箱 Token 文件

```
email----token
```

示例：

```
user1@hotmail.com----tok_abc123
user2@hotmail.com----tok_xyz789
```

✔ 使用后自动删除（防重复）

---

### 🌐 代理池（proxies.txt）

```
# 普通IP
127.0.0.1:7890

# 账号密码
user:pass@1.1.1.1:8080
```

---

## 📁 输出文件

| 文件           | 说明            |
| ------------ | ------------- |
| tokens/      | JSON token 文件 |
| accounts.txt | 账号密码          |

示例：

```
email----password
```

---

## 🤝 贡献

欢迎：

* 提交 Issue
* 提交 PR
* 提供优化建议

---

## ⭐ 支持项目

如果这个项目对你有帮助：

👉 请点一个 **Star ⭐**

---
