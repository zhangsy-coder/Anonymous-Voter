import os
import hashlib
from flask import Flask, request, jsonify
from flask_cors import CORS

# 引入队友编写的高级密码学与哈希链底层模块
from rsa_crypto import (
    load_private_key,
    load_public_key,
    sign_message,
    verify_signature,
    generate_project_keys,
    get_project_key_paths,
)
from hash_chain import (
    check_sn_exists,
    add_vote_to_chain,
    get_latest_block,
    create_genesis_block,
    get_block_by_sn,
)

app = Flask(__name__)

# 【关键配置】：开启全局 CORS 跨域资源共享
# 允许前端 (Live Server) 在匿名投递阶段、以及首页沙盒自检阶段，直接跨越 Node.js 访问底层 Python 节点
CORS(app, resources={r"/python/*": {"origins": "*"}})

# ====================================================================
# 🛡️ 初始化自检：确保区块链底层创世区块就绪
# ====================================================================
try:
    print("⏳ 正在检查区块链网络状态...")
    if not get_latest_block():
        print("⚠️ 未发现创世区块，正在初始化哈希链...")
        create_genesis_block()
    else:
        print("✅ 哈希链网络正常，已对接最新区块存证中心。")
except Exception as e:
    print(f"❌ 启动自检失败！详细错误: {e}")
    exit(1)


# ====================================================================
# 🆕 接口 1 & 2：SaaS 专属 - 分布式密钥物理隔离管理 (供 Node.js 网关调度)
# ====================================================================
@app.route("/python/generate_keys", methods=["POST"])
def api_generate_keys():
    """主办方创建新项目时触发：在物理硬盘上独立生成该项目的专属 RSA 密钥对"""
    project_id = request.json.get("project_id")
    if not project_id:
        return jsonify({"success": False, "message": "缺失 project_id"}), 400

    generate_project_keys(project_id)
    print(f"🔑 [密钥分发] 成功为项目 {project_id} 生成专属 RSA 密钥对！")
    return jsonify({"success": True})


@app.route("/python/get_public_key", methods=["GET"])
def api_get_public_key():
    """前端进入大厅或沙盒自检时触发：动态获取对应项目的公钥文件"""
    project_id = request.args.get("project_id")
    if not project_id:
        return jsonify({"success": False, "message": "缺失 project_id"}), 400

    _, public_path = get_project_key_paths(project_id)

    if not os.path.exists(public_path):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "未找到该项目的公钥，密码学环境可能已被级联抹除",
                }
            ),
            404,
        )

    with open(public_path, "r", encoding="utf-8") as f:
        public_key_pem = f.read()
    return jsonify({"success": True, "public_key": public_key_pem})


# ====================================================================
# 🔮 接口 3：盲签名签发中心 (利用项目私钥进行 RSA 签名)
# ====================================================================
@app.route("/python/sign_blind", methods=["POST"])
def sign_blind():
    try:
        data = request.json
        project_id = data.get("project_id")
        r_prime_hex = data.get("r_prime")

        if not project_id or not r_prime_hex:
            return jsonify({"success": False, "message": "参数不全"}), 400

        # 🚀 核心：动态定位并加载当前租户的私钥文件
        private_path, _ = get_project_key_paths(project_id)
        if not os.path.exists(private_path):
            return (
                jsonify({"success": False, "message": "该项目的私钥不存在，拒绝签发"}),
                404,
            )

        priv_key = load_private_key(private_path)
        r_prime_bytes = bytes.fromhex(r_prime_hex)

        print(
            f"\n📥 [盲签请求] 项目 {project_id} 收到前端发来的盲化数据: {r_prime_hex[:16]}..."
        )

        # 严格执行盲签草图公式：S' = (r')^d mod N
        s_prime_bytes = sign_message(priv_key, r_prime_bytes)

        print(f"🔮 [盲签成功] 已用项目 {project_id} 的顶级权限私钥完成数学盖章！")
        return jsonify({"success": True, "s_prime": s_prime_bytes.hex()})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ====================================================================
