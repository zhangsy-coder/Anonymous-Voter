#向 模拟主办方拥有的有权投票人信息表格 插入十个用户用于模拟 Sn生成等操作
#直接运行即可


# insert_test_users.py
# 功能：自动向 vote_user_db.voter 插入 10 个测试用户
# 账号：user1 ~ user10
# 密码：123456
# SN 默认为空
from voter import get_db_connection

def insert_10_test_users():
    conn, cur = get_db_connection()
    if not conn:
        return

    # 10 个测试用户数据（身份证不同，账号简单，SN 为空）
    users = [
        ("01", "用户一", "user1", "123456"),
        ("02", "用户二", "user2", "123456"),
        ("03", "用户三", "user3", "123456"),
        ("04", "用户四", "user4", "123456"),
        ("05", "用户五", "user5", "123456"),
        ("06", "用户六", "user6", "123456"),
        ("07", "用户七", "user7", "123456"),
        ("08", "用户八", "user8", "123456"),
        ("09", "用户九", "user9", "123456"),
        ("10", "用户十", "user10", "123456"),
    ]

    sql = """
    INSERT INTO voter (id_card, name, username, password)
    VALUES (%s, %s, %s, %s)
    """

    try:
        cur.executemany(sql, users)
        conn.commit()
        print(f"✅ 成功插入 {len(users)} 个测试用户！")
        print("📌 账号格式：user1 ~ user10")
        print("📌 统一密码：123456")
        print("📌 SN 均为空，等待后续生成")
    except Exception as e:
        print(f"❌ 插入失败：{e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    insert_10_test_users()
