/**
 * paint-data.mjs — 甘特图 / 思维导图 / 时间轴 / 饼图 / 四象限 / 柱线图
 */

import { measure, textBlock, mix, alpha, clamp, fmt } from './core.mjs';
import { createScene, rect, text, line, path, polygon, circle, arc, curve, labelChip } from './scene.mjs';
import { TS, paintHeader, paintFooter, paintLegend, drawCenteredText } from './paint-common.mjs';

/* --------------------------------- 甘特图 --------------------------------- */

const DAY = 86400000;

function fmtDate(ms) {
  const d = new Date(ms);
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
}

export function paintGantt(model, theme) {
  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  const tasks = model.tasks;
  const maxEnd = Math.max(1, ...tasks.map((t) => t.offset + Math.max(1, t.duration)));
  const nameW = Math.max(160, Math.min(260, Math.max(...tasks.map((t) => measure(t.name, 12.5))) + 30));
  const left = 30;
  const timelineW = clamp(maxEnd * 34, 420, 980);
  const dayW = timelineW / maxEnd;
  const axisY = headerH + 30;
  const rowH = 30;
  const sectionH = 26;

  let y = axisY + 14;

  // 时间刻度
  const tickStep = maxEnd <= 14 ? 1 : maxEnd <= 40 ? 5 : maxEnd <= 120 ? 10 : 30;
  for (let d = 0; d <= maxEnd; d += tickStep) {
    const x = left + nameW + d * dayW;
    line(scene, x, axisY + 6, x, axisY + 12, { stroke: theme.line, sw: 1 });
    const lbl = model.ganttOrigin ? fmtDate(model.ganttOrigin + d * DAY) : `D${d}`;
    text(scene, x, axisY, lbl, { size: 10.5, fill: theme.muted, anchor: 'middle' });
    line(scene, x, y - 8, x, y + 8, { stroke: alpha(theme.line, 0.25), sw: 1 });
  }
  line(scene, left, axisY + 6, left + nameW + timelineW, axisY + 6, { stroke: theme.line, sw: 1.2 });

  let sIdx = 0;
  let rowIdx = 0;
  for (const sec of model.sections) {
    if (sec.name) {
      text(scene, left, y + sectionH - 10, sec.name, { size: 11.5, weight: 700, fill: theme.muted });
      y += sectionH;
    }
    const color = theme.palette[sIdx % theme.palette.length];
    for (const t of sec.tasks) {
      const barX = left + nameW + t.offset * dayW;
      const barW = Math.max(t.milestone ? 0 : 6, t.duration * dayW);
      const cy = y + rowH / 2;

      if (rowIdx % 2 === 1) {
        rect(scene, left, y, nameW + timelineW, rowH, { fill: alpha(theme.fg, 0.022), stroke: 'none' });
      }
      rowIdx += 1;
      text(scene, left + 4, cy + 4, t.name, { size: 12.5, fill: theme.fg, weight: t.critical ? 600 : 400 });
      if (t.owner) {
        text(scene, left + nameW - 8, cy + 4, t.owner, { size: 10.5, fill: theme.muted, anchor: 'end' });
      }

      if (t.milestone) {
        polygon(
          scene,
          [
            [barX, cy - 8],
            [barX + 8, cy],
            [barX, cy + 8],
            [barX - 8, cy],
          ],
          { fill: t.critical ? theme.palette[5] : color, stroke: theme.bg, sw: 1.5 },
        );
      } else {
        rect(scene, barX, cy - 8, barW, 16, {
          r: 4,
          fill: t.critical ? alpha(theme.palette[5], 0.85) : alpha(color, 0.8),
          stroke: 'none',
        });
        if (barW > 46) {
          text(scene, barX + barW - 6, cy + 4, `${t.duration}d`, { size: 10, fill: '#ffffff', anchor: 'end', weight: 600 });
        }
      }
      y += rowH;
    }
    sIdx += 1;
  }

  scene.width = left * 2 + nameW + timelineW;
  scene.height = y + paintFooter(scene, model, theme, scene.width, y) + 12;
  return scene;
}

