/**
 * model.mjs — 图表中间模型（Diagram Model）的规范化与校验
 *
 * 设计要点：模型是渲染的唯一入口，Mermaid 源码是模型的一种「导出格式」。
 * 这样同一份结构可以同时产出 SVG / HTML / ASCII / .mmd，而不依赖外部解析器。
 */

import { clamp } from './core.mjs';

export const KINDS = [
  'flow', 'state', 'class', 'er', 'sequence',
  'gantt', 'mindmap', 'timeline', 'pie', 'quadrant', 'xy',
];

export const KIND_LABEL = {
  flow: '流程图', state: '状态图', class: '类图', er: 'ER 实体关系图',
  sequence: '时序图', gantt: '甘特图', mindmap: '思维导图', timeline: '时间轴',
  pie: '饼图', quadrant: '四象限图', xy: '柱线图',
};

const SHAPES = ['rect', 'round', 'stadium', 'circle', 'diamond', 'hex', 'cylinder', 'parallelogram', 'subroutine', 'note'];
const EDGE_STYLES = ['solid', 'dashed', 'thick'];
const ARROWS = ['end', 'both', 'none', 'open'];
const ROLES = ['primary', 'decision', 'data', 'external', 'success', 'danger', 'neutral'];

function err(list, path, msg) {
  list.push(`${path}: ${msg}`);
}

function asArray(v) {
  return Array.isArray(v) ? v : [];
}

function str(v, fallback = '') {
  return v === undefined || v === null ? fallback : String(v);
}

/**
 * @returns {{model: object, errors: string[], warnings: string[]}}
 */
export function normalizeModel(raw) {
  const errors = [];
  const warnings = [];
  const m = raw && typeof raw === 'object' ? raw : {};

  const kind = str(m.kind || m.type, '').toLowerCase();
  if (!KINDS.includes(kind)) {
    err(errors, 'kind', `必须是 ${KINDS.join(' | ')} 之一，当前为 "${kind || '(空)'}"`);
    return { model: null, errors, warnings };
  }

  const base = {
    kind,
    title: str(m.title),
    subtitle: str(m.subtitle),
    source: str(m.source),
    theme: str(m.theme, ''),
    direction: str(m.direction, 'TB').toUpperCase().replace('TD', 'TB'),
    directionGiven: !!m.direction,
    footnote: str(m.footnote),
  };
  if (!['TB', 'LR', 'BT', 'RL'].includes(base.direction)) {
    warnings.push(`direction: "${base.direction}" 不在 TB|LR|BT|RL 中，已回退为 TB`);
    base.direction = 'TB';
  }

  switch (kind) {
    case 'flow':
    case 'state':
      Object.assign(base, normalizeGraph(m, kind, errors, warnings));
      break;
    case 'class':
      Object.assign(base, normalizeClass(m, errors, warnings));
      break;
    case 'er':
      Object.assign(base, normalizeEr(m, errors, warnings));
      break;
    case 'sequence':
      Object.assign(base, normalizeSequence(m, errors, warnings));
      break;
    case 'gantt':
      Object.assign(base, normalizeGantt(m, errors, warnings));
      break;
    case 'mindmap':
      Object.assign(base, normalizeMindmap(m, errors, warnings));
      break;
    case 'timeline':
      Object.assign(base, normalizeTimeline(m, errors, warnings));
      break;
    case 'pie':
      Object.assign(base, normalizePie(m, errors, warnings));
      break;
    case 'quadrant':
      Object.assign(base, normalizeQuadrant(m, errors, warnings));
      break;
    case 'xy':
      Object.assign(base, normalizeXy(m, errors, warnings));
      break;
    default:
      break;
  }

  return { model: errors.length ? null : base, errors, warnings };
}

/* ------------------------------- flow / state ------------------------------ */

