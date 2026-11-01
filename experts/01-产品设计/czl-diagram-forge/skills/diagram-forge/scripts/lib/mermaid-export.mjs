/**
 * mermaid-export.mjs — 把中间模型导出为标准 Mermaid 源码
 *
 * 导出是「单向」的：模型是唯一事实来源，Mermaid 只是可粘贴到其他工具的产物。
 */

const RESERVED = new Set(['end', 'graph', 'subgraph', 'class', 'click', 'style', 'linkStyle', 'default']);

export function safeId(raw, prefix = 'n') {
  let id = String(raw).replace(/[^\p{L}\p{N}_]/gu, '_');
  if (!id) id = prefix;
  if (/^\d/.test(id)) id = `${prefix}_${id}`;
  if (RESERVED.has(id.toLowerCase())) id = `${prefix}_${id}`;
  return id;
}

function q(label) {
  return `"${String(label).replace(/"/g, '&quot;').replace(/\n/g, '<br/>')}"`;
}

export function toMermaid(model) {
  switch (model.kind) {
    case 'flow':
      return flow(model);
    case 'state':
      return state(model);
    case 'class':
      return klass(model);
    case 'er':
      return er(model);
    case 'sequence':
      return sequence(model);
    case 'gantt':
      return gantt(model);
    case 'mindmap':
      return mindmap(model);
    case 'timeline':
      return timeline(model);
    case 'pie':
      return pie(model);
    case 'quadrant':
      return quadrant(model);
    case 'xy':
      return xy(model);
    default:
      throw new Error(`不支持的图表类型: ${model.kind}`);
  }
}

const SHAPE = {
  rect: (id, l) => `${id}[${q(l)}]`,
  round: (id, l) => `${id}(${q(l)})`,
  stadium: (id, l) => `${id}([${q(l)}])`,
  circle: (id, l) => `${id}((${q(l)}))`,
  diamond: (id, l) => `${id}{${q(l)}}`,
  hex: (id, l) => `${id}{{${q(l)}}}`,
  cylinder: (id, l) => `${id}[(${q(l)})]`,
  parallelogram: (id, l) => `${id}[/${q(l)}/]`,
  subroutine: (id, l) => `${id}[[${q(l)}]]`,
  note: (id, l) => `${id}>${q(l)}]`,
};

function flow(model) {
  const dir = model.direction === 'BT' ? 'BT' : model.direction === 'LR' ? 'LR' : model.direction === 'RL' ? 'RL' : 'TB';
  const out = [`flowchart ${dir}`];
  if (model.title) out.unshift(`%% ${model.title}`);

  const idMap = new Map(model.nodes.map((n) => [n.id, safeId(n.id)]));
  const grouped = new Set();
  for (const g of model.groups) {
    out.push(`  subgraph ${safeId(g.id, 'g')}[${q(g.label)}]`);
    for (const mem of g.members) {
      const n = model.nodes.find((x) => x.id === mem);
      if (!n) continue;
      grouped.add(mem);
      out.push(`    ${(SHAPE[n.shape] || SHAPE.rect)(idMap.get(n.id), n.label)}`);
    }
    out.push('  end');
  }
  for (const n of model.nodes) {
    if (grouped.has(n.id)) continue;
    out.push(`  ${(SHAPE[n.shape] || SHAPE.rect)(idMap.get(n.id), n.label)}`);
  }

  const ARROW = {
    'solid-end': '-->', 'solid-both': '<-->', 'solid-none': '---', 'solid-open': '-->',
    'dashed-end': '-.->', 'dashed-both': '<-.->', 'dashed-none': '-.-',
    'thick-end': '==>', 'thick-both': '<==>', 'thick-none': '===',
  };
  for (const e of model.edges) {
    const key = `${e.style}-${e.arrow === 'both' ? 'both' : e.arrow === 'none' ? 'none' : e.arrow === 'open' ? 'open' : 'end'}`;
    const arrow = ARROW[key] || '-->';
    const label = e.label ? `|${q(e.label)}|` : '';
    out.push(`  ${idMap.get(e.from)} ${arrow}${label} ${idMap.get(e.to)}`);
  }

  const roles = [...new Set(model.nodes.map((n) => n.role))];
  const CLASS = { primary: 'cPrimary', decision: 'cDecision', data: 'cData', external: 'cExternal', success: 'cSuccess', danger: 'cDanger', neutral: 'cNeutral' };
  for (const r of roles) {
    out.push(`  classDef ${CLASS[r]} stroke-width:1.5px`);
  }
  for (const r of roles) {
    const ids = model.nodes.filter((n) => n.role === r).map((n) => idMap.get(n.id));
    if (ids.length) out.push(`  class ${ids.join(',')} ${CLASS[r]}`);
  }
  return out.join('\n');
}

