#本模块实现了vote_main数据库表的，入库，防多投，设置有效值等功能
#属于底层实现，无需管他

# 模块2：投票数据持久化存储模块

from db_base import db_insert, db_query_all, db_update

# ======================================================================
# 投票主表业务模块：vote_main 表的所有操作
# 功能：插入投票、防重复投票、查询投票、修改投票状态
# ======================================================================

def insert_vote(Sn, r, S, is_valid=1):
    """
    插入一条投票记录
    :param Sn: 用户唯一随机数（防多投）
    :param r: 投票内容
    :param S: RSA签名
    :param is_valid: 1=有效，0=无效
    :return: (True/False, 消息)
    """
    sql = """
    INSERT INTO vote_main (Sn, r, S, is_valid)
    VALUES (%s, %s, %s, %s)                          
    """                                          # 注意：%s 是占位符，参数通过 db_insert 传入，防止SQL注入攻击
    params = (Sn, r, S, is_valid)

    success, row_id = db_insert(sql, params)

    if success:
        return True, f"投票入库成功，ID：{row_id}"
    else:
        # 失败大概率是 Sn 重复（防多投）
        return False, "投票失败：Sn 已存在（重复投票）"


def check_sn_exists(Sn):
    """
    检查 Sn 是否已经投过票（防多投核心）
    """
    sql = "SELECT id FROM vote_main WHERE Sn = %s"     # 通过 Sn 查询是否已有记录
    res = db_query_all(sql, (Sn,))                     # 注意：参数必须是元组，即使只有一个元素也要加逗号
    return len(res) > 0                                # 如果查询结果不为空，说明 Sn 已存在，返回 True；否则返回 False


def get_all_votes():
    """获取所有投票记录"""
    sql = "SELECT * FROM vote_main ORDER BY id DESC"
    return db_query_all(sql)


def get_valid_votes():
    """获取所有有效投票"""
    sql = "SELECT * FROM vote_main WHERE is_valid = 1"
    return db_query_all(sql)


def set_vote_invalid(vote_id):
    """将某条投票设为无效"""
    sql = "UPDATE vote_main SET is_valid = 0 WHERE id = %s"
    return db_update(sql, (vote_id,))


# ------------------- 测试 -------------------
if __name__ == "__main__":
    # 测试插入（Sn唯一）
    test_Sn = "test_user_001"
    test_r = "Candidate_A"
    test_S = "signature_demo"

    print("=== 测试投票插入 ===")
    ok, msg = insert_vote(test_Sn, test_r, test_S)
    print(ok, msg)

    # 重复插入会失败
    ok2, msg2 = insert_vote(test_Sn, test_r, test_S)
    print(ok2, msg2)

    # 查询所有
    print("\n=== 所有投票 ===")
    votes = get_all_votes()
    for v in votes:
        print(v)
