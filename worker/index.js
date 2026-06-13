/**
 * Cloudflare Worker: OSS 动态签名 URL 代理 (Token + 可读路径双模式)
 *
 * 收到请求 → 验证 Referer → 用 HMAC-SHA1 生成 10 分钟签名 URL → 返回 302 跳转
 * 视频数据不经过 Worker，直接从 OSS 到浏览器。
 *
 * 部署:
 *   npx wrangler deploy
 *   npx wrangler secret put OSS_ACCESS_KEY_ID
 *   npx wrangler secret put OSS_ACCESS_KEY_SECRET
 *
 * 路径格式:
 *   Token 模式: /v/{16位随机hex}    例: /v/eb4225a4b24b36dd
 *   可读模式:   /v/{model}/{scenario}/{index}  例: /v/ViduQ3/AI漫剧/0
 */

// ============================================================
// Pure JS SHA1 实现 (Cloudflare Workers 的 Web Crypto 不支持 HMAC-SHA1)
// 接受字节数组输入，输出 hex 字符串
// ============================================================

function sha1(input) {
  // Rotate left
  function rotl(n, b) { return (n << b) | (n >>> (32 - b)); }

  // Convert input to byte array (accept string or byte array)
  let m;
  if (typeof input === 'string') {
    // UTF-8 encode
    m = [];
    for (let i = 0; i < input.length; i++) {
      let c = input.charCodeAt(i);
      if (c < 0x80) {
        m.push(c);
      } else if (c < 0x800) {
        m.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
      } else if (c < 0xd800 || c >= 0xe000) {
        m.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
      } else {
        i++;
        c = 0x10000 + (((c & 0x3ff) << 10) | (input.charCodeAt(i) & 0x3ff));
        m.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 0x3f), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
      }
    }
  } else {
    // Already a byte array — copy it
    m = input.slice();
  }

  const ml = m.length * 8; // Message length in bits

  // Pre-processing: padding
  m.push(0x80); // Append '1' bit (as 0x80 byte)
  while ((m.length % 64) !== 56) {
    m.push(0); // Pad with zeros to 56 mod 64
  }

  // Append 64-bit big-endian message length (in bits)
  const hi = Math.floor(ml / 0x100000000); // High 32 bits
  const lo = ml >>> 0;                      // Low 32 bits (unsigned)
  for (let i = 3; i >= 0; i--) m.push((hi >>> (i * 8)) & 0xff);
  for (let i = 3; i >= 0; i--) m.push((lo >>> (i * 8)) & 0xff);

  // Initialize hash values
  let h0 = 0x67452301, h1 = 0xEFCDAB89, h2 = 0x98BADCFE;
  let h3 = 0x10325476, h4 = 0xC3D2E1F0;

  // Process each 512-bit chunk
  for (let chunk = 0; chunk < m.length; chunk += 64) {
    const w = new Array(80);

    // Break chunk into 16 32-bit big-endian words
    for (let i = 0; i < 16; i++) {
      w[i] = (m[chunk + i * 4] << 24) |
             (m[chunk + i * 4 + 1] << 16) |
             (m[chunk + i * 4 + 2] << 8) |
             (m[chunk + i * 4 + 3]);
    }

    // Extend to 80 words
    for (let i = 16; i < 80; i++) {
      w[i] = rotl(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
    }

    let a = h0, b = h1, c = h2, d = h3, e = h4;

    for (let i = 0; i < 80; i++) {
      let f, k;
      if (i < 20) {
        f = (b & c) | (~b & d);
        k = 0x5A827999;
      } else if (i < 40) {
        f = b ^ c ^ d;
        k = 0x6ED9EBA1;
      } else if (i < 60) {
        f = (b & c) | (b & d) | (c & d);
        k = 0x8F1BBCDC;
      } else {
        f = b ^ c ^ d;
        k = 0xCA62C1D6;
      }

      const temp = (rotl(a, 5) + f + e + k + w[i]) >>> 0;
      e = d;
      d = c;
      c = rotl(b, 30);
      b = a;
      a = temp;
    }

    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
  }

  // Convert to hex
  function toHex(v) { return ('0000000' + v.toString(16)).slice(-8); }
  return toHex(h0) + toHex(h1) + toHex(h2) + toHex(h3) + toHex(h4);
}

// ============================================================
// HMAC-SHA1 (纯字节数组操作)
// ============================================================

