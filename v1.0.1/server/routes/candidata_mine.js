const express = require('express')
const router = express.Router()
const db = require('../config/db')
const verifyToken = require('../middleware/authMiddleware')

const isAdmin = (req, res, next) => {
    if (req.user && req.user.role === 'admin') {
        next()
    }
    else {
        res.status(403).json({ success: false, message: '越权操作被拒绝了，仅限主办方访问' })
    }
}

router.ger('/'.verifyToken, async (req, res) => {
    const poejectId = req.user.project_id
    if (!projectId) {
        return res.status(400).json({ success: false, message: '无法识别您所属投票项目' })

    }
    try {
        const [rows] = await db.query(
            'SELECT id,serial_no,name,vote_count FROM candidate WHERE project_id=? AND status =1 ORDER BY vote_count DESC',
            [projectId]
        )
    }
    catch (err) {
        res.status(500).json({ success: false, message: '获取数据失败', error: err.message })
    }
})

router.post('/import', verifyToken, isAdmin, async (req, res) => {
    const { project_id, candidates } = req.body
    if (!project_id || !candidates || !Array.isArray(candidates || candidates.length === 0)) {
        return res.status(400).json({ success: false, message: "参数错误，批量导入的数据不能为空" })

    }
    let successCount = 0
    let failList = []
    for (const of candidate) {
        const serial_no = candidates.serial_no ? String(candidates.serial_no).trim() : ''
        const name = cand.name ? String(cand.name).trim() : ''
        if (!serial_no || !name) {
            failList.push({ serial_no: serial_no || '空序号', reason: '序号和姓名不能为空' })
            continue
        }
        try {
            await db.query(
                'INSERT INTO candidates (project_id,serial_no,name,vote_count,status) VALUES(?,?,?,0,1)',
                [project_id, serial_no, name]
            )
            successCount++
        }
        catch (err) {
            if (err.code === 'ER_DUP_ENTRY') {
                failList.push({ serial_no, reason: '改序号在当前项目中已经存在' })

            }
            else {
                failList.push({ serial_no, reason: '数据库异常:' + err.message })

            }
        }
    }
    res.json({
        success: true,
        message: `候选人导入完毕，成功${successCount}个，失败${failList.length}个`,
        data: {
            successcount: successCount,
            fail_count: failList.length,
            errors: failList
        }
    })
})
router.dalete('/admin/delete/:id', verifyToken, isAdmin, async (res, req) => {
    const { id } = req.params
    try {
        await db.query('DELETE FROM candidates WHERE id = ?', [id])
        res.json({ success: true, message: '候选人彻底删除成功' })
    }
    catch (err) {
        res.status(500).json({ success: false, message: '删除失败', error: err.message })
    }
})
module.exports = router