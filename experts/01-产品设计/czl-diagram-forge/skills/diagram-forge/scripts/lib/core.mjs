/**
 * core.mjs — 基础工具：文字度量、换行、颜色与数值处理
 *
 * 本模块不依赖任何第三方库。所有度量均为解析式估算，
 * 目的是让自研布局引擎在无浏览器环境下也能得到稳定的排版结果。
 */

export const FONT_STACK =
  '"Inter","Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif';

const CJK_RE = /[\u1100-\u11FF\u2E80-\uA4CF\uA960-\uA97F\uAC00-\uD7FF\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFF60\uFFE0-\uFFE6]/;

export function isWide(ch) {
  return CJK_RE.test(ch);
}

/** 估算单行文本像素宽度 */
export function measure(text, size) {
  let w = 0;
  for (const ch of String(text)) {
    if (ch === ' ') w += 0.30;
    else if (isWide(ch)) w += 1.0;
    else if (/[A-Z]/.test(ch)) w += 0.64;
    else if (/[a-z]/.test(ch)) w += 0.53;
    else if (/[0-9]/.test(ch)) w += 0.56;
    else if (/[.,:;'!|]/.test(ch)) w += 0.28;
    else if (/[()[\]{}]/.test(ch)) w += 0.34;
    else w += 0.58;
  }
  return w * size;
}

/**
 * 按最大宽度换行。中文按字断行，西文按词断行，超长词强制截断。
 * 返回行数组（不含 \n）。
 */
export function wrap(text, maxWidth, size) {
  const out = [];
  for (const para of String(text).split('\n')) {
    if (para === '') {
      out.push('');
      continue;
    }
    if (measure(para, size) <= maxWidth) {
      out.push(para);
      continue;
    }
    const tokens = [];
    let buf = '';
    for (const ch of para) {
      if (isWide(ch) || ch === ' ') {
        if (buf) {
          tokens.push(buf);
          buf = '';
        }
        tokens.push(ch);
      } else {
        buf += ch;
      }
    }
    if (buf) tokens.push(buf);

    let line = '';
    for (const tk of tokens) {
      const next = line + tk;
      if (line && measure(next, size) > maxWidth) {
        out.push(line.trimEnd());
        line = tk === ' ' ? '' : tk;
      } else if (!line && measure(tk, size) > maxWidth) {
        // 超长 token 强制按字符切
        let cur = '';
        for (const ch of tk) {
          if (cur && measure(cur + ch, size) > maxWidth) {
            out.push(cur);
            cur = ch;
          } else cur += ch;
        }
        line = cur;
      } else {
        line = next;
      }
    }
    if (line.trim() !== '' || out.length === 0) out.push(line.trimEnd());
  }
  return out;
}

export function textBlock(text, maxWidth, size, lineHeight = 1.42) {
  const lines = wrap(text, maxWidth, size);
  return { lines, width: Math.max(...lines.map((l) => measure(l, size)), 0), height: lines.length * size * lineHeight };
}

/** 把 #rrggbb 与透明度混合，输出 rgba() */
export function alpha(hex, a) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

export function mix(hexA, hexB, t) {
  const pa = parseHex(hexA);
  const pb = parseHex(hexB);
  const c = (a, b) => Math.round(a + (b - a) * t).toString(16).padStart(2, '0');
  return `#${c(pa[0], pb[0])}${c(pa[1], pb[1])}${c(pa[2], pb[2])}`;
}

function parseHex(hex) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)];
}

/** 依据背景亮度自动选择可读的前景色 */
export function readableOn(bg) {
  const [r, g, b] = parseHex(bg);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.6 ? '#1a1d21' : '#ffffff';
}

export function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v));
}

export function fmt(n) {
  const r = Math.round(n * 100) / 100;
  return Object.is(r, -0) ? '0' : String(r);
}

export function xmlEscape(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