function hmacSha1(keyStr, messageStr) {
  const blockSize = 64; // SHA1 block size

  // Convert key to byte array
  let keyBytes;
  if (keyStr.length > blockSize) {
    // Hash long keys first
    keyBytes = hexToBytes(sha1(keyStr));
  } else {
    keyBytes = [];
    for (let i = 0; i < keyStr.length; i++) {
      keyBytes.push(keyStr.charCodeAt(i) & 0xff);
    }
  }

  // Pad key to blockSize with zeros
  while (keyBytes.length < blockSize) {
    keyBytes.push(0);
  }

  // XOR key with ipad (0x36) and opad (0x5c)
  const iKeyPad = keyBytes.map(b => b ^ 0x36);
  const oKeyPad = keyBytes.map(b => b ^ 0x5c);

  // Convert message to byte array (like sha1 does internally)
  let msgBytes;
  if (typeof messageStr === 'string') {
    // UTF-8 encode the message
    msgBytes = [];
    for (let i = 0; i < messageStr.length; i++) {
      const c = messageStr.charCodeAt(i);
      if (c < 0x80) {
        msgBytes.push(c);
      } else if (c < 0x800) {
        msgBytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
      } else if (c < 0xd800 || c >= 0xe000) {
        msgBytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
      } else {
        // surrogate pair — shouldn't happen for OSS signing strings
        msgBytes.push(c & 0xff); // fallback
      }
    }
  } else {
    msgBytes = messageStr.slice();
  }

  // Inner hash: SHA1(iKeyPad || message_bytes)
  const innerInput = iKeyPad.concat(msgBytes);
  const innerHash = sha1(innerInput);

  // Outer hash: SHA1(oKeyPad || innerHash_bytes)
  const innerHashBytes = hexToBytes(innerHash);
  const outerInput = oKeyPad.concat(innerHashBytes);
  return sha1(outerInput);
}

function hexToBytes(hex) {
  const bytes = [];
  for (let i = 0; i < hex.length; i += 2) {
    bytes.push(parseInt(hex.substring(i, i + 2), 16));
  }
  return bytes;
}

// ============================================================
// Base64 编码
// ============================================================

function base64Encode(bytes) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let result = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const b1 = bytes[i];
    const b2 = i + 1 < bytes.length ? bytes[i + 1] : 0;
    const b3 = i + 2 < bytes.length ? bytes[i + 2] : 0;
    result += chars.charAt(b1 >> 2);
    result += chars.charAt(((b1 & 3) << 4) | (b2 >> 4));
    result += i + 1 < bytes.length ? chars.charAt(((b2 & 15) << 2) | (b3 >> 6)) : '=';
    result += i + 2 < bytes.length ? chars.charAt(b3 & 63) : '=';
  }
  return result;
}

// ============================================================
// OSS 签名 URL 生成 (V1 签名)
// ============================================================

function generateOssSignedUrl(accessKeyId, accessKeySecret, bucket, endpoint, objectPath, expires) {
  const verb = 'GET';
  const contentMD5 = '';
  const contentType = '';
  const expiresTimestamp = Math.floor(Date.now() / 1000) + expires;

  // Canonicalized OSS headers (none for basic GET)
  const ossHeaders = '';

  // Normalize object path: ensure leading /, no trailing slash
  let normalizedPath = objectPath;
  if (!normalizedPath.startsWith('/')) normalizedPath = '/' + normalizedPath;
  if (normalizedPath.endsWith('/')) normalizedPath = normalizedPath.slice(0, -1);

  // Canonicalized resource: /bucket/object (path NOT URL-encoded for signing)
  const canonicalResource = '/' + bucket + normalizedPath;

  // String to sign (Expires timestamp as Date field for query-string auth)
  // CRITICAL: canonicalized resource includes bucket prefix; ossHeaders + resource
  // are combined into ONE element (no extra \n when ossHeaders is empty)
  const stringToSign = [
    verb,
    contentMD5,
    contentType,
    String(expiresTimestamp),
    ossHeaders + canonicalResource
  ].join('\n');

  // Sign with HMAC-SHA1
  const signatureHex = hmacSha1(accessKeySecret, stringToSign);
  const signatureBytes = hexToBytes(signatureHex);
  const signature = base64Encode(signatureBytes);

  // URL-encode each path segment for the actual URL
  const pathEncoded = normalizedPath.split('/').map(seg => encodeURIComponent(seg)).join('/');

  // Build URL
  const params = new URLSearchParams({
    'OSSAccessKeyId': accessKeyId,
    'Expires': String(expiresTimestamp),
    'Signature': signature
  });

  const url = `https://${bucket}.${endpoint}${pathEncoded}?${params.toString()}`;
  return url;
}

// ============================================================
// OSS Key 映射表 (由 generate_video_map.py --oss-key-map 生成后替换)
// 格式: "model/scenario/index": "96/model_folder/scenario_folder/filename.mp4"
// 实际使用时替换为 import 或直接嵌入
// ============================================================

