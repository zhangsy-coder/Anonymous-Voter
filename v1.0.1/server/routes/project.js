/**
 * ============================================================================
 * SaaS 匿名投票系统 - Node.js 项目管理路由 (多租户核心引擎)
 * 核心职责：项目的创建、关停、级联删除，以及面向公众开放的进行中/已结束活动列表抓取
 * 
 * 🆕 改进点：所有项目与创建者（admin）绑定，实现多管理员隔离
 * ============================================================================
 */

const express = require('express');
const router = express.Router();
const db = require('../config/db');
const verifyToken = require('../middleware/authMiddleware');
const axios = require('axios');

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://127.0.0.1:5000';

/**
 * 🔒 局部中间件：活动主办方（管理员）权限二次安全审计
 */
const isAdmin = (req, res, next) => {
    if (req.user && req.user.role === 'admin') {
        next();
    } else {
        res.status(403).json({ success: false, message: '越权操作被拒绝：当前操作仅限活动主办方访问' });
    }
};

// ============================================================================
// 👥 【开放接口域】（选民通道 / 游客门户 —— 免登录 JWT 验证拦截）
// ============================================================================

/**
 * @route   GET /api/projects/public_list
 * @desc    供选民在登录前，于下拉菜单中动态加载当前【进行中】的投票活动列表
 * @access  Public
 */
router.get('/public_list', async (req, res) => {
    try {
        const [projects] = await db.query(
            'SELECT id, title, description FROM projects WHERE status = 1 ORDER BY id DESC'
        );
        res.json({ success: true, data: projects });
    } catch (err) {
        console.error('公开进行中项目列表获取失败:', err);
        res.status(500).json({ success: false, message: '获取可参与的投票活动列表失败' });
    }
});

/**
 * @route   GET /api/projects/public_ended_list
 * @desc    供首页大盘展示当前【已结束】的历史投票活动归档
 * @access  Public
 */
router.get('/public_ended_list', async (req, res) => {
    try {
        const [projects] = await db.query(
            'SELECT id, title, description, created_at FROM projects WHERE status = 0 ORDER BY id DESC'
        );

        for (let proj of projects) {
            const [cands] = await db.query(
                'SELECT name, vote_count FROM candidates WHERE project_id = ? ORDER BY vote_count DESC LIMIT 1',
                [proj.id]
            );
            proj.winner = cands.length > 0 ? cands[0] : { name: '无人参选', vote_count: 0 };
        }

        res.json({ success: true, data: projects });
    } catch (err) {
        console.error('获取历史归档公示列表失败:', err);
        res.status(500).json({ success: false, message: '获取历史归档公示数据失败' });
    }
});

/**
 * @route   GET /api/projects/public_results/:id
 * @desc    供任何人查看已结束项目的完整候选人排榜单
 * @access  Public
 */
router.get('/public_results/:id', async (req, res) => {
    const { id } = req.params;
    try {
        const [projects] = await db.query('SELECT id, title, status FROM projects WHERE id = ?', [id]);
        if (projects.length === 0 || projects[0].status !== 0) {
            return res.status(403).json({ success: false, message: '该项目尚在进行中或不存在，结果未公开' });
        }

        const [candidates] = await db.query(
            'SELECT serial_no, name, vote_count FROM candidates WHERE project_id = ? ORDER BY vote_count DESC',
            [id]
        );

        res.json({
            success: true,
            data: {
                projectTitle: projects[0].title,
                candidates: candidates
            }
        });
    } catch (err) {
        console.error('获取项目完整结果失败:', err);
        res.status(500).json({ success: false, message: '获取完整结果失败' });
    }
});

// ============================================================================
// ⚙️ 【管理接口域】（仅限主办方控制台 —— 需实名 JWT + 管理员角色双重拦截）
// ============================================================================

/**
 * @route   GET /api/projects/list
 * @desc    只返回当前管理员自己创建的项目列表（多管理员隔离）
 * @access  Private
 */
router.get('/list', verifyToken, isAdmin, async (req, res) => {
    const adminId = req.user.id;
    try {
        const [projects] = await db.query(
            'SELECT * FROM projects WHERE created_by = ? ORDER BY created_at DESC',
            [adminId]
        );
        res.json({ success: true, data: projects });
    } catch (err) {
        console.error('大盘项目列表获取失败:', err);
        res.status(500).json({ success: false, message: '获取大盘项目数据失败' });
    }
});

/**
 * @route   POST /api/projects/create
 * @desc    创建项目时自动绑定当前管理员ID
 * @access  Private
 */
