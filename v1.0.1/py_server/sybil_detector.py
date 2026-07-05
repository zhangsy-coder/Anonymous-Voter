# ============================================================================
# 🛡️ 女巫攻击检测模块 (Sybil Attack Detection)
# ============================================================================
# 功能：基于深度学习的异常检测，利用无监督学习在匿名投票中识别自动化脚本/僵尸网络
# 策略：双引擎架构 — 规则引擎(快速硬拦截) + Isolation Forest(统计异常检测)
# 原理：提取非身份行为特征（时间间隔、鼠标轨迹、页面停留时间等），不破坏匿名性
# ============================================================================

import math
import json
import numpy as np
from db_base import db_insert, db_query_all


# ============================================================================
# 🔧 规则引擎：硬拦截明显脚本特征（零假阳性，可解释）
# ============================================================================
def rule_engine_check(features):
    """
    硬规则快速拦截：检测明显不符合人类行为的极端值
    
    features: dict {
        dwell_time:     页面停留时间 (秒)
        total_distance: 鼠标累计移动距离 (像素)
        avg_speed:      鼠标平均移动速度 (像素/毫秒)
        jitter_rate:    方向突变率 (突变次数/总距离)
        move_count:     鼠标移动事件总数
        key_count:      键盘事件总数
        click_count:    点击事件总数
        scroll_count:   滚动事件总数
        max_pause:      最大停顿间隔 (毫秒)
        accel_variance: 加速度方差
    }
    
    :return: (is_suspicious: bool, reason: str)
    """
    
    # --- 规则1：人类必定有页面停留时间；脚本瞬时提交 ---
    dwell = features.get("dwell_time", 0)
    if dwell < 2.0:
        return True, "停留时间异常短 (< 2秒)，疑似脚本瞬时提交"

    # --- 规则2：正常人类一定会移动鼠标；完全没有鼠标事件 = 脚本 ---
    total_dist = features.get("total_distance", 0)
    move_cnt = features.get("move_count", 0)
    if total_dist < 10 or move_cnt < 3:
        return True, "鼠标移动极少 (< 10px 或 < 3次事件)，疑似无头浏览器/API 直调"

    # --- 规则3：鼠标速度过快 (> 8 px/ms)，人类不可能 ---
    avg_spd = features.get("avg_speed", 0)
    if avg_spd > 8.0:
        return True, f"鼠标平均速度过快 ({avg_spd:.1f} px/ms)，超出人类生理极限"

    # --- 规则4：方向突变率极低 = 机器人直线移动（脚本常匀速直线） ---
    jitter = features.get("jitter_rate", 0)
    if total_dist > 100 and jitter < 0.001:
        return True, f"方向突变率极低 ({jitter:.6f})，疑似脚本匀速直线移动"

    # --- 规则5：完全没有键盘事件，但页面停留很久 — 可疑 ---
    key_cnt = features.get("key_count", 0)
    if dwell > 30 and key_cnt == 0:
        return True, "长时间停留无键盘操作，不符合正常交互模式"

    # --- 规则6：点击次数为0但完成了投票提交 ---
    click_cnt = features.get("click_count", 0)
    if click_cnt == 0:
        return True, "零点击完成投票，疑似 DOM 直调"

    return False, ""


