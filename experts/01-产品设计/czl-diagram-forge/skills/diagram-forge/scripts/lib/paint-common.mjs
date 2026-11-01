/**
 * paint-common.mjs — 各类图表共用的绘制辅助：标题区、图例、节点形状、文字排版
 */

import { measure, textBlock, mix, readableOn, alpha } from './core.mjs';
import { rect, text, line, polygon, circle, path, labelChip } from './scene.mjs';

export const TS = { title: 19, subtitle: 12.5, node: 13, small: 11.5, edge: 11.5 };

/** 标题 + 副标题，返回占用高度 */
export function paintHeader(scene, model, theme, opts = {}) {
  const left = opts.left ?? 30;
  let y = opts.top ?? 26;
  let h = 0;
  if (model.title) {
    text(scene, left, y + TS.title, model.title, {
      size: TS.title,
      weight: 700,
      fill: theme.fg,
    });
    y += TS.title + 8;
    h += TS.title + 8;
  }
  if (model.subtitle) {
    text(scene, left, y + TS.subtitle, model.subtitle, { size: TS.subtitle, fill: theme.muted });
    y += TS.subtitle + 6;
    h += TS.subtitle + 6;
  }
  return h ? h + 14 : 0;
}

export function paintFooter(scene, model, theme, width, y) {
  if (!model.footnote) return 0;
  text(scene, 30, y + 14, model.footnote, { size: TS.small, fill: theme.muted });
  return 24;
}

/** 节点形状 */
export function drawShape(scene, x, y, w, h, shape, fill, stroke, sw = 1.6) {
  const base = { fill, stroke, sw };
  switch (shape) {
    case 'round':
      rect(scene, x, y, w, h, { ...base, r: 12 });
      break;
    case 'stadium':
      rect(scene, x, y, w, h, { ...base, r: h / 2 });
      break;
    case 'circle':
      circle(scene, x + w / 2, y + h / 2, Math.min(w, h) / 2, base);
      break;
    case 'diamond':
      polygon(
        scene,
        [
          [x + w / 2, y],
          [x + w, y + h / 2],
          [x + w / 2, y + h],
          [x, y + h / 2],
        ],
        base,
      );
      break;
    case 'hex': {
      const k = Math.min(w * 0.18, 22);
      polygon(
        scene,
        [
          [x + k, y],
          [x + w - k, y],
          [x + w, y + h / 2],
          [x + w - k, y + h],
          [x + k, y + h],
          [x, y + h / 2],
        ],
        base,
      );
      break;
    }
    case 'cylinder': {
      const ry = Math.min(9, h * 0.16);
      path(
        scene,
        `M${x},${y + ry} A${w / 2},${ry} 0 0 1 ${x + w},${y + ry} L${x + w},${y + h - ry} A${w / 2},${ry} 0 0 1 ${x},${y + h - ry} Z`,
        base,
      );
      path(scene, `M${x},${y + ry} A${w / 2},${ry} 0 0 0 ${x + w},${y + ry}`, {
        fill: 'none',
        stroke,
        sw: sw * 0.8,
        opacity: 0.75,
      });
      break;
    }
    case 'parallelogram': {
      const k = Math.min(16, w * 0.14);
      polygon(
        scene,
        [
          [x + k, y],
          [x + w, y],
          [x + w - k, y + h],
          [x, y + h],
        ],
        base,
      );
      break;
    }
    case 'subroutine':
      rect(scene, x, y, w, h, { ...base, r: 3 });
      line(scene, x + 10, y, x + 10, y + h, { stroke, sw: sw * 0.8 });
      line(scene, x + w - 10, y, x + w - 10, y + h, { stroke, sw: sw * 0.8 });
      break;
    case 'note': {
      const k = 13;
      path(
        scene,
        `M${x},${y} L${x + w - k},${y} L${x + w},${y + k} L${x + w},${y + h} L${x},${y + h} Z`,
        base,
      );
      path(scene, `M${x + w - k},${y} L${x + w - k},${y + k} L${x + w},${y + k}`, {
        fill: 'none',
        stroke,
        sw: sw * 0.8,
      });
      break;
    }
    default:
      rect(scene, x, y, w, h, { ...base, r: 6 });
      break;
  }
}

/** 居中对齐的多行文字 */
export function drawCenteredText(scene, cx, cy, lines, size, color, weight = 500, lineHeight = 1.42) {
  const total = lines.length * size * lineHeight;
  let y = cy - total / 2 + size * lineHeight * 0.5 + size * 0.36;
  for (const l of lines) {
    text(scene, cx, y, l, { size, fill: color, anchor: 'middle', weight });
    y += size * lineHeight;
  }
}

/** 节点本体（形状 + 文本） */
export function paintNode(scene, theme, node, box, opt = {}) {
  const color = theme.palette[roleIdx(theme, node.role)];
  const emph = node.emphasis;
  const fill = emph ? color : mix(theme.surface, color, 0.11);
  const textColor = emph ? readableOn(color) : theme.fg;
  const sw = emph ? 2 : 1.5;

  if (opt.shadow) {
    rect(scene, box.x + 1.5, box.y + 2, box.w, box.h, {
      r: 8,
      fill: alpha(theme.fg, 0.05),
      stroke: 'none',
    });
  }
  drawShape(scene, box.x, box.y, box.w, box.h, node.shape, fill, color, sw);

  const maxW = box.w - (node.shape === 'diamond' ? box.w * 0.34 : 26);
  const tb = textBlock(node.label, Math.max(48, maxW), opt.size || TS.node);
  drawCenteredText(scene, box.x + box.w / 2, box.y + box.h / 2, tb.lines, opt.size || TS.node, textColor, opt.weight || 500);

  if (node.note) {
    text(scene, box.x + box.w / 2, box.y + box.h + 14, node.note, {
      size: TS.small,
      fill: theme.muted,
      anchor: 'middle',
    });
  }
}

export function roleIdx(theme, role) {
  const order = ['primary', 'decision', 'data', 'external', 'success', 'danger', 'neutral'];
  const i = order.indexOf(role);
  return (i < 0 ? 0 : i) % theme.palette.length;
}

/** 分组框 */
export function paintGroup(scene, theme, box) {
  rect(scene, box.x, box.y, box.w, box.h, {
    r: 10,
    fill: alpha(theme.accent, 0.045),
    stroke: alpha(theme.accent, 0.42),
    sw: 1.2,
    dash: '5 4',
  });
  if (box.label) {
    const w = measure(box.label, TS.small) + 14;
    rect(scene, box.x + 12, box.y - 9, w, 18, { r: 9, fill: theme.surface, stroke: alpha(theme.accent, 0.42), sw: 1 });
    text(scene, box.x + 12 + w / 2, box.y + 1, box.label, {
      size: TS.small,
      fill: theme.accent,
      anchor: 'middle',
      baseline: 'middle',
      weight: 600,
    });
  }
}

/** 图例 */
export function paintLegend(scene, theme, items, x, y, opt = {}) {
  const size = TS.small;
  const gap = 16;
  let cx = x;
  for (const it of items) {
    const color = it.color;
    rect(scene, cx, y - 8, 10, 10, { r: 3, fill: mix(theme.surface, color, 0.2), stroke: color, sw: 1.2 });
    text(scene, cx + 15, y, it.label, { size, fill: theme.muted });
    cx += 15 + measure(it.label, size) + gap;
  }
  return cx - x;
}
