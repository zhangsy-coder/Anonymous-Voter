const express = require('express');
const router = express.Router();
const db = require('../config/db');
const axios = require('axios');

const authMiddleware = require('../middleware/authMiddleware');
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://127.0.0.1:5000';

/**
 * @route   GET /api/vote/project_info
 * @desc    🆕 [新增接口] 选民进入大厅时，动态拉取候选人名单和该项目的 RSA 公钥
 * @access  Private (需要 JWT Token)
 */
router.get('/project_info', authMiddleware, async (req, res) => {
    const { project_id } = req.query;

    if (!project_id) {
        return res.status(400).json({ success: false, message: "参数缺失：需要指定 project_id" });
    }

    try {
        // 1. 从 MySQL 中捞出该项目下所有状态正常的候选人
        const [candidates] = await db.query(
            'SELECT id, serial_no,name FROM candidates WHERE project_id = ? AND status = 1 ORDER BY serial_no ASC',
            [project_id]
        );

        // 2. 跨服向 Python 索要该项目专属的 RSA 公钥字符串
        let publicKeyPem = '';
        try {
            const pyRes = await axios.get(`${PYTHON_SERVICE_URL}/python/get_public_key?project_id=${project_id}`);
            if (pyRes.data.success) {
                publicKeyPem = pyRes.data.public_key;
            }
        } catch (pyErr) {
            console.error(`[Node.js 网关] 获取项目 ${project_id} 公钥失败:`, pyErr.message);
            return res.status(500).json({ success: false, message: "无法获取密码学公钥，请联系管理员启动 Python 服务。" });
        }

        // 3. 打包数据合并返回给前端
        return res.json({
            success: true,
            candidates: candidates,
            public_key: publicKeyPem
        });

    } catch (error) {
        console.error("拉取项目大厅信息失败:", error);
        return res.status(500).json({ success: false, message: "服务器内部错误" });
    }
});

/**
 * @route   POST /api/vote/request_sign
 * @desc    【阶段一：实名索取签名】核销选民资格，并携带 project_id 向 Python 索要盲签名
 * @access  Private (必须携带 JWT Token)
 */
router.post('/request_sign', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const { project_id, r_prime } = req.body;

    if (!project_id || !r_prime) {
        return res.status(400).json({ success: false, message: "参数缺失：需要 project_id 和盲化数据 r_prime" });
    }

    try {
        // 防多投拦截（实名验证）
        const [existingLogs] = await db.query(
            'SELECT id FROM signature_logs WHERE user_id = ? AND project_id = ?',
            [userId, project_id]
        );

        if (existingLogs.length > 0) {
            return res.status(403).json({ success: false, message: "拦截：您已在该项目中领取过选票签名，禁止重复领票！" });
        }

        console.log(`\n[Node.js 网关] 选民 ${userId} 通过资格验证，正在向 Python 请求项目 ${project_id} 的盲签...`);

        // 🚀 [重写位置]：向 Python 请求时，不仅传 r_prime，还必须带上 project_id
        let pythonResponse;
        try {
            pythonResponse = await axios.post(`${PYTHON_SERVICE_URL}/python/sign_blind`, {
                project_id: project_id, // 👈 核心修改：透传租户 ID
                r_prime: r_prime
            });
        } catch (pythonErr) {
            console.error("[Node.js 网关] 连接 Python 服务失败:", pythonErr.message);
            return res.status(500).json({ success: false, message: "密码学引擎服务暂不可用。" });
        }

        const s_prime = pythonResponse.data.s_prime;
        if (!s_prime) {
            throw new Error("Python 服务未能返回合法的签名 s_prime");
        }

        // 核销投票资格
        await db.query(
            'INSERT INTO signature_logs (user_id, project_id, has_signed) VALUES (?, ?, 1)',
            [userId, project_id]
        );

        console.log(`[Node.js 网关] 签发完毕！已核销选民 ${userId} 在项目 ${project_id} 的投票资格。\n`);

        return res.json({
            success: true,
            message: "签名获取成功！请在本地去盲后进行匿名投递。",
            s_prime: s_prime
        });

    } catch (error) {
        console.error("签发接口致命错误:", error);
        return res.status(500).json({ success: false, message: "服务器内部错误" });
    }
});

module.exports = router;