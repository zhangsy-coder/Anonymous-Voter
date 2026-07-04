const jwt = require('jsonwebtoken');

/**
 * 核心身份验证中间件 (SaaS 多租户架构版)
 * 作用：拦截请求，提取并校验 JWT 令牌。
 * 核心升级：验证通过后，向下游透传的 req.user 中将携带 project_id (租户/项目隔离标识)。
 */
const verifyToken = (req, res, next) => {
    // 1. 从 HTTP 请求头中提取 Authorization 字段
    const authHeader = req.headers['authorization'] || req.headers['Authorization'];

    // 2. 检查头信息是否存在，且格式是否符合 'Bearer <token>' 标准
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({
            success: false,
            message: '访问被拒绝：未提供有效的身份令牌，或请求头格式错误'
        });
    }

    // 3. 截取掉前缀 'Bearer '，提取出纯净的 Token 字符串
    const token = authHeader.split(' ')[1];

    try {
        // 4. 使用 JWT_SECRET 密钥对 Token 进行验签和解析
        // 如果 Token 被伪造、篡改，或超过了 24 小时有效期，此行会直接抛出异常
        const decoded = jwt.verify(token, 'my_super_secret_key_12345');   // ← 和上面保持一致
        // 5. 【多项目架构核心透传】
        // 将解析出来的用户信息挂载到 req 对象上。
        // 此时的 decoded 对象内部包含：{ id, username, role, project_id, iat, exp }
        // 这样一来，下游的所有业务路由（如 vote.js, candidate.js）就能直接通过 req.user.project_id 知道当前操作属于哪个项目。
        req.user = decoded;

        // 6. 身份与防篡改验证全部通过，放行请求，进入真实的后端业务路由
        next();

    } catch (error) {
        // 7. 捕获验证失败的异常（涵盖 Token过期、签名无效等所有情况）
        console.error('JWT 安检拦截异常:', error.message);
        return res.status(401).json({
            success: false,
            message: '身份认证已失效、过期或无权访问，请重新登录'
        });
    }
};

module.exports = verifyToken;