# ============================================================================
# 🧠 Isolation Forest 统计异常检测引擎
# ============================================================================
class SybilDetector:
    """
    基于 Isolation Forest 的无监督异常检测器
    
    - 使用非身份行为特征（鼠标、键盘、时间），不需要用户ID
    - 隔离开脚本的"异常短路径"模式：自动化脚本的行为在多维空间中容易隔离
    - 滚动训练窗口：每次有新的正常投票数据，更新模型
    """
    
    def __init__(self, contamination=0.1):
        """
        contamination: 预期的异常比例（默认 10%），即假设最多 10% 是刷票
        """
        self.contamination = contamination
        self.model = None
        self.feature_names = [
            "dwell_time",
            "total_distance",
            "avg_speed",
            "jitter_rate",
            "move_count",
            "key_count",
            "click_count",
            "scroll_count",
            "max_pause",
            "accel_variance",
        ]
        self.fitted = False
        self._init_model()

    def _init_model(self):
        """惰性初始化模型，避免 sklearn 导入延迟影响启动"""
        try:
            from sklearn.ensemble import IsolationForest
            self.model = IsolationForest(
                n_estimators=100,
                contamination=self.contamination,
                random_state=42,
                n_jobs=-1,
            )
        except ImportError:
            print("⚠️ [女巫检测] sklearn 未安装，Isolation Forest 引擎禁用，仅启用规则引擎")
            self.model = None

    def _dict_to_array(self, features):
        """将特征字典转为 numpy 数组，按固定顺序，缺失填0"""
        return np.array([features.get(name, 0) for name in self.feature_names], dtype=np.float64)

    def fit_on_historical(self):
        """
        用数据库中存储的历史行为数据训练/更新模型
        """
        if self.model is None:
            return

        rows = db_query_all(
            "SELECT dwell_time, total_distance, avg_speed, jitter_rate, "
            "move_count, key_count, click_count, scroll_count, "
            "max_pause, accel_variance FROM sybil_behavior_log "
            "WHERE is_sybil = 0 ORDER BY id DESC LIMIT 500"
        )
        if len(rows) < 50:
            print(f"⚠️ [女巫检测] 历史正常样本不足 ({len(rows)} < 50)，跳过模型训练")
            return

        X = []
        for row in rows:
            X.append([
                float(row.get("dwell_time") or 0),
                float(row.get("total_distance") or 0),
                float(row.get("avg_speed") or 0),
                float(row.get("jitter_rate") or 0),
                float(row.get("move_count") or 0),
                float(row.get("key_count") or 0),
                float(row.get("click_count") or 0),
                float(row.get("scroll_count") or 0),
                float(row.get("max_pause") or 0),
                float(row.get("accel_variance") or 0),
            ])

        X = np.array(X, dtype=np.float64)
        self.model.fit(X)
        self.fitted = True
        print(f"✅ [女巫检测] Isolation Forest 模型已用 {len(rows)} 条历史数据训练完成")

    def predict(self, features):
        """
        对单条行为特征进行异常检测
        
        :param features: dict 行为特征
        :return: (is_sybil: bool, anomaly_score: float, reason: str)
        """
        if self.model is None:
            return False, 0.0, "模型未加载"

        # 快速规则引擎先行（零假阳性硬拦截）
        is_suspicious, rule_reason = rule_engine_check(features)
        if is_suspicious:
            return True, -1.0, f"[规则引擎] {rule_reason}"

        # Isolation Forest 预测
        X = self._dict_to_array(features).reshape(1, -1)
        
        if not self.fitted:
            # 未训练时退化为简易统计
            score = self._fallback_score(features)
            return score < -0.3, score, f"[统计退避] 异常分数 {score:.4f}"
        
        pred = self.model.predict(X)[0]         # 1=正常, -1=异常
        score = self.model.decision_function(X)[0]  # 越负越异常

        if pred == -1:
            return True, score, f"[IsolationForest] 行为模式与正常投票分布显著偏离，异常分数 {score:.4f}"

        return False, score, ""

    def _fallback_score(self, features):
        """统计退避：基于 Z-score 的简单异常评估"""
        rows = db_query_all(
            "SELECT AVG(dwell_time) as m1, STD(dwell_time) as s1, "
            "AVG(total_distance) as m2, STD(total_distance) as s2, "
            "AVG(avg_speed) as m3, STD(avg_speed) as s3, "
            "AVG(jitter_rate) as m4, STD(jitter_rate) as s4 "
            "FROM sybil_behavior_log WHERE is_sybil = 0"
        )
        if not rows or rows[0]["m1"] is None:
            return 0.0

        r = rows[0]
        z_scores = []
        
        for key, mean_key, std_key in [
            ("dwell_time", "m1", "s1"),
            ("total_distance", "m2", "s2"),
            ("avg_speed", "m3", "s3"),
            ("jitter_rate", "m4", "s4"),
        ]:
            m = float(r[mean_key] or 0)
            s = float(r[std_key] or 1)
            if s == 0:
                s = 1
            z_scores.append(abs(float(features.get(key, 0)) - m) / s)

        # 平均 Z-score，负值表示"异常"
        avg_z = np.mean(z_scores)
        return -avg_z


# ============================================================================
# 📊 特征数据持久化：记录每一次投票的行为特征和检测结果
# ============================================================================
def log_behavior(sn, project_id, features, is_sybil, score, reason):
    """
    将投票行为特征写入 sybil_behavior_log 表，用于后续模型训练和审计
    
    :param sn:         匿名凭证（非身份信息，不破坏匿名性）
    :param project_id: 项目ID
    :param features:   dict 行为特征
    :param is_sybil:   是否被判定为女巫
    :param score:      异常分数
    :param reason:     判定原因
    """
    sql = """
    INSERT INTO sybil_behavior_log 
    (sn, project_id, dwell_time, total_distance, avg_speed, jitter_rate,
     move_count, key_count, click_count, scroll_count, max_pause, accel_variance,
     is_sybil, anomaly_score, detect_reason)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        str(sn),
        int(project_id),
        float(features.get("dwell_time", 0)),
        float(features.get("total_distance", 0)),
        float(features.get("avg_speed", 0)),
        float(features.get("jitter_rate", 0)),
        int(features.get("move_count", 0)),
        int(features.get("key_count", 0)),
        int(features.get("click_count", 0)),
        int(features.get("scroll_count", 0)),
        float(features.get("max_pause", 0)),
        float(features.get("accel_variance", 0)),
        1 if is_sybil else 0,
        float(score),
        str(reason)[:1024],
    )
    return db_insert(sql, params)


# ============================================================================
# 🧪 单体测试入口
# ============================================================================
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 女巫攻击检测模块 单体测试")
    print("=" * 50)

    detector = SybilDetector(contamination=0.1)
    detector.fit_on_historical()

    # 测试用例1：正常人类
    human_features = {
        "dwell_time": 25.0,
        "total_distance": 3500.0,
        "avg_speed": 0.35,
        "jitter_rate": 0.008,
        "move_count": 120,
        "key_count": 2,
        "click_count": 3,
        "scroll_count": 8,
        "max_pause": 5000,
        "accel_variance": 0.02,
    }
    is_syb, score, reason = detector.predict(human_features)
    print(f"\n[正常人] sybil={is_syb}, score={score:.4f}, reason={reason}")

    # 测试用例2：脚本机器人
    bot_features = {
        "dwell_time": 0.3,
        "total_distance": 0.0,
        "avg_speed": 0.0,
        "jitter_rate": 0.0,
        "move_count": 0,
        "key_count": 0,
        "click_count": 0,
        "scroll_count": 0,
        "max_pause": 0,
        "accel_variance": 0.0,
    }
    is_syb, score, reason = detector.predict(bot_features)
    print(f"\n[脚本机器人] sybil={is_syb}, score={score:.4f}, reason={reason}")

    print("\n" + "=" * 50)
    print("🏁 测试结束")