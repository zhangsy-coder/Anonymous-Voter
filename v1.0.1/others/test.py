from __future__ import annotations

import copy
import argparse
import hashlib
import json
import random
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
import requests
import numpy as np

# ==========================================
# 自动化测试底座配置
# ==========================================
SCRIPT_DIR = Path(__file__).resolve().parent
PY_SERVER_DIR = SCRIPT_DIR.parent / "py_server"
if str(PY_SERVER_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(PY_SERVER_DIR))

def load_module_from_path(module_name: str, file_path: Path):
    spec = __import__("importlib.util").util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载核心行为检测组件: {file_path}")
    module = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

sybil_detector_mod = load_module_from_path("sybil_detector", PY_SERVER_DIR / "sybil_detector.py")
rule_engine_check = sybil_detector_mod.rule_engine_check

PROJECT_ID = 1
DEFAULT_CANDIDATE = "Candidate_A"
MOCK_HOST = "127.0.0.1"
MOCK_PORT = 5001


def build_behavior_features(behavior_data: Optional[dict]) -> Optional[dict]:
    if behavior_data is None:
        return None
    if not isinstance(behavior_data, dict):
        return behavior_data

    features = dict(behavior_data)
    tracks = features.get("mouse_tracks") or []
    if tracks:
        features.setdefault("move_count", len(tracks))
        features.setdefault("dwell_time", max(0.0, (tracks[-1][2] - tracks[0][2]) / 1000.0) if len(tracks) > 1 else 0.0)
        total_distance = 0.0
        total_time = max(1.0, tracks[-1][2] - tracks[0][2]) if len(tracks) > 1 else 1.0
        jitter_changes = 0
        last_dx = None
        last_dy = None
        for idx in range(1, len(tracks)):
            x1, y1, _ = tracks[idx - 1]
            x2, y2, _ = tracks[idx]
            dx = float(x2) - float(x1)
            dy = float(y2) - float(y1)
            total_distance += float((dx ** 2 + dy ** 2) ** 0.5)
            if last_dx is not None and (dx == 0 or dy == 0 or (dx > 0) != (last_dx > 0) or (dy > 0) != (last_dy > 0)):
                jitter_changes += 1
            last_dx, last_dy = dx, dy
        features.setdefault("total_distance", total_distance)
        features.setdefault("avg_speed", total_distance / total_time if total_time else 0.0)
        features.setdefault("jitter_rate", jitter_changes / max(1, len(tracks) - 1))
        features.setdefault("max_pause", max(
            [float(tracks[i][2]) - float(tracks[i - 1][2]) for i in range(1, len(tracks))] or [0.0]
        ))
    features.setdefault("key_count", len(features.get("key_events", [])) if isinstance(features.get("key_events"), list) else 0)
    features.setdefault("click_count", len(features.get("click_intervals", [])) + (1 if features.get("click_intervals") else 0))
    features.setdefault("accel_variance", float(features.get("kd_variance", 0) or 0))
    features.setdefault("scroll_count", int(features.get("scroll_count", 0) or 0))
    return features


def evaluate_sybil_locally(behavior_data: Optional[dict]) -> Tuple[int, dict]:
    features = build_behavior_features(behavior_data)
    if not features:
        return 403, {"success": False, "message": "缺少行为特征数据，疑似 API 直调"}

    is_suspicious, reason = rule_engine_check(features)
    if is_suspicious:
        return 403, {"success": False, "message": reason}
    return 200, {"success": True, "message": "行为正常，放行"}

def make_sandbox_payload(seed: str, candidate_id: str, behavior_data: Optional[dict] = None) -> dict:
    """构造仅用于 mock 服务的测试报文。"""
    sn = f"test_" + hashlib.sha256(seed.encode()).hexdigest()[:24]
    return {
        "project_id": PROJECT_ID,
        "r": candidate_id,
        "Sn": sn,
        "behavior_features": behavior_data,
    }
   