router.post('/create', verifyToken, isAdmin, async (req, res) => {
    const { title, description } = req.body;
    const adminId = req.user.id;
    const adminName = req.user.username;

    if (!title) return res.status(400).json({ success: false, message: '参数错误：项目名称不能为空' });

    try {
        const [result] = await db.query(
            'INSERT INTO projects (title, description, status, created_by, created_by_name) VALUES (?, ?, 1, ?, ?)',
            [title, description || '', adminId, adminName]
        );
        const newProjectId = result.insertId;

        console.log(`\n[Node.js 网关] 管理员 ${adminName} (ID: ${adminId}) 创建了项目 [ID: ${newProjectId}]`);

        try {
            await axios.post(`${PYTHON_SERVICE_URL}/python/generate_keys`, { project_id: newProjectId });
            console.log(`[Node.js 网关] Python 引擎响应成功！已生成项目 ${newProjectId} 的 PEM 密钥文件。\n`);
        } catch (pythonErr) {
            console.error(`[Node.js 网关] 联动 Python 密码学引擎失败: ${pythonErr.message}`);
            throw new Error('底层区块链密码学环境初始化失败，请核查 Python 服务状态。');
        }

        res.json({ success: true, message: '项目创建成功，密码学密钥已同步下发！', data: { project_id: newProjectId } });
    } catch (err) {
        console.error('创建项目路由致命异常:', err);
        res.status(500).json({ success: false, message: err.message || '服务器内部错误，项目创建失败' });
    }
});

/**
 * @route   GET /api/projects/check_owner/:id
 * @desc    检查当前管理员是否为该项目的创建者
 * @access  Private
 */
router.get('/check_owner/:id', verifyToken, isAdmin, async (req, res) => {
    const projectId = req.params.id;
    const adminId = req.user.id;

    try {
        const [projects] = await db.query(
            'SELECT created_by FROM projects WHERE id = ?',
            [projectId]
        );
        if (projects.length === 0) {
            return res.status(404).json({ success: false, message: '项目不存在' });
        }
        // 🚀 核心修复：强制转为字符串比对，防止隐式类型越权拦截误判
        const isOwner = String(projects[0].created_by) === String(adminId);
        res.json({ success: true, data: { isOwner } });
    } catch (err) {
        res.status(500).json({ success: false, message: '校验失败' });
    }
});

/**
 * @route   POST /api/projects/end/:id
 * @desc    活动管理面板一键计票结算（需校验创建者身份）
 * @access  Private
 */
router.post('/end/:id', verifyToken, isAdmin, async (req, res) => {
    const { id } = req.params;
    const adminId = req.user.id;

    try {
        const [project] = await db.query('SELECT created_by FROM projects WHERE id = ?', [id]);
        if (project.length === 0) {
            return res.status(404).json({ success: false, message: '项目不存在' });
        }
        // 🚀 核心修复：强制转为字符串比对
        if (String(project[0].created_by) !== String(adminId)) {
            return res.status(403).json({ success: false, message: '您不是该项目的创建者，无权结算' });
        }

        const [result] = await db.query('UPDATE projects SET status = 0 WHERE id = ?', [id]);

        if (result.affectedRows === 0) {
            return res.status(404).json({ success: false, message: '结算失败：找不到指定的活动项目' });
        }

        console.log(`[Node.js 网关] 活动项目 [ID: ${id}] 已成功结算上锁。`);
        res.json({ success: true, message: '项目已结算上锁，当前活动已被强制转换为只读审计状态' });
    } catch (err) {
        console.error('关停项目状态机失败:', err);
        res.status(500).json({ success: false, message: '结算失败，网关内部执行异常' });
    }
});

/**
 * @route   DELETE /api/projects/delete/:id
 * @desc    物理级联清理整个项目（需校验创建者身份）
 * @access  Private
 */
router.delete('/delete/:id', verifyToken, isAdmin, async (req, res) => {
    const { id } = req.params;
    const adminId = req.user.id;

    console.log(`\n🚨 [高危级联预警] 管理员 ${adminId} 正在请求物理销毁项目 [ID: ${id}]...`);

    try {
        const [project] = await db.query('SELECT created_by FROM projects WHERE id = ?', [id]);
        if (project.length === 0) {
            return res.status(404).json({ success: false, message: '项目不存在' });
        }
        // 🚀 核心修复：强制转为字符串比对
        if (String(project[0].created_by) !== String(adminId)) {
            return res.status(403).json({ success: false, message: '您不是该项目的创建者，无权删除' });
        }

        // 🚀 核心修复：追加底层区块链与日志数据表的级联抹除，做到比赛级别的数据粉碎
        await db.query('DELETE FROM vote_main WHERE project_id = ?', [id]);
        await db.query('DELETE FROM hash_chain WHERE project_id = ?', [id]);
        await db.query('DELETE FROM system_log WHERE project_id = ?', [id]);
        await db.query('DELETE FROM ai_security_log WHERE project_id = ?', [id]);

        await db.query('DELETE FROM candidates WHERE project_id = ?', [id]);
        await db.query('DELETE FROM users WHERE project_id = ? AND role = "voter"', [id]);
        await db.query('DELETE FROM signature_logs WHERE project_id = ?', [id]);
        await db.query('DELETE FROM projects WHERE id = ?', [id]);

        console.log(`🚨 项目 [ID: ${id}] 及其关联数据已物理删除！\n`);

        res.json({ success: true, message: '该投票项目及其名下的所有候选人、选民账户与链上日志已彻底清理完毕！' });
    } catch (err) {
        console.error('执行级联销毁失败:', err);
        res.status(500).json({ success: false, message: '级联销毁项目失败' });
    }
});

module.exports = router;