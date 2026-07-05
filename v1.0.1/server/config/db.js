/**
 * ============================================================================
 * SaaS 投票系统 - 生产级数据库连接池配置
 * 采用 mysql2/promise 实现高性能异步并发处理
 * ============================================================================
 */

// 引入 mysql2 的 Promise 版本，支持 async/await 语法
const mysql = require('mysql2/promise');

// 确保环境变量被正确加载

const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });

// 1. 创建高并发数据库连接池 (Connection Pool)
// 为什么不用 createConnection？因为 createPool 可以维持多个长连接，
// 当成百上千的选民同时投票时，可以极大地减少频繁创建和销毁连接带来的巨大性能损耗。
const pool = mysql.createPool({
    host: process.env.DB_HOST || '127.0.0.1',
    user: process.env.DB_USER || 'root',
    // 兼容可能存在的不同环境变量命名 (DB_PASS 或 DB_PASSWORD)
    password: process.env.DB_PASS || process.env.DB_PASSWORD || 'geshuai1234!',
    database: process.env.DB_NAME || 'voting_system',

    // 【高并发核心配置】
    waitForConnections: true, // 当连接池满时，新请求排队等待，而不是直接报错拒绝
    connectionLimit: 50,      // 最大并发连接数（SaaS 模式下建议调高，默认通常是 10）
    queueLimit: 0             // 排队等待的请求数量上限（0 表示不限制，防止高峰期丢票）
});

// 2. 启动时自检 (Health Check)
// 在后端服务器启动的第一时间，主动去数据库“敲一次门”，确保配置无误
pool.getConnection()
    .then(connection => {
        console.log(`📦 MySQL 数据库连接池初始化成功！[并发额度: 50]`);
        // 测试完毕后务必释放连接，归还给连接池
        connection.release();
    })
    .catch(err => {
        console.error(`❌ MySQL 数据库连接致命失败！`);
        console.error(`请检查宝塔面板中的数据库是否运行，以及 .env 里的账号密码是否正确。`);
        console.error(`详细错误信息: ${err.message}`);
    });

// 3. 导出连接池供各个 routes 路由文件使用
module.exports = pool;