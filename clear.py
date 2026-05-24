#用于清空vote_main 和 hash_chain 表
#直接运行即可

from db_base import get_db_connection

def clear_all_tables():
    """
    清空数据库所有4张表的数据
    只删记录，不删表
    """
    conn, cur = get_db_connection()
    if not conn:
        return

    try:
        # 关闭外键约束（防止清空失败）
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")

        # 清空所有表
        cur.execute("TRUNCATE TABLE vote_main")
        cur.execute("TRUNCATE TABLE hash_chain")
        cur.execute("TRUNCATE TABLE system_log")
        cur.execute("TRUNCATE TABLE vote_stat")

        # 重新开启外键
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        conn.commit()
        print("✅ 数据库已清空！所有表数据归零！")

    except Exception as e:
        print("清空失败：", e)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    clear_all_tables()
