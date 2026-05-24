#本模块用于汇总投票，得出选票结果
#直接调用运行即可，无需传参
#最下方第一个函数用于测试篡改，实际运行时要注释掉


# vote_result.py 【最终汇总模块】
from hash_chain import verify_blockchain, get_all_blocks, tamper_two_blocks_test
from db_base import db_query_all, db_update
from vote_storage import get_valid_votes

def invalidate_tampered_votes():
    """
    校验哈希链，并将被篡改的区块对应的投票设为无效（is_valid=0）
    返回：被作废的票数
    """
    print("=" * 60)
    print("完整校验哈希链")
    print("=" * 60)

    # 1. 完整校验链（不会中途退出）
    chain = get_all_blocks()
    invalid_sn_list = []

    for i in range(1, len(chain)):
        current = chain[i]
        previous = chain[i-1]
        block_num = i + 1

        # 检查链是否断裂
        chain_broken = (current["prev_hash"] != previous["curr_hash"])
        # 检查哈希是否正确
        real_hash = compute_block_hash(
            current["prev_hash"], current["Sn"], current["r"], current["S"]
        )
        hash_invalid = (current["curr_hash"] != real_hash)

        if chain_broken or hash_invalid:
            sn = current["Sn"]
            if sn != "GENESIS":
                invalid_sn_list.append(sn)

    # 2. 将被篡改的票作废
    invalid_count = 0
    for sn in invalid_sn_list:
        sql = "UPDATE vote_main SET is_valid = 0 WHERE Sn = %s"
        db_update(sql, (sn,))
        invalid_count += 1
        print(f"❌作废投票：Sn = {sn}（哈希链异常）")

    print(f"\n共作废 {invalid_count} 张异常票")
    return invalid_count

def summarize_vote_result():
    """
    最终汇总：统计有效投票结果
    """
    print("\n" + "=" * 60)
    print("：最终投票结果汇总")
    print("=" * 60)

    # 获取有效票
    valid_votes = get_valid_votes()
    total = len(valid_votes)

    # 统计候选人
    result = {}
    for v in valid_votes:
        cand = v["r"]
        result[cand] = result.get(cand, 0) + 1

    # 输出
    print(f"\n总有效票数：{total}")
    print("\n候选人得票：")
    for cand, cnt in result.items():
        print(f"   {cand}：{cnt} 票")

    print("\n🎉 投票汇总完成！")
    return result

def full_result_flow():
    """完整结果流程"""
    # 1. 校验链 + 作废异常票
    invalidate_tampered_votes()
    # 2. 汇总结果
    return summarize_vote_result()

# 必须导入的依赖
from hash_chain import compute_block_hash

if __name__ == "__main__":
    tamper_two_blocks_test()    #用于测试恶意篡改后的统计，排除异常票的干扰
    full_result_flow()
