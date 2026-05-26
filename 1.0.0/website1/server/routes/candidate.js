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

// ============================================================================
// 【普通投票者接口】
// ============================================================================

/**
 * @route   GET /api/candidates
 * @desc    获取当前选民所属项目下的候选人排行榜
 * @access  已登录的投票者 (携带的 Token 中包含 project_id)
 */
router.get('/', verifyToken, async (req, res) => {
    // 【SaaS 核心逻辑】：从解密后的 JWT Token 中，提取该选民绑定的项目 ID
    const projectId = req.user.project_id;

    if (!projectId) {
        return res.status(400).json({ success: false, message: '无法识别您所属的投票项目' });
    }

    try {
        // 【租户隔离】：强制加上 WHERE project_id = ? 条件
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
 * @desc    主办方获取指定项目下的所有候选人 (包含已禁用的)
 * @调用示例 GET /api/candidates/admin/list?project_id=1
 */
router.get('/admin/list', verifyToken, isAdmin, async (req, res) => {
    const { project_id } = req.query;

    if (!project_id) {
        return res.status(400).json({ success: false, message: '请求失败：必须指定项目ID' });
    }

    try {
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
 * @desc    主办方批量导入指定项目下的候选人
 * @数据格式 { "project_id": 1, "candidates": [{"serial_no": "01", "name": "张三"}, ...] }
 */
router.post('/import', verifyToken, isAdmin, async (req, res) => {
    const { project_id, candidates } = req.body;

    if (!project_id || !candidates || !Array.isArray(candidates) || candidates.length === 0) {
        return res.status(400).json({ success: false, message: '参数错误：批量导入的数据不能为空' });
    }

    let successCount = 0;
    let failList = [];

    // 遍历批量处理候选人数据
    for (const cand of candidates) {
        const serial_no = cand.serial_no ? String(cand.serial_no).trim() : '';
        const name = cand.name ? String(cand.name).trim() : '';

        // 基础清洗
        if (!serial_no || !name) {
            failList.push({ serial_no: serial_no || '空序号', reason: '序号和姓名不能为空' });
            continue; // 跳过，处理下一条
        }

        try {
            // 插入数据库，绑定 project_id
            await db.query(
                'INSERT INTO candidates (project_id, serial_no, name, vote_count, status) VALUES (?, ?, ?, 0, 1)',
                [project_id, serial_no, name]
            );
            successCount++;
        } catch (err) {
            // 我们在数据库升级时，把唯一索引改成了 (`project_id`, `serial_no`) 复合索引
            // 只有同一个项目下出现重复序号才会报错，不同项目间的序号是可以重复的！
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
 * @desc    主办方删除指定的候选人
 */
router.delete('/admin/delete/:id', verifyToken, isAdmin, async (req, res) => {
    const { id } = req.params;
    try {
        await db.query('DELETE FROM candidates WHERE id = ?', [id]);
        res.json({ success: true, message: '候选人彻底删除成功' });
    } catch (err) {
        res.status(500).json({ success: false, message: '删除失败', error: err.message });
    }
});

module.exports = router;