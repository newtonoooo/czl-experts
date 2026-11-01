/**
 * lint.mjs — 语法体检与质量评分
 *
 * 两个入口：
 *  - lintMermaidSource(text)：对任意 Mermaid 源码做静态检查（不渲染、不联网）
 *  - qualityReport(model)：对中间模型给出可量化的质量分与改进建议
 */

/* ----------------------------- Mermaid 源码体检 ---------------------------- */

import { rankNodes } from './layout-graph.mjs';

const TYPE_HINT = [
  [/^\s*(flowchart|graph)\b/m, 'flow'],
  [/^\s*sequenceDiagram\b/m, 'sequence'],
  [/^\s*classDiagram\b/m, 'class'],
  [/^\s*erDiagram\b/m, 'er'],
  [/^\s*stateDiagram(-v2)?\b/m, 'state'],
  [/^\s*gantt\b/m, 'gantt'],
  [/^\s*mindmap\b/m, 'mindmap'],
  [/^\s*timeline\b/m, 'timeline'],
  [/^\s*pie\b/m, 'pie'],
  [/^\s*quadrantChart\b/m, 'quadrant'],
  [/^\s*xychart(-beta)?\b/m, 'xy'],
  [/^\s*(journey|gitGraph|C4Context|sankey)\b/m, 'unsupported'],
];

export function detectKind(text) {
  for (const [re, kind] of TYPE_HINT) if (re.test(text)) return kind;
  return null;
}