function normalizeGraph(m, kind, errors, warnings) {
  const ids = new Set();
  const nodes = [];

  for (const [i, n] of asArray(m.nodes).entries()) {
    if (!n || typeof n !== 'object') {
      err(errors, `nodes[${i}]`, '必须是对象');
      continue;
    }
    const id = str(n.id);
    if (!id) {
      err(errors, `nodes[${i}]`, '缺少 id');
      continue;
    }
    if (ids.has(id)) {
      err(errors, `nodes[${i}]`, `id "${id}" 重复`);
      continue;
    }
    ids.add(id);
    const shape = SHAPES.includes(n.shape) ? n.shape : kind === 'state' ? 'round' : 'rect';
    const role = ROLES.includes(n.role) ? n.role : 'primary';
    nodes.push({
      id,
      label: str(n.label, id),
      shape,
      role,
      note: str(n.note),
      emphasis: !!n.emphasis,
    });
  }

  if (nodes.length === 0) err(errors, 'nodes', '至少需要 1 个节点');
  if (nodes.length > 60) warnings.push(`nodes: 共 ${nodes.length} 个节点，超过 30 个可读性会明显下降，建议拆分`);

  const edges = [];
  for (const [i, e] of asArray(m.edges).entries()) {
    if (!e || typeof e !== 'object') {
      err(errors, `edges[${i}]`, '必须是对象');
      continue;
    }
    const from = str(e.from);
    const to = str(e.to);
    if (!ids.has(from)) err(errors, `edges[${i}].from`, `引用了不存在的节点 "${from}"`);
    if (!ids.has(to)) err(errors, `edges[${i}].to`, `引用了不存在的节点 "${to}"`);
    if (!from || !to) continue;
    edges.push({
      from,
      to,
      label: str(e.label),
      style: EDGE_STYLES.includes(e.style) ? e.style : 'solid',
      arrow: ARROWS.includes(e.arrow) ? e.arrow : 'end',
    });
  }

  const groups = [];
  const gids = new Set();
  for (const [i, g] of asArray(m.groups).entries()) {
    if (!g || typeof g !== 'object') {
      err(errors, `groups[${i}]`, '必须是对象');
      continue;
    }
    const id = str(g.id);
    if (!id) {
      err(errors, `groups[${i}]`, '缺少 id');
      continue;
    }
    if (gids.has(id) || ids.has(id)) {
      err(errors, `groups[${i}]`, `id "${id}" 与已有节点或分组冲突`);
      continue;
    }
    gids.add(id);
    const members = asArray(g.members).map(String);
    const valid = members.filter((x) => {
      if (!ids.has(x)) {
        err(errors, `groups[${i}].members`, `引用了不存在的节点 "${x}"`);
        return false;
      }
      return true;
    });
    if (valid.length === 0) {
      err(errors, `groups[${i}]`, '没有有效成员');
      continue;
    }
    groups.push({ id, label: str(g.label, id), members: valid });
  }

  // 同一节点不得属于多个分组
  const seen = new Map();
  for (const g of groups) {
    for (const mem of g.members) {
      if (seen.has(mem)) warnings.push(`groups: 节点 "${mem}" 同时属于 "${seen.get(mem)}" 与 "${g.id}"，仅第一个分组生效`);
      else seen.set(mem, g.id);
    }
  }

  return { nodes, edges, groups };
}

/* ---------------------------------- class --------------------------------- */

function normalizeClass(m, errors, warnings) {
  const ids = new Set();
  const classes = [];
  for (const [i, c] of asArray(m.classes).entries()) {
    const id = str(c && c.id);
    if (!id) {
      err(errors, `classes[${i}]`, '缺少 id');
      continue;
    }
    if (ids.has(id)) {
      err(errors, `classes[${i}]`, `id "${id}" 重复`);
      continue;
    }
    ids.add(id);
    const members = asArray(c.members).map((x) =>
      typeof x === 'string' ? { text: x, kind: guessMemberKind(x) } : { text: str(x.text), kind: x.kind === 'method' ? 'method' : 'field' },
    );
    classes.push({
      id,
      name: str(c.name, id),
      stereotype: str(c.stereotype),
      role: ROLES.includes(c.role) ? c.role : 'primary',
      members,
    });
  }
  if (classes.length === 0) err(errors, 'classes', '至少需要 1 个类');

  const REL = ['inherit', 'compose', 'aggregate', 'assoc', 'depend'];
  const relations = [];
  for (const [i, r] of asArray(m.relations).entries()) {
    const from = str(r && r.from);
    const to = str(r && r.to);
    if (!ids.has(from)) err(errors, `relations[${i}].from`, `引用了不存在的类 "${from}"`);
    if (!ids.has(to)) err(errors, `relations[${i}].to`, `引用了不存在的类 "${to}"`);
    if (!from || !to) continue;
    relations.push({
      from,
      to,
      kind: REL.includes(r.kind) ? r.kind : 'assoc',
      label: str(r.label),
      fromCard: str(r.fromCard),
      toCard: str(r.toCard),
    });
  }
  return { classes, relations };
}

