/**
 * ============================================================================
 * SaaS 多项目投票系统 - 前端全局公共工具库
 * 包含：全局配置、身份获取、请求拦截器、退出登录逻辑
 * ============================================================================
 */

// 1. 全局配置中心
const CONFIG = {
    API_BASE: `${window.APP_CONFIG.NODE_API}/api`
};

// 2. 身份状态提取工具
const AuthUtils = {
    getToken: () => localStorage.getItem('token'),
    getRole: () => localStorage.getItem('role'),
    getProjectId: () => localStorage.getItem('project_id'),
    getUsername: () => localStorage.getItem('username'),
    getIsDuress: () => localStorage.getItem('is_duress') === 'true',   // 🆕

    clearAuth: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('project_id');
        localStorage.removeItem('username');
        localStorage.removeItem('is_duress');   // 🆕
    }
};

// 3. 智能请求拦截器
async function fetchWithAuth(endpoint, options = {}) {
    const token = AuthUtils.getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    try {
        const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, { ...options, headers });
        if (response.status === 401 || response.status === 403) {
            const errorData = await response.json().catch(() => ({}));
            alert(errorData.message || '登录状态异常或已过期，请重新登录！');
            AuthUtils.clearAuth();
            const inSubFolder = window.location.pathname.includes('/admin/') || window.location.pathname.includes('/voter/');
            window.location.href = inSubFolder ? '../index.html' : 'index.html';
            throw new Error('Auth failed: 身份认证被拦截');
        }
        return response;
    } catch (error) {
        console.error(`[API 请求错误] ${endpoint}:`, error);
        throw error;
    }
}

// 4. 全局统一的退出登录动作
function logout() {
    if (confirm('您确定要安全退出当前系统吗？')) {
        AuthUtils.clearAuth();
        const inSubFolder = window.location.pathname.includes('/admin/') || window.location.pathname.includes('/voter/');
        window.location.href = inSubFolder ? '../index.html' : 'index.html';
    }
}