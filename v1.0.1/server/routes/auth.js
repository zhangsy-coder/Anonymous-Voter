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

// ============================================================================
// 🔐 JWT 密钥（与 authMiddleware.js 保持一致）
// ============================================================================
const JWT_SECRET = 'my_super_secret_key_12345';

// ============================================================================
// 📝 注册接口（开放注册，任何人都能成为管理员）
// ============================================================================
router.post('/register', async (req, res) => {
    const { username, password } = req.body;

    // 1. 输入校验
    if (!username || !password) {
        return res.status(400).json({ success: false, message: '用户名和密码不能为空' });
    }
    if (password.length < 6) {
        return res.status(400).json({ success: false, message: '密码长度不能少于6位' });
    }

    try {
        // 2. 检查用户名是否已被占用
        const [rows] = await db.query('SELECT * FROM users WHERE username = ?', [username]);
        if (rows.length > 0) {
            return res.status(409).json({ success: false, message: '用户名已被注册' });
        }

        // 3. 加密密码
        const hashedPassword = await bcrypt.hash(password, 10);

        // 4. 插入新用户，角色默认为 admin（可创建项目）
        const [result] = await db.query(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            [username, hashedPassword, 'admin']
        );

        console.log(`[注册成功] 新管理员: ${username}`);

        res.status(201).json({
            success: true,
            message: '注册成功！请前往登录',
            data: { id: result.insertId, username, role: 'admin' }
        });

    } catch (err) {
        console.error('注册接口异常:', err);
        res.status(500).json({ success: false, message: '服务器内部错误，注册失败' });
    }
});

// ============================================================================
// 🔑 登录接口
// ============================================================================
router.post('/login', async (req, res) => {
    const { username, password, loginType, project_id } = req.body;

    if (!username || !password) {
        return res.status(400).json({ success: false, message: '账号和密码不能为空' });
    }

    if (loginType === 'voter' && !project_id) {
        return res.status(400).json({ success: false, message: '登录失败：选民登录必须选择具体的投票项目' });
    }

    try {
        let users = [];

        if (loginType === 'admin') {
            const [rows] = await db.query(
                'SELECT * FROM users WHERE username = ? AND role = "admin"',
                [username]
            );
            users = rows;
        } else {
            const [rows] = await db.query(
                'SELECT * FROM users WHERE username = ? AND project_id = ? AND role = "voter"',
                [username, project_id]
            );
            users = rows;
        }

        if (users.length === 0) {
            return res.status(401).json({ success: false, message: '账号或密码错误' });
        }

        const user = users[0];

        const isMatch = await bcrypt.compare(password, user.password);
        if (!isMatch) {
            return res.status(401).json({ success: false, message: '账号或密码错误' });
        }

        const payload = {
            id: user.id,
            username: user.username,
            role: user.role,
            project_id: user.project_id
        };

        const token = jwt.sign(payload, JWT_SECRET, { expiresIn: '24h' });

        console.log(`[认证成功] 角色: ${user.role} | 账号: ${user.username} | 所属项目: ${user.project_id || '全局(主办方)'}`);

        res.json({
            success: true,
            message: '登录成功',
            data: {
                token: token,
                role: user.role,
                username: user.username,
                project_id: user.project_id
            }
        });

    } catch (err) {
        console.error('多项目登录接口异常:', err);
        res.status(500).json({ success: false, message: '服务器内部错误，登录失败' });
    }
});

module.exports = router;