function state(model) {
  const out = ['stateDiagram-v2'];
  const idMap = new Map();
  model.nodes.forEach((n, i) => idMap.set(n.id, safeId(n.id, 's')));
  for (const n of model.nodes) {
    if (n.shape === 'circle' && /^(start|开始)$/i.test(n.label)) continue;
    out.push(`  state ${q(n.label)} as ${idMap.get(n.id)}`);
  }
  for (const e of model.edges) {
    const from = /^(start|开始)$/i.test(model.nodes.find((n) => n.id === e.from)?.label || '') ? '[*]' : idMap.get(e.from);
    const to = /^(end|结束)$/i.test(model.nodes.find((n) => n.id === e.to)?.label || '') ? '[*]' : idMap.get(e.to);
    out.push(`  ${from} --> ${to}${e.label ? ` : ${e.label}` : ''}`);
  }
  return out.join('\n');
}

function klass(model) {
  const out = ['classDiagram'];
  for (const c of model.classes) {
    const name = safeId(c.id, 'C');
    if (c.stereotype) out.push(`  class ${name} {`, `    <<${c.stereotype}>>`);
    else out.push(`  class ${name} {`);
    for (const m of c.members) {
      out.push(`    ${m.kind === 'method' ? '+' : '+'}${m.text}`);
    }
    out.push('  }');
  }
  const REL = { inherit: '<|--', compose: '*--', aggregate: 'o--', assoc: '-->', depend: '..>' };
  for (const r of model.relations) {
    const a = safeId(r.from, 'C');
    const b = safeId(r.to, 'C');
    const label = r.label ? ` : ${r.label}` : '';
    out.push(`  ${b} ${REL[r.kind] || '-->'} ${a}${label}`);
  }
  return out.join('\n');
}

function er(model) {
  const out = ['erDiagram'];
  for (const e of model.entities) {
    out.push(`  ${safeId(e.id, 'E').toUpperCase()} {`);
    for (const a of e.attributes) {
      const type = (a.type || 'string').replace(/[^\p{L}\p{N}_]+/gu, '_').replace(/^_+|_+$/g, '') || 'string';
      const key = a.key ? ` ${a.key.toUpperCase()}` : '';
      out.push(`    ${type} ${safeId(a.name || a.raw, 'attr')}${key}`);
    }
    out.push('  }');
  }
  const CARD = {
    '1-1': ['||', '||'],
    '1-n': ['||', 'o{'],
    'n-n': ['}o', 'o{'],
  };
  for (const r of model.relations) {
    const [l, rr] = CARD[r.card] || CARD['1-n'];
    out.push(`  ${safeId(r.from, 'E').toUpperCase()} ${l}--${rr} ${safeId(r.to, 'E').toUpperCase()} : ${q(r.label || 'rel')}`);
  }
  return out.join('\n');
}