function guessMemberKind(text) {
  return /\(.*\)\s*(:.*)?$/.test(String(text)) ? 'method' : 'field';
}

/* ------------------------------------ er ---------------------------------- */

function normalizeEr(m, errors, warnings) {
  const ids = new Set();
  const entities = [];
  for (const [i, e] of asArray(m.entities).entries()) {
    const id = str(e && e.id);
    if (!id) {
      err(errors, `entities[${i}]`, '缺少 id');
      continue;
    }
    if (ids.has(id)) {
      err(errors, `entities[${i}]`, `id "${id}" 重复`);
      continue;
    }
    ids.add(id);
    const attributes = asArray(e.attributes).map((a) =>
      typeof a === 'string'
        ? { name: a, type: '', key: /^[*#]/.test(a) ? 'pk' : '', raw: a.replace(/^[*#]\s*/, '') }
        : { name: str(a.name), type: str(a.type), key: a.key === 'pk' || a.key === 'fk' ? a.key : '', raw: '' },
    );
    entities.push({ id, name: str(e.name, id), role: ROLES.includes(e.role) ? e.role : 'data', attributes });
  }
  if (entities.length === 0) err(errors, 'entities', '至少需要 1 个实体');

  const relations = [];
  for (const [i, r] of asArray(m.relations).entries()) {
    const from = str(r && r.from);
    const to = str(r && r.to);
    if (!ids.has(from)) err(errors, `relations[${i}].from`, `引用了不存在的实体 "${from}"`);
    if (!ids.has(to)) err(errors, `relations[${i}].to`, `引用了不存在的实体 "${to}"`);
    if (!from || !to) continue;
    const card = ['1-1', '1-n', 'n-n'].includes(r.card) ? r.card : '1-n';
    relations.push({ from, to, card, label: str(r.label) });
  }
  return { entities, relations };
}

/* -------------------------------- sequence -------------------------------- */

function normalizeSequence(m, errors, warnings) {
  const ids = new Set();
  const participants = [];
  for (const [i, p] of asArray(m.participants).entries()) {
    const id = str(p && p.id);
    if (!id) {
      err(errors, `participants[${i}]`, '缺少 id');
      continue;
    }
    if (ids.has(id)) {
      err(errors, `participants[${i}]`, `id "${id}" 重复`);
      continue;
    }
    ids.add(id);
    participants.push({
      id,
      label: str(p.label, id),
      kind: ['actor', 'service', 'db', 'queue', 'external'].includes(p.kind) ? p.kind : 'service',
      role: ROLES.includes(p.role) ? p.role : 'primary',
    });
  }
  if (participants.length === 0) err(errors, 'participants', '至少需要 1 个参与者');

  const steps = [];
  let openFrag = null;
  const push = (item) => {
    if (openFrag) openFrag.steps.push(item);
    else steps.push(item);
  };
  for (const [i, s] of asArray(m.steps).entries()) {
    const type = str(s && s.type, 'message');
    if (type === 'message') {
      const from = str(s.from);
      const to = str(s.to);
      if (!ids.has(from)) err(errors, `steps[${i}].from`, `引用了不存在的参与者 "${from}"`);
      if (!ids.has(to)) err(errors, `steps[${i}].to`, `引用了不存在的参与者 "${to}"`);
      if (!from || !to) continue;
      push({
        type: 'message',
        from,
        to,
        text: str(s.text),
        style: ['sync', 'async', 'return'].includes(s.style) ? s.style : 'sync',
        activate: !!s.activate,
      });
    } else if (type === 'note') {
      const over = asArray(s.over).map(String).filter((x) => ids.has(x));
      if (over.length === 0) {
        err(errors, `steps[${i}].over`, 'note 需要至少一个有效参与者');
        continue;
      }
      push({ type: 'note', over, text: str(s.text) });
    } else if (type === 'fragment') {
      const fk = ['loop', 'alt', 'opt', 'par'].includes(s.frag) ? s.frag : 'opt';
      if (openFrag) {
        err(errors, `steps[${i}]`, '不支持嵌套 fragment');
        continue;
      }
      const frag = { type: 'fragment', frag: fk, label: str(s.label), steps: [] };
      steps.push(frag);
      openFrag = frag;
    } else if (type === 'end') {
      if (!openFrag) {
        err(errors, `steps[${i}]`, 'end 没有对应的 fragment');
        continue;
      }
      openFrag = null;
    } else {
      err(errors, `steps[${i}].type`, `未知类型 "${type}"，可用 message|note|fragment|end`);
    }
  }
  if (openFrag) warnings.push('steps: fragment 未闭合，已自动闭合');
  return { participants, steps };
}

/* ---------------------------------- gantt --------------------------------- */

function parseDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || '').trim());
  if (!m) return null;
  const d = Date.UTC(+m[1], +m[2] - 1, +m[3]);
  return Number.isFinite(d) ? d : null;
}

