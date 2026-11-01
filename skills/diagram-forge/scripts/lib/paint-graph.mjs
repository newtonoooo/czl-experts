/**
 * paint-graph.mjs — 流程图 / 状态图 / 类图 / ER 图的绘制
 */

import { measure, textBlock, mix, readableOn, alpha } from './core.mjs';
import { createScene, rect, text, line, path, polygon, edge, labelChip } from './scene.mjs';
import { layoutLayered, applyDirection, graphProfile, autoDirection } from './layout-graph.mjs';
import { TS, paintHeader, paintFooter, paintNode, paintGroup, paintLegend, roleIdx, drawCenteredText } from './paint-common.mjs';

const MAX_LABEL_W = 188;

function nodeSize(node, kind) {
  const tb = textBlock(node.label, MAX_LABEL_W, TS.node);
  let w = Math.max(96, tb.width + 40);
  let h = Math.max(46, tb.height + 26);
  if (node.shape === 'diamond') {
    w = Math.max(w * 1.42, tb.width * 1.55 + 40);
    h = Math.max(h * 1.34, tb.height * 1.55 + 26);
  }
  if (node.shape === 'circle') {
    const r = Math.max(Math.hypot(tb.width / 2, tb.height / 2) + 12, 34);
    w = r * 2;
    h = r * 2;
  }
  if (kind === 'state' && node.shape === 'round') {
    w = Math.max(w, 104);
  }
  return { w: Math.ceil(w), h: Math.ceil(h) };
}

function edgeColor(theme, style) {
  return style === 'thick' ? theme.fg : theme.line;
}

function shiftLayout(l, dy) {
  for (const p of l.pos.values()) p.y += dy;
  for (const g of l.groupBoxes) g.y += dy;
  for (const r of l.routes) r.pts = r.pts.map(([x, y]) => [x, y + dy]);
  l.height += dy;
  return l;
}

export function paintFlow(model, theme, opts = {}) {
  const kind = model.kind;
  const profile = graphProfile(
    model.nodes.map((n) => ({ id: n.id })),
    model.edges,
  );
  const dir = model.directionGiven ? model.direction : autoDirection(profile);

  const sizes = new Map();
  for (const n of model.nodes) sizes.set(n.id, nodeSize(n, kind));

  const groupOf = new Map();
  for (const g of model.groups) for (const m of g.members) if (!groupOf.has(m)) groupOf.set(m, g.id);

  const layoutNodes = model.nodes.map((n) => {
    const s = sizes.get(n.id);
    const swap = dir === 'LR' || dir === 'RL';
    return {
      id: n.id,
      w: swap ? s.h : s.w,
      h: swap ? s.w : s.h,
      group: groupOf.get(n.id) || '',
    };
  });

  let l = layoutLayered(layoutNodes, model.edges, {
    direction: dir,
    groups: model.groups.map((g) => ({ ...g, members: g.members.filter((m) => sizes.has(m)) })),
    nodeGap: 36,
    layerGap: Math.max(56, 88 - profile.depth * 3),
  });
  l = applyDirection(l, dir);

  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);

  // 预估标题宽度，避免画布过窄
  const titleW = model.title ? measure(model.title, TS.title) + 60 : 0;

  shiftLayout(l, headerH);
  const obstacles = [...l.pos.values()].map((p) => ({ x: p.x, y: p.y, w: p.w, h: p.h }));

  for (const g of l.groupBoxes) paintGroup(scene, theme, g);

  const deferred = [];
  for (const r of l.routes) {
    const color = edgeColor(theme, r.style);
    const dash = r.style === 'dashed' ? '6 5' : null;
    const sw = r.style === 'thick' ? 2.6 : 1.6;
    edge(scene, r.pts, { stroke: color, sw, dash, arrowEnd: r.arrow === 'none' ? 'none' : r.arrow === 'open' ? 'open' : 'end', arrowStart: r.arrow === 'both' ? 'end' : 'none' });
    if (r.label) deferred.push({ label: r.label, pts: r.pts });
  }

  for (const n of model.nodes) {
    const box = l.pos.get(n.id);
    if (!box) continue;
    paintNode(scene, theme, n, box, { shadow: true });
  }

  // 边标签最后绘制，避免被节点填充遮挡
  for (const d of deferred) placeEdgeLabel(scene, theme, d.label, d.pts, obstacles);

  const roles = [...new Set(model.nodes.map((n) => n.role))];
  const footerY = l.height + 6;
  let footerH = 0;
  if (roles.length > 1) {
    paintLegend(
      scene,
      theme,
      roles.map((r) => ({ label: roleLabel(r), color: theme.palette[roleIdx(theme, r)] })),
      30,
      footerY + 12,
    );
    footerH = 26;
  }
  footerH += paintFooter(scene, model, theme, l.width, footerY + footerH);

  scene.width = Math.max(l.width, titleW, 320);
  scene.height = l.height + footerH + 10;
  return scene;
}

