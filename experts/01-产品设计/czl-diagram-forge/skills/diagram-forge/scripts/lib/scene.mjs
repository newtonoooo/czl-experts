/**
 * scene.mjs — 场景图（Scene）构造工具
 *
 * 布局层只产出「绘制指令」数组，序列化层负责转成 SVG / HTML / ASCII。
 * 这样换输出格式不需要重写任何布局代码。
 */

import { xmlEscape, fmt } from './core.mjs';

export function createScene(width, height) {
  return { width, height, items: [] };
}

/* --------------------------------- 基础图元 -------------------------------- */

export function rect(scene, x, y, w, h, opt = {}) {
  scene.items.push({ t: 'rect', x, y, w, h, ...opt });
}

export function text(scene, x, y, s, opt = {}) {
  if (s === undefined || s === null || s === '') return;
  scene.items.push({ t: 'text', x, y, s: String(s), ...opt });
}

export function line(scene, x1, y1, x2, y2, opt = {}) {
  scene.items.push({ t: 'line', x1, y1, x2, y2, ...opt });
}

export function path(scene, d, opt = {}) {
  scene.items.push({ t: 'path', d, ...opt });
}

export function polygon(scene, pts, opt = {}) {
  scene.items.push({ t: 'polygon', pts, ...opt });
}

export function circle(scene, cx, cy, r, opt = {}) {
  scene.items.push({ t: 'circle', cx, cy, r, ...opt });
}

export function arc(scene, cx, cy, r, a0, a1, opt = {}) {
  // a0/a1 为弧度，0 指向 12 点方向，顺时针
  const p = (a) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a1);
  const large = Math.abs(a1 - a0) > Math.PI ? 1 : 0;
  const sweep = a1 > a0 ? 1 : 0;
  const d = `M${fmt(cx)},${fmt(cy)} L${fmt(x0)},${fmt(y0)} A${fmt(r)},${fmt(r)} 0 ${large} ${sweep} ${fmt(x1)},${fmt(y1)} Z`;
  path(scene, d, opt);
}

/* --------------------------------- 箭头与连线 ------------------------------- */

function arrowHead(scene, x, y, angle, size, color, open = false) {
  const a = size;
  const w = size * 0.46;
  const bx = x - a * Math.cos(angle);
  const by = y - a * Math.sin(angle);
  const p1 = [bx + w * Math.sin(angle), by - w * Math.cos(angle)];
  const p2 = [bx - w * Math.sin(angle), by + w * Math.cos(angle)];
  if (open) {
    path(scene, `M${fmt(p1[0])},${fmt(p1[1])} L${fmt(x)},${fmt(y)} L${fmt(p2[0])},${fmt(p2[1])}`, {
      fill: 'none',
      stroke: color,
      sw: 1.6,
      cap: 'round',
      join: 'round',
    });
  } else {
    polygon(scene, [[x, y], p1, p2], { fill: color, stroke: color, sw: 0.5 });
  }
}

