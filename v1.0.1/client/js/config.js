/**
 * ====================================================================
 * 🌐 全局网络通信配置文件 (client/js/config.js)
 * ====================================================================
 * 核心原理：通过浏览器原生 API window.location.hostname 动态获取当前页面所在的宿主 IP 或域名。
 * - 本地开发调试时：自动匹配 '127.0.0.1' 或 'localhost'
 * - 部署至 Ubuntu 上线后：自动匹配云服务器的公网 IP 或具体域名
 * ====================================================================
 */

// 1. 获取当前页面运行所在的宿主主机名（加入保底机制防止特殊老旧浏览器返回空）
const HOST = window.location.hostname || '127.0.0.1';

// 2. 将后台微服务的 API 基准地址暴露给全局 window 对象
window.APP_CONFIG = {
    // Node.js 业务网关默认运行在 3000 端口
    NODE_API: `http://${HOST}:3000`,

    // Python 密码学盲签与区块链存证引擎默认运行在 5000 端口
    PY_API: `http://${HOST}:5000`
};

console.log(`📡 [全局通信配置就绪] 当前网络宿主: ${HOST}`);
console.log(`🔗 Node.js 业务网关映射: ${window.APP_CONFIG.NODE_API}`);
console.log(`🔗 Python 密码学机房映射: ${window.APP_CONFIG.PY_API}`);