function roleLabel(r) {
  return {
    primary: '主流程', decision: '判断', data: '数据', external: '外部系统',
    success: '成功', danger: '异常', neutral: '其他',
  }[r] || r;
}

function midPoint(pts) {
  if (pts.length === 2) return [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2];
  // 取最长线段的中点，标签更稳定
  let best = 0;
  let len = -1;
  for (let i = 0; i < pts.length - 1; i += 1) {
    const d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    if (d > len) {
      len = d;
      best = i;
    }
  }
  const [x1, y1] = pts[best];
  const [x2, y2] = pts[best + 1];
  return [(x1 + x2) / 2, (y1 + y2) / 2];
}

/** 把边标签放在线段侧上方/侧右方，并避开节点包围盒 */
function placeEdgeLabel(scene, theme, label, pts, obstacles = []) {
  const [x1, y1, x2, y2] = longestSegment(pts);
  const horizontal = Math.abs(x2 - x1) >= Math.abs(y2 - y1);
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const w = measure(label, TS.edge) + 10;
  const h = TS.edge * 1.35 + 4;
  const base = horizontal ? [mx, my - 10] : [mx + 6 + w / 2, my];

  const offsets = [
    [0, 0], [0, -h - 4], [0, h + 4], [w / 2 + 10, 0], [-w / 2 - 10, 0],
    [0, -2 * (h + 4)], [0, 2 * (h + 4)], [w / 2 + 12, -h - 4], [-w / 2 - 12, -h - 4],
  ];
  let cx = base[0];
  let cy = base[1];
  for (const [dx, dy] of offsets) {
    const tx = base[0] + dx;
    const ty = base[1] + dy;
    const hit = obstacles.some(
      (o) => tx + w / 2 > o.x && tx - w / 2 < o.x + o.w && ty + h / 2 > o.y && ty - h / 2 < o.y + o.h,
    );
    if (!hit) {
      cx = tx;
      cy = ty;
      break;
    }
  }

  labelChip(scene, cx, cy, label, {
    measure,
    size: TS.edge,
    fill: theme.bg,
    color: theme.muted,
    padX: 5,
    padY: 2,
  });
}

function longestSegment(pts) {
  let best = 0;
  let len = -1;
  for (let i = 0; i < pts.length - 1; i += 1) {
    const d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    if (d > len) {
      len = d;
      best = i;
    }
  }
  const a = pts[best];
  const b = pts[best + 1];
  return [a[0], a[1], b[0], b[1]];
}

/* --------------------------------- 类图 ---------------------------------- */

export function paintClass(model, theme) {
  const dir = model.directionGiven ? model.direction : 'LR';
  const sizes = new Map();
  for (const c of model.classes) {
    const nameW = measure(c.name, 13.5) + 28;
    const stW = c.stereotype ? measure(`«${c.stereotype}»`, 11) + 28 : 0;
    const rows = c.members.map((m) => textBlock(m.text, 190, 12).lines.length * 12 * 1.5);
    const memberW = Math.max(
      0,
      ...c.members.map((m) => textBlock(m.text, 190, 12).width + 30),
    );
    const w = Math.ceil(Math.max(168, nameW, stW, memberW));
    const headerH = c.stereotype ? 48 : 34;
    const h = Math.ceil(headerH + (c.members.length ? c.members.length * 18 + 10 : 8));
    sizes.set(c.id, { w, h, rows });
  }

  const swap = dir === 'LR' || dir === 'RL';
  const layoutNodes = model.classes.map((c) => {
    const s = sizes.get(c.id);
    return { id: c.id, w: swap ? s.h : s.w, h: swap ? s.w : s.h };
  });
  let l = layoutLayered(layoutNodes, model.relations, { direction: dir, nodeGap: 54, layerGap: 96 });
  l = applyDirection(l, dir);

  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);
  shiftLayout(l, headerH);
  const obstacles = [...l.pos.values()].map((p) => ({ x: p.x, y: p.y, w: p.w, h: p.h }));

  const deferred = [];
  for (const r of l.routes) {
    const color = theme.line;
    const dash = r.kind === 'depend' ? '5 4' : null;
    const pts = trimRoute(r.pts, 0);
    path(scene, ptsToPath(pts), { fill: 'none', stroke: color, sw: 1.5, dash, cap: 'round' });
    drawRelationEnd(scene, theme, r, pts);
    if (r.label) deferred.push({ label: r.label, pts });
  }

  for (const c of model.classes) {
    const b = l.pos.get(c.id);
    if (!b) continue;
    const color = theme.palette[roleIdx(theme, c.role)];
    const headerH = c.stereotype ? 48 : 34;
    rect(scene, b.x + 1.5, b.y + 2, b.w, b.h, { r: 8, fill: alpha(theme.fg, 0.05), stroke: 'none' });
    rect(scene, b.x, b.y, b.w, b.h, { r: 8, fill: theme.surface, stroke: color, sw: 1.5 });
    rect(scene, b.x, b.y, b.w, headerH, { r: 8, fill: mix(theme.surface, color, 0.18), stroke: 'none' });
    line(scene, b.x, b.y + headerH, b.x + b.w, b.y + headerH, { stroke: color, sw: 1.1 });
    text(scene, b.x + b.w / 2, b.y + (c.stereotype ? 21 : 22), c.name, {
      size: 13.5, weight: 700, fill: theme.fg, anchor: 'middle', baseline: 'middle',
    });
    if (c.stereotype) {
      text(scene, b.x + b.w / 2, b.y + 36, `«${c.stereotype}»`, {
        size: 10.5, fill: theme.muted, anchor: 'middle', baseline: 'middle',
      });
    }
    let yy = b.y + headerH + 6;
    for (const m of c.members) {
      const isM = m.kind === 'method';
      text(scene, b.x + 12, yy + 13, m.text, { size: 12, fill: isM ? theme.fg : theme.muted, weight: isM ? 500 : 400 });
      yy += 18;
    }
  }

  for (const d of deferred) placeEdgeLabel(scene, theme, d.label, d.pts, obstacles);

  scene.width = Math.max(l.width, 320);
  scene.height = l.height + paintFooter(scene, model, theme, l.width, l.height) + 8;
  return scene;
}