export function lintMermaidSource(text) {
  const errors = [];
  const warnings = [];
  const lines = String(text).replace(/\r\n/g, '\n').split('\n');
  const kind = detectKind(text);

  if (!kind) {
    errors.push({ line: 1, msg: '未识别到图表类型声明（如 flowchart TD / sequenceDiagram）' });
    return { ok: false, kind, errors, warnings, stats: {} };
  }
  if (kind === 'unsupported') {
    warnings.push({ line: 1, msg: '该图表类型不在本工具的渲染范围内，仅做语法检查' });
  }

  // 括号与引号平衡（逐行累计）
  const pairs = { '[': ']', '(': ')', '{': '}' };
  const stack = [];
  let inQuote = false;
  lines.forEach((raw, i) => {
    if (/^\s*%%/.test(raw)) return;
    // ER 关系行中的 o{ / }| 是基数符号，不是括号
    if (kind === 'er' && raw.includes('--')) return;
    for (const ch of raw) {
      if (ch === '"') inQuote = !inQuote;
      if (inQuote) continue;
      if (pairs[ch]) stack.push({ ch, line: i + 1 });
      else if (ch === ']' || ch === ')' || ch === '}') {
        const top = stack.pop();
        if (!top || pairs[top.ch] !== ch) {
          errors.push({ line: i + 1, msg: `括号不匹配：出现多余的 "${ch}"` });
        }
      }
    }
  });
  for (const s of stack) errors.push({ line: s.line, msg: `括号未闭合："${s.ch}"` });
  if (inQuote) errors.push({ line: lines.length, msg: '引号未闭合' });

  // 块结构平衡：flowchart 的 subgraph、时序图的 loop/alt/opt 等以 end 收尾
  const OPENER = {
    flow: /^subgraph\b/,
    sequence: /^(loop|alt|opt|par|critical|break|rect|else)\b/,
  };
  const openerRe = OPENER[kind];
  if (openerRe) {
    let depth = 0;
    lines.forEach((raw, i) => {
      const t = raw.trim();
      if (!t || t.startsWith('%%')) return;
      if (openerRe.test(t)) depth += 1;
      else if (t === 'end') {
        depth -= 1;
        if (depth < 0) {
          errors.push({ line: i + 1, msg: '多余的 end：没有对应的 subgraph / loop / alt' });
          depth = 0;
        }
      }
    });
    if (depth > 0) errors.push({ line: lines.length, msg: `有 ${depth} 个块未闭合（缺少 end）` });
  }

  // 常见书写错误
  lines.forEach((raw, i) => {
    const t = raw.trim();
    if (!t || t.startsWith('%%')) return;
    if (kind === 'flow') {
      const empty = /\[\s*\]|\(\s*\)|\{\s*\}/.test(t);
      if (empty) warnings.push({ line: i + 1, msg: '存在空标签的节点' });
      const unquotedParen = /\[[^\]"]*\([^\]"]*\]/.test(t) && !/\["/.test(t);
      if (unquotedParen) warnings.push({ line: i + 1, msg: '标签内含圆括号但未加引号，部分渲染器会解析失败' });
      if (/-->\s*$/.test(t)) errors.push({ line: i + 1, msg: '箭头缺少目标节点' });
    }
    if (kind === 'sequence') {
      if (/^\s*participant\s+\S+\s*$/.test(t) === false && /participant\s*$/.test(t)) {
        errors.push({ line: i + 1, msg: 'participant 缺少名称' });
      }
      if (/->>\s*$/.test(t) || /-->>\s*$/.test(t)) errors.push({ line: i + 1, msg: '消息箭头缺少接收方或内容' });
    }
    if (kind === 'gantt' && /\d{4}-\d{2}-\d{2}/.test(t)) {
      if (/:\s*\d{4}-\d{1,2}-\d{1,2}/.test(t) && !/:\s*\w+,\s*\d{4}-\d{2}-\d{2}/.test(t)) {
        warnings.push({ line: i + 1, msg: '日期建议使用 YYYY-MM-DD 两位月份格式' });
      }
    }
    if (kind === 'class' && /<\|\-\-/.test(t) === false && /<\|\-/.test(t)) {
      warnings.push({ line: i + 1, msg: '继承箭头建议写全为 <|--' });
    }
  });

  // 统计
  const nodeRe = /(?:^|[\s>])([A-Za-z_\u4e00-\u9fa5][\w\u4e00-\u9fa5-]*)\s*(\[\(|\[\[|\[|\(\(|\(|\{\{|\{|>)/g;
  const ids = new Set();
  let m;
  while ((m = nodeRe.exec(text))) ids.add(m[1]);
  const edgeCount = (text.match(/-->|-\.->|==>|->>|-->>/g) || []).length;

  return {
    ok: errors.length === 0,
    kind,
    errors,
    warnings,
    stats: { lines: lines.length, nodeLikeIds: ids.size, edgeCount },
  };
}

/* -------------------------------- 质量评分 -------------------------------- */

export function qualityReport(model) {
  const issues = [];
  let score = 100;
  const metrics = {};

  const penalize = (n, msg) => {
    score -= n;
    issues.push({ level: n >= 8 ? 'high' : n >= 4 ? 'mid' : 'low', msg, cost: n });
  };

  if (model.kind === 'flow' || model.kind === 'state') {
    const n = model.nodes.length;
    const e = model.edges.length;
    metrics.nodes = n;
    metrics.edges = e;
    metrics.density = n ? +(e / n).toFixed(2) : 0;

    if (n > 30) penalize(12, `节点 ${n} 个，超出单图舒适上限（30），建议按子域拆图`);
    else if (n > 20) penalize(5, `节点 ${n} 个偏多，可考虑合并同层节点`);

    const longLabels = model.nodes.filter((x) => x.label.length > 24);
    if (longLabels.length) penalize(Math.min(10, longLabels.length * 2), `${longLabels.length} 个节点标签超过 24 字，渲染后会换行挤压`);

    const isolated = model.nodes.filter(
      (x) => !model.edges.some((ed) => ed.from === x.id || ed.to === x.id),
    );
    if (isolated.length) penalize(Math.min(9, isolated.length * 3), `${isolated.length} 个孤立节点（无任何连线）：${isolated.map((x) => x.label).slice(0, 3).join('、')}`);

    const outDeg = new Map();
    for (const ed of model.edges) outDeg.set(ed.from, (outDeg.get(ed.from) || 0) + 1);
    const maxFan = Math.max(0, ...outDeg.values());
    metrics.maxFanout = maxFan;
    if (maxFan > 5) penalize(6, `存在扇出 ${maxFan} 的节点，连线会明显交叉，建议加中间层`);

    const hasDecision = model.nodes.some((x) => x.shape === 'diamond');
    if (model.kind === 'flow' && !hasDecision && n > 5) {
      penalize(3, '流程中没有任何判断节点（菱形），确认是否缺少分支');
    }
    const diamonds = model.nodes.filter((x) => x.shape === 'diamond');
    for (const d of diamonds) {
      const outs = model.edges.filter((e2) => e2.from === d.id);
      if (outs.length < 2) penalize(4, `判断节点「${d.label}」只有 ${outs.length} 条出边，缺少分支`);
      if (outs.length > 3) penalize(4, `判断节点「${d.label}」有 ${outs.length} 条出边，超过 3 条可读性差`);
      const unlabeled = outs.filter((e2) => !e2.label);
      if (outs.length >= 2 && unlabeled.length) {
        penalize(3, `判断节点「${d.label}」有 ${unlabeled.length} 条出边未标注条件`);
      }
    }
    const longEdgeLabels = model.edges.filter((x) => x.label && x.label.length > 10);
    if (longEdgeLabels.length) penalize(Math.min(6, longEdgeLabels.length * 2), `${longEdgeLabels.length} 条连线标签超过 10 字，会挤压连线间距`);

    if (model.groups.length === 0 && n >= 12) {
      penalize(3, '节点较多但未分组，建议用 subgraph 划分职责边界');
    }
    metrics.groups = model.groups.length;
    metrics.depth = estimateDepth(model);
    if (metrics.depth > 7) penalize(4, `层级深度 ${metrics.depth}，链条过长，建议合并相邻步骤或拆图`);
  }

  if (model.kind === 'sequence') {
    const p = model.participants.length;
    const s = countSteps(model.steps);
    metrics.participants = p;
    metrics.steps = s;
    if (p > 8) penalize(8, `参与者 ${p} 个，横向会非常宽，建议合并同类参与者`);
    if (s > 24) penalize(6, `交互 ${s} 步，建议只保留关键路径`);
    const empty = [];
    walkSteps(model.steps, (x) => {
      if (x.type === 'message' && !x.text) empty.push(x);
    });
    if (empty.length) penalize(Math.min(8, empty.length * 3), `${empty.length} 条消息没有说明文字`);
  }

  if (model.kind === 'gantt') {
    const t = model.tasks.length;
    metrics.tasks = t;
    if (t > 30) penalize(6, `任务 ${t} 条，建议按里程碑聚合`);
    const neg = model.tasks.filter((x) => x.offset < 0);
    if (neg.length) penalize(10, `${neg.length} 个任务开始时间为负偏移，时间轴会错位`);
    const zero = model.tasks.filter((x) => !x.milestone && x.duration <= 0);
    if (zero.length) penalize(5, `${zero.length} 个任务工期为 0，请改为里程碑`);
  }

  if (model.kind === 'pie') {
    const total = model.slices.reduce((a, b) => a + b.value, 0);
    const tiny = model.slices.filter((x) => x.value / total < 0.03);
    if (tiny.length) penalize(Math.min(9, tiny.length * 3), `${tiny.length} 个扇区占比 <3%，建议合并为「其他」`);
    if (model.slices.length > 8) penalize(5, '扇区超过 8 个，建议改用条形图');
  }

  if (model.kind === 'xy') {
    if (model.series.length > 4) penalize(6, '系列超过 4 条，颜色难以区分');
    const flat = model.series.flatMap((x) => x.values);
    if (Math.max(...flat) / Math.max(1e-9, Math.min(...flat.filter((v) => v !== 0), Infinity)) > 1000) {
      penalize(3, '数值跨度过大，建议使用对数轴或拆图');
    }
  }

  if (model.kind === 'mindmap') {
    const c = countMindmap(model.root);
    metrics.nodes = c;
    if (c > 45) penalize(8, `节点 ${c} 个，思维导图会过于密集`);
    const depth = mindmapDepth(model.root);
    if (depth > 5) penalize(5, `层级 ${depth} 层，建议压缩到 4 层以内`);
  }

  if (model.kind === 'timeline' && model.events.length > 10) {
    penalize(5, '事件超过 10 个，卡片会重叠，建议合并同类事件');
  }

  if (model.kind === 'quadrant') {
    const clustered = model.points.filter((p) => Math.hypot(p.x - 0.5, p.y - 0.5) < 0.08);
    if (clustered.length) penalize(4, `${clustered.length} 个点紧贴中心线，象限归属不明确`);
  }

  const total = Math.max(0, Math.min(100, score));
  return {
    score: total,
    grade: total >= 90 ? 'A' : total >= 78 ? 'B' : total >= 65 ? 'C' : 'D',
    metrics,
    issues,
    verdict:
      total >= 90
        ? '结构清晰，可直接交付'
        : total >= 78
          ? '基本可用，建议处理中高风险项'
          : total >= 65
            ? '存在明显可读性问题，建议重构结构'
            : '结构问题较多，建议重新梳理信息层级',
  };
}

function countSteps(steps) {
  let n = 0;
  for (const s of steps) {
    if (s.type === 'fragment') n += countSteps(s.steps);
    else n += 1;
  }
  return n;
}

function walkSteps(steps, fn) {
  for (const s of steps) {
    fn(s);
    if (s.type === 'fragment') walkSteps(s.steps, fn);
  }
}

function estimateDepth(model) {
  const rank = rankNodes(model.nodes, model.edges);
  return Math.max(0, ...rank.values()) + 1;
}

function countMindmap(root) {
  if (!root) return 0;
  return 1 + root.children.reduce((a, c) => a + countMindmap(c), 0);
}

function mindmapDepth(n) {
  if (!n) return 0;
  if (!n.children.length) return 1;
  return 1 + Math.max(...n.children.map(mindmapDepth));
}
