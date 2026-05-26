# 🗳️ 全栈项目上下文交接文档 (AI Handoff Context)

你好，AI 助手！接下来你需要协助我完成一个**“基于盲签名与哈希链的 SaaS 匿名防多投投票系统”**的开发。以下是该项目的全部背景、架构规范以及当前进度。请仔细阅读并严格遵循。

## 🎯 1. 项目业务概览
这是一个支持多租户（SaaS）、且具备极高安全级别的微服务投票平台。
- **业务痛点**：传统的实名投票会泄露隐私，匿名投票又容易被“刷票”。
- **解决方案**：引入**RSA 盲签名（Blind Signature）**与**哈希链（Hash Chain）**。利用盲签名彻底切断“投票权”与“投票内容”的关联；利用哈希链实现选票的防篡改与永久存证。

## 🏗️ 2. 全栈微服务架构设计
系统被严格拆分为三个物理隔离的端：

1. **Client (纯前端)**：HTML/CSS/Vanilla JS。
   - 包含 SaaS 门户、登录、大盘管理、投票大厅。
   - **核心职责**：在本地浏览器使用 `forge.min.js` 完成随机凭证 $Sn$ 和盲因子 $b$ 的生成，并在**本地**完成哈希 $H(r || Sn)$、选票盲化 ($r'$) 和去盲计算 ($S$)。绝对不把明文传给 Node.js 盲化。
2. **Node.js Server (鉴权网关)**：基于 Express + MySQL。
   - **核心职责**：管理 SaaS 多租户逻辑（`project_id`）。验证选民的 JWT，核销投票资格。
   - 作为内部网关，向 Python 微服务发起**内网 HTTP 请求**索要盲签名，然后将签名转发给前端。
3. **Python Server (区块链与密码学引擎)**：基于 Flask + Cryptography。
   - 运行在 `5000` 端口。提供两个核心 API：
   - `POST /python/sign_blind`（内网接口）：接收乱码 $r'$，用私钥返回签名 $S'$。
   - `POST /python/cast_vote`（公开跨域接口）：接收前端发来的无身份明文 `(r, Sn, S)`，验证 $S^e \pmod N == H(r || Sn)$，查重 $Sn$，并写入 MySQL 的哈希链表。

## 📂 3. 当前项目物理目录结构
```text
website1/
├── client/                     # 前端工程
│   ├── js/
│   │   ├── auth.js             # 包含 fetchWithAuth 拦截器
│   │   ├── vote_crypto.js      # [🚧待编写] 前端密码学大脑
│   │   └── forge.min.js        # 前端 RSA/SHA-256 运算库
│   ├── admin/                  # 主办方 UI
│   └── voter/                  
│       └── vote_hall.html      # [🚧待重写] 投票大厅两阶段交互 UI
├── server/                     # Node.js 工程
│   ├── config/db.js            # MySQL 连接池
│   ├── routes/
│   │   └── vote.js             # [🚧待重写] 内部鉴权与向 Python 索要盲签名
│   └── app.js                  
└── py_server/                  # Python 微服务工程 (✅已完成)
    ├── app.py                  # Flask 引擎 (已实现 sign_blind 和 cast_vote)
    ├── rsa_crypto.py           # RSA 数学库
    ├── hash_chain.py           # 区块链存储库
    ├── myrsa_test/             # 存放 RSA 密钥对 .pem
    └── requirements.txt