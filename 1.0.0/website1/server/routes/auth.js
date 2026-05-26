/**
 * ============================================================================
 * SaaS 多项目投票平台 - 统一认证网关路由 (多租户隔离版)
 * 核心职责：动态区分管理员与选民、执行(账号+项目ID)联合安全校验、签发多租户 JWT
 * ============================================================================
 */

const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../config/db'); // 引入 MySQL 数据库连接池

/**
 * @route   POST /api/auth/login
 * @desc    多项目/多租户模式下的多维度登录接口
 * @access  公开访问
 */
router.post('/login', async (req, res) => {
    // 1. 🚀 [重写]: 从前端请求体中解构出四个核心参数（新增登录类型与项目ID）
    const { username, password, loginType, project_id } = req.body;

    // 2. 基础数据非空校验
    if (!username || !password) {
        return res.status(400).json({ success: false, message: '账号和密码不能为空' });
    }

    // 🚀 [核心业务校验]: 如果是选民通道登录，必须强制要求提供所选的项目 ID
    if (loginType === 'voter' && !project_id) {
        return res.status(400).json({ success: false, message: '登录失败：选民登录必须选择具体的投票项目' });
    }

    try {
        let users = [];

        // 3. 🚀 [多租户核心流转]: 根据不同身份，执行不同的 SQL 查询策略
        if (loginType === 'admin') {
            // 主办方策略：全局唯一，直接依靠用户名和角色锁定记录
            const [rows] = await db.query(
                'SELECT * FROM users WHERE username = ? AND role = "admin"',
                [username]
            );
            users = rows;
        } else {
            // 选民策略：多租户隔离！利用 (project_id + username) 联合钥匙开门
            // 这样不同项目下的相同用户名（如 project 1 的 user001 和 project 2 的 user001）就能精准区分
            const [rows] = await db.query(
                'SELECT * FROM users WHERE username = ? AND project_id = ? AND role = "voter"',
                [username, project_id]
            );
            users = rows;
        }

        // 4. 账号存在性校验（模糊提示，防止黑客暴力撞库枚举用户）
        if (users.length === 0) {
            return res.status(401).json({ success: false, message: '账号或密码错误' });
        }

        // 提取出查询到的单条用户记录对象
        const user = users[0];

        // 5. 密码哈希解密比对（安全比对盐值后的密文）
        const isMatch = await bcrypt.compare(password, user.password);
        if (!isMatch) {
            return res.status(401).json({ success: false, message: '账号或密码错误' });
        }

        // 6. 构建面向多租户隔离的 JWT 载荷 (Payload)
        // 确保 project_id 被动态、准确地写入通行证碎片中
        const payload = {
            id: user.id,
            username: user.username,
            role: user.role,
            project_id: user.project_id // 如果是 admin，这里会自动变为 null；如果是 voter，则是对应整数 ID
        };

        // 7. 签发带多租户上下文的无状态身份令牌 (JWT Token)
        const token = jwt.sign(
            payload,
            process.env.JWT_SECRET || 'your_fallback_secret', // 优先读取系统环境变量
            { expiresIn: '24h' } // 令牌有效期 24 小时
        );

        // 8. 成功响应：将多租户上下文 Token 及流转字段打包返回给前端
        console.log(`[认证成功] 角色: ${user.role} | 账号: ${user.username} | 所属项目: ${user.project_id || '全局(主办方)'}`);

        res.json({
            success: true,
            message: '登录成功',
            data: {
                token: token,
                role: user.role,
                username: user.username,
                project_id: user.project_id // 返回给前端，用于辅助前端执行无感知分流
            }
        });

    } catch (err) {
        console.error('多项目登录接口异常:', err);
        res.status(500).json({ success: false, message: '服务器内部错误，登录失败' });
    }
});

module.exports = router;