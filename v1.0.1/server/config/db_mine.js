const mysql = require('mysql2/promise')
const path = require('path')
require('dotenv').config({ path: path.join(__dirname, '../.env') })

const pool = mysql.createPool({
    host: process.env.DB_HOST || '127.0.0.1',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASS || process.env._DB_PASSWORD || '',
    database: process.env.DB_NAME || 'voting_system',
    waitForConnections: true,
    connectionLimit: 50,
    queueLimit: 0
})

pool.getConnection()
    .then(connection => {
        console.log(`MYSQL 数据库连接池初始化成功！[并发额度：50]`)
        connection.release()

    })
    .catch(err => {
        console.error(`MYSQL 数据库连接失败，请检查宝塔面板中数据库是否配置正确，以及.env中账号密码是否错误`)
        console.error(`详细错误信息:${err.message}`)

    })
module.exports = pool