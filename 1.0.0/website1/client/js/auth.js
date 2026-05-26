/**
 * ============================================================================
 * SaaS 多项目投票系统 - 前端全局公共工具库
 * 包含：全局配置、身份获取、请求拦截器、退出登录逻辑
 * ============================================================================
 */

// 1. 全局配置中心
const CONFIG = {
    // 切换环境只需改这一行：
    // 本地开发填 'http://127.0.0.1:3000/api'
    // 上线云服务器填 'http://你的公网IP:3000/api'
    API_BASE: 'http://127.0.0.1:3000/api'
};

// 2. 身份状态提取工具
// 封装获取本地缓存的方法，方便其他页面直接调用
const AuthUtils = {
    getToken: () => localStorage.getItem('token'),
    getRole: () => localStorage.getItem('role'),
    getProjectId: () => localStorage.getItem('project_id'),
    getUsername: () => localStorage.getItem('username'),

    // 清理所有身份痕迹
    clearAuth: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('project_id');
        localStorage.removeItem('username');
    }
};

// 3. 智能请求拦截器 (Fetch Wrapper)
// 以后所有的发请求都不要直接用 fetch()，改用这个 fetchWithAuth()
async function fetchWithAuth(endpoint, options = {}) {
    const token = AuthUtils.getToken();

    // 自动配置请求头
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    // 如果本地有 Token，自动为每一次请求带上 "通行证"
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    try {
        // 发起真实的网络请求
        const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, {
            ...options,
            headers
        });

        // 【核心拦截逻辑】：如果后端安检中间件返回了 401(未授权) 或 403(禁止访问)
        if (response.status === 401 || response.status === 403) {
            // 解析后端的错误提示信息
            const errorData = await response.json().catch(() => ({}));
            alert(errorData.message || '登录状态异常或已过期，请重新登录！');

            // 强制清理缓存的无效身份
            AuthUtils.clearAuth();

            // 智能计算跳转路径：判断当前页面是在根目录还是在子文件夹(admin/voter)中
            const inSubFolder = window.location.pathname.includes('/admin/') || window.location.pathname.includes('/voter/');
            window.location.href = inSubFolder ? '../index.html' : 'index.html';

            // 抛出错误，强行阻断下游页面的继续渲染
            throw new Error('Auth failed: 身份认证被拦截');
        }

        return response; // 安检通过，正常返回数据

    } catch (error) {
        console.error(`[API 请求错误] ${endpoint}:`, error);
        throw error; // 将普通网络错误继续向上抛出，交给页面自行处理
    }
}

// 4. 全局统一的退出登录动作
function logout() {
    if (confirm('您确定要安全退出当前系统吗？')) {
        AuthUtils.clearAuth();

        // 同样进行智能跳转判定
        const inSubFolder = window.location.pathname.includes('/admin/') || window.location.pathname.includes('/voter/');
        window.location.href = inSubFolder ? '../index.html' : 'index.html';
    }
}