/* -------------------------------- 思维导图 -------------------------------- */

export function paintMindmap(model, theme) {
  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  const NODE_PAD_X = 16;
  const NODE_H = 34;
  const GAP_Y = 12;
  const GAP_X = 54;

  // 计算每层最大宽度
  const levelW = [];
  const walkLevels = (n, d) => {
    const w = measure(n.label, d === 0 ? 15 : 13) + NODE_PAD_X * 2;
    levelW[d] = Math.max(levelW[d] || 0, w);
    n.children.forEach((c) => walkLevels(c, d + 1));
  };
  walkLevels(model.root, 0);

  const levelX = [];
  let acc = 30;
  for (let d = 0; d < levelW.length; d += 1) {
    levelX[d] = acc;
    acc += (levelW[d] || 120) + GAP_X;
  }

  const nodes = [];
  let cursorY = headerH + 20;
  const layout = (n, d) => {
    const w = measure(n.label, d === 0 ? 15 : 13) + NODE_PAD_X * 2;
    const h = d === 0 ? 42 : NODE_H;
    const childYs = [];
    for (const c of n.children) childYs.push(layout(c, d + 1));
    let cy;
    if (childYs.length === 0) {
      cy = cursorY + h / 2;
      cursorY += h + GAP_Y;
    } else {
      cy = (childYs[0] + childYs[childYs.length - 1]) / 2;
    }
    nodes.push({ n, d, x: levelX[d], y: cy - h / 2, w, h, cy });
    return cy;
  };
  layout(model.root, 0);

  const byNode = new Map(nodes.map((x) => [x.n, x]));

  // 连线
  for (const item of nodes) {
    for (const c of item.n.children) {
      const ci = byNode.get(c);
      if (!ci) continue;
      const x0 = item.x + item.w;
      const y0 = item.cy;
      const x1 = ci.x;
      const y1 = ci.cy;
      const mx = (x0 + x1) / 2;
      curve(scene, [x0, y0], [mx, y0], [mx, y1], [x1, y1], {
        stroke: alpha(theme.line, 0.8),
        sw: Math.max(1.1, 2.4 - ci.d * 0.45),
      });
    }
  }

  for (const item of nodes) {
    const color = theme.palette[item.d % theme.palette.length];
    const isRoot = item.d === 0;
    rect(scene, item.x, item.y, item.w, item.h, {
      r: isRoot ? 10 : 17,
      fill: isRoot ? color : mix(theme.surface, color, 0.14),
      stroke: isRoot ? color : alpha(color, 0.75),
      sw: 1.4,
    });
    text(scene, item.x + item.w / 2, item.cy, item.n.label, {
      size: isRoot ? 15 : 13,
      weight: isRoot ? 700 : item.d === 1 ? 600 : 400,
      fill: isRoot ? '#ffffff' : theme.fg,
      anchor: 'middle',
      baseline: 'middle',
    });
    if (item.n.note) {
      text(scene, item.x + item.w + 8, item.cy + 4, item.n.note, { size: 10.5, fill: theme.muted });
    }
  }

  const maxRight = Math.max(...nodes.map((n) => n.x + n.w));
  scene.width = Math.max(maxRight + 40, 360);
  scene.height = cursorY + 16;
  return scene;
}

/* --------------------------------- 时间轴 --------------------------------- */

