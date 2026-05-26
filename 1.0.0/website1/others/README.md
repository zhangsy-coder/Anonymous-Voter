# 🗳️ SaaS 多租户分布式投票平台 (SaaS Voting System)

基于 Node.js + Express + MySQL 构建的企业级轻量化多项目投票系统。采用 SaaS (Software as a Service) 架构，支持单实例多租户数据完全隔离。提供主办方后台管理系统与选民实时投票大厅。

## ✨ 核心特性
- **🛡️ 多租户数据隔离**：基于 `project_id` 的底层架构，支持同时开展无数个互不干扰的投票活动。
- **🔐 智能 JWT 身份网关**：无状态 Token 认证，内置防越权（IDOR）拦截与 RBAC 角色分离机制。
- **🚀 效率神器**：支持主办方控制台文本解析引擎，实现选民账号、候选人名单的一键批量导入。
- **🧱 极简强韧的前端**：原生 Vanilla JS 构建，0 依赖，极致首屏加载速度，自适应动态 UI 路由。
- **🛡️ 闭环防刷票体系**：身份溯源 + 幂等性校验 + 复合唯一索引，杜绝重复投票与跨界投票。

---

## 📂 完整目录结构与功能说明

```text
website1/
├── client/                     # 🌐 前端客户端代码 (基于原生 HTML/CSS/JS)
│   ├── admin/                  # ⚙️ 主办方/管理员专用页面
│   │   ├── dashboard.html      # 项目大盘：展示所有创建的投票项目及新建入口
│   │   └── project_manage.html # 深度管理：特定项目的控制台，支持批量导入与数据管理
│   ├── css/                    
│   │   └── style.css           # 🎨 全局 CSS 样式库：采用 CSS 变量与组件化架构
│   ├── js/                     
│   │   └── auth.js             # 🛠️ 前端核心工具库：含全局配置、Token 管理及智能拦截器 fetchWithAuth
│   ├── voter/                  # 👥 普通选民专用页面
│   │   └── vote_hall.html      # 投票大厅：带实时数据加载与实名防刷票投票交互
│   ├── index.html              # 🚪 网站门户：SaaS 落地页，动态分流路由入口
│   └── login.html              # 🔑 统一门禁：双角色自适应登录验证页面
│
└── server/                     # 💻 后端服务端代码 (Node.js + Express)
    ├── config/                 
    │   ├── db.js               # 🗄️ MySQL 数据库连接池配置 (含自动重连与并发控制)
    │   └── db_copy.js          # 数据库配置备份文件
    ├── middleware/             
    │   └── authMiddleware.js   # 🛂 核心安检中间件：解析 JWT，透传 user 角色与 project_id
    ├── routes/                 # 🛣️ 核心业务路由层
    │   ├── auth.js             # 认证模块：处理登录校验、Bcrypt 比对与 Token 签发
    │   ├── candidate.js        # 候选人模块：处理排行获取、批量导入与删除
    │   ├── project.js          # 项目模块：SaaS 租户核心，处理项目创建与拉取
    │   ├── user.js             # 选民管理模块：处理选民账号的批量生成与作废
    │   └── vote.js             # 投票引擎模块：核心防作弊、幂等性校验与事务模拟
    ├── .env                    # 🔒 环境变量文件 (存放数据库密码、JWT 密钥、端口号等机密信息)
    ├── app.js                  # 🚀 后端应用程序主入口：配置全局中间件并挂载路由
    └── package.json            # 📦 Node.js 项目依赖与运行脚本清单
```

---

## 📡 API 接口参考文档 (API Reference)

系统所有接口均挂载于 `http://[YOUR_IP]:3000/api` 之下，所有需鉴权的接口必须在 Header 中携带 `Authorization: Bearer <Token>`。

### 1. 认证中心 (`/api/auth`)
| 接口方法 | 路径 | 权限 | 描述 | 请求体/参数 (Body/Query) |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/login` | 公开 | 用户统一登录 | `{ username, password }` |

### 2. 项目管理 (`/api/projects`)
| 接口方法 | 路径 | 权限 | 描述 | 请求体/参数 (Body/Query) |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/list` | Admin | 获取主办方名下所有项目 | 无 |
| `POST` | `/create`| Admin | 新建投票项目 | `{ title, description }` |

### 3. 选民管理 (`/api/users`)
| 接口方法 | 路径 | 权限 | 描述 | 请求体/参数 (Body/Query) |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/list` | Admin | 获取特定项目的选民 | `Query: ?project_id=1` |
| `POST` | `/import`| Admin | 批量导入/生成选民通行证 | `{ project_id, voters: [{username, password}] }` |
| `DELETE`| `/delete/:id` | Admin | 作废选民账号 | URL Params: `:id` |

### 4. 候选人管理 (`/api/candidates`)
| 接口方法 | 路径 | 权限 | 描述 | 请求体/参数 (Body/Query) |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | Voter | 选民获取所属项目排行榜 | 无 (通过 Token 解析 project_id) |
| `GET` | `/admin/list` | Admin | 后台获取项目候选人列表 | `Query: ?project_id=1` |
| `POST` | `/import` | Admin | 后台批量导入候选人 | `{ project_id, candidates: [{serial_no, name}] }` |
| `DELETE`| `/admin/delete/:id`| Admin | 彻底删除候选人 | URL Params: `:id` |

### 5. 核心投票 (`/api/vote`)
| 接口方法 | 路径 | 权限 | 描述 | 请求体/参数 (Body/Query) |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/` | Voter | 提交实名选票 (防刷票) | `{ serial_no }` |

---

## 🛠️ 部署与本地调试指南

### 一、 数据库初始化 (MySQL)
1. 确保 MySQL 服务运行，创建一个数据库（如 `voting_system`）。
2. 在数据库中执行完整的表结构 SQL 脚本，务必确保以下核心表及字段存在：
   - `projects` 表
   - `users` 表 (含 `project_id`, `username` 全局唯一索引)
   - `candidates` 表 (含 `project_id` 与 `(project_id, serial_no)` 复合唯一索引)
   - `vote_logs` 表 (含 `project_id` 用以隔离溯源)
3. 并在 `users` 表中手动插入至少一个超级管理员账号 (role: `admin`) 用于首次登录。

### 二、 后端服务启动
1. 进入 `server` 文件夹：
   ```bash
   cd server
   ```
2. 安装依赖 (如果尚未安装)：
   ```bash
   npm install
   ```
3. 检查 `.env` 文件。确保 `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME` 和 `JWT_SECRET` 配置正确无误。
4. 启动 Node.js 服务器：
   ```bash
   node app.js
   # 或者使用 pm2 守护进程: pm2 start app.js --name "vote-api"
   ```
5. 看到 `🚀 SaaS 多项目投票平台 - 后端核心服务已启动！` 说明后端正常运行。

### 三、 前端调试注意事项
1. **API 地址配置**：打开 `client/js/auth.js`，确认 `CONFIG.API_BASE` 的值：
   - 本地调试时，请使用 `http://127.0.0.1:3000/api`
   - 上线部署时，务必将其改为你云服务器的真实公网 IP 或域名。
2. **启动方式**：强烈建议不要直接双击 `.html` 文件打开，而是使用 VS Code 的 **Live Server** 插件，或将 `client` 文件夹部署到 Nginx/宝塔面板中，以 `http://` 协议运行前端，避免浏览器本地的跨域策略限制。
3. **缓存清理**：如果遇到死循环跳转或身份错乱，可以在浏览器控制台 (F12) 运行 `localStorage.clear()` 彻底清理旧的鉴权缓存。