function sequence(model) {
  const out = ['sequenceDiagram'];
  const idMap = new Map(model.participants.map((p) => [p.id, safeId(p.id, 'P')]));
  for (const p of model.participants) {
    out.push(`  participant ${idMap.get(p.id)} as ${p.label}`);
  }
  const emit = (steps, indent) => {
    for (const s of steps) {
      if (s.type === 'message') {
        const arrow = s.style === 'async' ? '-->>' : s.style === 'return' ? '-->>' : '->>';
        out.push(`${indent}${idMap.get(s.from)}${arrow}${idMap.get(s.to)}: ${s.text}`);
      } else if (s.type === 'note') {
        out.push(`${indent}Note over ${s.over.map((o) => idMap.get(o)).join(',')}: ${s.text}`);
      } else if (s.type === 'fragment') {
        out.push(`${indent}${s.frag}${s.label ? ` ${s.label}` : ''}`);
        emit(s.steps, `${indent}  `);
        out.push(`${indent}end`);
      }
    }
  };
  emit(model.steps, '  ');
  return out.join('\n');
}

function gantt(model) {
  const out = ['gantt', '  dateFormat YYYY-MM-DD', '  axisFormat %m-%d'];
  if (model.title) out.unshift(`%% ${model.title}`);
  const base = model.ganttOrigin;
  let counter = 0;
  for (const sec of model.sections) {
    if (sec.name) out.push(`  section ${sec.name}`);
    for (const t of sec.tasks) {
      counter += 1;
      const id = `t${counter}`;
      if (t.milestone) {
        const when = base ? new Date(base + t.offset * 86400000).toISOString().slice(0, 10) : `${t.offset}d`;
        out.push(`  ${t.name} : milestone, ${id}, ${when}, 0d`);
      } else if (base) {
        const start = new Date(base + t.offset * 86400000).toISOString().slice(0, 10);
        out.push(`  ${t.name} : ${id}, ${start}, ${t.duration}d`);
      } else {
        out.push(`  ${t.name} : ${id}, ${t.offset}d, ${t.duration}d`);
      }
    }
  }
  return out.join('\n');
}

function mindmap(model) {
  const out = ['mindmap'];
  const walk = (n, depth) => {
    const indent = '  '.repeat(depth + 1);
    out.push(`${indent}${depth === 0 ? `root((${n.label}))` : n.label}`);
    n.children.forEach((c) => walk(c, depth + 1));
  };
  walk(model.root, 0);
  return out.join('\n');
}

function timeline(model) {
  const out = ['timeline'];
  if (model.title) out.push(`  title ${model.title}`);
  for (const e of model.events) {
    out.push(`  ${e.date || '-'} : ${e.label}${e.detail ? ` : ${e.detail}` : ''}`);
  }
  return out.join('\n');
}

function pie(model) {
  const out = ['pie showData'];
  if (model.title) out.push(`  title ${model.title}`);
  for (const s of model.slices) out.push(`  ${q(s.label)} : ${s.value}`);
  return out.join('\n');
}

function quadrant(model) {
  const out = ['quadrantChart'];
  if (model.title) out.push(`  title ${model.title}`);
  out.push(`  x-axis ${model.xAxis.low} --> ${model.xAxis.high}`);
  out.push(`  y-axis ${model.yAxis.low} --> ${model.yAxis.high}`);
  // 本工具的象限顺序为 [左上, 右上, 左下, 右下]，Mermaid 为 1=右上 2=左上 3=左下 4=右下
  const MAP = [2, 1, 3, 4];
  model.quadrants.forEach((label, i) => out.push(`  quadrant-${MAP[i]} ${label}`));
  for (const p of model.points) out.push(`  ${p.label}: [${p.x.toFixed(2)}, ${p.y.toFixed(2)}]`);
  return out.join('\n');
}

function xy(model) {
  const out = ['xychart-beta'];
  if (model.title) out.push(`  title ${q(model.title)}`);
  out.push(`  x-axis [${model.xLabels.map((x) => q(x)).join(', ')}]`);
  const vals = model.series.flatMap((s) => s.values);
  const min = Math.min(0, ...vals);
  const max = Math.max(...vals, 1);
  out.push(`  y-axis ${q(model.unit || '数值')} ${Math.floor(min)} --> ${Math.ceil(max * 1.05)}`);
  for (const s of model.series) {
    out.push(`  ${s.type === 'line' || s.type === 'area' ? 'line' : 'bar'} [${s.values.join(', ')}]`);
  }
  return out.join('\n');
}
