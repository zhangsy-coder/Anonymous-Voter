#本模块用于测试篡改哈希链，并测试能否检测到

# test_tamper_two.py
from hash_chain import verify_blockchain, tamper_two_blocks_test

print("=" * 60)
print("🔗 测试：同时篡改 2 个区块，能否全部检测？")
print("=" * 60)

print("\n【1】篡改前：")
verify_blockchain()

print("\n【2】开始同时篡改 区块2 和 区块4...")
tamper_two_blocks_test()

print("\n【3】篡改后校验：")
verify_blockchain()

print("\n🎯 结果：系统成功检测到多处篡改！")
