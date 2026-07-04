const express = require('express');
const cors = require('cors');
// 载入 .env 环境变量文件中的配置
require('dotenv').config();

const app = express();

// ============================================================================
// 1. 全局安检与预处理中间件 (必须放在所有路由的最前面)
// ============================================================================
app.use(cors());         // 允许前端跨域访问 (CORS)，解决前后端分离时的端口不一致问题
app.use(express.json()); // 内置 JSON 解析器，将前端发来的 JSON 数据自动转化为 req.body 对象
const path = require('path');
app.use(express.static(path.join(__dirname, '../client')));

// ============================================================================
// 2. 导入具体的业务路由模块
// ============================================================================
const authRoutes = require('./routes/auth');           // 登录与身份签发模块
const projectRoutes = require('./routes/project');     // 投票项目管理模块 (SaaS基石)
const userRoutes = require('./routes/user');           // 选民账号管理模块 (支持批量导入)
const candidateRoutes = require('./routes/candidate'); // 候选人管理模块 (支持批量导入)
const voteRoutes = require('./routes/vote');           // 核心防刷票实名投票模块

// ============================================================================
// 3. 注册并挂载路由 (分配统一的 API 前缀)
// ============================================================================
app.use('/api/auth', authRoutes);             // 统一登录入口: POST /api/auth/login
app.use('/api/projects', projectRoutes);      // 项目流转入口: GET /api/projects/list 等
app.use('/api/users', userRoutes);            // 选民管理入口: POST /api/users/import 等
app.use('/api/candidates', candidateRoutes);  // 候选人展示与管理入口
app.use('/api/vote', voteRoutes);             // 投票动作专属入口: POST /api/vote

// ============================================================================
// 4. 启动服务器并监听指定端口
// ============================================================================
const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(`\n==================================================`);
    console.log(`🚀 SaaS 多项目投票平台 - 后端核心服务已启动！`);
    console.log(`📡 正在监听端口: ${PORT}`);
    console.log(`🛡️ 租户数据隔离机制与 JWT 身份拦截网已全线生效。`);
    console.log(`==================================================\n`);
});