export function paintTimeline(model, theme) {
  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  const n = model.events.length;
  const CARD_W = clamp(1000 / Math.max(3, n) - 24, 150, 240);
  const colW = CARD_W + 26;
  const left = 34;
  const axisY = headerH + 150;

  const width = Math.max(left * 2 + colW * n, 480);

  line(scene, left - 8, axisY, left + colW * n - 12, axisY, { stroke: alpha(theme.line, 0.7), sw: 1.6 });

  model.events.forEach((e, i) => {
    const cx = left + colW * i + CARD_W / 2;
    const up = i % 2 === 0;
    const color = theme.palette[i % theme.palette.length];

    circle(scene, cx, axisY, 6.5, { fill: theme.bg, stroke: color, sw: 2.2 });
    circle(scene, cx, axisY, 2.4, { fill: color, stroke: 'none' });

    const cardH = 74;
    const cardY = up ? axisY - 24 - cardH : axisY + 24;
    line(scene, cx, up ? axisY - 7 : axisY + 7, cx, up ? cardY + cardH : cardY, {
      stroke: alpha(color, 0.6),
      sw: 1.2,
      dash: '3 3',
    });

    rect(scene, cx - CARD_W / 2, cardY, CARD_W, cardH, {
      r: 8,
      fill: mix(theme.surface, color, 0.08),
      stroke: alpha(color, 0.55),
      sw: 1.2,
    });
    rect(scene, cx - CARD_W / 2, cardY, 3.5, cardH, { r: 2, fill: color, stroke: 'none' });
    if (e.date) {
      text(scene, cx - CARD_W / 2 + 12, cardY + 18, e.date, { size: 10.5, weight: 700, fill: color });
    }
    const tb = textBlock(e.label, CARD_W - 26, 12.5);
    let ty = cardY + (e.date ? 34 : 22);
    for (const l of tb.lines.slice(0, 2)) {
      text(scene, cx - CARD_W / 2 + 12, ty, l, { size: 12.5, weight: 500, fill: theme.fg });
      ty += 17;
    }
    if (e.detail) {
      const dt = textBlock(e.detail, CARD_W - 26, 10.5);
      for (const l of dt.lines.slice(0, 2)) {
        text(scene, cx - CARD_W / 2 + 12, ty, l, { size: 10.5, fill: theme.muted });
        ty += 14;
      }
    }
  });

  scene.width = width;
  scene.height = axisY + 24 + 74 + 26;
  return scene;
}

/* ---------------------------------- 饼图 ---------------------------------- */

export function paintPie(model, theme) {
  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  const total = model.slices.reduce((a, b) => a + b.value, 0);
  const R = 108;
  const cx = 30 + R + 10;
  const cy = headerH + 20 + R + 10;
  let a = 0;

  model.slices.forEach((s, i) => {
    const color = theme.palette[i % theme.palette.length];
    const ang = (s.value / total) * Math.PI * 2;
    if (ang >= Math.PI * 2 - 1e-6) {
      circle(scene, cx, cy, R, { fill: color, stroke: theme.bg, sw: 2 });
    } else {
      arc(scene, cx, cy, R, a, a + ang, { fill: color, stroke: theme.bg, sw: 2 });
    }
    const mid = a + ang / 2;
    const ratio = s.value / total;
    if (ratio >= 0.05) {
      const tx = cx + Math.sin(mid) * R * 0.66;
      const ty = cy - Math.cos(mid) * R * 0.66;
      text(scene, tx, ty, `${Math.round(ratio * 100)}%`, {
        size: 12.5,
        weight: 700,
        fill: '#ffffff',
        anchor: 'middle',
        baseline: 'middle',
      });
    }
    a += ang;
  });

  circle(scene, cx, cy, R * 0.46, { fill: theme.bg, stroke: 'none' });
  text(scene, cx, cy - 4, fmt(total), { size: 17, weight: 700, fill: theme.fg, anchor: 'middle', baseline: 'middle' });
  text(scene, cx, cy + 16, '合计', { size: 10.5, fill: theme.muted, anchor: 'middle', baseline: 'middle' });

  // 图例
  let ly = cy - R + 6;
  const lx = cx + R + 42;
  let maxLabelW = 0;
  for (const s of model.slices) {
    const color = theme.palette[model.slices.indexOf(s) % theme.palette.length];
    rect(scene, lx, ly - 8, 11, 11, { r: 3, fill: color, stroke: 'none' });
    text(scene, lx + 18, ly + 1, s.label, { size: 12, fill: theme.fg });
    const pct = ((s.value / total) * 100).toFixed(1);
    text(scene, lx + 250, ly + 1, `${fmt(s.value)} · ${pct}%`, { size: 11.5, fill: theme.muted, anchor: 'end' });
    maxLabelW = Math.max(maxLabelW, measure(s.label, 12) + 18);
    ly += 24;
  }

  scene.width = lx + Math.max(250, maxLabelW + 90) + 30;
  scene.height = Math.max(cy + R + 30, ly + 20);
  return scene;
}

