# sn_generator.py
# 功能：用户登录后 → 检查有无SN → 无则生成并保存 → 保证全局唯一
# 只需传入用户唯一ID（能代表用户唯一身份的）规定为身份证号
# 用于生成大小写字母加数字的，随机十位字符串Sn
import sys
import random
import string

from voter import get_db_connection

# 字符集：大小写字母 + 数字
CHAR_SET = string.ascii_uppercase + string.ascii_lowercase + string.digits


def generate_unique_sn():
    """
    生成 10 位 大小写+数字 唯一SN
    自动检查数据库，确保不重复
    """
    conn, cur = get_db_connection()
    if not conn:
        return None

    while True:
        # 生成10位随机SN
        sn = ''.join(random.choice(CHAR_SET) for _ in range(10))

        # 查询是否已存在
        cur.execute("SELECT id FROM voter WHERE sn = %s", (sn,))
        if not cur.fetchone():
            conn.close()
            return sn

def get_or_create_user_sn(user_id):
    """
    核心函数：
    1. 查询用户是否有SN
    2. 有 → 返回
    3. 没有 → 生成唯一SN → 保存 → 返回
    :param user_id: 登录用户的 id
    """
    conn, cur = get_db_connection()

    # 1. 查询当前SN
    cur.execute("SELECT sn FROM voter WHERE id = %s", (user_id,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return None

    current_sn = user["sn"]

    # 2. 如果已有SN，直接返回
    if current_sn and current_sn.strip() != "":
        conn.close()
        return current_sn

    # 3. 没有SN → 生成
    new_sn = generate_unique_sn()

    # 4. 写入数据库
    cur.execute("UPDATE voter SET sn = %s WHERE id = %s", (new_sn, user_id))
    conn.commit()
    conn.close()

    return new_sn

# 测试：生成10个SN，确保唯一且正确保存
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 测试 SN 生成/获取模块（登录后自动生成）")
    print("=" * 60)

    # 测试用户 ID：1～10 你随便改
    test_user_id = 5

    # 执行
    sn = get_or_create_user_sn(test_user_id)

    print(f"✅ 用户 ID {test_user_id} 的 SN = {sn}")
    print("✅ 功能正常！已自动生成并保存到数据库！")