function normalizeGantt(m, errors, warnings) {
  const sections = [];
  const flat = [];

  const readTasks = (arr, sectionName, path) => {
    const tasks = [];
    for (const [i, t] of asArray(arr).entries()) {
      const name = str(t && t.name, str(t && t.id));
      if (!name) {
        err(errors, `${path}[${i}]`, '缺少 name');
        continue;
      }
      const startRaw = t.start;
      let start = startRaw;
      let date = null;
      if (typeof startRaw === 'string' && parseDate(startRaw)) {
        date = parseDate(startRaw);
      } else if (startRaw !== undefined && !Number.isFinite(Number(startRaw))) {
        err(errors, `${path}[${i}].start`, `无法识别 "${startRaw}"，应为 YYYY-MM-DD 或数字偏移`);
        continue;
      } else {
        start = Number(startRaw || 0);
      }
      const duration = t.milestone ? 0 : Math.max(1, Number(t.duration ?? 1) || 1);
      tasks.push({
        name,
        start: start === undefined ? 0 : start,
        date,
        duration,
        milestone: !!t.milestone,
        critical: !!t.critical,
        owner: str(t.owner),
      });
    }
    return tasks;
  };

  if (asArray(m.sections).length) {
    for (const [i, s] of asArray(m.sections).entries()) {
      const name = str(s && s.name, `阶段 ${i + 1}`);
      const tasks = readTasks(s && s.tasks, name, `sections[${i}].tasks`);
      sections.push({ name, tasks });
      flat.push(...tasks);
    }
  } else {
    const tasks = readTasks(m.tasks, '任务', 'tasks');
    sections.push({ name: '', tasks });
    flat.push(...tasks);
  }

  if (flat.length === 0) err(errors, 'tasks', '至少需要 1 个任务');

  // 统一为相对天数
  const dates = flat.map((t) => t.date).filter(Boolean);
  if (dates.length && dates.length !== flat.length) {
    warnings.push('tasks: 部分任务使用日期、部分使用偏移，已按日期模式统一换算');
  }
  let origin = null;
  if (dates.length) {
    origin = Math.min(...dates);
    for (const t of flat) {
      if (t.date) t.offset = Math.round((t.date - origin) / 86400000);
      else t.offset = Number(t.start) || 0;
    }
  } else {
    for (const t of flat) t.offset = Number(t.start) || 0;
  }

  return { sections, tasks: flat, ganttOrigin: origin };
}

/* --------------------------------- mindmap -------------------------------- */

function normalizeMindmap(m, errors, warnings) {
  const seen = new Set();
  let count = 0;
  const walk = (n, depth, path) => {
    if (!n || typeof n !== 'object') {
      err(errors, path, '必须是对象');
      return null;
    }
    const label = str(n.label, str(n.id));
    if (!label) {
      err(errors, path, '缺少 label');
      return null;
    }
    if (depth > 6) {
      warnings.push(`${path}: 层级超过 6 层，建议收敛`);
    }
    count += 1;
    const children = asArray(n.children)
      .map((c, i) => walk(c, depth + 1, `${path}.children[${i}]`))
      .filter(Boolean);
    return { label, note: str(n.note), children };
  };

  const rootRaw = m.root || (m.nodes && m.nodes[0]) || null;
  const root = walk(rootRaw, 0, 'root');
  if (!root) err(errors, 'root', '思维导图需要根节点');
  if (count > 60) warnings.push(`mindmap: 共 ${count} 个节点，建议精简到 40 以内`);
  return { root };
}