/* -------------------------------- 四象限图 -------------------------------- */

export function paintQuadrant(model, theme) {
  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  const S = 460;
  const left = 96;
  const top = headerH + 40;
  const x0 = left;
  const y0 = top;

  const quadFill = [0.07, 0.05, 0.04, 0.06];
  const cells = [
    [0, 0, model.quadrants[0]],
    [1, 0, model.quadrants[1]],
    [0, 1, model.quadrants[2]],
    [1, 1, model.quadrants[3]],
  ];
  for (const [cxi, cyi, label] of cells) {
    rect(scene, x0 + cxi * (S / 2), y0 + cyi * (S / 2), S / 2, S / 2, {
      fill: alpha(theme.accent, quadFill[cyi * 2 + cxi] ?? 0.05),
      stroke: 'none',
    });
    text(scene, x0 + cxi * (S / 2) + 14, y0 + cyi * (S / 2) + 22, label, {
      size: 12,
      weight: 700,
      fill: alpha(theme.muted, 0.95),
    });
  }

  line(scene, x0 + S / 2, y0, x0 + S / 2, y0 + S, { stroke: alpha(theme.line, 0.8), sw: 1.2, dash: '5 5' });
  line(scene, x0, y0 + S / 2, x0 + S, y0 + S / 2, { stroke: alpha(theme.line, 0.8), sw: 1.2, dash: '5 5' });
  rect(scene, x0, y0, S, S, { fill: 'none', stroke: theme.line, sw: 1.4 });

  text(scene, x0 + S / 2, y0 + S + 34, `${model.xAxis.low}  →  ${model.xAxis.high}`, {
    size: 12,
    fill: theme.muted,
    anchor: 'middle',
  });
  // 纵轴：上方为高值，下方为低值
  line(scene, x0 - 34, y0 + S, x0 - 34, y0 + 6, { stroke: alpha(theme.line, 0.7), sw: 1.2 });
  path(scene, `M${x0 - 38},${y0 + 12} L${x0 - 34},${y0 + 2} L${x0 - 30},${y0 + 12}`, {
    fill: 'none', stroke: alpha(theme.line, 0.7), sw: 1.2, cap: 'round', join: 'round',
  });
  text(scene, x0 - 40, y0 + 16, model.yAxis.high, { size: 11.5, fill: theme.muted, anchor: 'end' });
  text(scene, x0 - 40, y0 + S - 4, model.yAxis.low, { size: 11.5, fill: theme.muted, anchor: 'end' });

  model.points.forEach((p, i) => {
    const px = x0 + p.x * S;
    const py = y0 + S - p.y * S;
    const color = theme.palette[i % theme.palette.length];
    circle(scene, px, py, 15, { fill: alpha(color, 0.16), stroke: 'none' });
    circle(scene, px, py, 6, { fill: color, stroke: theme.bg, sw: 2 });
    const right = px + 22 + measure(p.label, 11.5) <= x0 + S - 2;
    text(scene, right ? px + 22 : px - 22, py + 4, p.label, {
      size: 11.5,
      weight: 500,
      fill: theme.fg,
      anchor: right ? 'start' : 'end',
    });
  });

  scene.width = x0 + S + 60;
  scene.height = y0 + S + 60;
  return scene;
}

/* --------------------------------- 柱线图 --------------------------------- */

function niceMax(v) {
  if (v <= 0) return 1;
  const mag = 10 ** Math.floor(Math.log10(v));
  const n = v / mag;
  const step = n <= 1.2 ? 1.2 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return step * mag;
}

