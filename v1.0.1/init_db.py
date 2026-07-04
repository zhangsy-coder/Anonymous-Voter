# init_db.py - 从零初始化数据库
# 执行前确保：1) MySQL已启动  2) 已激活虚拟环境

import pymysql

# ============================================================
# 数据库连接配置
# PHPStudy 默认：root / root，端口 3306
# 如果你的 MySQL 密码不是 root，请修改下面的 password
# ============================================================
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '123456',        # ← PHPStudy 默认密码是 root，如果改过请修改
    'port': 3306,
    'charset': 'utf8mb4'
}

# ============================================================
# 创建数据库 + 所有表 + 默认管理员
# ============================================================
def main():
    # 1. 连接 MySQL（不指定数据库）
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print("📦 正在创建数据库 voting_system...")
    cursor.execute("CREATE DATABASE IF NOT EXISTS voting_system DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
    conn.select_db('voting_system')

    # 2. 创建所有表
    tables = [
        # users 表
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            salt VARCHAR(64),
            role ENUM('admin', 'voter') DEFAULT 'voter',
            project_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # projects 表（含 created_by 支持多管理员隔离）
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INT PRIMARY KEY AUTO_INCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            status INT DEFAULT 1,
            created_by INT,
            created_by_name VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        );
        """,
        # candidates 表
        """
        CREATE TABLE IF NOT EXISTS candidates (
            id INT PRIMARY KEY AUTO_INCREMENT,
            project_id INT NOT NULL,
            serial_no VARCHAR(20) NOT NULL,
            name VARCHAR(50) NOT NULL,
            vote_count INT DEFAULT 0,
            status INT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE KEY (project_id, serial_no)
        );
        """,
        # signature_logs 表
        """
        CREATE TABLE IF NOT EXISTS signature_logs (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            project_id INT NOT NULL,
            has_signed INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        # hash_chain 表（Python 微服务使用）
        """
        CREATE TABLE IF NOT EXISTS hash_chain (
            block_id INT PRIMARY KEY AUTO_INCREMENT,
            project_id INT,
            Sn VARCHAR(100) NOT NULL,
            r VARCHAR(100) NOT NULL,
            S TEXT NOT NULL,
            prev_hash VARCHAR(64),
            curr_hash VARCHAR(64),
            timestamp INT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """
    ]

    print("📋 正在创建数据表...")
    for sql in tables:
        try:
            cursor.execute(sql)
            print(f"  ✅ 表创建成功")
        except Exception as e:
            print(f"  ❌ 表创建失败: {e}")

    # 3. 插入默认管理员
    # 密码是 123456 的 bcrypt 哈希值 (salt rounds=10)
    print("👤 正在创建默认管理员账号...")
    admin_sql = """
    INSERT IGNORE INTO users (username, password, role) 
    VALUES ('admin', '$2a$10$sFKehFTHRqDz5rDxL/4nE.iQyG.w6GGj7JXGb/H1nXX.5Rr4FbY4C', 'admin');
    """
    cursor.execute(admin_sql)
    conn.commit()

    # 4. 验证
    cursor.execute("SELECT id, username, role FROM users WHERE username='admin';")
    admin = cursor.fetchone()
    if admin:
        print(f"  ✅ 管理员创建成功: id={admin[0]}, username={admin[1]}, role={admin[2]}")
    else:
        print("  ⚠️ 管理员创建可能失败，请手动检查")

    cursor.close()
    conn.close()

    print("\n" + "=" * 50)
    print("🎉 数据库初始化完成！")
    print("=" * 50)
    print("📌 管理员账号: admin")
    print("📌 管理员密码: 123456")
    print("📌 数据库名称: voting_system")
    print("=" * 50)


if __name__ == "__main__":
    main()