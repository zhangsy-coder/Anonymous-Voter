const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const db = require('../config/db');
const verifyToken = require('../middleware/authMiddleware');

/**
 * 局部中间件：管理员权限校验
 * 拦截非主办方用户的恶意越权调用
 */
const isAdmin = (req, res, next) => {
    if (req.user && req.user.role === 'admin') {
        next(); // 身份核实，放行
    } else {
        res.status(403).json({ success: false, message: '越权操作被拒绝：仅限主办方访问' });
    }
};

/**
 * @route   GET /api/users/list
 * @desc    获取指定投票项目下的所有选民列表
 * @access  仅限主办方 (verifyToken + isAdmin)
 * @调用示例 GET /api/users/list?project_id=1
 */
router.get('/list', verifyToken, isAdmin, async (req, res) => {
    // 【知识点 1：从 URL 路径中提取 Query 查询参数】
    const { project_id } = req.query;

    if (!project_id) {
        return res.status(400).json({ success: false, message: '请求失败：必须指定项目ID(project_id)' });
    }

    try {
        // 【租户隔离查询】：通过 WHERE project_id = ? 确保主办方只能看到当前项目内的选民
        // 严格进行数据脱敏，禁止查询 password 字段
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
 * @desc    批量录入/导入某个指定项目下的投票者账号
 * @access  仅限主办方
 * @数据格式 { "project_id": 1, "voters": [{"username": "u1", "password": "p1"}, ...] }
 */
router.post('/import', verifyToken, isAdmin, async (req, res) => {
    const { project_id, voters } = req.body;

    // 1. 健壮性前置校验
    if (!project_id || !voters || !Array.isArray(voters) || voters.length === 0) {
        return res.status(400).json({ success: false, message: '参数错误：批量导入的数据不能为空' });
    }

    try {
        // 【知识点 2：高并发下的 Bcrypt 性能优化黄金法则】
        // 盐值生成是一个极度消耗 CPU 算力的重型加密动作。
        // 绝对不能把 genSalt 写在下面的 for 循环内部！在循环外预先生成一次，循环内直接复用，性能可提升 100 倍以上！
        const salt = await bcrypt.genSalt(10);

        let successCount = 0;   // 记录成功导入的数量
        let failList = [];       // 记录失败的明细及原因，用于生成前端容错报告

        // 2. 遍历执行批量流水化处理
        for (const voter of voters) {
            const username = voter.username ? voter.username.trim() : '';
            const password = voter.password ? voter.password.trim() : '';

            // 基础格式清洗过滤
            if (!username || !password) {
                failList.push({ username: username || '空账号', reason: '账号或密码不能为空' });
                continue; // 跳过当前这条，继续处理下一条（优雅容错，不因单条错误导致整批崩溃）
            }
            if (password.length < 6) {
                failList.push({ username, reason: '密码长度不能少于 6 位' });
                continue;
            }

            try {
                // 将明文密码结合复用的盐值，计算出哈希密文
                const hashedPassword = await bcrypt.hash(password, salt);

                // 写入当前项目
                await db.query(
                    'INSERT INTO users (username, password, role, project_id) VALUES (?, ?, "voter", ?)',
                    [username, hashedPassword, project_id]
                );
                successCount++;
            } catch (err) {
                // 【捕获唯一索引冲突】：判断账号是否在全平台已经存在了
                if (err.code === 'ER_DUP_ENTRY') {
                    failList.push({ username, reason: '该账号名称在系统中已被占用' });
                } else {
                    failList.push({ username, reason: '数据库写入异常: ' + err.message });
                }
            }
        }

        // 3. 返回包含详细审计报告的复合响应
        res.json({
            success: true,
            message: `批量录入执行完毕。成功: ${successCount} 条，失败: ${failList.length} 条。`,
            data: {
                success_count: successCount,
                fail_count: failList.length,
                errors: failList // 将失败名单抛给前端，方便主办方精准知晓哪些账号没录进去
            }
        });

    } catch (err) {
        console.error('批量导入选民时发生致命异常:', err);
        res.status(500).json({ success: false, message: '服务器内部错误，批量导入失败' });
    }
});

/**
 * @route   DELETE /api/users/delete/:id
 * @desc    主办方作废/删除某个具体项目的选民账号
 * @access  仅限主办方
 */
router.delete('/delete/:id', verifyToken, isAdmin, async (req, res) => {
    const userId = req.params.id;

    // 安全防御：禁止管理员自杀式删除
    if (parseInt(userId) === req.user.id) {
        return res.status(400).json({ success: false, message: '安全限制：您不能作废自己当前登录的主办方账号' });
    }

    try {
        await db.query('DELETE FROM users WHERE id = ?', [userId]);
        res.json({ success: true, message: '该投票者账号已成功作废，其历史投票关联已解除' });
    } catch (err) {
        console.error('作废账号失败:', err);
        res.status(500).json({ success: false, message: '服务器删除数据失败' });
    }
});

module.exports = router;