# 数据库基础连接、Python建表、初始化
# ---------------------------------------------------------------------------------------------
# 功能说明：数据库全局配置、自动建库建表、通用增删改查工具、事务支持，项目所有数据库操作均依赖此底层模块
# 架构升级：已升级为 SaaS 多租户逻辑隔离架构，支持跨项目同名账号互不干扰
# ---------------------------------------------------------------------------------------------

import pymysql
from pymysql import Error

# ====================== 数据库全局配置 ======================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "geshuai1234!",  # 请修改为自己的数据库密码
    "port": 3306,  # MySQL默认端口
    "database": "voting_system",  # 数据库名称，后续会自动创建
    "charset": "utf8mb4",  # 使用utf8mb4字符集支持更多字符（如表情符号）
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
            autocommit=False,
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)
        return conn, cur
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
            charset=DB_CONFIG["charset"],
        )
        cur = conn.cursor()
        sql = f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET utf8mb4"
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        print(f"数据库 {DB_CONFIG['database']} 初始化成功或已存在")
    except Error as e:
        print(f"创建数据库失败：{e}")


def create_all_tables():
    """
    Python代码自动创建全部数据表
    SaaS多租户升级：通过 project_id 实现物理同表、逻辑隔离
    """
    conn, cur = get_db_connection()
    if not conn:
        return

    # 🚀 核心改造 1：多租户用户表 (取消全局UNIQUE，改为联合UNIQUE)
    users = """
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(50) NOT NULL COMMENT '账号名称（已取消全局唯一）',
        password VARCHAR(255) NOT NULL,
        salt VARCHAR(64),
        role ENUM('admin', 'voter') DEFAULT 'voter' COMMENT '角色身份',
        project_id INT COMMENT '租户/项目ID（隔离关键）',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_project_username (project_id, username) COMMENT '联合唯一：限制同一项目内账号不得重复'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统全局多租户用户表';
    """

    # 项目表（依赖 users 表）
    projects = """
    CREATE TABLE IF NOT EXISTS projects (
        id INT PRIMARY KEY AUTO_INCREMENT,
        title VARCHAR(200) NOT NULL,
        description TEXT,
        status INT DEFAULT 1,
        created_by INT,
        created_by_name VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='投票项目大盘';
    """
    
    # 候选人表 (级联隔离：项目删除时自动清理名下候选人)
    candidates = """
    CREATE TABLE IF NOT EXISTS candidates (
        id INT PRIMARY KEY AUTO_INCREMENT,
        project_id INT NOT NULL,
        serial_no VARCHAR(20) NOT NULL,
        name VARCHAR(50) NOT NULL,
        vote_count INT DEFAULT 0,
        status INT DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        UNIQUE KEY uk_proj_serial (project_id, serial_no)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户候选人隔离表';
    """  
    
    # 实名领票核销记录表
    signature_logs = """
    CREATE TABLE IF NOT EXISTS signature_logs (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        project_id INT NOT NULL,
        has_signed INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='选民领票核销记录';
    """
    
    # 1. 投票主表
    sql_vote_main = """
    CREATE TABLE IF NOT EXISTS vote_main (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增记录ID',
        project_id INT,
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
        project_id INT,
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
        project_id INT,
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
    
    # 5. AI安全边界防御拦截日志表
    sql_ai_security_log = """
    CREATE TABLE IF NOT EXISTS ai_security_log (
        log_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '拦截记录ID',
        project_id INT NOT NULL COMMENT '关联项目/租户ID',
        attack_sn VARCHAR(128) NOT NULL COMMENT '黑客尝试使用的匿名凭证Sn',
        malicious_r VARCHAR(512) NOT NULL COMMENT '被拦截的恶意/违规选票内容源码',
        intercept_reason VARCHAR(1024) NOT NULL COMMENT 'AI安全官给出的深度语义审计拦截原因',
        intercept_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '拦截防御发生时间'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI安全边界防御拦截日志表';
    """

    # 6. 女巫攻击行为特征日志表 (无监督异常检测训练数据源)
    sql_sybil_behavior_log = """
    CREATE TABLE IF NOT EXISTS sybil_behavior_log (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
        sn VARCHAR(128) NOT NULL COMMENT '匿名凭证(非身份)',
        project_id INT NOT NULL COMMENT '项目ID',
        dwell_time DOUBLE DEFAULT 0 COMMENT '页面停留时间(秒)',
        total_distance DOUBLE DEFAULT 0 COMMENT '鼠标累计移动距离(像素)',
        avg_speed DOUBLE DEFAULT 0 COMMENT '鼠标平均移动速度(像素/毫秒)',
        jitter_rate DOUBLE DEFAULT 0 COMMENT '方向突变率(突变次数/总距离)',
        move_count INT DEFAULT 0 COMMENT '鼠标移动事件总数',
        key_count INT DEFAULT 0 COMMENT '键盘事件总数',
        click_count INT DEFAULT 0 COMMENT '点击事件总数',
        scroll_count INT DEFAULT 0 COMMENT '滚动事件总数',
        max_pause DOUBLE DEFAULT 0 COMMENT '相邻鼠标事件间最大停顿(毫秒)',
        accel_variance DOUBLE DEFAULT 0 COMMENT '鼠标加速度方差',
        is_sybil TINYINT(1) DEFAULT 0 COMMENT '是否判定为女巫攻击(1=是 0=否)',
        anomaly_score DOUBLE DEFAULT 0 COMMENT '异常分数(越负越异常)',
        detect_reason VARCHAR(1024) DEFAULT '' COMMENT '判定原因',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
        KEY idx_project (project_id),
        KEY idx_sybil (is_sybil),
        KEY idx_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='女巫攻击行为特征日志表';
    """

    try:
        cur.execute(users)
        cur.execute(projects)
        cur.execute(candidates)
        cur.execute(signature_logs)
        cur.execute(sql_vote_main)
        cur.execute(sql_hash_chain)
        cur.execute(sql_system_log)
        cur.execute(sql_vote_stat)
        cur.execute(sql_ai_security_log)
        cur.execute(sql_sybil_behavior_log)
        conn.commit()
        print("SaaS多租户升级完毕：全部数据表创建成功或已存在")
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
        cur.execute(sql, params)
        conn.commit()
        return True, cur.lastrowid
    except Error as e:
        conn.rollback()
        print("插入失败：", e)
        return False, 0
    finally:
        cur.close()
        conn.close()


def db_query_all(sql, params=None):
    """通用查询所有"""
    conn, cur = get_db_connection()
    if not conn:
        return []
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
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
        cur.execute(sql, params)
        conn.commit()
        return True
    except Error as e:
        conn.rollback()
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