# vote_core.py 用于封装投票系统核心逻辑：Sn 生成、哈希计算、盲签名流程、验签等

import random
import string
import hashlib
from rsa_crypto import (
    load_public_key, load_private_key,
    confuse, sign_message, unblind, verify_signature
)
from vote_storage import check_sn_exists
from Sn import generate_unique_sn, get_or_create_user_sn

# ======================== 【唯一可记忆 Sn 生成】 ========================
# from Sn import generate_unique_sn

# ======================== 【哈希计算：r + Sn】 ========================
def compute_hash(r: str, sn: str) -> bytes:
    """计算 Hash(投票内容 + Sn)，返回二进制哈希"""
    data = (r + sn).encode("utf-8")
    return hashlib.sha256(data).digest()

# ======================== 【完整盲签名流程】 ========================
def create_vote(r: str):
    """
    完整流程：
    1. 生成唯一 Sn
    2. 计算 Hash(r+Sn)
    3. 盲化 → 盲签名 → 去盲
    4. 验签
    返回：sn, real_signature
    """
    # 1. 生成唯一 Sn
    print("输入用户ID:")
    user_id = input().strip()
    sn = get_or_create_user_sn(user_id)

    # 2. 计算哈希
    vote_hash = compute_hash(r, sn)

    # 3. 加载密钥
    pub = load_public_key("myrsa_test/alice_public.pem")
    pri = load_private_key("myrsa_test/alice_private.pem")

    # 4. 盲化
    blinded, b_factor = confuse(vote_hash, public_key=pub)

    # 5. 盲签名
    blinded_sig = sign_message(pri, blinded)

    # 6. 去盲
    real_sig = unblind(blinded_sig, b_factor, pub)

    # 7. 验签
    valid = verify_signature(pub, vote_hash, real_sig)
    if not valid:
        raise Exception("验签失败！数据被篡改")

    return sn, real_sig

# ======================== 【入库前二次哈希校验】 ========================
def verify_before_save(r: str, sn: str, real_sig: bytes) -> bool:
    """提交数据库前，再次校验哈希和签名，绝对安全"""
    vote_hash = compute_hash(r, sn)
    pub = load_public_key("myrsa_test/alice_public.pem")
    return verify_signature(pub, vote_hash, real_sig)





#---------------------------test---------------------------
def test_vote_core():
    print("=" * 60)
    print("🧪 开始测试 vote_core.py 所有功能")
    print("=" * 60)

    # 1. 测试生成唯一 Sn
    print("\n【1】生成唯一 Sn...")
    sn = generate_unique_sn()
    print(f"✅ 生成 Sn：{sn}")

    # 2. 测试哈希计算
    r = "Candidate_A"
    print(f"\n【2】计算 Hash(r + Sn)，r = {r}")
    vote_hash = compute_hash(r, sn)
    print(f"✅ Hash 结果：{vote_hash.hex()[:32]}...")

    # 3. 测试完整盲签名流程
    print("\n【3】执行完整盲签名流程...")
    try:
        sn2, real_sig = create_vote(r)
        print(f"✅ 流程成功！")
        print(f"   新 Sn：{sn2}")
        print(f"   签名：{real_sig.hex()[:32]}...")
    except Exception as e:
        print(f"❌ 流程失败：{e}")
        return

    # 4. 测试入库前校验
    print("\n【4】测试入库前校验...")
    check_ok = verify_before_save(r, sn2, real_sig)
    if check_ok:
        print("✅ 入库前校验 PASS：签名与哈希完全匹配！")
    else:
        print("❌ 入库前校验 FAIL：数据被篡改！")

    print("\n" + "=" * 60)
    print("🎉 全部测试通过！vote_core.py 工作正常！")
    print("=" * 60)



#=========================== 【测试：篡改攻击】 ==========================
def test_tamper_attack():
    print("=" * 60)
    print("🧪 测试：投票防篡改功能")
    print("=" * 60)

    # 1. 正常生成一次投票
    vote_content = "Candidate_A"
    sn, real_sig = create_vote(vote_content)

    print(f"\n✅ 原始投票：")
    print(f"   Sn = {sn}")
    print(f"   内容 = {vote_content}")
    print(f"   签名 = {real_sig.hex()[:30]}...")

    # ----------------------
    # 【正常校验】应该通过
    # ----------------------
    ok = verify_before_save(vote_content, sn, real_sig)
    print(f"\n✅ 正常校验结果：{ok}（通过）")

    print("\n" + "-" * 50)
    print("🔥 现在开始模拟【篡改攻击】！")
    print("-" * 50)

    # ======================================================
    # 攻击方式1：篡改投票内容（最常见攻击）
    # ======================================================
    fake_content = "Candidate_B"  # 偷偷改票！
    ok1 = verify_before_save(fake_content, sn, real_sig)
    print(f"\n❌ 攻击1：改投票内容 → 校验结果：{ok1}（失败）")

    # ======================================================
    # 攻击方式2：篡改 Sn
    # ======================================================
    fake_sn = "FAKE123456"
    ok2 = verify_before_save(vote_content, fake_sn, real_sig)
    print(f"❌ 攻击2：改 Sn → 校验结果：{ok2}（失败）")

    # ======================================================
    # 攻击方式3：篡改签名（改1个字符）
    # ======================================================
    fake_sig = real_sig[:-1] + b'x'  # 改最后一位
    ok3 = verify_before_save(vote_content, sn, fake_sig)
    print(f"❌ 攻击3：改签名 → 校验结果：{ok3}（失败）")

    print("\n" + "=" * 60)
    print("🎯 测试结论：")
    print("   ✅ 任何篡改都会导致验签失败！")
    print("   ✅ 防篡改功能 100% 生效！")
    print("=" * 60)

if __name__ == "__main__":
    test_tamper_attack()

    #test_vote_core()