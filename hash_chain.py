import hashlib
from db_base import db_insert, db_query_all, get_db_connection, db_update

# ======================================================================
# 哈希链模块（真正带链式串联 + 防篡改）
# ======================================================================

def check_sn_exists(Sn):
    """
    检查 Sn 是否已经投过票（防多投核心）
    """
    sql = "SELECT block_id FROM hash_chain WHERE Sn = %s"     # 通过 Sn 查询是否已有记录
    res = db_query_all(sql, (Sn,))                     # 注意：参数必须是元组，即使只有一个元素也要加逗号
    return len(res) > 0                                # 如果查询结果不为空，说明 Sn 已存在，返回 True；否则返回 False


# --------------------- 【核心1】计算区块哈希（串链的关键！）---------------------
def compute_block_hash(prev_hash, Sn, r, S):
    """
    计算当前区块的哈希
    哈希 = 上一块哈希 + 当前数据
    改任何一个字符，哈希全变 → 链就断
    """
    data = f"{prev_hash}{Sn}{r}{S}".encode("utf-8")    # 把字符串转换成字节，才能计算哈希
    return hashlib.sha256(data).hexdigest()            # 计算SHA-256哈希，返回16进制字符串


# --------------------- 【核心2】创建创世区块（链的起点）---------------------
def create_genesis_block():
    prev_hash = "0" * 64  # 第一块没有上一块，用全0
    curr_hash = compute_block_hash(prev_hash, "GENESIS", "GENESIS_BLOCK", "GENESIS_SIGN")  # 创世块数据固定，哈希也固定
    
    sql = """
    INSERT INTO hash_chain (Sn, r, S, prev_hash, curr_hash)
    VALUES (%s, %s, %s, %s, %s)
    """
    params = ("GENESIS", "GENESIS_BLOCK", "GENESIS_SIGN", prev_hash, curr_hash)
    db_insert(sql, params)
    print("创世区块已创建（真正哈希链起点）")


# --------------------- 【核心3】创建新区块 + 自动串链！---------------------
def add_vote_to_chain(Sn, r, S):
    """
    投票上链（带防重复）
    """
    # ===================== 【关键】防重复入库 =====================
    if check_sn_exists(Sn):
        print(f"哈希链拒绝重复上链：Sn {Sn} 已存在！")
        return False, "重复上链"

    # 1. 获取最新区块
    last_block = get_latest_block()
    if not last_block:
        create_genesis_block()
        last_block = get_latest_block()  # 再次获取创世块

    # 2. 拼接链式关系
    new_prev_hash = last_block["curr_hash"]
    new_curr_hash = compute_block_hash(new_prev_hash, Sn, r, S)

    # 3. 插入数据库
    sql = """
    INSERT INTO hash_chain (Sn, r, S, prev_hash, curr_hash)
    VALUES (%s, %s, %s, %s, %s)
    """
    return db_insert(sql, (Sn, r, S, new_prev_hash, new_curr_hash))


# --------------------- 【核心4】校验整条链（防篡改关键）---------------------
"""
def verify_blockchain():

    chain = get_all_blocks()

    for i in range(1, len(chain)):
        current = chain[i]
        previous = chain[i-1]

        # 检查：当前块的 prev_hash 是否等于上一块的 curr_hash
        if current["prev_hash"] != previous["curr_hash"]:
            print(f"链断裂！第{i+1}块被篡改！")
            return False

        # 重新计算哈希，看是否匹配
        real_hash = compute_block_hash(current["prev_hash"], current["Sn"], current["r"], current["S"])
        if current["curr_hash"] != real_hash:
            print(f" 第{i+1}块数据被篡改！")
            return False

    print("哈希链完整，未被篡改！")
    return True
"""

