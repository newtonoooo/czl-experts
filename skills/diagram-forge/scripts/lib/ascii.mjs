/**
 * ascii.mjs — 终端友好的纯文本输出
 *
 * 目标场景：日志、代码注释、聊天窗口等无法显示图片的地方。
 * 采用「按层排布 + 竖直连接」的紧凑画法，保证在任何等宽字体下都能对齐。
 */

import { isWide } from './core.mjs';
import { rankNodes } from './layout-graph.mjs';

function dw(s) {
  let w = 0;
  for (const ch of String(s)) w += isWide(ch) ? 2 : 1;
  return w;
}

function padEnd(s, w) {
  const d = dw(s);
  return d >= w ? s : s + ' '.repeat(w - d);
}

function center(s, w) {
  const d = dw(s);
  if (d >= w) return s;
  const left = Math.floor((w - d) / 2);
  return ' '.repeat(left) + s + ' '.repeat(w - d - left);
}

function truncate(s, maxW) {
  let out = '';
  let w = 0;
  for (const ch of String(s)) {
    const cw = isWide(ch) ? 2 : 1;
    if (w + cw > maxW) return `${out}…`;
    out += ch;
    w += cw;
  }
  return out;
}

function boxTop(w) {
  return `┌${'─'.repeat(w)}┐`;
}
function boxBottom(w) {
  return `└${'─'.repeat(w)}┘`;
}

export function toAscii(model) {
  switch (model.kind) {
    case 'flow':
    case 'state':
      return graphAscii(model);
    case 'sequence':
      return sequenceAscii(model);
    case 'class':
      return classAscii(model);
    case 'er':
      return erAscii(model);
    case 'gantt':
      return ganttAscii(model);
    case 'mindmap':
      return mindmapAscii(model);
    case 'timeline':
      return listAscii(model.title, model.events.map((e) => `${e.date || '—'}  ${e.label}${e.detail ? `（${e.detail}）` : ''}`));
    case 'pie':
      return listAscii(model.title, model.slices.map((s) => `${s.label}  ${s.value}`));
    case 'quadrant':
      return listAscii(
        model.title,
        model.points.map((p) => `${p.label}  x=${p.x.toFixed(2)} y=${p.y.toFixed(2)}`),
      );
    case 'xy':
      return xyAscii(model);
    default:
      return '该图表类型暂不支持纯文本输出，请使用 SVG。';
  }
}

/* ------------------------------- 图结构 ASCII ------------------------------ */

function ranksOf(model) {
  const rank = rankNodes(model.nodes, model.edges);
  const byRank = [];
  for (const n of model.nodes) {
    const r = rank.get(n.id) || 0;
    (byRank[r] ||= []).push(n);
  }
  for (let i = 0; i < byRank.length; i += 1) if (!byRank[i]) byRank[i] = [];
  return { byRank, rank };
}

function graphAscii(model) {
  const { byRank, rank } = ranksOf(model);
  const INNER = Math.min(24, Math.max(6, Math.max(...model.nodes.map((n) => dw(n.label)))));
  const GAP = 5;
  const CELL = INNER + 2;
  const lines = [];
  if (model.title) lines.push(model.title, '');
  const colOf = new Map();

  // 预计算所有节点的列位置（列宽统一，与所在层无关）
  for (const nodes of byRank) {
    nodes.forEach((n, i) => {
      colOf.set(n.id, i * (CELL + GAP) + Math.floor(CELL / 2));
    });
  }

  for (let r = 0; r < byRank.length; r += 1) {
    const nodes = byRank[r];
    if (!nodes.length) continue;
    const top = [];
    const mid = [];
    const bot = [];
    nodes.forEach((n, i) => {
      const lead = ' '.repeat(i === 0 ? 0 : GAP);
      const label = truncate(n.label, INNER);
      top.push(`${lead}${boxTop(INNER)}`);
      mid.push(`${lead}│${padEnd(center(label, INNER), INNER)}│`);
      bot.push(`${lead}${boxBottom(INNER)}`);
    });
    lines.push(top.join(''), mid.join(''), bot.join(''));

    const next = byRank[r + 1] || [];
    if (!next.length) continue;

    const src = new Set();
    const dst = new Set();
    const tags = [];
    for (const e of model.edges) {
      if (rank.get(e.from) !== r || rank.get(e.to) !== r + 1) continue;
      const cs = colOf.get(e.from);
      const cd = colOf.get(e.to);
      if (cs === undefined || cd === undefined) continue;
      src.add(cs);
      dst.add(cd);
      if (e.label) tags.push({ col: cd, text: e.label });
    }
    const W = Math.max(0, ...src, ...dst) + 1;
    const l1 = Array.from({ length: W }, () => ' ');
    for (const c of src) l1[c] = '│';
    const l2 = Array.from({ length: W }, () => ' ');
    for (const c of dst) l2[c] = '▼';
    lines.push(l1.join('').replace(/\s+$/, ''), l2.join('').replace(/\s+$/, ''));
    for (const t of tags) lines.push(`${' '.repeat(t.col)}└ ${t.text}`);
  }
  return lines.join('\n');
}

/* -------------------------------- 其他类型 -------------------------------- */

