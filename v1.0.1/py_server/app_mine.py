import os
import hashlib
from flask import Flask,request,jsonify
from flask_cors import CORS

from rsa_crypto import(
    load_private_key,
    load_public_key,
    sign_message,
    verify_signature,
    generate_project_keys,
    get_project_key_paths,
)
from hash_chain import(
    check_sn_exists,
    add_vote_to_chain,
    get_all_blocks,
    create_genesis_block,
    get_block_by_sn
)
app=Flask(__name__)
CORS(app,resources={r"/python/*":{"origin":"*"}})

try:
    print("正在检查区块链网络状态:...")
    if not get_latest_block():
        print("未发现创世区块，正在初始化哈希链:...")
        create_genesis_block
    else:
        print("哈希链网络正常，已对接最新区块存证中心")
except Exception as e:
    print(f"启动自检失败，详细错误:{e}")
    exit(1)

@app.route("/python/generate_keys",methods=["POST"])
def api_generate_keys():
    project_id=request.json.get("project_id")
    if not project_id:
        return jsonify({"success":False,"message":"缺失project_id"}),400
    generate_project_keys(project_id)
    print(f"成功为项目{project_id}生成专属密钥")
    return jsonify({"success":True})

@app.route("/python/get_public_key",method=["GET"])
def api_get_public_keys():
    project_id=request.args.get("project_id")
    if not project_id:
        return jsonify({"success":False,"message":"缺失Project_id"}),400
    _,public_path=get_project_key_paths(project_id)
    if not os.path.exists(public_path):
        return(
            jsonify({"success":False,"message":"未找到该项目公钥，密码学环境可能被级联抹除"}),400
        )
    with open(public_path,"r",encoding="utf-8") as f:
        public_key_pem=f.read()
    return jsonify({"success":True,"public_key":public_key_pem})

@app.route("/python/sign_blind",methods=["POST"])
def sign_blind():
    try:
        data=request.json
        project_id=data.get("project_id")
        r_prime_hex=data.get("r_prime")
        if not project_id or not r_prime_hex:
            return jsonify({"success":False,"message":"参数不全"}),400
        private_path,_=get_project_keys_paths(project_id)
        if not os.path.exists(private_path):
            return (jsonify({"success":False,"message":"该项目的私钥不存在，拒绝签发"}))
        priv_key=load_private_key(private_path)
        r_prime_bytes=bytes.fromhex(r_prime_hex)
        print(f"\n[盲签请求] 项目 {project_id} 收到前端发来的盲化数据: {r_prime_hex[:16]}...")
        s_prime_bytes=sign_message(priv_key,r_prime_bytes)
        print(f"🔮 [盲签成功] 已用项目 {project_id} 的顶级权限私钥完成数学盖章！")
        return jsonify({"success": True, "s_prime": s_prime_bytes.hex()})


    except Exception as e:    
        return jsonify({"success":False,"message":str(e)}),500
    

@app.route("/python/cast_vote",methods=["POST"])
def cast_vote():
    try:
        data=request.json
        project_id=data.get("project_id")
        r=data.get("r")
        Sn=data.get("Sn")
        S_hex=data.get("S")
    
        if not all([project_id,r,Sn,S_hex]):
            return (jsonify({"success":False,"message":"选票凭证不完整，已驳回"}))
        print(
            f"\n📬 [选票投递] 收到网络广播中项目 {project_id} 的匿名选票！内容:【{r}】"
        )
        _,public_path=get_project_paths(project_id)
        if not os.path.exists(public_path):
            return (
                jsonify(
                    {"success": False, "message": "该项目公钥丢失，无法执行验签计算"}
                ),
                404,
            )
        pub_key = load_public_key(public_path)
        vote_hash=hashlib.sha256((r+sn).encode("utf-8")).degest()
        S_bytes=bytes_fromhex(S_hex)

        if not verify_signature(pub_key,vote_hash,S_bytes):
            print("❌ [安检失败] 密码学非对称验签未通过！该选票涉嫌伪造！")
            return (
                jsonify(
                    {"success": False, "message": "选票签名数据异常，拒绝存入区块链！"}
                ),
                403,
            )
        if check_sn_exists(Sn):
            print(f"❌ [安检失败] 哈希链拦截：凭证 Sn [{Sn}] 已存在！(发生重放攻击)")
            return (
                jsonify(
                    {"success": False, "message": "该选票凭证已被消耗，禁止复印多投！"}
                ),
                403,
            )
        success,msg=add_vote_to_chain(Sn,r,hex)
        if success:
            try:
                from db_base import get_db_connection
                conn,cur=get_db_connection()
                if conn and cur:
                    p_id=int(project_id)
                    can_serial =str(r).strip()
                    update_sql = """
                        UPDATE candidates 
                        SET vote_count = IFNULL(vote_count, 0) + 1 
                        WHERE project_id = %s AND serial_no = %s
                    """
                    affected_rows=cur.execute(update_sql,(p_id,cand_serial))
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

        else:
            return jsonify({"success": False, "message": f"上链级联失败: {msg}"}), 500

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500