# 模块1：RSA盲签名密码学核心模块
"""
本模块解决：RSA密钥生成，密钥存入文件，从文件中读取密钥，加密，解密，数字签名，检验数字签名，根据时间生成随机数，匿名投票系统中的盲化与去盲
特别注意：本模块采用教科书RSA（无填充），明文长度不可超过 190 字节
main函数作为测试函数，测试"密钥存入文件"部分的结果已经存入myrsa_test
"""

import random
import time
import math
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
# import os


def generate_rsa_keys(private_key_path="private_key.pem", public_key_path="public_key.pem"):
    """
    生成 RSA 密钥对，并保存为 PEM 文件。
    - 私钥使用传统的 PKCS#1 格式。
    - 公钥使用 SubjectPublicKeyInfo 格式。
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(private_key_path, "wb") as f:
        f.write(private_pem)

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(public_key_path, "wb") as f:
        f.write(public_pem)

    print(f"[密钥生成] 私钥已保存至 {private_key_path}")
    print(f"[密钥生成] 公钥已保存至 {public_key_path}")
    return private_key, public_key


def load_private_key(filepath="private_key.pem"):
    """从文件加载私钥"""
    with open(filepath, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    return private_key


def load_public_key(filepath="public_key.pem"):
    """从文件加载公钥"""
    with open(filepath, "rb") as f:
        public_key = serialization.load_pem_public_key(
            f.read(),
            backend=default_backend()
        )
    return public_key


# ================== RSA 加密 / 解密 ==================
def encrypt_with_public_key(public_key, plaintext: bytes) -> bytes:
    """
    教科书 RSA 加密：c = m^e mod n
    注意：明文必须转换为整数且小于 n
    """
    n = public_key.public_numbers().n
    e = public_key.public_numbers().e
    m_int = int.from_bytes(plaintext, byteorder='big')
    if m_int >= n:
        raise ValueError("明文整数太大，必须小于模数 n")
    c_int = pow(m_int, e, n)
    # 将密文转换为与 n 等长的字节串
    return c_int.to_bytes((n.bit_length() + 7) // 8, byteorder='big')


def decrypt_with_private_key(private_key, ciphertext: bytes) -> bytes:
    """
    教科书 RSA 解密：m = c^d mod n
    """
    n = private_key.public_key().public_numbers().n
    d = private_key.private_numbers().d
    c_int = int.from_bytes(ciphertext, byteorder='big')
    m_int = pow(c_int, d, n)
    # 去除前导零字节（保持原始长度，但可能有前导零，这里直接转回字节串）
    # 注意：可能丢失前导零，但通常明文没有前导零，此处简单处理
    return m_int.to_bytes((n.bit_length() + 7) // 8, byteorder='big').lstrip(b'\x00')


# ================== RSA 签名 / 验签 ==================
def sign_message(private_key, message: bytes) -> bytes:
    """
    教科书 RSA 签名：s = m^d mod n
    注意：消息整数必须小于 n
    """
    n = private_key.public_key().public_numbers().n
    d = private_key.private_numbers().d
    m_int = int.from_bytes(message, byteorder='big')
    if m_int >= n:
        raise ValueError("消息整数太大，必须小于模数 n")
    s_int = pow(m_int, d, n)
    return s_int.to_bytes((n.bit_length() + 7) // 8, byteorder='big')


def verify_signature(public_key, message: bytes, signature: bytes) -> bool:
    """
    教科书 RSA 验签：验证 s^e mod n == m
    """
    n = public_key.public_numbers().n
    e = public_key.public_numbers().e
    m_int = int.from_bytes(message, byteorder='big')
    s_int = int.from_bytes(signature, byteorder='big')
    try:
        recovered = pow(s_int, e, n)
        return recovered == m_int
    except Exception:
        return False


# ================== 盲签名相关函数 ==================
def createrandom(public_key=None):
    """
    生成一个与 RSA 模数 n 互质的随机整数，作为盲因子 r。
    """
    if public_key is None:
        public_key = load_public_key("public_key.pem")
    n = public_key.public_numbers().n
    random.seed(time.time())
    while True:
        r = random.randint(2, n - 1)
        if math.gcd(r, n) == 1:
            return r


def confuse(message: bytes, randomnum: int = None, public_key=None) -> Tuple[bytes, int]:
    """
    RSA 盲化操作：m' = m * (r^e) mod n
    返回 (盲化消息, 盲因子 r)
    """
    if public_key is None:
        public_key = load_public_key("public_key.pem")
    m_int = int.from_bytes(message, byteorder='big')
    n = public_key.public_numbers().n
    e = public_key.public_numbers().e

    if randomnum is None:
        r = createrandom(public_key)
    else:
        r = randomnum
        if math.gcd(r, n) != 1:
            raise ValueError("盲因子 r 必须与模数 n 互质")

    r_e = pow(r, e, n)
    blinded_int = (m_int * r_e) % n
    blinded_bytes = blinded_int.to_bytes((n.bit_length() + 7) // 8, byteorder='big')
    return blinded_bytes, r


def unblind(blinded_signature: bytes, r: int, public_key=None) -> bytes:
    """
    RSA 去盲操作：s = s' * r^{-1} mod n
    """
    if public_key is None:
        public_key = load_public_key("public_key.pem")
    n = public_key.public_numbers().n
    s_int = int.from_bytes(blinded_signature, byteorder='big')
    r_inv = pow(r, -1, n)
    sig_int = (s_int * r_inv) % n
    sig_bytes = sig_int.to_bytes((n.bit_length() + 7) // 8, byteorder='big')
    return sig_bytes


def distribute_public_key_as_string(public_key) -> str:
    """
    将公钥序列化为字符串（PEM 格式），以便通过网络或文件传输。
    """
    pem_data = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem_data.decode('utf-8')


def load_public_key_from_string(pem_string: str):
    """从 PEM 字符串加载公钥"""
    pem_data = pem_string.encode('utf-8')
    return serialization.load_pem_public_key(pem_data, backend=default_backend())




def test():
    # 步骤 1：生成密钥对（首次运行）
    print("=== 生成 RSA 密钥对 ===")
    priv_key, pub_key = generate_rsa_keys("./myrsa_test/alice_private.pem", "./myrsa_test/alice_public.pem")

    # 步骤 2：模拟分配公钥给 Bob
    print("\n=== 分配公钥 ===")
    pub_pem_str = distribute_public_key_as_string(pub_key)
    print("公钥 PEM 字符串（可发送给 Bob）：")
    print(pub_pem_str)

    bob_public_key = load_public_key_from_string(pub_pem_str)

    # 步骤 3：Bob 使用公钥加密机密信息（教科书 RSA）
    print("\n=== 加密阶段（Bob 使用公钥加密） ===")
    secret_msg = b"Hello Alice, this is a top-secret message!"
    ciphertext = encrypt_with_public_key(bob_public_key, secret_msg)
    print(f"加密后的密文（十六进制前64位）: {ciphertext.hex()[:64]}...")

    # 步骤 4：Alice 收到密文，用自己的私钥解密
    print("\n=== 解密阶段（Alice 使用私钥解密） ===")
    decrypted_msg = decrypt_with_private_key(priv_key, ciphertext)
    print(f"解密后的原文: {decrypted_msg.decode('utf-8')}")

    # 步骤 5：数字签名与验签（教科书 RSA）
    print("\n=== 数字签名（Alice 签署一段指令） ===")
    command = b"Transfer 1000 coins to Bob"
    signature = sign_message(priv_key, command)
    print(f"签名（十六进制前64位）: {signature.hex()[:64]}...")

    print("=== 验签（Bob 使用 Alice 的公钥验证） ===")
    is_valid = verify_signature(bob_public_key, command, signature)
    print(f"签名验证结果: {'通过 ✓' if is_valid else '失败 ✗'}")

    # 篡改消息验证
    tampered_command = b"Transfer 10000 coins to Eve"
    is_valid_tampered = verify_signature(bob_public_key, tampered_command, signature)
    print(f"篡改后的消息验签结果: {'通过 ✓' if is_valid_tampered else '失败 ✗'}")

    # ========== 盲签名演示 ==========
    print("\n=== 盲签名演示（模拟匿名投票） ===")
    # 原始选票
    vote = b"Vote for Candidate A"
    print(f"原始选票: {vote.decode()}")

    # 盲化
    blinded_vote, r = confuse(vote, public_key=pub_key)
    print(f"生成的盲因子 r = {r}")
    print(f"盲化后的选票（十六进制前64位）: {blinded_vote.hex()[:64]}...")

    # 对盲化消息进行签名（教科书签名）
    blinded_signature = sign_message(priv_key, blinded_vote)
    print(f"对盲选票的签名（十六进制前64位）: {blinded_signature.hex()[:64]}...")

    # 去盲
    real_signature = unblind(blinded_signature, r, pub_key)
    print(f"去盲后得到的真实签名（十六进制前64位）: {real_signature.hex()[:64]}...")

    # 验证去盲后的签名是否与原始选票匹配
    is_valid_blind = verify_signature(pub_key, vote, real_signature)
    print(f"盲签名验证结果: {'通过 ✓' if is_valid_blind else '失败 ✗'}")



# ==================== 【完整业务测试：RSA + Sn + 投票】 ====================
if __name__ == "__main__":
    test()