function ptsToPath(pts) {  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ');
}

function trimRoute(pts) {
  return pts;
}

function drawRelationEnd(scene, theme, r, pts) {
  const color = theme.line;
  const end = pts[pts.length - 1];
  const prev = pts[pts.length - 2];
  const ang = Math.atan2(end[1] - prev[1], end[0] - prev[0]);

  if (r.kind === 'inherit') {
    hollowTriangle(scene, end, ang, 11, color, theme.bg);
  } else if (r.kind === 'assoc' || r.kind === 'depend') {
    openArrow(scene, end, ang, 9, color);
  } else if (r.kind === 'compose' || r.kind === 'aggregate') {
    const start = pts[0];
    const nxt = pts[1];
    const a2 = Math.atan2(start[1] - nxt[1], start[0] - nxt[0]);
    diamondEnd(scene, start, a2, 12, color, r.kind === 'compose' ? color : theme.bg);
    openArrow(scene, end, ang, 8, color);
  }

  if (r.fromCard) text(scene, pts[0][0] + Math.cos(ang) * 2, pts[0][1] - 8, r.fromCard, { size: 10.5, fill: theme.muted, anchor: 'middle' });
  if (r.toCard) text(scene, end[0], end[1] - 10, r.toCard, { size: 10.5, fill: theme.muted, anchor: 'middle' });
}

function hollowTriangle(scene, [x, y], ang, size, color, fill) {
  const p1 = [x - size * Math.cos(ang) + size * 0.5 * Math.sin(ang), y - size * Math.sin(ang) - size * 0.5 * Math.cos(ang)];
  const p2 = [x - size * Math.cos(ang) - size * 0.5 * Math.sin(ang), y - size * Math.sin(ang) + size * 0.5 * Math.cos(ang)];
  polygon(scene, [[x, y], p1, p2], { fill, stroke: color, sw: 1.4 });
}

function openArrow(scene, [x, y], ang, size, color) {
  const p1 = [x - size * Math.cos(ang) + size * 0.5 * Math.sin(ang), y - size * Math.sin(ang) - size * 0.5 * Math.cos(ang)];
  const p2 = [x - size * Math.cos(ang) - size * 0.5 * Math.sin(ang), y - size * Math.sin(ang) + size * 0.5 * Math.cos(ang)];
  path(scene, `M${p1[0]},${p1[1]} L${x},${y} L${p2[0]},${p2[1]}`, { fill: 'none', stroke: color, sw: 1.5, cap: 'round', join: 'round' });
}

function diamondEnd(scene, [x, y], ang, size, color, fill) {
  const ux = Math.cos(ang);
  const uy = Math.sin(ang);
  const mx = x - ux * size * 0.5;
  const my = y - uy * size * 0.5;
  const w = size * 0.34;
  polygon(
    scene,
    [
      [x, y],
      [mx + w * uy, my - w * ux],
      [x - ux * size, y - uy * size],
      [mx - w * uy, my + w * ux],
    ],
    { fill, stroke: color, sw: 1.3 },
  );
}