function sequenceAscii(model) {
  const lines = [];
  if (model.title) lines.push(model.title, '');
  const label = new Map(model.participants.map((p) => [p.id, p.label]));
  const emit = (steps, indent) => {
    for (const s of steps) {
      if (s.type === 'message') {
        const arrow = s.style === 'return' ? '<--' : s.style === 'async' ? '-->>' : '->>';
        lines.push(`${indent}${label.get(s.from)} ${arrow} ${label.get(s.to)} : ${s.text}`);
      } else if (s.type === 'note') {
        lines.push(`${indent}[注] ${s.over.map((o) => label.get(o)).join(', ')} : ${s.text}`);
      } else if (s.type === 'fragment') {
        lines.push(`${indent}${s.frag}${s.label ? ` ${s.label}` : ''}`);
        emit(s.steps, `${indent}  `);
        lines.push(`${indent}end`);
      }
    }
  };
  emit(model.steps, '');
  return lines.join('\n');
}

function classAscii(model) {
  const lines = [];
  if (model.title) lines.push(model.title, '');
  for (const c of model.classes) {
    const head = `${c.name}${c.stereotype ? ` «${c.stereotype}»` : ''}`;
    const rows = c.members.map((m) => ` ${m.text}`);
    const w = Math.min(46, Math.max(dw(head) + 4, ...rows.map((r) => dw(r) + 2), 14));
    lines.push(`┌${'─'.repeat(w)}┐`);
    lines.push(`│${padEnd(center(head, w), w)}│`);
    if (rows.length) {
      lines.push(`├${'─'.repeat(w)}┤`);
      for (const r of rows) lines.push(`│${padEnd(truncate(r, w), w)}│`);
    }
    lines.push(`└${'─'.repeat(w)}┘`);
  }
  if (model.relations.length) {
    lines.push('');
    const SIGN = { inherit: '<|--', compose: '*--', aggregate: 'o--', assoc: '-->', depend: '..>' };
    for (const r of model.relations) {
      lines.push(`  ${r.from} ${SIGN[r.kind] || '-->'} ${r.to}${r.label ? ` : ${r.label}` : ''}`);
    }
  }
  return lines.join('\n');
}

function erAscii(model) {
  const lines = [];
  if (model.title) lines.push(model.title, '');
  for (const e of model.entities) {
    const rows = e.attributes.map((a) => `${a.key ? `[${a.key.toUpperCase()}] ` : ''}${a.raw || a.name}${a.type ? ` : ${a.type}` : ''}`);
    const w = Math.min(42, Math.max(dw(e.name) + 4, ...rows.map((r) => dw(r) + 4), 14));
    lines.push(`┌${'─'.repeat(w)}┐`, `│${padEnd(center(e.name, w), w)}│`, `├${'─'.repeat(w)}┤`);
    for (const r of rows) lines.push(`│${padEnd(` ${truncate(r, w - 2)}`, w)}│`);
    lines.push(`└${'─'.repeat(w)}┘`);
  }
  if (model.relations.length) {
    lines.push('');
    for (const r of model.relations) {
      lines.push(`  ${r.from} ${r.card === 'n-n' ? '}o--o{' : r.card === '1-1' ? '||--||' : '||--o{'} ${r.to}${r.label ? ` : ${r.label}` : ''}`);
    }
  }
  return lines.join('\n');
}

function ganttAscii(model) {
  const lines = [];
  if (model.title) lines.push(model.title, '');
  const maxEnd = Math.max(1, ...model.tasks.map((t) => t.offset + Math.max(1, t.duration)));
  const W = 46;
  const scale = W / maxEnd;
  for (const sec of model.sections) {
    if (sec.name) lines.push(`[${sec.name}]`);
    for (const t of sec.tasks) {
      const start = Math.round(t.offset * scale);
      const len = Math.max(1, Math.round(Math.max(1, t.duration) * scale));
      const bar = t.milestone ? `${' '.repeat(start)}◆` : `${' '.repeat(start)}${'█'.repeat(len)}`;
      lines.push(`  ${padEnd(truncate(t.name, 22), 24)}${bar}`);
    }
  }
  lines.push(`  0${' '.repeat(Math.max(1, W - String(maxEnd).length - 2))}${maxEnd} 天`);
  return lines.join('\n');
}

function mindmapAscii(model) {
  const lines = [];
  if (model.title) lines.push(model.title, '');
  const walk = (n, prefix, isLast, depth) => {
    const branch = depth === 0 ? '' : `${prefix}${isLast ? '└─ ' : '├─ '}`;
    lines.push(`${branch}${n.label}`);
    const nextPrefix = depth === 0 ? '' : `${prefix}${isLast ? '   ' : '│  '}`;
    n.children.forEach((c, i) => walk(c, nextPrefix, i === n.children.length - 1, depth + 1));
  };
  walk(model.root, '', true, 0);
  return lines.join('\n');
}

function listAscii(title, items) {
  const lines = title ? [title, ''] : [];
  for (const it of items) lines.push(`  • ${it}`);
  return lines.join('\n');
}

function xyAscii(model) {
  const lines = [];
  if (model.title) lines.push(model.title, '');
  const max = Math.max(...model.series.flatMap((s) => s.values), 1);
  const W = 34;
  model.xLabels.forEach((lbl, i) => {
    const parts = model.series.map((s) => `${s.name}=${s.values[i]}`).join('  ');
    const bar = '▇'.repeat(Math.max(1, Math.round((model.series[0].values[i] / max) * W)));
    lines.push(`  ${padEnd(truncate(lbl, 12), 13)}${padEnd(bar, W + 2)}${parts}`);
  });
  return lines.join('\n');
}
