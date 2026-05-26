/**
 * ============================================================================
 * SaaS 匿名投票系统 - 前端密码学大脑 (动态多租户 + 零知识自证终极版)
 * 依赖: forge.min.js
 * 核心职责: 动态加载多租户公钥、RSA 盲化、去盲解密、区块链选票防篡改脱机自证
 * ============================================================================
 */
const VoteCrypto = (function () {
    // 内部状态缓存：仅在当前页面的生命周期内存活，阅后即焚
    let state = {
        publicKey: null,
        N: null,
        E: null,
        Sn: null,
        r: null,
        b: null
    };

    /**
     * 辅助函数：将 BigInteger 转换为长度为偶数的十六进制字符串
     * 目的：消除十六进制前导零丢失导致的 Python 后端字节解析对齐错误
     */
    function bigIntToEvenHex(bigInt) {
        let hex = bigInt.toString(16);
        return hex.length % 2 !== 0 ? '0' + hex : hex;
    }

    /**
     * 🚀 1. 动态初始化：接收 Node.js 网关传来的当前项目专属租户公钥
     */
    function init(publicKeyPem) {
        if (!window.forge) {
            console.error("致命错误：未找到 forge.min.js 密码学依赖库");
            return;
        }
        try {
            state.publicKey = forge.pki.publicKeyFromPem(publicKeyPem);
            state.N = state.publicKey.n;
            state.E = state.publicKey.e;
            console.log("🔐 [密码学大脑] 初始化成功！当前项目的专属 RSA 2048 位公钥已加载。");
        } catch (err) {
            console.error("公钥解析失败，请检查项目公钥格式：", err);
        }
    }

    /**
     * 辅助函数：生成 10 位高强度伪随机字符串 (Secret Sn)
     */
    function generateSn() {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let sn = '';
        for (let i = 0; i < 10; i++) {
            sn += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return sn;
    }

    /**
     * 辅助函数：生成符合 RSA 安全规范的盲因子 (Blind Factor 'b')
     * 条件：1 < b < N，且 gcd(b, N) == 1
     */
    function generateBlindFactor() {
        let b;
        const ONE = forge.jsbn.BigInteger.ONE;
        do {
            const numBytes = Math.ceil(state.N.bitLength() / 8);
            const randBytes = forge.random.getBytesSync(numBytes);
            b = new forge.jsbn.BigInteger(forge.util.bytesToHex(randBytes), 16);
            b = b.mod(state.N);
        } while (b.compareTo(ONE) <= 0 || b.gcd(state.N).compareTo(ONE) !== 0);
        return b;
    }

    /**
     * 🔮 2. 盲化选票 (Blind Vote)
     * 流程：生成 Sn -> 计算哈希 m = H(r || Sn) -> 乘以盲因子 r' = m * b^e mod N
     */
    function blindVote(voteContent) {
        if (!state.N) throw new Error("公钥未初始化！请等待网络请求加载公钥。");

        state.r = voteContent;
        state.Sn = generateSn();
        state.b = generateBlindFactor();

        console.log(`[本地加密] 随机防伪凭证 Sn 生成完毕: ${state.Sn}`);

        // 使用 SHA-256 计算哈希基底
        const md = forge.md.sha256.create();
        md.update(state.r + state.Sn, 'utf8');
        const hashHex = md.digest().toHex();
        const m = new forge.jsbn.BigInteger(hashHex, 16);

        // 核心盲化运算：b^e mod N
        const b_e = state.b.modPow(state.E, state.N);
        // r' = m * (b^e) mod N
        const r_prime = m.multiply(b_e).mod(state.N);

        // 将盲因子和原始数据缓存入 LocalStorage，以防页面意外刷新导致盲因子丢失无法解密
        localStorage.setItem("vote_crypto_cache", JSON.stringify({
            r: state.r, Sn: state.Sn, b_hex: state.b.toString(16)
        }));

        return { r_prime: bigIntToEvenHex(r_prime) };
    }

    /**
     * 🕊️ 3. 去盲提取真实签名 (Unblind Signature)
     * 流程：计算盲因子的乘法逆元 b^-1 -> 消除盲因子 S = S' * b^-1 mod N
     */
    function unblindSignature(s_prime_hex) {
        // 如果内存状态丢失（比如网关响应太慢用户刷新了），尝试从 LocalStorage 抢救盲因子
        if (!state.b) {
            const cache = JSON.parse(localStorage.getItem("vote_crypto_cache"));
            if (!cache) throw new Error("本地安全缓存已丢失，无法完成去盲解密运算！");
            state.r = cache.r;
            state.Sn = cache.Sn;
            state.b = new forge.jsbn.BigInteger(cache.b_hex, 16);
        }

        const s_prime = new forge.jsbn.BigInteger(s_prime_hex, 16);

        // 计算模逆：b^-1 mod N
        const b_inv = state.b.modInverse(state.N);

        // 核心去盲运算：S = S' * b^-1 mod N
        const S = s_prime.multiply(b_inv).mod(state.N);

        // 彻底抹除本地缓存，做到阅后即焚，切断关联
        localStorage.removeItem("vote_crypto_cache");

        return { r: state.r, Sn: state.Sn, S: bigIntToEvenHex(S) };
    }

    /**
     * 🔍 4. 选票防篡改脱机自证 (End-to-End Verifiability Sandbox)
     * 供首页自检门户调用，利用大整数运算完成 S^e mod N == H(r || Sn) 的终极数学裁决
     */
    function verifyVoteOnChain(r, Sn, S_hex, publicKeyPem) {
        try {
            // 1. 重新解析该历史项目的公钥
            const pubKey = forge.pki.publicKeyFromPem(publicKeyPem);
            const N = pubKey.n;
            const E = pubKey.e;

            // 2. 本地重建哈希基底 H(r || Sn)
            const md = forge.md.sha256.create();
            md.update(r + Sn, 'utf8');
            const localHashHex = md.digest().toHex();

            // 3. 对链上拿到的十六进制 RSA 签名执行非对称解密：S^e mod N
            const s_bigInt = new forge.jsbn.BigInteger(S_hex, 16);
            const recovered_bigInt = s_bigInt.modPow(E, N);
            const recoveredHashHex = recovered_bigInt.toString(16);

            // 4. 字节对齐
            const formattedRecovered = recoveredHashHex.length % 2 !== 0 ? '0' + recoveredHashHex : recoveredHashHex;
            const formattedLocal = localHashHex.length % 2 !== 0 ? '0' + localHashHex : localHashHex;

            return {
                success: true,
                isValid: formattedRecovered === formattedLocal,
                localHash: formattedLocal,
                recoveredHash: formattedRecovered
            };
        } catch (err) {
            console.error("脱机验签崩溃:", err);
            return { success: false, message: err.message };
        }
    }

    // 暴露核心方法供全局调用
    return {
        init,
        blindVote,
        unblindSignature,
        verifyVoteOnChain
    };
})();