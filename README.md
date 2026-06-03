# 🗳️ SaaS 多项目分布式匿名投票平台 (Anonymous Voting System)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-v1.0.1-green.svg)
![Node.js](https://img.shields.io/badge/Node.js-Gateway-339933?logo=node.js)
![Python](https://img.shields.io/badge/Python-Crypto_Engine-3776AB?logo=python)
![MySQL](https://img.shields.io/badge/MySQL-Storage-4479A1?logo=mysql)

本项目是一个基于 **Textbook RSA 盲签名算法** 与 **底层不可篡改哈希链** 构建的企业级 SaaS 投票平台。系统通过严密的密码学设计与微服务架构，完美解决了传统电子投票中“实名认证”与“选票隐私”之间的矛盾，实现了真正的 **“人票分离”** 与 **“端到端可验证 (E2E Verifiability)”**。

---

## ✨ 核心特性

- **🛡️ 绝对匿名性 (Anonymity)**：基于 RSA 盲签名（Blind Signature），主办方仅能对被“数学盲化”的选票进行盖章，系统在投递前会自动物理抹除 JWT 身份令牌，实现人票分离。
- **🔍 端到端自证 (E2E Verifiability)**：不依赖可信第三方！选民凭借投票时在本地生成的秘密凭证 $(Sn)$ 与真实签名 $(S)$，可在完全脱机的纯前端沙盒中，通过大整数模幂运算 $S^e \pmod N \equiv H(r||Sn)$ 自证选票未被篡改。
- **⛓️ 防篡改哈希链 (Tamper-evident Hash Chain)**：底层 Python 引擎将选票作为区块（Block）进行串联，$Hash_{curr} = SHA256(Hash_{prev} + Sn + r + S)$，任何针对 MySQL 的“脱库篡改”都会导致哈希雪崩并被探针立刻捕获。
- **🚫 防多投机制 (Anti-Double Voting)**：实名领票阶段（Node.js 网关）记录用户领取日志；匿名投递阶段（Python 区块链）利用唯一约束防御凭证重放攻击（Replay Attack）。
- **🏢 SaaS 多租户隔离 (Multi-Tenancy)**：支持单一平台同时承载多场独立的选举活动。Node.js 负责租户数据隔离，Python 引擎自动为每个项目生成、分发物理隔离的专属 RSA 2048 位密钥对。

---

## 🏗️ 系统架构设计

系统采用 **前后端分离 + 微服务协管** 架构，分为三大核心域：

1. **BFF 网关层 (Node.js)**：负责高并发的读写请求、JWT 鉴权、多租户大盘调度、CSV 报表导出以及高危的级联删除事务。
2. **密码学与存证层 (Python Flask)**：作为内部微服务，负责非对称密钥生成、盲签发证、哈希链构造与校验、以及链上数据的公开提取。
3. **前端密码学大脑 (Vanilla JS / forge.js)**：在用户浏览器端就地完成盲因子生成、去盲解密、脱机哈希验证，确保敏感数据绝不离开本地设备。

---

## 🔐 密码学原理与数学实现

系统核心建立在 Textbook RSA 的乘法同态特性上。

### 1. 领票与盲化 (Blind) - `vote_crypto.js`

- 选民在前端生成随机秘密凭证 $Sn$ 和符合 $gcd(b, N)=1$ 的盲因子 $b$。
- 将选项 $r$ 与凭证拼接并哈希：$m = H(r || Sn)$。
- 盲化选票：$r' = m \cdot b^e \pmod N$，将其发给实名发证局。

### 2. 盲签名 (Sign) - `rsa_crypto.py`

- 主办方（Python端）核验实名身份后，使用项目的私钥 $d$ 对盲化数据签名：
- $S' = (r')^d \pmod N \equiv (m \cdot b^e)^d \pmod N \equiv m^d \cdot b \pmod N$。

### 3. 去盲与投递 (Unblind) - `vote_crypto.js`

- 选民前端收到 $S'$ 后，计算盲因子的模逆元 $b^{-1}$，消除盲因子：
- $S = S' \cdot b^{-1} \pmod N \equiv m^d \cdot b \cdot b^{-1} \pmod N \equiv m^d \pmod N$。
- 此时得到的 $S$，正是主办方针对原始明文 $m$ 的合法签名，且主办方从未见过 $m$。选民随后以**无 Token 游客身份**将 $(r, Sn, S)$ 广播上链。

### 4. 零知识脱机验签 (Verify) -`public_results.html`

- 任何人均可提取项目的公钥 $(e, N)$，对签名进行模幂还原：$S^e \pmod N$。
- 只要 $S^e \pmod N == H(r || Sn)$，即可证明数据是由持有私钥的主办方合法签发，且未被任何中间人篡改。

---

## 📂 核心项目结构与文件功能

```text
anonymous-voter/
├── client/                     # 🌐 前端 UI 与 密码学大脑
│   ├── admin/                  # 主办方控制台页面
│   │   ├── dashboard.html      # 租户大盘 (创建项目、级联删除)
│   │   └── project_manage.html # 项目深度管理 (批量导入、结束封盘、导出CSV)
│   ├── voter/                  # 选民通道页面
│   │   └── vote_hall.html      # 匿名投票大厅 (包含完整盲签协议交互及安全退出机制)
│   ├── js/
│   │   ├── auth.js             # JWT 拦截器与 Token/Role 状态管理
│   │   └── vote_crypto.js      # 【核心】前端密码学引擎 (大整数运算、盲化、去盲、验证)
│   ├── index.html              # 门户首页 (动态路由分流、历史归档卡片)
│   ├── public_results.html     # 公示大厅与沙盒 (展示排行，执行纯脱机防篡改自证)
│   └── login.html              # 统一实名鉴权登录入口
│
├── server/                     # 🟢 Node.js 业务网关 (BFF 层)
│   ├── app.js                  # Express 服务器入口及 CORS 配置
│   ├── config/db.js            # MySQL 数据库连接池配置
│   ├── middleware/             #
│   │   └── authMiddleware.js   # JWT 令牌拦截及多租户身份识别
│   ├── routes/                 # 业务路由
│   │   ├── auth.js             # 登录下发 Token (按角色路由)
│   │   ├── project.js          # 项目管理生命周期 (含联动 Python 生成密钥、级联洗表)
│   │   ├── candidate.js        # 候选人管理
│   │   ├── user.js             # 批量导入与分发选民通行证
│   │   └── vote.js             # 盲签名实名中转与核销接口
│   └── package.json
│
├── py_server/                  # 🐍 Python 区块链与密码学微服务
│   ├── app.py                  # Flask 主服务 (暴露密钥生成、盲签、上链、沙盒查票接口)
│   ├── rsa_crypto.py           # 密码学基建 (文件级 RSA 密钥对生成、核心签名验证算法)
│   ├── hash_chain.py           # 【核心】联盟链引擎 (创世区块、哈希串联、全链完整性审计)
│   ├── db_base.py              # Python 端的 MySQL 直连适配器 (处理上链事务)
│   └── myrsa_test/             # 自动挂载的多租户专属 RSA 密钥文件 (PEM格式)
│
└── others/                     # 额外文档与依赖
    └── requirements.txt        # Python 依赖清单
```

## 🗄️ 数据库核心表结构 (MySQL)

系统依托高度关联的多张表实现租户隔离与数据管理：

1. **`projects` (项目大盘)**：存储活动名称、状态 (`status`)，是所有隔离数据的外键根基。
2. **`users` (通信证门禁)**：按 `project_id` 划分，记录普通选民与管理员(全局)的账密与角色。
3. **`candidates` (候选人排行榜)**：记录候选人序号 (`serial_no`) 与实时得票数 (`vote_count`)。
4. **`signature_logs` (实名核销防多投)**：记录某选民在某项目中是否已领取过盲签名，控制领票阈值。
5. **`hash_chain` (底层哈希区块链)**：存储脱敏后的匿名选票。
   - `block_id`: 块高
   - `Sn`: 秘密凭证 (唯一索引，防上链重放攻击)
   - `r`, `S`: 选票选项与合法签名
   - `prev_hash`, `curr_hash`: 链式哈希防篡改指针

---

## 🚀 系统交互闭环流转指南

1. **环境准备与建库**：
   - 管理员登录 `dashboard.html` 创建活动。
   - Node.js 将主记录写入 MySQL，同时呼叫 Python 在磁盘生成专属 `project_X_private.pem` 密钥。
2. **环境配置**：
   - 在 `project_manage.html` 批量导入候选人及随机选民账号。
3. **实名领票阶段**：
   - 选民登录进入 `vote_hall.html`。
   - 选民点击候选人，触发前端 `vote_crypto.js` 盲化运算。
   - 携带实名 Token 请求 Node.js，核销领票资格后，Python 完成盲签并返回 $S'$。
4. **绝对匿名上链阶段**：
   - 浏览器自动利用 $b^{-1}$ 去盲还原出 $S$。
   - **关键动作**：浏览器物理销毁 LocalStorage 中的 Token。
   - 以纯游客身份直接请求 Python 微服务，完成验证并打包入 `hash_chain` 表，同时更新计票器。
5. **关停与归档公示**：
   - 投票结束，管理员“结算并关闭活动”，导出防乱码 CSV，彻底封死写操作接口。
   - 首页 `index.html` 动态渲染历史卡片。
6. **脱机验证与自证清白**：
   - 任何人点击进入 `public_results.html`。
   - 选民输入自己保存的 $(Sn, r, S)$，沙盒仅从服务器请求公钥，随后进行纯本地零知识对撞，核验 $S^e \pmod N \equiv H(r||Sn)$，可以有效解决对系统后台的质疑。

---

## 💻 部署与运行说明

### 1. 数据库配置

在 MySQL 中建立库并导入所需的建表 SQL 语句，确保 `hash_chain` 表包含自增主键、唯一凭证键与哈希指针字段。
修改以下两处的数据库连接配置（账号、密码、库名）：

- `server/config/db.js`
- `py_server/db_base.py`

### 2. 启动 Node.js 网关

```bash
cd server
npm install
node app.js
# 默认运行在 3000 端口
```

### 3. 启动 Python 区块链引擎

```bash
cd py_server
pip install -r ../others/requirements.txt
python app.py
# 默认运行在 5000 端口
```

### 4. 启动前端

推荐使用 VS Code 的 Live Server 插件，右键点击 client/index.html 选择 "Open with Live Server" (默认在 5500 端口运行)。
