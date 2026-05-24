# 项目主程序入口（全流程调度）
# 主要在这个模块进行整合
# 比如需要从前端传入 投票内容给 vote_content变量
# Sn生成也可以直接在此处实现，此处我也调用了Sn生成器 只需要传入ID即可
# 自动实现 签名等全流程，入库前的检查，没问题后入库

# main.py 【最终完整版】
# 功能：初始化 → 生成投票 → 查重 → 入库前校验 → 双表入库 → 完成
from db_base import init_db
from hash_chain import create_genesis_block, get_latest_block, verify_blockchain, add_vote_to_chain
from vote_storage import insert_vote, check_sn_exists
from vote_core import create_vote, verify_before_save

def main():
    # ===================== 【初始化：仅第一次运行打开】 =====================
    # init_db()
    # if not get_latest_block():
    #     create_genesis_block()
    # ====================================================================

    # ===================== 投票业务开始 =====================
    print("=" * 60)
    print("🗳️  匿名投票系统 - 完整流程")
    print("=" * 60)

    # 1. 用户选择投票内容
    vote_content = "Candidate_A"
    print(f"\n📝 用户投票内容：{vote_content}")

    try:
        # 2. 执行完整盲签名流程（生成唯一Sn + 签名）
        sn, real_signature = create_vote(vote_content)
        print(f"✅ 生成唯一投票ID（Sn）：{sn}")

        # 3. 数据库查重：是否已经投过票（防重复）
        if check_sn_exists(sn):
            print(f"❌ 投票失败：Sn {sn} 已存在，禁止重复投票！")
            return

        # 4. 入库前安全校验（防篡改：校验签名是否对应 Hash(r+Sn)）
        if not verify_before_save(vote_content, sn, real_signature):
            print("❌ 投票失败：数据被篡改，校验不通过！")
            return
        print("✅ 入库前校验通过：数据未被篡改")

        # 5. 存入【普通投票库】
        insert_vote(sn, vote_content, real_signature.hex())
        print("✅ 已存入普通投票数据库")

        # 6. 存入【哈希链】（防篡改存证）
        if not get_latest_block(): create_genesis_block() # 确保创世块存在
        add_vote_to_chain(sn, vote_content, real_signature.hex())
        print("✅ 已上哈希链存证")

        # ===================== 投票成功 =====================
        print("\n" + "=" * 60)
        print("🎉 投票全部完成！")
        print(f"🆔 你的唯一投票ID：{sn}")
        print(f"🗳️  投票内容：{vote_content}")
        print("✅ 状态：有效票 | 已入库 | 已上链 | 防篡改保护")
        print("=" * 60)

        # 可选：校验哈希链完整性
        print("\n🔍 哈希链完整性校验：")
        verify_blockchain()

    except Exception as e:
        print(f"\n❌ 系统异常：{str(e)}")

if __name__ == "__main__":
    main()
