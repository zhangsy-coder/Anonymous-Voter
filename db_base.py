# 数据库基础连接、Python建表、初始化
#---------------------------------------------------------------------------------------------
#功能说明：数据库全局配置、自动建库建表、通用增删改查工具、事务支持，项目所有数据库操作均依赖此底层模块
#---------------------------------------------------------------------------------------------

import pymysql
from pymysql import Error

# ====================== 数据库全局配置 ======================
DB_CONFIG = {
    "host": "localhost",   
    "user": "root",              
    "password": "##",  # 请修改为自己的数据库密码
    "port": 3306,                # MySQL默认端口
    "database": "vote_system_db",# 数据库名称，后续会自动创建
    "charset": "utf8mb4"         # 使用utf8mb4字符集支持更多字符（如表情符号）
}


def get_db_connection():
    """
    获取数据库连接
    :return: connection, cursor对象，如果连接失败则返回None, None
    """
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
        return conn, cur  # 返回连接和游标对象
    except Error as e: 
        print(f"数据库连接失败：{e}")
        return None, None

def create_database():
    """
    不存在则自动创建数据库（无需库名连接）
    """
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            charset=DB_CONFIG["charset"]
        )
        cur = conn.cursor()
        sql = f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET utf8mb4" # 创建数据库并设置默认字符集为utf8mb4
        cur.execute(sql) # 执行创建数据库的SQL语句
        conn.commit()    # 提交事务
        cur.close()      # 关闭游标
        conn.close()     # 关闭连接
        print(f"数据库 {DB_CONFIG['database']} 初始化成功或已存在")
    except Error as e:
        print(f"创建数据库失败：{e}")


def create_all_tables():
    """
    Python代码自动创建全部4张表
    vote_main / hash_chain / system_log / vote_stat
    """
    conn, cur = get_db_connection()
    if not conn:
        return

    # 1. 投票主表
    sql_vote_main = """
    CREATE TABLE IF NOT EXISTS vote_main (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增记录ID',
        Sn VARCHAR(128) NOT NULL COMMENT '用户唯一随机凭证（防多投）',
        r VARCHAR(256) NOT NULL COMMENT '投票内容',
        S VARCHAR(512) NOT NULL COMMENT 'RSA签名值',
        vote_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '投票时间',
        is_valid TINYINT(1) DEFAULT 1 COMMENT '1有效 0无效',
        UNIQUE KEY uk_sn (Sn)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='投票核心主数据表';
    """

    # 2. 哈希链独立表
    sql_hash_chain = """
    CREATE TABLE IF NOT EXISTS hash_chain (
        block_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '区块高度',
        Sn VARCHAR(128) NOT NULL COMMENT '用户唯一凭证',
        r VARCHAR(256) NOT NULL COMMENT '投票内容',
        S VARCHAR(512) NOT NULL COMMENT '签名值',
        prev_hash VARCHAR(256) NOT NULL COMMENT '上一区块哈希',
        curr_hash VARCHAR(256) NOT NULL COMMENT '当前区块哈希',
        block_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上链时间',
        UNIQUE KEY uk_sn (Sn)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='哈希链区块表';
    """

    # 3. 系统日志表
    sql_system_log = """
    CREATE TABLE IF NOT EXISTS system_log (
        log_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
        opt_type VARCHAR(64) NOT NULL COMMENT '操作类型',
        opt_desc VARCHAR(512) NOT NULL COMMENT '操作详情',
        rel_sn VARCHAR(128) NULL COMMENT '关联用户Sn',
        log_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '日志时间',
        status TINYINT(1) DEFAULT 1 COMMENT '1正常 0异常'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统操作日志表';
    """

    # 4. 投票统计表
    sql_vote_stat = """
    CREATE TABLE IF NOT EXISTS vote_stat (
        stat_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '统计ID',
        vote_option VARCHAR(64) NOT NULL COMMENT '投票选项/候选人',
        total_num INT DEFAULT 0 COMMENT '总票数',
        valid_num INT DEFAULT 0 COMMENT '有效票数',
        invalid_num INT DEFAULT 0 COMMENT '无效票数',
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='投票汇总统计表';
    """

    try:
        cur.execute(sql_vote_main)
        cur.execute(sql_hash_chain)
        cur.execute(sql_system_log)
        cur.execute(sql_vote_stat)
        conn.commit()
        print("全部数据表创建成功或已存在")
    except Error as e:
        conn.rollback()
        print(f"建表失败：{e}")
    finally:
        cur.close()
        conn.close()

# ====================== 通用数据库工具函数 ======================
def db_insert(sql, params):
    """通用插入"""
    conn, cur = get_db_connection()
    if not conn:
        return False, 0
    try:
        cur.execute(sql, params)           # 执行插入SQL语句
        conn.commit()                      # 提交事务
        return True, cur.lastrowid
    except Error as e:
        conn.rollback()                    # 回滚事务
        print("插入失败：", e)
        return False, 0
    finally:
        cur.close()
        conn.close()


def db_query_all(sql, params=None):
    """通用查询所有"""
    conn, cur = get_db_connection()        # 获取数据库连接和游标
    if not conn:
        return []
    try:
        cur.execute(sql, params or ())     # 执行查询SQL语句，params默认为空元组
        return cur.fetchall()              # 获取所有查询结果并返回
    except Error as e:
        print("查询失败：", e)
        return []   
    finally:
        cur.close()
        conn.close()


def db_update(sql, params):
    """通用更新"""
    conn, cur = get_db_connection()
    if not conn:
        return False
    try:
        cur.execute(sql, params)         # 执行更新SQL语句
        conn.commit()                    # 提交事务
        return True
    except Error as e:
        conn.rollback()                  # 回滚事务
        print("更新失败：", e)
        return False
    finally:
        cur.close()
        conn.close()


def init_db():
    """项目初始化入口"""
    create_database()
    create_all_tables()


if __name__ == "__main__":
    # 自测：运行自动建库建表
    init_db()


