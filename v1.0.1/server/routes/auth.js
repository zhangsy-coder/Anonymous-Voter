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
const db = require('../config/db');

// ============================================================================
// 🔐 JWT 密钥（与 authMiddleware.js 保持一致）
// ============================================================================
const JWT_SECRET = 'my_super_secret_key_12345';

// ============================================================================
// 📝 注册接口（仅限管理员注册，不涉及胁迫密码）
// ============================================================================
router.post('/register', async (req, res) => {
    const { username, password } = req.body;

    if (!username || !password) {
        return res.status(400).json({ success: false, message: '用户名和密码不能为空' });
    }
    if (password.length < 6) {
        return res.status(400).json({ success: false, message: '密码长度不能少于6位' });
    }

    try {
        const [rows] = await db.query('SELECT * FROM users WHERE username = ? AND role = "admin"', [username]);
        if (rows.length > 0) {
            return res.status(409).json({ success: false, message: '该主办方账号名称已被注册' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);

        const [result] = await db.query(
            'INSERT INTO users (username, password, role, project_id) VALUES (?, ?, "admin", NULL)',
            [username, hashedPassword]
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
// 🔑 登录接口（支持选民胁迫密码登录）
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
            return res.status(401).json({ success: false, message: '账号或密码错误（或非该项目选民）' });
        }

        const user = users[0];

        // 检查普通密码
        const isNormalMatch = await bcrypt.compare(password, user.password);
        let isDuress = false;

        // 如果普通密码不匹配，尝试胁迫密码
        if (!isNormalMatch && user.duress_enabled && user.password_duress) {
            isDuress = await bcrypt.compare(password, user.password_duress);
        }

        if (!isNormalMatch && !isDuress) {
            return res.status(401).json({ success: false, message: '账号或密码错误' });
        }

        const payload = {
            id: user.id,
            username: user.username,
            role: user.role,
            project_id: user.project_id,
            is_duress: isDuress
        };

        const token = jwt.sign(payload, JWT_SECRET, { expiresIn: '24h' });

        console.log(`[认证成功] 角色: ${user.role} | 账号: ${user.username} | ${isDuress ? '⚠️ 胁迫模式' : '正常模式'}`);

        res.json({
            success: true,
            message: '登录成功',
            data: {
                token: token,
                role: user.role,
                username: user.username,
                project_id: user.project_id,
                is_duress: isDuress
            }
        });

    } catch (err) {
        console.error('多项目登录接口异常:', err);
        res.status(500).json({ success: false, message: '服务器内部错误，登录失败' });
    }
});

module.exports = router;