/* -------------------------------- timeline -------------------------------- */

function normalizeTimeline(m, errors, warnings) {
  const events = [];
  for (const [i, e] of asArray(m.events).entries()) {
    const label = str(e && e.label, str(e && e.title));
    if (!label) {
      err(errors, `events[${i}]`, '缺少 label');
      continue;
    }
    events.push({ date: str(e.date, str(e.when)), label, detail: str(e.detail) });
  }
  if (events.length === 0) err(errors, 'events', '至少需要 1 个事件');
  if (events.length > 12) warnings.push(`events: 共 ${events.length} 个事件，横向排布可能拥挤，建议合并同类项`);
  return { events };
}

/* ----------------------------------- pie ---------------------------------- */

function normalizePie(m, errors, warnings) {
  const slices = [];
  for (const [i, s] of asArray(m.slices).entries()) {
    const label = str(s && s.label);
    const value = Number(s && s.value);
    if (!label) {
      err(errors, `slices[${i}]`, '缺少 label');
      continue;
    }
    if (!Number.isFinite(value) || value <= 0) {
      err(errors, `slices[${i}].value`, `必须为正数，当前 "${s && s.value}"`);
      continue;
    }
    slices.push({ label, value });
  }
  if (slices.length === 0) err(errors, 'slices', '至少需要 1 个数据项');
  if (slices.length > 8) warnings.push(`slices: 共 ${slices.length} 项，建议合并为 8 项以内`);
  const total = slices.reduce((a, b) => a + b.value, 0);
  if (total > 0) {
    const tiny = slices.filter((s) => s.value / total < 0.02);
    if (tiny.length) warnings.push(`slices: ${tiny.map((s) => s.label).join('、')} 占比不足 2%，在图上几乎不可见`);
  }
  return { slices };
}

/* --------------------------------- quadrant ------------------------------- */

function normalizeQuadrant(m, errors, warnings) {
  const axis = (a, fallback) => ({
    low: str(a && a.low, fallback.low),
    high: str(a && a.high, fallback.high),
  });
  const points = [];
  for (const [i, p] of asArray(m.points).entries()) {
    const label = str(p && p.label);
    const x = Number(p && p.x);
    const y = Number(p && p.y);
    if (!label) {
      err(errors, `points[${i}]`, '缺少 label');
      continue;
    }
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      err(errors, `points[${i}]`, 'x / y 必须是 0~1 之间的数字');
      continue;
    }
    points.push({ label, x: clamp(x, 0, 1), y: clamp(y, 0, 1) });
  }
  if (points.length === 0) err(errors, 'points', '至少需要 1 个散点');
  const quadrants = asArray(m.quadrants).map(String);
  return {
    xAxis: axis(m.xAxis, { low: '低', high: '高' }),
    yAxis: axis(m.yAxis, { low: '低', high: '高' }),
    quadrants: [quadrants[0] || '高价值', quadrants[1] || '待评估', quadrants[2] || '低优先', quadrants[3] || '可观察'],
    points,
  };
}

/* ------------------------------------ xy ---------------------------------- */

function normalizeXy(m, errors, warnings) {
  const xLabels = asArray(m.xLabels).map(String);
  if (xLabels.length === 0) err(errors, 'xLabels', '至少需要 1 个横轴标签');
  const series = [];
  for (const [i, s] of asArray(m.series).entries()) {
    const name = str(s && s.name, `系列 ${i + 1}`);
    const values = asArray(s && s.values).map(Number);
    if (values.length !== xLabels.length) {
      err(errors, `series[${i}].values`, `长度 ${values.length} 与 xLabels 长度 ${xLabels.length} 不一致`);
      continue;
    }
    if (values.some((v) => !Number.isFinite(v))) {
      err(errors, `series[${i}].values`, '包含非数字值');
      continue;
    }
    series.push({ name, values, type: s.type === 'line' ? 'line' : s.type === 'area' ? 'area' : 'bar' });
  }
  if (series.length === 0) err(errors, 'series', '至少需要 1 个数据系列');
  if (series.length > 4) warnings.push(`series: 共 ${series.length} 个系列，建议不超过 4 个以保证可读`);
  return { xLabels, series, unit: str(m.unit), stacked: !!m.stacked };
}