class MockSybilRequestHandler(BaseHTTPRequestHandler):
    server_version = "AnonymousVoterMock/1.0"

    def do_POST(self):
        if self.path != "/python/cast_vote":
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "not found"}, ensure_ascii=False).encode("utf-8"))
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "message": "invalid json"}, ensure_ascii=False).encode("utf-8"))
            return

        code, body = evaluate_sybil_locally(payload.get("behavior_features"))
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return


def start_mock_sybil_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((MOCK_HOST, MOCK_PORT), MockSybilRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def send_behavior_test_case(label: str, payload: dict, endpoint: str) -> Tuple[int, str]:
    """向 mock HTTP 服务发送请求并返回结果。"""
    try:
        res = requests.post(endpoint, json=payload, timeout=5)
        body_text = res.text.encode("utf-8").decode("unicode_escape") if "\\u" in res.text else res.text
        return res.status_code, body_text
    except Exception as e:
        return 0, f"mock 网关直调失败: {e}"

# ==========================================
# 📊 复合行为防女巫对抗测试主流程
# ==========================================
def run_sybil_defense_only_test():
    print("=========================================================")
    print("🗳️  Anonymous-Voter 后端【防女巫攻击与行为特征】专项联调")
    print("=========================================================")
    print(f"当前探测目标后端防女巫网关: http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print("当前模式: mock HTTP，仅测试女巫分支，不触发真实验签。\n")

    server = start_mock_sybil_server()

    print(">>> 核心测试：后端全链路行为指纹多维交叉交叉验证")
    print("-" * 75)

    # --------------------------------------------------
    # 用例 1：硬阻断 - 缺失行为特征
    # --------------------------------------------------
    p_miss = make_sandbox_payload("seed_case_miss_behavior", DEFAULT_CANDIDATE, behavior_data=None)
    code1, msg1 = send_behavior_test_case("【用例 1】故意缺失行为特征报文", p_miss, f"http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print(f"   -> 预期拦截码: 403 | 实际状态码: {code1}")
    print(f"   -> 后端拒绝响应: {msg1.strip()}\n")

    # --------------------------------------------------
    # 用例 2：硬阻断 - 命中规则引擎（停留时间异常短）
    # --------------------------------------------------
    # 模拟自动化脚本（瞬时注入、完全没有真实的移动轨迹序列）
    p_fast_bot = make_sandbox_payload("seed_case_fast_bot", DEFAULT_CANDIDATE, {
        "mouse_tracks": [[100, 100, int(time.time()*1000)]],  # 只有一个点
        "click_intervals": [],
        "kd_variance": 0.0,
        "scroll_count": 0
    })
    code2, msg2 = send_behavior_test_case("【用例 2】机器自动化高频秒点脚本", p_fast_bot, f"http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print(f"   -> 预期拦截码: 403 | 实际状态码: {code2}")
    print(f"   -> 后端拒绝响应: {msg2.strip()}\n")

    # --------------------------------------------------
    # 用例 3：硬阻断 - 命中规则引擎（全固定死板、零物理方差）
    # --------------------------------------------------
    # 机械化直线匀速脚本
    p_naive_bot = make_sandbox_payload("seed_case_naive_bot", DEFAULT_CANDIDATE, {
        "mouse_tracks": [[100, 100, 1000], [200, 200, 1100], [300, 300, 1200]], # 完美的绝对直线且时间戳完全固定
        "click_intervals": [500, 500, 500],  # 绝对死板的500ms
        "kd_variance": 0.0,                  # 物理抖动方差为0
        "scroll_count": 0
    })
    code3, msg3 = send_behavior_test_case("【用例 3】死板匀速简单循环机器人", p_naive_bot, f"http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print(f"   -> 预期拦截码: 403 | 实际状态码: {code3}")
    print(f"   -> 后端拒绝响应: {msg3.strip()}\n")

    # --------------------------------------------------
    # 用例 4：正向放行 - 模拟常规物理世界真实人用户（防误杀测试）
    # --------------------------------------------------
    steps = 15
    # 生成从 (150, 180) 到 (420, 500) 的复合人类肌肉微小神经抖动 (np.random.normal) 的轨迹
    x_path = np.linspace(150, 420, steps) + np.sin(np.linspace(0, 4 * np.pi, steps)) * 28 + np.random.normal(0, 1.2, steps)
    y_path = np.linspace(180, 500, steps) + np.cos(np.linspace(0, 3 * np.pi, steps)) * 22 + np.random.normal(0, 1.2, steps)
    timestamps = time.time() * 1000 + np.cumsum(np.random.normal(220, 25, steps))
    legit_tracks_1 = [[float(x), float(y), int(t)] for x, y, t in zip(x_path, y_path, timestamps)]
    
    p_human_normal = make_sandbox_payload("seed_case_legit_human_A", DEFAULT_CANDIDATE, {
        "mouse_tracks": legit_tracks_1,
        "click_intervals": [550, 890, 620],  # 正常人类点击间隔方差
        "kd_variance": 134.8,                 # 正常的物理键盘输入抖动
        "scroll_count": 3                     # 有滚动阅读动作
    })
    code4, msg4 = send_behavior_test_case("【用例 4】常规慢速真人操作输入", p_human_normal, f"http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print(f"   -> 预期成功码: 200 | 实际状态码: {code4}")
    print(f"   -> 后端成功响应: {msg4.strip()}\n")

    # --------------------------------------------------
    # 用例 5：正向放行 - 模拟极速敏捷型真人用户（边界防误杀）
    # --------------------------------------------------
    f_steps = 10
    x_f = np.linspace(200, 260, f_steps) + np.random.normal(0, 0.5, f_steps)
    y_f = np.linspace(300, 330, f_steps) + np.random.normal(0, 0.5, f_steps)
    t_f = time.time() * 1000 + np.cumsum(np.random.normal(250, 20, f_steps))
    legit_tracks_2 = [[float(x), float(y), int(t)] for x, y, t in zip(x_f, y_f, t_f)]
    
    p_human_fast = make_sandbox_payload("seed_case_legit_human_B", DEFAULT_CANDIDATE, {
        "mouse_tracks": legit_tracks_2,
        "click_intervals": [210, 250, 230],  # 操作飞快，但有微观物理特征
        "kd_variance": 45.6,
        "scroll_count": 1
    })
    code5, msg5 = send_behavior_test_case("【用例 5】极速敏捷型熟练人类用户", p_human_fast, f"http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print(f"   -> 预期成功码: 200 | 实际状态码: {code5}")
    print(f"   -> 后端成功响应: {msg5.strip()}\n")

    # --------------------------------------------------
    # 用例 6：全局防刷防女巫 - 哈希链 Sn 全局查重
    # --------------------------------------------------
    print("--- 启动全局哈希链选票唯一性（防刷重放女巫）校验 ---")
    replay_seed = "unique_voter_replay_token_pack"
    replay_behavior = {
        "mouse_tracks": [[120, 140, 1712398000000], [160, 180, 1712398000120]],
        "click_intervals": [450, 680], "kd_variance": 95.1, "scroll_count": 1
    }
    p_replay_first = make_sandbox_payload(replay_seed, DEFAULT_CANDIDATE, replay_behavior)
    p_replay_second = copy.deepcopy(p_replay_first) # 恶意重放：完全复制上一票
    
    _, msg6_1 = send_behavior_test_case("重放流：第 1 次诚实投递当前特征", p_replay_first, f"http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print(f"   -> 首次投递响应内容: {msg6_1.strip()}")
    code6_2, msg6_2 = send_behavior_test_case("重放流：第 2 次克隆同份凭证恶意刷选票", p_replay_second, f"http://{MOCK_HOST}:{MOCK_PORT}/python/cast_vote")
    print(f"   -> 二次黑刷拦截状态: 状态码={code6_2} | 消息={msg6_2.strip()}")

    server.shutdown()


if __name__ == "__main__":
    run_sybil_defense_only_test()
    print("\n" + "="*57)
    print("🎉 防女巫纯防御特征压测执行完毕！请在后端控制台观察判定。")
    print("="*57)