/** 折线路径，pts 为 [[x,y],...]；可选两端箭头 */
export function edge(scene, pts, opt = {}) {
  const { stroke = '#888', sw = 1.5, dash = null, arrowEnd = 'end', arrowStart = 'none', size = 9 } = opt;
  if (pts.length < 2) return;
  const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${fmt(p[0])},${fmt(p[1])}`).join(' ');
  path(scene, d, { fill: 'none', stroke, sw, dash, cap: 'round', join: 'round' });

  if (arrowEnd !== 'none') {
    const [x0, y0] = pts[pts.length - 2];
    const [x1, y1] = pts[pts.length - 1];
    arrowHead(scene, x1, y1, Math.atan2(y1 - y0, x1 - x0), size, stroke, arrowEnd === 'open');
  }
  if (arrowStart !== 'none') {
    const [x0, y0] = pts[0];
    const [x1, y1] = pts[1];
    arrowHead(scene, x0, y0, Math.atan2(y0 - y1, x0 - x1), size, stroke, arrowStart === 'open');
  }
}

/** 曲线路径（贝塞尔） */
export function curve(scene, p0, p1, p2, p3, opt = {}) {
  const { stroke = '#888', sw = 1.5, dash = null } = opt;
  path(scene, `M${fmt(p0[0])},${fmt(p0[1])} C${fmt(p1[0])},${fmt(p1[1])} ${fmt(p2[0])},${fmt(p2[1])} ${fmt(p3[0])},${fmt(p3[1])}`, {
    fill: 'none',
    stroke,
    sw,
    dash,
    cap: 'round',
  });
}

/* --------------------------------- 复合图元 -------------------------------- */

/** 带文字的标签底板，返回占位尺寸 */
export function labelChip(scene, cx, cy, s, opt = {}) {
  const { size = 12, padX = 6, padY = 3, fill = '#fff', stroke = 'none', color = '#333', measure } = opt;
  if (!measure) throw new Error('labelChip 需要 measure 函数');
  const w = measure(s, size) + padX * 2;
  const h = size * 1.35 + padY * 2;
  rect(scene, cx - w / 2, cy - h / 2, w, h, { r: h / 2, fill, stroke, sw: 1, opacity: opt.opacity });
  text(scene, cx, cy, s, { size, fill: color, anchor: 'middle', baseline: 'middle', weight: opt.weight || 500 });
  return { w, h };
}

/* --------------------------------- 序列化 ---------------------------------- */

const ANCHOR = { start: 'start', middle: 'middle', end: 'end' };
const BASELINE = { middle: 'central', top: 'hanging', bottom: 'auto', alphabetic: 'auto' };

function attrs(obj) {
  return Object.entries(obj)
    .filter(([, v]) => v !== undefined && v !== null && v !== false)
    .map(([k, v]) => `${k}="${typeof v === 'number' ? fmt(v) : xmlEscape(v)}"`)
    .join(' ');
}

export function sceneToSvg(scene, opt = {}) {
  const { background = null, fontFamily, padding = 0, title = '', idPrefix = 'dg' } = opt;
  const W = Math.ceil(scene.width + padding * 2);
  const H = Math.ceil(scene.height + padding * 2);
  const out = [];
  out.push(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${xmlEscape(
      title || 'diagram',
    )}" font-family='${fontFamily}'>`,
  );
  if (title) out.push(`<title>${xmlEscape(title)}</title>`);
  if (background) out.push(`<rect x="0" y="0" width="${W}" height="${H}" fill="${background}"/>`);
  out.push(`<g transform="translate(${fmt(padding)},${fmt(padding)})" id="${idPrefix}-root">`);

  for (const it of scene.items) {
    switch (it.t) {
      case 'rect': {
        const r = it.r ? Math.min(it.r, it.w / 2, it.h / 2) : 0;
        out.push(
          `<rect ${attrs({
            x: it.x,
            y: it.y,
            width: Math.max(0, it.w),
            height: Math.max(0, it.h),
            rx: r || undefined,
            fill: it.fill || 'none',
            stroke: it.stroke && it.stroke !== 'none' ? it.stroke : undefined,
            'stroke-width': it.stroke && it.stroke !== 'none' ? it.sw ?? 1 : undefined,
            'stroke-dasharray': it.dash || undefined,
            opacity: it.opacity ?? undefined,
          })}/>`,
        );
        break;
      }
      case 'text': {
        out.push(
          `<text ${attrs({
            x: it.x,
            y: it.y,
            'font-size': it.size || 13,
            'font-weight': it.weight || 400,
            fill: it.fill || '#222',
            'text-anchor': ANCHOR[it.anchor || 'start'],
            'dominant-baseline': BASELINE[it.baseline || 'alphabetic'],
            'letter-spacing': it.ls || undefined,
            opacity: it.opacity ?? undefined,
          })}>${xmlEscape(it.s)}</text>`,
        );
        break;
      }
      case 'line':
        out.push(
          `<line ${attrs({
            x1: it.x1,
            y1: it.y1,
            x2: it.x2,
            y2: it.y2,
            stroke: it.stroke || '#888',
            'stroke-width': it.sw ?? 1,
            'stroke-dasharray': it.dash || undefined,
            'stroke-linecap': 'round',
            opacity: it.opacity ?? undefined,
          })}/>`,
        );
        break;
      case 'path':
        out.push(
          `<path ${attrs({
            d: it.d,
            fill: it.fill || 'none',
            stroke: it.stroke && it.stroke !== 'none' ? it.stroke : undefined,
            'stroke-width': it.stroke && it.stroke !== 'none' ? it.sw ?? 1 : undefined,
            'stroke-dasharray': it.dash || undefined,
            'stroke-linecap': it.cap || undefined,
            'stroke-linejoin': it.join || undefined,
            opacity: it.opacity ?? undefined,
          })}/>`,
        );
        break;
      case 'polygon':
        out.push(
          `<polygon ${attrs({
            points: it.pts.map((p) => `${fmt(p[0])},${fmt(p[1])}`).join(' '),
            fill: it.fill || 'none',
            stroke: it.stroke && it.stroke !== 'none' ? it.stroke : undefined,
            'stroke-width': it.stroke && it.stroke !== 'none' ? it.sw ?? 1 : undefined,
            opacity: it.opacity ?? undefined,
          })}/>`,
        );
        break;
      case 'circle':
        out.push(
          `<circle ${attrs({
            cx: it.cx,
            cy: it.cy,
            r: Math.max(0, it.r),
            fill: it.fill || 'none',
            stroke: it.stroke && it.stroke !== 'none' ? it.stroke : undefined,
            'stroke-width': it.stroke && it.stroke !== 'none' ? it.sw ?? 1 : undefined,
            opacity: it.opacity ?? undefined,
          })}/>`,
        );
        break;
      default:
        break;
    }
  }

  out.push('</g>');
  out.push('</svg>');
  return out.join('\n');
}
