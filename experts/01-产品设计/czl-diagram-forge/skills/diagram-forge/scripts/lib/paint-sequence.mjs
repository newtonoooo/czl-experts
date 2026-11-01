/**
 * paint-sequence.mjs — 时序图布局与绘制
 */

import { measure, textBlock, mix, alpha } from './core.mjs';
import { createScene, rect, text, line, path, labelChip } from './scene.mjs';
import { TS, paintHeader, paintFooter, roleIdx, drawCenteredText } from './paint-common.mjs';

const ROW = 46;
const NOTE_H = 54;

export function paintSequence(model, theme) {
  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  const left = 30;
  const gap = 34;
  const cols = [];
  let cursor = left;
  for (const p of model.participants) {
    const w = Math.max(132, measure(p.label, 13) + 36);
    cols.push({ p, w, cx: cursor + w / 2 });
    cursor += w + gap;
  }
  const totalW = cursor - gap + left;
  const cxOf = new Map(cols.map((c) => [c.p.id, c.cx]));
  const colOf = new Map(cols.map((c) => [c.p.id, c]));

  const top = headerH + 12;
  const boxH = 46;

  // 先测高度，再绘制
  const hSteps = measureSteps(model.steps);
  const bottom = top + boxH + 26 + hSteps + 26;

  // 参与者头
  for (const c of cols) {
    const color = theme.palette[roleIdx(theme, c.p.role)];
    rect(scene, c.cx - c.w / 2, top, c.w, boxH, { r: 8, fill: mix(theme.surface, color, 0.16), stroke: color, sw: 1.6 });
    text(scene, c.cx, top + boxH / 2, c.p.label, {
      size: 13,
      weight: 600,
      fill: theme.fg,
      anchor: 'middle',
      baseline: 'middle',
    });
    if (c.p.kind !== 'service') {
      text(scene, c.cx, top - 8, kindLabel(c.p.kind), { size: 10, fill: theme.muted, anchor: 'middle' });
    }
    line(scene, c.cx, top + boxH, c.cx, bottom, {
      stroke: alpha(theme.line, 0.55),
      sw: 1.2,
      dash: '5 5',
    });
  }

  drawSteps(scene, model, theme, model.steps, top + boxH + 26, cxOf, colOf, left, totalW);

  scene.width = Math.max(totalW, 360);
  scene.height = bottom + paintFooter(scene, model, theme, totalW, bottom - 10) + 10;
  return scene;
}

function kindLabel(k) {
  return { actor: '角色', db: '存储', queue: '消息队列', external: '外部' }[k] || '';
}

function measureSteps(steps) {
  let h = 0;
  for (const s of steps) {
    if (s.type === 'message') h += s.from === s.to ? 58 : ROW;
    else if (s.type === 'note') h += NOTE_H + 8;
    else if (s.type === 'fragment') h += measureSteps(s.steps) + 46;
  }
  return h;
}

function drawSteps(scene, model, theme, steps, y0, cxOf, colOf, left, totalW) {
  let y = y0;
  for (const s of steps) {
    if (s.type === 'message') {
      if (s.from === s.to) {
        y = drawSelfMessage(scene, theme, s, y, cxOf.get(s.from));
      } else {
        y = drawMessage(scene, theme, s, y, cxOf.get(s.from), cxOf.get(s.to));
      }
    } else if (s.type === 'note') {
      y = drawNote(scene, theme, s, y, cxOf, colOf);
    } else if (s.type === 'fragment') {
      const inner = measureSteps(s.steps);
      const top = y + 6;
      const h = inner + 40;
      const fragRight = Math.max(...[...cxOf.values()]) + 30;
      const fragLeft = left - 10;
      rect(scene, fragLeft, top, fragRight - fragLeft, h, {
        r: 8,
        fill: alpha(theme.accent, 0.04),
        stroke: alpha(theme.accent, 0.45),
        sw: 1.2,
        dash: '6 4',
      });
      const tabLabel = `${s.frag}${s.label ? ` [${s.label}]` : ''}`;
      const tw = measure(tabLabel, 11) + 18;
      path(
        scene,
        `M${fragLeft},${top} L${fragLeft + tw},${top} L${fragLeft + tw},${top + 18} L${fragLeft},${top + 24} Z`,
        { fill: alpha(theme.accent, 0.14), stroke: 'none' },
      );
      text(scene, fragLeft + 8, top + 12, tabLabel, { size: 11, weight: 600, fill: theme.accent, baseline: 'middle' });
      drawSteps(scene, model, theme, s.steps, top + 30, cxOf, colOf, left, totalW);
      y = top + h + 6;
    }
  }
  return y;
}

