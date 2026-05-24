# test_3_votes.py
# 功能：模拟四个人投 4 票，测试存储、哈希链、防重复是否正常（虽然命名是3，但是实际模拟了投4票）


from vote_storage import insert_vote, check_sn_exists
from hash_chain import add_vote_to_chain, verify_blockchain, get_all_blocks
from vote_core import create_vote, verify_before_save

def cast_3_votes():
    print("=" * 60)
    print("🗳️  测试：连续投 3 票 → 正常入库 + 上哈希链")
    print("=" * 60)

    # 3个用户分别投不同候选人
    vote_list = [
        "Candidate_A",
        "Candidate_B",
        "Candidate_C",
        "Candidate_A",  # 重复投票测试
    ]

    for idx, content in enumerate(vote_list, 1):
        print(f"\n===== 第 {idx} 票开始 =====")

        try:
            # 1. 生成投票（唯一Sn + 签名）
            sn, real_sig = create_vote(content)
            print(f"✅ 生成投票ID：{sn}")
            print(f"投票内容：{content}")

            # 2. 查重
            if check_sn_exists(sn):
                print(f"❌ 第 {idx} 票失败：重复投票！")
                continue

            # 3. 入库前校验
            if not verify_before_save(content, sn, real_sig):
                print(f"❌ 第 {idx} 票失败：数据被篡改！")
                continue

            # 4. 入普通库
            insert_vote(sn, content, real_sig.hex())

            # 5. 入哈希链
            add_vote_to_chain(sn, content, real_sig.hex())

            print(f"✅ 第 {idx} 票：全部完成！已入库+上链")

        except Exception as e:
            print(f"❌ 第 {idx} 票异常：{str(e)}")

    # 最后展示结果
    print("\n" + "=" * 60)
    print("📊 4 票全部投完！")
    print("🔍 哈希链校验结果：")
    verify_blockchain()

    print("\n📦 当前哈希链所有区块：")
    blocks = get_all_blocks()
    for b in blocks:
        print(f"区块{b['block_id']} | Sn={b['Sn']} | 内容={b['r']}")

if __name__ == "__main__":
    cast_3_votes()
