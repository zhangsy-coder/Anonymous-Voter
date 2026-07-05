// v1.0.1/client/js/behavior_collector.js
// ============================================================================
// 🛡️ 行为特征采集器 — 女巫攻击检测前端数据源
// 采集非身份行为特征：鼠标轨迹、键盘、点击、滚动、停顿、加速度方差
// 所有数据均为匿名行为统计，不包含任何个人身份信息
// ============================================================================
(function () {
    let pageLoadTime = Date.now();
    let lastMoveTime = null;
    let totalDistance = 0;
    let moveCount = 0;
    let totalSpeed = 0;
    let directionChanges = 0;
    let lastX = null, lastY = null;
    let lastAngle = null;

    // --- 新增特征采集 ---
    let keyCount = 0;           // 键盘事件计数
    let clickCount = 0;         // 点击事件计数
    let scrollCount = 0;        // 滚动事件计数
    let maxPause = 0;           // 相邻鼠标事件之间的最大停顿 (毫秒)
    let lastSpeed = null;       // 上一个速度值，用于计算加速度方差
    let accelSamples = [];      // 加速度样本数组

    // 持续监听鼠标移动事件
    window.addEventListener('mousemove', (e) => {
        let now = Date.now();
        if (lastX !== null && lastY !== null) {
            let dx = e.clientX - lastX;
            let dy = e.clientY - lastY;
            let dist = Math.sqrt(dx * dx + dy * dy);

            if (!isNaN(dist) && dist > 0) {
                totalDistance += dist;

                if (lastMoveTime) {
                    let dt = now - lastMoveTime;
                    if (dt > 0) {
                        let speed = dist / dt;
                        totalSpeed += speed;
                        moveCount++;

                        // 追踪最大停顿
                        if (dt > maxPause) {
                            maxPause = dt;
                        }

                        // 计算加速度 (速度变化) 用于方差统计
                        if (lastSpeed !== null) {
                            let accel = speed - lastSpeed;
                            accelSamples.push(accel);
                            // 限制样本量防止内存泄漏
                            if (accelSamples.length > 500) accelSamples.shift();
                        }
                        lastSpeed = speed;
                    }
                }

                // 计算鼠标移动的方向夹角（弧度）
                let angle = Math.atan2(dy, dx);
                if (lastAngle !== null) {
                    if (Math.abs(angle - lastAngle) > 0.2) {
                        directionChanges++;
                    }
                }
                lastAngle = angle;
            }
        }
        lastX = e.clientX;
        lastY = e.clientY;
        lastMoveTime = now;
    });

    // 键盘事件
    window.addEventListener('keydown', () => { keyCount++; });

    // 点击事件 (仅记录页面内的用户点击)
    window.addEventListener('click', () => { clickCount++; });

    // 滚动事件 (节流，累积计数)
    let scrollThrottle = 0;
    window.addEventListener('scroll', () => {
        let now = Date.now();
        if (now - scrollThrottle > 200) {
            scrollCount++;
            scrollThrottle = now;
        }
    });

    // 加速度方差辅助函数
    function calcAccelVariance() {
        if (accelSamples.length < 2) return 0;
        let mean = accelSamples.reduce((a, b) => a + b, 0) / accelSamples.length;
        let variance = accelSamples.reduce((s, v) => s + (v - mean) * (v - mean), 0) / accelSamples.length;
        return variance;
    }

    // ===================================================================
    // 暴露给投票提交按钮调用的全局核心函数
    // 返回 10 维特征数组：
    //   [dwell_time, total_distance, avg_speed, jitter_rate,
    //    move_count, key_count, click_count, scroll_count,
    //    max_pause, accel_variance]
    // ===================================================================
    window.getBehaviorFeatures = function() {
        let dwellTime = (Date.now() - pageLoadTime) / 1000;
        let finalDistance = totalDistance || 0;
        let avgSpeed = moveCount > 0 ? (totalSpeed / moveCount) : 0;
        let jitterRate = finalDistance > 0 ? (directionChanges / finalDistance) : 0;
        let accelVar = calcAccelVariance();

        return [
            Number(dwellTime) || 0,
            Number(finalDistance) || 0,
            Number(avgSpeed) || 0,
            Number(jitterRate) || 0,
            Number(moveCount) || 0,
            Number(keyCount) || 0,
            Number(clickCount) || 0,
            Number(scrollCount) || 0,
            Number(maxPause) || 0,
            Number(accelVar) || 0
        ];
    };
})();