# migrate_db.py
import mysql.connector
import sys
import os

# 从你的配置中获取数据库连接信息（直接写在这里，或者引用 db_base.py）
# 这里直接从 db_base.py 读可能更干净，但为了简单，我们手动指定（与你的 db.js 一致）
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',      # 你的 MySQL 密码，如果是空就留空
    'database': 'voting_system',
    'port': 3306
}

def main():
    # 1. 先连接数据库，查询管理员 id
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 查询第一个管理员
        cursor.execute("SELECT id, username FROM users WHERE role = 'admin' LIMIT 1;")
        result = cursor.fetchone()
        if not result:
            print("❌ 未找到管理员账号，请先创建至少一个 admin 用户。")
            return
        admin_id, admin_name = result
        print(f"✅ 找到管理员：id={admin_id}, username={admin_name}")

        # 2. 执行修改表的 SQL
        sqls = [
            "ALTER TABLE projects ADD COLUMN created_by INT;",
            "ALTER TABLE projects ADD COLUMN created_by_name VARCHAR(50);",
            f"UPDATE projects SET created_by = {admin_id}, created_by_name = '{admin_name}' WHERE created_by IS NULL;",
            "ALTER TABLE projects ADD FOREIGN KEY (created_by) REFERENCES users(id);"
        ]

        for sql in sqls:
            try:
                cursor.execute(sql)
                print(f"✅ 执行成功: {sql[:60]}...")
            except mysql.connector.Error as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e):
                    print(f"⚠️ 跳过（字段已存在）: {sql[:40]}...")
                else:
                    print(f"❌ 执行失败: {e}")
                    # 继续执行后续语句
        conn.commit()
        print("\n🎉 数据库迁移完成！")
        
    except mysql.connector.Error as err:
        print(f"❌ 数据库连接失败: {err}")
        print("请检查你的 MySQL 服务是否运行，以及 DB_CONFIG 配置是否正确。")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()