# 🕊️ 接口 4：匿名选票投递与哈希链上链 (利用项目公钥进行鉴权安检)
# ====================================================================
@app.route("/python/cast_vote", methods=["POST"])
def cast_vote():
    try:
        data = request.json
        project_id = data.get("project_id")
        r = data.get("r")
        Sn = data.get("Sn")
        S_hex = data.get("S")

        if not all([project_id, r, Sn, S_hex]):
            return (
                jsonify({"success": False, "message": "选票凭证碎片不完整，已驳回"}),
                400,
            )

        print(
            f"\n📬 [选票投递] 收到网络广播中项目 {project_id} 的匿名选票！内容:【{r}】"
        )

        # 🚀 核心：动态加载对应项目的公钥文件进行数学解密
        _, public_path = get_project_key_paths(project_id)
        if not os.path.exists(public_path):
            return (
                jsonify(
                    {"success": False, "message": "该项目公钥丢失，无法执行验签计算"}
                ),
                404,
            )

        pub_key = load_public_key(public_path)

        # 【密码学第一道防线】：验签 H(r || Sn) == S^e mod N
        vote_hash = hashlib.sha256((r + Sn).encode("utf-8")).digest()
        S_bytes = bytes.fromhex(S_hex)

        if not verify_signature(pub_key, vote_hash, S_bytes):
            print("❌ [安检失败] 密码学非对称验签未通过！该选票涉嫌伪造！")
            return (
                jsonify(
                    {"success": False, "message": "选票签名数据异常，拒绝存入区块链！"}
                ),
                403,
            )

        # 【密码学第二道防线】：哈希链底层物理查重
        if check_sn_exists(Sn):
            print(f"❌ [安检失败] 哈希链拦截：凭证 Sn [{Sn}] 已存在！(发生重放攻击)")
            return (
                jsonify(
                    {"success": False, "message": "该选票凭证已被消耗，禁止复印多投！"}
                ),
                403,
            )

        # 一切安全，批准入块存证
        success, msg = add_vote_to_chain(Sn, r, S_hex)

        if success:
            # 🚀 终极修复：使用显式数据库连接，防范 NULL 值，并强制提交事务
            try:
                from db_base import get_db_connection

                conn, cur = get_db_connection()
                if conn and cur:
                    # 1. 强制类型转换，防范字符串传参导致的 MySQL 匹配失效
                    p_id = int(project_id)
                    cand_serial = str(r).strip()

                    # 2. 加入 IFNULL 防御，防止 vote_count 初始值为 NULL 时加 1 失效
                    update_sql = """
                        UPDATE candidates 
                        SET vote_count = IFNULL(vote_count, 0) + 1 
                        WHERE project_id = %s AND serial_no = %s
                    """

                    # 3. 执行并获取受影响行数
                    affected_rows = cur.execute(update_sql, (p_id, cand_serial))

                    # 4. 🧨 极其关键：显式提交事务！(之前的 db_update 极有可能漏了这一句)
                    conn.commit()

                    cur.close()
                    conn.close()

                    if affected_rows > 0:
                        print(
                            f"📈 [计票同步] 项目 {p_id} 候选人 {cand_serial} 实时票数成功 +1！(更新了 {affected_rows} 行)"
                        )
                    else:
                        print(
                            f"⚠️ [计票警告] 找不到候选人！受影响行数为 0 (项目ID:{p_id}, 编号:{cand_serial})"
                        )
            except Exception as db_err:
                print(f"⚠️ [计票同步异常]: 数据库更新报错 - {db_err}")

            print(f"🎉 [上链成功] 项目 {project_id} 的选票已成功打入底层哈希联盟链！")
            return jsonify(
                {
                    "success": True,
                    "message": "恭喜！您的选票已成功完成去中心化永久存证！",
                }
            )
        else:
            return jsonify({"success": False, "message": f"上链级联失败: {msg}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ====================================================================
# 🚀 接口 5：【需求三新增】公开链上区块查询 (供前端密码学沙盒自检使用)
# ====================================================================
@app.route("/python/query_vote", methods=["GET"])
def query_vote():
    """
    供门户首页的极客沙盒调用。
    选民输入 Sn，Python 直接切入底层哈希链表，把对应的原始区块 (r, S, hash) 原封不动吐给前端去验证。
    """
    try:
        sn = request.args.get("Sn")
        if not sn:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "参数缺失：需要提供您手中保留的凭证 Sn",
                    }
                ),
                400,
            )

        print(f"\n🔍 [沙盒自证] 正在底层区块链网络全表检索凭证 Sn: {sn} ...")

        # 调用 hash_chain.py 里的函数捞出字典数据
        block = get_block_by_sn(sn)
        if not block:
            print(f"❌ [沙盒自证] 未找到凭证 {sn} 的上链记录。")
            return (
                jsonify(
                    {"success": False, "message": "未在区块链底层找到该凭证的存证流水"}
                ),
                404,
            )

        print(
            f"✅ [沙盒自证] 成功提取到历史区块 [{block['block_id']}]，正在封装发送至前端沙盒..."
        )

        # 将 datetime 对象转化为字符串防止 JSON 序列化崩溃
        block_time_str = (
            block["block_time"].strftime("%Y-%m-%d %H:%M:%S")
            if block.get("block_time")
            else None
        )

        return jsonify(
            {
                "success": True,
                "data": {
                    "block_id": block["block_id"],
                    "Sn": block["Sn"],
                    "r": block["r"],
                    "S": block["S"],
                    "curr_hash": block["curr_hash"],
                    "prev_hash": block["prev_hash"],
                    "block_time": block_time_str,
                },
            }
        )

    except Exception as e:
        print(f"❌ [沙盒查询异常]: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    # 绑定 0.0.0.0 开启全网域监听，微服务驻留 5000 端口
    app.run(host="0.0.0.0", port=5000, debug=True)