import ossKeyMapRaw from './oss_key_map.json';
import tokenMapRaw from './token_map.json';

const OSS_KEY_MAP = ossKeyMapRaw;
const TOKEN_MAP = tokenMapRaw;

// ============================================================
// 速率限制 (简单内存实现，每 IP 每分钟 30 次)
// ============================================================

const rateLimitMap = new Map();

function checkRateLimit(ip) {
  const now = Date.now();
  const windowMs = 60 * 1000; // 1 minute window
  const maxRequests = 30;

  // Clean up old entries periodically
  if (rateLimitMap.size > 10000) {
    const cutoff = now - windowMs;
    for (const [key, entry] of rateLimitMap) {
      if (entry.resetAt < now) {
        rateLimitMap.delete(key);
      }
    }
  }

  let entry = rateLimitMap.get(ip);
  if (!entry || entry.resetAt < now) {
    entry = { count: 0, resetAt: now + windowMs };
    rateLimitMap.set(ip, entry);
  }

  entry.count++;
  return entry.count <= maxRequests;
}

// ============================================================
// URL 解析 & 路径匹配 (双模式: token 优先, 可读路径兜底)
// ============================================================

const TOKEN_PATTERN = /^\/v\/([a-f0-9]{16})$/;           // /v/eb4225a4b24b36dd
const READABLE_PATTERN = /^\/v\/(.+)\/(.+)\/(\d+)$/;    // /v/ViduQ3/AI漫剧/0

function resolveOssPath(pathname) {
  // 1. Try token mode
  const tokenMatch = pathname.match(TOKEN_PATTERN);
  if (tokenMatch) {
    const token = tokenMatch[1];
    return TOKEN_MAP[token] || null;
  }

  // 2. Fall back to readable path mode
  const readableMatch = pathname.match(READABLE_PATTERN);
  if (readableMatch) {
    const [, model, scenario, indexStr] = readableMatch;
    const index = parseInt(indexStr, 10);
    if (index >= 0 && index <= 3) {
      const key = `${model}/${scenario}/${index}`;
      return OSS_KEY_MAP[key] || null;
    }
  }

  return null;
}

// ============================================================
// Worker 入口
// ============================================================

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // CORS headers for ALL responses (debug + preflight)
    const corsHeaders = {
      'Access-Control-Allow-Origin': 'https://zzsh0621.github.io',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Max-Age': '86400',
    };

    // Handle OPTIONS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // ---- 1. 解析路由 & 查找 OSS 路径 ----
    const ossPath = resolveOssPath(url.pathname);
    if (!ossPath) {
      return new Response('Not Found', { status: 404, headers: corsHeaders });
    }

    // ---- 2. Referer 校验 ----
    const referer = request.headers.get('Referer') || '';
    const isAllowed = referer.includes('zzsh0621.github.io') || referer.includes('localhost');
    if (!isAllowed) {
      return new Response('Forbidden', { status: 403, headers: corsHeaders });
    }

    // ---- 3. 速率限制 ----
    const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';
    if (!checkRateLimit(clientIP)) {
      return new Response('Too Many Requests', { status: 429, headers: corsHeaders });
    }

    // ---- 5. 获取 OSS 凭证 (Worker Secrets) ----
    // Strip BOM and any non-printable chars that may have leaked into secrets
    const accessKeyId = (env.OSS_ACCESS_KEY_ID || '').replace(/[^A-Za-z0-9]/g, '');
    const accessKeySecret = (env.OSS_ACCESS_KEY_SECRET || '').replace(/[^A-Za-z0-9\/+=]/g, '');
    const bucket = env.OSS_BUCKET || '96vedio';
    const endpoint = env.OSS_ENDPOINT || 'oss-cn-beijing.aliyuncs.com';

    if (!accessKeyId || !accessKeySecret) {
      return new Response('Server Config: OSS keys not set', { status: 500, headers: corsHeaders });
    }

    // ---- 6. 生成签名 URL (10 分钟有效) ----
    const expires = 600; // 10 minutes
    let signedUrl;
    try {
      signedUrl = generateOssSignedUrl(
        accessKeyId, accessKeySecret, bucket, endpoint, ossPath, expires
      );
    } catch (e) {
      return new Response('Signature Error: ' + e.message, { status: 500, headers: corsHeaders });
    }

    // ---- 7. 302 跳转 ----
    return new Response(null, {
      status: 302,
      headers: {
        'Location': signedUrl,
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Access-Control-Allow-Origin': 'https://zzsh0621.github.io'
      }
    });
  }
};
