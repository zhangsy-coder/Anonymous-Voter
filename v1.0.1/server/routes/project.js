/**
 * ============================================================================
 * SaaS 匿名投票系统 - Node.js 项目管理路由 (多租户核心引擎)
 * 核心职责：项目的创建、关停、级联删除，以及面向公众开放的进行中/已结束活动列表抓取
 * ============================================================================
 */

const express = require('express');
const router = express.Router();
const db = require('../config/db'); // 引入 MySQL 数据库连接池
const verifyToken = require('../middleware/authMiddleware'); // JWT 身份认证中间件
const axios = require('axios'); // 引入 axios 用于与 Python 密码学微服务进行内网通信

// 从环境变量读取 Python 微服务的内网直连地址，若无则默认本地 5000 端口
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://127.0.0.1:5000';

/**
 * 🔒 局部中间件：活动主办方（管理员）权限二次安全审计
 * 职责：强行拦截普通选民或恶意游客通过伪造 Token 试图闯入管理域
 */
const isAdmin = (req, res, next) => {
    if (req.user && req.user.role === 'admin') {
        next(); // 权限核验通过，放行至下一个核心业务路由函数
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
 * @access  Public (未挂载 verifyToken 中间件)
 */
router.get('/public_list', async (req, res) => {
    try {
        // 【数据脱敏】：登录前只捞出处于“进行中(status = 1)”的项目 ID 和标题，杜绝暴露后台敏感流水
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
 * @desc    🆕 [对应需求三] 供首页大盘展示当前【已结束】的历史投票活动归档，并附带聚合计算出的最终冠军
 * @access  Public
 */
router.get('/public_ended_list', async (req, res) => {
    try {
        // 1. 捞出所有已关停(status = 0)的历史投票项目基本记录
        const [projects] = await db.query(
            'SELECT id, title, description, created_at FROM projects WHERE status = 0 ORDER BY id DESC'
        );

        // 2. 🚀【数据动态聚合（Aggregation）】：依靠循环，为每个已结束的项目追查出得票最高的候选人
        for (let proj of projects) {
            const [cands] = await db.query(
                'SELECT name, vote_count FROM candidates WHERE project_id = ? ORDER BY vote_count DESC LIMIT 1',
                [proj.id]
            );
            // 绑定冠军信息至项目对象中，若无候选人数据则给出“无人参选”的默认数据兜底
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
 * @desc    🆕 供任何人查看已结束项目的完整候选人排榜单
 * @access  Public (免登录验证)
 */
router.get('/public_results/:id', async (req, res) => {
    const { id } = req.params;
    try {
        // 1. 安全校验：确保该项目真的已经结束 (status = 0)
        const [projects] = await db.query('SELECT id, title, status FROM projects WHERE id = ?', [id]);
        if (projects.length === 0 || projects[0].status !== 0) {
            return res.status(403).json({ success: false, message: '该项目尚在进行中或不存在，结果未公开' });
        }

        // 2. 拉取所有候选人，并按票数从高到低排序
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
 * @desc    主办方大盘获取所有的投票项目列表（包含进行中和已结束，用于控制台卡片渲染）
 * @access  Private
 */
router.get('/list', verifyToken, isAdmin, async (req, res) => {
    try {
        const [projects] = await db.query('SELECT * FROM projects ORDER BY created_at DESC');
        res.json({ success: true, data: projects });
    } catch (err) {
        console.error('大盘项目列表获取失败:', err);
        res.status(500).json({ success: false, message: '获取大盘项目数据失败' });
    }
});

/**
 * @route   POST /api/projects/create
 * @desc    主办方创建一个新的投票项目，并动态异步联动 Python 密码学引擎同步部署非对称密钥文件
 * @access  Private
 */
router.post('/create', verifyToken, isAdmin, async (req, res) => {
    const { title, description } = req.body;
    if (!title) return res.status(400).json({ success: false, message: '参数错误：项目名称不能为空' });

    try {
        // 1. 往 MySQL 关系型数据库 projects 表中抢先插入一条基本的活动记录
        const [result] = await db.query(
            'INSERT INTO projects (title, description, status) VALUES (?, ?, 1)',
            [title, description || '']
        );
        const newProjectId = result.insertId; // 捕获自增的主键项目租户 ID

        // 2. 🚀【租户密码学环境同步联动】：发起内网 HTTP 请求，通知 Python 微服务生成文件级 RSA 密钥对
        console.log(`\n[Node.js 网关] 活动项目 [ID: ${newProjectId}] 关系记录创建成功，正在呼叫 Python 同步密码学底座...`);
        try {
            await axios.post(`${PYTHON_SERVICE_URL}/python/generate_keys`, { project_id: newProjectId });
            console.log(`[Node.js 网关] Python 引擎响应成功！已成功在磁盘生成项目 ${newProjectId} 的独立 PEM 密钥文件。\n`);
        } catch (pythonErr) {
            // 【致命依赖熔断】：若密钥文件创建失败，属于业务重大异常，抛出错误阻断后续数据入账
            console.error(`[Node.js 网关] 联动 Python 密码学引擎发生阻断性失败: ${pythonErr.message}`);
            throw new Error('底层区块链密码学环境初始化失败，请核查 Python 服务的通电状态。');
        }

        res.json({ success: true, message: '项目创建成功，密码学密钥已同步下发！', data: { project_id: newProjectId } });
    } catch (err) {
        console.error('创建项目路由致命异常:', err);
        res.status(500).json({ success: false, message: err.message || '服务器内部错误，项目创建失败' });
    }
});

/**
 * @route   POST /api/projects/end/:id
 * @desc    🆕 [对应需求二] 活动管理面板一键计票结算，切断选民投票通道（封盘上锁）
 * @access  Private
 */
router.post('/end/:id', verifyToken, isAdmin, async (req, res) => {
    const { id } = req.params;
    try {
        // 【状态机硬关断】：将 status 字段从 1(进行中) 修正更新为 0(已结束)
        const [result] = await db.query('UPDATE projects SET status = 0 WHERE id = ?', [id]);

        if (result.affectedRows === 0) {
            return res.status(404).json({ success: false, message: '结算失败：找不到指定的活动项目' });
        }

        console.log(`[Node.js 网关] 活动项目 [ID: ${id}] 已成功结算上锁，投票通道已对公众永久关闭。`);
        res.json({ success: true, message: '项目已结算上锁，当前活动已被强制转换为只读审计状态' });
    } catch (err) {
        console.error('关停项目状态机失败:', err);
        res.status(500).json({ success: false, message: '结算失败，网关内部执行异常' });
    }
});

/**
 * @route   DELETE /api/projects/delete/:id
 * @desc    🆕 [对应需求二] 最高危路由：物理级联清理整个项目及其名下绑定的所有多租户候选人、选民账户和领票日志
 * @access  Private
 */
router.delete('/delete/:id', verifyToken, isAdmin, async (req, res) => {
    const { id } = req.params;
    console.log(`\n🚨 [高危级联预警] 管理员正在请求物理销毁项目 [ID: ${id}] 的全套隔离环境...`);

    try {
        // 🚀【严谨的级联事务清理（Cascading Delete）】
        // 由于没有设置硬性级联外键，为了杜绝产生大量的“孤儿僵尸数据”，网关必须顺藤摸瓜，从最底层的子表向主表依次清理

        // 1. 清空归属于该项目的所有候选人及得票快照
        await db.query('DELETE FROM candidates WHERE project_id = ?', [id]);

        // 2. 清空归属于该项目批量分发出的所有选民账号 (加角色限制，严防误切掉管理员 admin 本身)
        await db.query('DELETE FROM users WHERE project_id = ? AND role = "voter"', [id]);

        // 3. 清空该项目沉淀下来的所有实名领票核销记录
        await db.query('DELETE FROM signature_logs WHERE project_id = ?', [id]);

        // 4. 拔除最后的根基：删除 projects 表中的项目主记录
        await db.query('DELETE FROM projects WHERE id = ?', [id]);

        console.log(`🚨 [销毁大盘落定] 项目 [ID: ${id}] 关联的数千条多租户碎片段已成功从 MySQL 物理蒸发！\n`);

        res.json({ success: true, message: '该投票项目及其名下的所有候选人、选民账户已彻底级联清理完毕！' });
    } catch (err) {
        console.error('执行级联销毁失败:', err);
        res.status(500).json({ success: false, message: '级联销毁项目失败，数据库连接池可能存在死锁' });
    }
});

module.exports = router;