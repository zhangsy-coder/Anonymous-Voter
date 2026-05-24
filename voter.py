# db_init.py
# 功能：自动创建【投票人员信息数据库】+【用户表】
# 独立库，不影响原有投票系统
import pymysql
from pymysql import Error

# ====================== 数据库配置（全新独立库） ======================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "##",     #请修改为自己的数据库密码
    "port": 3306,
    "database": "vote_user_db",  # 全新数据库！
    "charset": "utf8mb4"
}


def create_database_and_table():
    """创建全新数据库 + 用户信息表"""
    conn = None
    cursor = None

    try:
        # 1. 连接 MySQL（不选库）
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            charset=DB_CONFIG["charset"]
        )
        cursor = conn.cursor()

        # 2. 创建新数据库
        db_name = DB_CONFIG["database"]
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} DEFAULT CHARACTER SET utf8mb4")
        print(f"✅ 数据库【{db_name}】创建成功/已存在")

        # 3. 切换到新库
        cursor.execute(f"USE {db_name}")

        # 4. 创建投票人员表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS voter (
            id INT PRIMARY KEY AUTO_INCREMENT,
            id_card VARCHAR(18) NOT NULL UNIQUE,   -- 身份证（唯一）
            name VARCHAR(20) NOT NULL,            -- 姓名
            sn VARCHAR(10) UNIQUE NULL,           -- 投票SN（一人一个）
            username VARCHAR(20) NOT NULL UNIQUE, -- 登录账号
            password VARCHAR(64) NOT NULL,        -- 密码（实际项目中应加密存储）
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_table_sql)
        print("✅ 表【voter】创建成功/已存在")

        conn.commit()

    except Error as e:
        print(f"❌ 初始化失败：{str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_db_connection():
    """提供给其他模块使用的数据库连接"""
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG["charset"],
            autocommit=False
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)
        return conn, cur
    except Error as e:
        print(f"❌ 数据库连接失败：{e}")
        return None, None


# ===================== 运行 =====================
if __name__ == "__main__":
    print("=" * 50)
    print("🔧 初始化投票人员信息系统")
    print("=" * 50)
    create_database_and_table()
    print("\n🎉 初始化完成！")
    print("📦 新数据库：vote_user_db")
    print("📋 新表：voter")