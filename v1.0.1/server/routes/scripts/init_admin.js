/**
 * 生产环境管理员初始化工具 (CLI 脚本)
 * 用法: 在服务器终端运行 `node scripts/init_admin.js [你想设置的密码]`
 */

const bcrypt = require('bcryptjs');
const db = require('../config/db'); // 复用你已经写好的高并发连接池

async function run() {
    console.log('\n=======================================');
    console.log('🔧 启动超级管理员账号初始化/重置程序');
    console.log('=======================================\n');

    // 1. 从命令行参数中读取密码（如果没有输入，默认使用 123456）
    // process.argv 数组的第3个元素即为我们在终端敲入的附加参数
    const rawPassword = process.argv[2] || '123456';
    const adminUsername = 'admin';

    try {
        console.log(`⏳ 正在为账号 [${adminUsername}] 生成加密摘要...`);
        const hash = await bcrypt.hash(rawPassword, 10);

        console.log(`⏳ 正在连接生产环境数据库...`);

        // 2. 尝试执行更新（如果数据库里已经有 admin 了，就覆盖它的密码）
        const [updateResult] = await db.query(
            'UPDATE `users` SET `password` = ?, `role` = "admin" WHERE `username` = ?',
            [hash, adminUsername]
        );

        // 3. 如果受影响的行数为 0，说明表里压根没有 admin，我们需要执行插入
        if (updateResult.affectedRows === 0) {
            console.log(`⚠️ 未找到现有的 [${adminUsername}] 账号，正在全新创建...`);
            await db.query(
                'INSERT INTO `users` (`username`, `password`, `role`, `project_id`) VALUES (?, ?, "admin", NULL)',
                [adminUsername, hash]
            );
            console.log(`✅ 超级管理员创建成功！账号: ${adminUsername}，密码: ${rawPassword}`);
        } else {
            console.log(`✅ 现有超级管理员密码重置成功！新密码为: ${rawPassword}`);
        }

    } catch (error) {
        console.error('\n❌ 数据库操作失败，请检查配置或网络！');
        console.error('详细报错:', error.message);
    } finally {
        // 4. 无论成功失败，操作完成后必须强制退出当前进程，释放数据库连接池
        console.log('\n🚪 脚本执行完毕，自动退出进程。\n');
        process.exit(0);
    }
}

// 启动执行
run();