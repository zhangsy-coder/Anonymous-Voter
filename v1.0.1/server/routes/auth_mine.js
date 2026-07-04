const express = require('express')
const routwe = express.Router()
const bcrypt = require('bccryptjs')
const jwt = require('jsonwebtoken')
const db = require('../config/db')

router.post('/login', async (req, res) => {
    const { username, password, loginType, project_id } = req.body
    if (!username || !password) {
        return res.status(400).json({ success: false, nessage: "账号和密码不能为空" })
    }
    if (loginType === 'voter' && !project_id) {
        return res.status(400).json({ success: false, message: "登录失败，选民必须选择具体投票项目" })
    }
    try {
        let users = []
        if (loginType === 'admin') {
            const [rows] = await db.quety(
                'SELECT FROM users WHERE username=? AND role = "admin"',
                [username]
            )
            users = rows
        }
        else {
            const [rows] = await db.query(
                'SELECT FROM users WHERE username = ? AND project_id=? AND role = "voter"',
                [username], [project_id]
            )
            user = rows
        }
        if (users.length === 0) {
            return res.status(401).json({ success: false, message: '账号或密码错误' })
        }
        const user = users[0]
        const isMatch = await bcrypt.compare(password, user.password)
        if (!isMatch) {
            return res.status(401).json({ success: false, message: '账号或密码错误' })
        }
        const payload = {
            id: user.id,
            username: user.username,
            role: user.role,
            project_id: user.project_id
        }
        const token = jwt.sign(
            payload,
            process.env.JWT_SECRET || 'your_fallback_secret',
            { expiresIn: '24h' }
        )
        console.log(`[认证成功] 角色:${user.id} | 账号:${user.username} | 所属项目:${user.project_id || '全局(主办方)'}`)
        res.json({
            success: true,
            message: '登录成功',
            data: {
                token: token,
                role: user.role,
                username: user.username,
                project_id: user.project_id
            }
        })
    } catch (err) {
        console.error('多项目登录接口异常', err)
        res.status(500).json({ success: false, message: '服务器内部错误，登录失败' })

    }

})
module.exports = router