/* ---------------------------------- ER 图 --------------------------------- */

export function paintEr(model, theme) {
  const dir = model.directionGiven ? model.direction : 'LR';
  const sizes = new Map();
  for (const e of model.entities) {
    const nameW = measure(e.name, 13.5) + 30;
    const attrW = Math.max(0, ...e.attributes.map((a) => measure(`${a.name}  ${a.type}`, 12) + 44));
    const w = Math.ceil(Math.max(178, nameW, attrW));
    const h = Math.ceil(32 + Math.max(1, e.attributes.length) * 20 + 10);
    sizes.set(e.id, { w, h });
  }
  const swap = dir === 'LR' || dir === 'RL';
  const layoutNodes = model.entities.map((e) => {
    const s = sizes.get(e.id);
    return { id: e.id, w: swap ? s.h : s.w, h: swap ? s.w : s.h };
  });
  let l = layoutLayered(layoutNodes, model.relations, { direction: dir, nodeGap: 66, layerGap: 104 });
  l = applyDirection(l, dir);

  const scene = createScene(0, 0);
  const headerH = paintHeader(scene, model, theme);
  shiftLayout(l, headerH);
  const obstacles = [...l.pos.values()].map((p) => ({ x: p.x, y: p.y, w: p.w, h: p.h }));

  const deferred = [];
  for (const r of l.routes) {
    const color = theme.line;
    path(scene, ptsToPath(r.pts), { fill: 'none', stroke: color, sw: 1.5, cap: 'round' });
    const end = r.pts[r.pts.length - 1];
    const prev = r.pts[r.pts.length - 2];
    const start = r.pts[0];
    const nxt = r.pts[1];
    const many = (card) => card === 'n-n' || card === '1-n';
    crowFoot(scene, start, Math.atan2(start[1] - nxt[1], start[0] - nxt[0]), many(r.card), color);
    crowFoot(scene, end, Math.atan2(end[1] - prev[1], end[0] - prev[0]), many(r.card), color);
    if (r.label) deferred.push({ label: r.label, pts: r.pts });
  }

  for (const e of model.entities) {
    const b = l.pos.get(e.id);
    if (!b) continue;
    const color = theme.palette[roleIdx(theme, e.role)];
    rect(scene, b.x + 1.5, b.y + 2, b.w, b.h, { r: 8, fill: alpha(theme.fg, 0.05), stroke: 'none' });
    rect(scene, b.x, b.y, b.w, b.h, { r: 8, fill: theme.surface, stroke: color, sw: 1.5 });
    rect(scene, b.x, b.y, b.w, 32, { r: 8, fill: mix(theme.surface, color, 0.18), stroke: 'none' });
    line(scene, b.x, b.y + 32, b.x + b.w, b.y + 32, { stroke: color, sw: 1.1 });
    text(scene, b.x + b.w / 2, b.y + 21, e.name, { size: 13.5, weight: 700, fill: theme.fg, anchor: 'middle', baseline: 'middle' });
    let yy = b.y + 32 + 5;
    for (const a of e.attributes) {
      const label = a.raw || a.name;
      if (a.key) {
        const badge = a.key.toUpperCase();
        rect(scene, b.x + 10, yy + 3, 22, 14, { r: 3, fill: alpha(color, 0.16), stroke: 'none' });
        text(scene, b.x + 21, yy + 10, badge, { size: 9, fill: color, anchor: 'middle', baseline: 'middle', weight: 700 });
        text(scene, b.x + 38, yy + 14, label, { size: 12, fill: theme.fg, weight: 500 });
      } else {
        text(scene, b.x + 12, yy + 14, label, { size: 12, fill: theme.muted });
      }
      if (a.type) {
        text(scene, b.x + b.w - 12, yy + 14, a.type, { size: 11, fill: theme.muted, anchor: 'end' });
      }
      yy += 20;
    }
  }

  for (const d of deferred) placeEdgeLabel(scene, theme, d.label, d.pts, obstacles);

  scene.width = Math.max(l.width, 320);
  scene.height = l.height + paintFooter(scene, model, theme, l.width, l.height) + 8;
  return scene;
}

function crowFoot(scene, [x, y], ang, many, color) {
  const ux = Math.cos(ang);
  const uy = Math.sin(ang);
  const len = 9;
  if (many) {
    for (const spread of [-0.55, 0, 0.55]) {
      const a = ang + Math.PI + spread;
      line(scene, x, y, x + Math.cos(a) * len, y + Math.sin(a) * len, { stroke: color, sw: 1.4 });
    }
  } else {
    const bx = x + ux * 7;
    const by = y + uy * 7;
    line(scene, bx - uy * 6, by + ux * 6, bx + uy * 6, by - ux * 6, { stroke: color, sw: 1.4 });
  }
}