function drawMessage(scene, theme, s, y, x1, x2) {
  const color = s.style === 'return' ? theme.muted : theme.fg;
  const dash = s.style === 'return' ? '6 5' : null;
  const yy = y + 20;
  const dir = x2 > x1 ? 1 : -1;
  const pad = 2;
  path(scene, `M${x1 + dir * pad},${yy} L${x2 - dir * 8},${yy}`, {
    fill: 'none',
    stroke: color,
    sw: s.style === 'async' ? 1.3 : 1.6,
    dash,
    cap: 'round',
  });
  const ax = x2 - dir * 1;
  const head = s.style === 'sync'
    ? [[ax, yy], [ax - dir * 10, yy - 4.6], [ax - dir * 10, yy + 4.6]]
    : null;
  if (head) {
    path(scene, `M${head[0][0]},${head[0][1]} L${head[1][0]},${head[1][1]} L${head[2][0]},${head[2][1]} Z`, {
      fill: color,
      stroke: 'none',
    });
  } else {
    path(scene, `M${ax - dir * 10},${yy - 5} L${ax},${yy} L${ax - dir * 10},${yy + 5}`, {
      fill: 'none',
      stroke: color,
      sw: 1.4,
      cap: 'round',
      join: 'round',
    });
  }
  if (s.text) {
    const mx = (x1 + x2) / 2;
    labelChip(scene, mx, yy - 11, s.text, {
      measure,
      size: TS.edge,
      fill: theme.bg,
      color: theme.muted,
      padX: 5,
      padY: 2,
    });
  }
  return y + ROW;
}

function drawSelfMessage(scene, theme, s, y, x) {
  const yy = y + 18;
  const w = 54;
  const h = 22;
  path(
    scene,
    `M${x},${yy} L${x + w},${yy} L${x + w},${yy + h} L${x + 9},${yy + h}`,
    { fill: 'none', stroke: theme.fg, sw: 1.5, cap: 'round', join: 'round' },
  );
  path(scene, `M${x + 1},${yy + h} L${x + 10},${yy + h - 4.6} L${x + 10},${yy + h + 4.6} Z`, { fill: theme.fg, stroke: 'none' });
  if (s.text) {
    labelChip(scene, x + w / 2, yy - 9, s.text, {
      measure,
      size: TS.edge,
      fill: theme.bg,
      color: theme.muted,
      padX: 5,
      padY: 2,
    });
  }
  return y + 58;
}

function drawNote(scene, theme, s, y, cxOf, colOf) {
  const xs = s.over.map((id) => cxOf.get(id)).filter((v) => v !== undefined);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const w = Math.max(160, maxX - minX + 40);
  const cx = (minX + maxX) / 2;
  const tb = textBlock(s.text, w - 24, 12);
  const h = Math.max(42, tb.height + 22);
  rect(scene, cx - w / 2, y + 4, w, h, {
    r: 5,
    fill: mix(theme.surface, theme.palette[1], 0.16),
    stroke: alpha(theme.palette[1], 0.7),
    sw: 1.1,
  });
  drawCenteredText(scene, cx, y + 4 + h / 2, tb.lines, 12, theme.fg, 400);
  return y + h + 12;
}