def verify_blockchain():
    """
    【完整版】校验哈希链是否被篡改
    遍历整条链，输出所有被篡改的区块，不中途退出
    """
    chain = get_all_blocks()
    tampered_blocks = []  # 存放所有被篡改的区块号

    print("\n" + "="*50)
    print("开始完整校验整条哈希链...")
    print("="*50)

    for i in range(1, len(chain)):
        current = chain[i]
        previous = chain[i-1]
        block_num = i + 1  # 人类可读区块号

        # 标记是否合法
        valid = True

        # 1. 检查链是否断裂
        if current["prev_hash"] != previous["curr_hash"]:
            print(f"区块 {block_num}：链断裂！前哈希不匹配")
            tampered_blocks.append(block_num)
            valid = False

        # 2. 检查区块自身哈希是否被篡改
        real_hash = compute_block_hash(
            current["prev_hash"],
            current["Sn"],
            current["r"],
            current["S"]
        )
        if current["curr_hash"] != real_hash:
            print(f" 区块 {block_num}：数据被篡改！哈希不匹配")
            if block_num not in tampered_blocks:
                tampered_blocks.append(block_num)
            valid = False

    # 最终结果
    print("="*50)
    if len(tampered_blocks) == 0:
        print(" 整条哈希链完整，未被篡改！")
        return True
    else:
        print(f"  共发现 {len(tampered_blocks)} 个被篡改的区块：{tampered_blocks}")
        print("❌ 哈希链已被篡改！")
        return False

# --------------------- 下面是你原来的数据库工具函数 ---------------------
def get_latest_block():
    sql = "SELECT * FROM hash_chain ORDER BY block_id DESC LIMIT 1"
    res = db_query_all(sql)           # 查询最新区块，按 block_id 降序排序，取第一条
    return res[0] if res else None    # 返回最新区块，如果没有返回 None

def get_all_blocks():
    sql = "SELECT * FROM hash_chain ORDER BY block_id ASC"
    return db_query_all(sql)          # 查询所有区块，按 block_id 升序排序，返回完整链


# 加到 hash_chain.py 最下面
def tamper_block_2_for_test():
    """【测试专用】篡改第二个区块的投票内容"""
    sql = "UPDATE hash_chain SET r = %s WHERE block_id = 2"
    db_update(sql, ("我被恶意篡改了！",))
    print("✅ 已成功篡改第二个区块！")

def tamper_two_blocks_test():
    """测试：同时篡改 区块2 和 区块4"""
    sql1 = "UPDATE hash_chain SET r = %s WHERE block_id = 2"
    sql2 = "UPDATE hash_chain SET r = %s WHERE block_id = 4"
    from db_base import db_update
    db_update(sql1, ("【恶意篡改】区块2",))
    db_update(sql2, ("【恶意篡改】区块4",))
    print("✅ 已同时篡改区块 2 和 区块 4！")


#-------------------------------------------------------------------------
#测试

# ------------------- 完整哈希链全功能测试 -------------------
if __name__ == "__main__":
    print("="*50)
    print("========== 哈希链全功能测试 ==========")
    print("="*50)

    # 1. 创建创世区块（只跑第一次）
    print("\n【步骤1】创建创世区块")
    # 先判断有没有创世块
    if not get_latest_block():
        create_genesis_block()

    # 2. 模拟投票1 → 自动上链
    print("\n【步骤2】用户1投票 → 上链")
    add_vote_to_chain(
        Sn="USER001",
        r="Candidate_A",
        S="SIGNATURE_001"
    )

    # 3. 模拟投票2 → 自动上链
    print("\n【步骤3】用户2投票 → 上链")
    add_vote_to_chain(
        Sn="USER002",
        r="Candidate_B",
        S="SIGNATURE_002"
    )

    print("\n【步骤3】用户3投票 → 上链")
    add_vote_to_chain(
        Sn="USER002",
        r="Candidate_C",
        S="SIGNATURE_003"
    )

    # 4. 查看整条链
    print("\n【步骤4】查看整条哈希链")
    chain = get_all_blocks()
    for block in chain:
        print(f"区块 {block['block_id']} | prev_hash={block['prev_hash'][:10]}... | curr_hash={block['curr_hash'][:10]}...")

    # 5. 校验链是否完整
    print("\n【步骤5】校验哈希链完整性")
    verify_blockchain()

    # 6. 模拟篡改数据（故意破坏链）
    print("\n【步骤6】模拟攻击者篡改数据库！")
    # 这里我们手动修改一下 hash_chain 表（模拟攻击）
    conn, cur = get_db_connection()
    cur.execute("UPDATE hash_chain SET r='FAKE_VOTE' WHERE block_id=2")
    conn.commit()
    cur.close()
    conn.close()

    # 7. 再次校验 → 必然失败
    print("\n【步骤7】篡改后再次校验")
    verify_blockchain()