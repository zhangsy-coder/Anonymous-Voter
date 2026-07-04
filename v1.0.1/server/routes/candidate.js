const express = require('express');
const router = express.Router();
const db = require('../config/db');
const verifyToken = require('../middleware/authMiddleware');

/**
 * 局部中间件：管理员权限校验
 */
const isAdmin = (req, res, next) => {
    if (req.user && req.user.role === 'admin') {
        next();
    } else {
        res.status(403).json({ success: false, message: '越权操作被拒绝：仅限主办方访问' });
    }
};

/**
 * 🆕 校验当前用户是否为该项目的创建者
 */
const checkProjectOwner = async (req, res, next) => {
    const projectId = req.body.project_id || req.query.project_id;
    const adminId = req.user.id;

    if (!projectId) {
        return res.status(400).json({ success: false, message: '缺少项目ID' });
    }

    try {
        const [project] = await db.query('SELECT created_by FROM projects WHERE id = ?', [projectId]);
        if (project.length === 0) {
            return res.status(404).json({ success: false, message: '项目不存在' });
        }
        if (project[0].created_by !== adminId) {
            return res.status(403).json({ success: false, message: '您不是该项目的创建者，无权操作' });
        }
        next();
    } catch (err) {
        res.status(500).json({ success: false, message: '权限校验失败' });
    }
};

// ============================================================================
// 【普通投票者接口】
// ============================================================================

/**
 * @route   GET /api/candidates
 * @desc    获取当前选民所属项目下的候选人排行榜
 * @access  已登录的投票者
 */
router.get('/', verifyToken, async (req, res) => {
    const projectId = req.user.project_id;

    if (!projectId) {
        return res.status(400).json({ success: false, message: '无法识别您所属的投票项目' });
    }

    try {
        const [rows] = await db.query(
            'SELECT id, serial_no, name, vote_count FROM candidates WHERE project_id = ? AND status = 1 ORDER BY vote_count DESC',
            [projectId]
        );
        res.json({ success: true, data: rows });
    } catch (err) {
        console.error('获取排行榜失败:', err);
        res.status(500).json({ success: false, message: '获取数据失败', error: err.message });
    }
});

// ============================================================================
// 【主办方(管理员)接口】
// ============================================================================

/**
 * @route   GET /api/candidates/admin/list
 * @desc    🆕 改进：校验当前管理员是否为该项目的创建者
 */
router.get('/admin/list', verifyToken, isAdmin, async (req, res) => {
    const { project_id } = req.query;
    const adminId = req.user.id;

    if (!project_id) {
        return res.status(400).json({ success: false, message: '请求失败：必须指定项目ID' });
    }

    try {
        // 🆕 校验创建者身份
        const [project] = await db.query('SELECT created_by FROM projects WHERE id = ?', [project_id]);
        if (project.length === 0) {
            return res.status(404).json({ success: false, message: '项目不存在' });
        }
        if (project[0].created_by !== adminId) {
            return res.status(403).json({ success: false, message: '您不是该项目的创建者，无权查看' });
        }

        const [rows] = await db.query(
            'SELECT * FROM candidates WHERE project_id = ? ORDER BY id DESC',
            [project_id]
        );
        res.json({ success: true, data: rows });
    } catch (err) {
        res.status(500).json({ success: false, message: '获取数据失败', error: err.message });
    }
});

/**
 * @route   POST /api/candidates/import
 * @desc    🆕 改进：校验当前管理员是否为该项目的创建者
 */
router.post('/import', verifyToken, isAdmin, checkProjectOwner, async (req, res) => {
    const { project_id, candidates } = req.body;

    if (!project_id || !candidates || !Array.isArray(candidates) || candidates.length === 0) {
        return res.status(400).json({ success: false, message: '参数错误：批量导入的数据不能为空' });
    }

    let successCount = 0;
    let failList = [];

    for (const cand of candidates) {
        const serial_no = cand.serial_no ? String(cand.serial_no).trim() : '';
        const name = cand.name ? String(cand.name).trim() : '';

        if (!serial_no || !name) {
            failList.push({ serial_no: serial_no || '空序号', reason: '序号和姓名不能为空' });
            continue;
        }

        try {
            await db.query(
                'INSERT INTO candidates (project_id, serial_no, name, vote_count, status) VALUES (?, ?, ?, 0, 1)',
                [project_id, serial_no, name]
            );
            successCount++;
        } catch (err) {
            if (err.code === 'ER_DUP_ENTRY') {
                failList.push({ serial_no, reason: '该序号在当前项目中已存在' });
            } else {
                failList.push({ serial_no, reason: '数据库异常: ' + err.message });
            }
        }
    }

    res.json({
        success: true,
        message: `候选人导入完毕。成功: ${successCount} 个，失败: ${failList.length} 个。`,
        data: {
            success_count: successCount,
            fail_count: failList.length,
            errors: failList
        }
    });
});

/**
 * @route   DELETE /api/candidates/admin/delete/:id
 * @desc    🆕 改进：校验当前管理员是否为该项目的创建者
 */
router.delete('/admin/delete/:id', verifyToken, isAdmin, async (req, res) => {
    const { id } = req.params;
    const adminId = req.user.id;

    try {
        // 🆕 先查询该候选人所属的项目，再校验创建者
        const [candidate] = await db.query('SELECT project_id FROM candidates WHERE id = ?', [id]);
        if (candidate.length === 0) {
            return res.status(404).json({ success: false, message: '候选人不存在' });
        }
        const [project] = await db.query('SELECT created_by FROM projects WHERE id = ?', [candidate[0].project_id]);
        if (project.length === 0 || project[0].created_by !== adminId) {
            return res.status(403).json({ success: false, message: '您不是该项目的创建者，无权删除' });
        }

        await db.query('DELETE FROM candidates WHERE id = ?', [id]);
        res.json({ success: true, message: '候选人彻底删除成功' });
    } catch (err) {
        res.status(500).json({ success: false, message: '删除失败', error: err.message });
    }
});

module.exports = router;