export function paintXy(model, theme) {
  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  const plotW = clamp(model.xLabels.length * 78, 420, 900);
  const plotH = 300;
  const left = 74;
  const multi = model.series.length > 1;
  const top = headerH + (multi ? 46 : 26);
  const allVals = model.series.flatMap((s) => s.values);
  const hasNeg = allVals.some((v) => v < 0);
  const maxV = niceMax(Math.max(...allVals, 1) * 1.08);
  const minV = hasNeg ? -niceMax(Math.abs(Math.min(...allVals))) : 0;
  const span = maxV - minV;
  const py = (v) => top + plotH - ((v - minV) / span) * plotH;

  // 网格与 y 轴
  const ticks = 5;
  for (let i = 0; i <= ticks; i += 1) {
    const v = minV + (span * i) / ticks;
    const y = py(v);
    line(scene, left, y, left + plotW, y, {
      stroke: alpha(theme.line, i === 0 && !hasNeg ? 0.85 : 0.22),
      sw: 1,
    });
    text(scene, left - 10, y + 4, fmt(Math.round(v * 100) / 100), { size: 10.5, fill: theme.muted, anchor: 'end' });
  }
  line(scene, left, top, left, top + plotH, { stroke: alpha(theme.line, 0.85), sw: 1.2 });

  const slot = plotW / model.xLabels.length;
  model.xLabels.forEach((lbl, i) => {
    text(scene, left + slot * i + slot / 2, top + plotH + 20, lbl, {
      size: 11,
      fill: theme.muted,
      anchor: 'middle',
    });
  });

  const bars = model.series.filter((s) => s.type === 'bar');
  const lines = model.series.filter((s) => s.type !== 'bar');
  const barW = Math.min(26, (slot * 0.62) / Math.max(1, bars.length));

  bars.forEach((s, si) => {
    const color = theme.palette[(si + 0) % theme.palette.length];
    s.values.forEach((v, i) => {
      const cx = left + slot * i + slot / 2;
      const offset = (si - (bars.length - 1) / 2) * (barW + 4);
      const yTop = py(Math.max(v, 0));
      const yBot = py(Math.min(v, 0));
      rect(scene, cx + offset - barW / 2, yTop, barW, Math.max(1.5, yBot - yTop), {
        r: 3,
        fill: alpha(color, 0.88),
        stroke: 'none',
      });
    });
  });

  lines.forEach((s, si) => {
    const color = theme.palette[(bars.length + si) % theme.palette.length];
    const pts = s.values.map((v, i) => [left + slot * i + slot / 2, py(v)]);
    if (s.type === 'area') {
      const d = `M${pts[0][0]},${py(Math.max(minV, 0))} ` + pts.map((p) => `L${p[0]},${p[1]}`).join(' ') + ` L${pts[pts.length - 1][0]},${py(Math.max(minV, 0))} Z`;
      path(scene, d, { fill: alpha(color, 0.14), stroke: 'none' });
    }
    path(scene, pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' '), {
      fill: 'none',
      stroke: color,
      sw: 2.2,
      cap: 'round',
      join: 'round',
    });
    for (const p of pts) circle(scene, p[0], p[1], 3.4, { fill: theme.bg, stroke: color, sw: 2 });
  });

  if (multi) {
    const items = model.series.map((s, i) => ({ label: s.name, color: theme.palette[i % theme.palette.length] }));
    const totalW = items.reduce((a, it) => a + 15 + measure(it.label, 11.5) + 16, 0);
    paintLegend(scene, theme, items, Math.max(left, left + plotW - totalW), headerH + 22);
  }
  if (model.unit) {
    text(scene, left - 10, top - 10, model.unit, { size: 10.5, fill: theme.muted, anchor: 'end' });
  }

  scene.width = left + plotW + 46;
  scene.height = top + plotH + 44 + (model.footnote ? 22 : 0);
  return scene;
}
