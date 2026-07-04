const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
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

/**
 * @route   GET /api/users/list
 * @desc    🆕 改进：校验当前管理员是否为该项目的创建者
 */
router.get('/list', verifyToken, isAdmin, async (req, res) => {
    const { project_id } = req.query;
    const adminId = req.user.id;

    if (!project_id) {
        return res.status(400).json({ success: false, message: '请求失败：必须指定项目ID(project_id)' });
    }

    try {
        const [project] = await db.query('SELECT created_by FROM projects WHERE id = ?', [project_id]);
        if (project.length === 0) {
            return res.status(404).json({ success: false, message: '项目不存在' });
        }
        if (project[0].created_by !== adminId) {
            return res.status(403).json({ success: false, message: '您不是该项目的创建者，无权查看' });
        }

        const [users] = await db.query(
            'SELECT id, username, role, project_id, created_at FROM users WHERE project_id = ? AND role = "voter" ORDER BY created_at DESC',
            [project_id]
        );

        res.json({ success: true, data: users });
    } catch (err) {
        console.error('获取项目选民列表失败:', err);
        res.status(500).json({ success: false, message: '服务器内部错误，读取数据失败' });
    }
});

/**
 * @route   POST /api/users/import
 * @desc    🆕 改进：校验当前管理员是否为该项目的创建者
 */
router.post('/import', verifyToken, isAdmin, checkProjectOwner, async (req, res) => {
    const { project_id, voters } = req.body;

    if (!project_id || !voters || !Array.isArray(voters) || voters.length === 0) {
        return res.status(400).json({ success: false, message: '参数错误：批量导入的数据不能为空' });
    }

    try {
        const salt = await bcrypt.genSalt(10);

        let successCount = 0;
        let failList = [];

        for (const voter of voters) {
            const username = voter.username ? voter.username.trim() : '';
            const password = voter.password ? voter.password.trim() : '';

            if (!username || !password) {
                failList.push({ username: username || '空账号', reason: '账号或密码不能为空' });
                continue;
            }
            if (password.length < 6) {
                failList.push({ username, reason: '密码长度不能少于 6 位' });
                continue;
            }

            try {
                const hashedPassword = await bcrypt.hash(password, salt);
                await db.query(
                    'INSERT INTO users (username, password, role, project_id) VALUES (?, ?, "voter", ?)',
                    [username, hashedPassword, project_id]
                );
                successCount++;
            } catch (err) {
                if (err.code === 'ER_DUP_ENTRY') {
                    failList.push({ username, reason: '该账号名称在系统中已被占用' });
                } else {
                    failList.push({ username, reason: '数据库写入异常: ' + err.message });
                }
            }
        }

        res.json({
            success: true,
            message: `批量录入执行完毕。成功: ${successCount} 条，失败: ${failList.length} 条。`,
            data: {
                success_count: successCount,
                fail_count: failList.length,
                errors: failList
            }
        });

    } catch (err) {
        console.error('批量导入选民时发生致命异常:', err);
        res.status(500).json({ success: false, message: '服务器内部错误，批量导入失败' });
    }
});

/**
 * @route   DELETE /api/users/delete/:id
 * @desc    🆕 改进：校验当前管理员是否为该项目的创建者
 */
router.delete('/delete/:id', verifyToken, isAdmin, async (req, res) => {
    const userId = req.params.id;
    const adminId = req.user.id;

    if (parseInt(userId) === adminId) {
        return res.status(400).json({ success: false, message: '安全限制：您不能作废自己当前登录的主办方账号' });
    }

    try {
        // 🆕 先查询该用户所属的项目，再校验创建者
        const [user] = await db.query('SELECT project_id FROM users WHERE id = ?', [userId]);
        if (user.length === 0) {
            return res.status(404).json({ success: false, message: '用户不存在' });
        }
        const [project] = await db.query('SELECT created_by FROM projects WHERE id = ?', [user[0].project_id]);
        if (project.length === 0 || project[0].created_by !== adminId) {
            return res.status(403).json({ success: false, message: '您不是该项目的创建者，无权删除' });
        }

        await db.query('DELETE FROM users WHERE id = ?', [userId]);
        res.json({ success: true, message: '该投票者账号已成功作废' });
    } catch (err) {
        console.error('作废账号失败:', err);
        res.status(500).json({ success: false, message: '服务器删除数据失败' });
    }
});

module.exports = router;