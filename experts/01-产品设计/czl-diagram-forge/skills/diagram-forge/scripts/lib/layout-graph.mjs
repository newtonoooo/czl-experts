/**
 * layout-graph.mjs — 分层图布局引擎（自研）
 *
 * 步骤：环检测 → 最长路径分层 → 重心法排序 → 正交路由 → 方向变换。
 * 适用于流程图、状态图、类图、ER 图的骨架布局。
 */

const DEFAULTS = {
  layerGap: 56,
  nodeGap: 34,
  margin: 28,
  groupPad: 18,
  sweeps: 4,
};

/**
 * @param {Array<{id:string,w:number,h:number,group?:string}>} nodes
 * @param {Array<{from:string,to:string}>} edges
 * @param {{direction?:string,groups?:Array}} opts
 */
export function layoutLayered(nodes, edges, opts = {}) {
  const o = { ...DEFAULTS, ...opts };
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const idx = new Map(nodes.map((n, i) => [n.id, i]));

  const valid = edges.filter((e) => byId.has(e.from) && byId.has(e.to) && e.from !== e.to);
  const backEdges = detectBackEdges(nodes, valid);

  const fwd = valid.filter((e) => !backEdges.has(e));
  const rank = assignRanks(nodes, fwd, idx);

  // 同层内的初始顺序：先按分组聚拢，再按声明顺序
  const groupOf = new Map();
  for (const n of nodes) groupOf.set(n.id, n.group || '');

  const ranks = [];
  for (const n of nodes) {
    const r = rank.get(n.id) || 0;
    (ranks[r] ||= []).push(n.id);
  }
  for (let r = 0; r < ranks.length; r += 1) {
    if (!ranks[r]) ranks[r] = [];
    ranks[r].sort((a, b) => {
      const ga = groupOf.get(a);
      const gb = groupOf.get(b);
      if (ga !== gb) return ga < gb ? -1 : 1;
      return idx.get(a) - idx.get(b);
    });
  }

  orderByBarycenter(ranks, fwd, o.sweeps);

  // 沿 rank 轴的尺寸（TB 下为高度）
  const rankSizes = ranks.map((ids) =>
    ids.reduce((mx, id) => Math.max(mx, byId.get(id).h), 0),
  );
  const crossSizes = ranks.map((ids) => {
    const ws = ids.map((id) => byId.get(id).w);
    return ws.reduce((a, b) => a + b, 0) + Math.max(0, ids.length - 1) * o.nodeGap;
  });
  const maxCross = Math.max(0, ...crossSizes);

  const pos = new Map();
  let cursor = o.margin;
  for (let r = 0; r < ranks.length; r += 1) {
    const ids = ranks[r];
    let x = o.margin + (maxCross - crossSizes[r]) / 2;
    for (const id of ids) {
      const n = byId.get(id);
      const y = cursor + (rankSizes[r] - n.h) / 2;
      pos.set(id, { x, y, w: n.w, h: n.h, rank: r });
      x += n.w + o.nodeGap;
    }
    cursor += rankSizes[r] + o.layerGap;
  }

  const routes = [];
  const globalMinX = Math.min(...[...pos.values()].map((p) => p.x));
  const globalMaxX = Math.max(...[...pos.values()].map((p) => p.x + p.w));
  // 跨层与回边统一走右侧通道，避免压住标题区
  let sideChannel = globalMaxX + 26;

  valid.forEach((e, i) => {
    const a = pos.get(e.from);
    const b = pos.get(e.to);
    if (!a || !b) return;
    const span = Math.abs(b.rank - a.rank);
    let pts;
    if (a.rank === b.rank) {
      // 同层：走右侧通道绕行
      const cx = Math.max(a.x + a.w, b.x + b.w) + 22 + (i % 2) * 12;
      const y1 = a.y + a.h / 2;
      const y2 = b.y + b.h / 2;
      pts = [
        [a.x + a.w, y1],
        [cx, y1],
        [cx, y2],
        [b.x + b.w, y2],
      ];
    } else if (b.rank < a.rank) {
      // 回边：从右侧绕回上层
      const cx = Math.max(a.x + a.w, b.x + b.w) + 26 + (i % 3) * 10;
      pts = [
        [a.x + a.w, a.y + a.h / 2],
        [cx, a.y + a.h / 2],
        [cx, b.y + b.h / 2],
        [b.x + b.w, b.y + b.h / 2],
      ];
    } else if (span === 1) {
      const yMid = (a.y + a.h + b.y) / 2;
      const x1 = a.x + a.w / 2;
      const x2 = b.x + b.w / 2;
      pts = Math.abs(x1 - x2) < 0.8
        ? [[x1, a.y + a.h], [x2, b.y]]
        : [[x1, a.y + a.h], [x1, yMid], [x2, yMid], [x2, b.y]];
    } else {
      // 跨层：走左侧通道，避免穿越中间层节点
      sideChannel += 12;
      const cx = sideChannel;
      const yStart = a.y + a.h;
      const yEnd = b.y;
      const gapY1 = yStart + o.layerGap * 0.45;
      const gapY2 = yEnd - o.layerGap * 0.45;
      const x1 = a.x + a.w / 2;
      const x2 = b.x + b.w / 2;
      pts = [
        [x1, yStart],
        [x1, gapY1],
        [cx, gapY1],
        [cx, gapY2],
        [x2, gapY2],
        [x2, yEnd],
      ];
    }
    routes.push({ ...e, pts, span, sameRank: a.rank === b.rank });
  });

  // 分组包围盒
  const groupBoxes = [];
  const groups = o.groups || [];
  for (const g of groups) {
    const members = g.members.filter((id) => pos.has(id));
    if (!members.length) continue;
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    for (const id of members) {
      const p = pos.get(id);
      x0 = Math.min(x0, p.x);
      y0 = Math.min(y0, p.y);
      x1 = Math.max(x1, p.x + p.w);
      y1 = Math.max(y1, p.y + p.h);
    }
    groupBoxes.push({
      id: g.id,
      label: g.label,
      x: x0 - o.groupPad,
      y: y0 - o.groupPad - 8,
      w: x1 - x0 + o.groupPad * 2,
      h: y1 - y0 + o.groupPad * 2 + 8,
    });
  }

  // 归一化到正坐标
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of pos.values()) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x + p.w);
    maxY = Math.max(maxY, p.y + p.h);
  }
  for (const g of groupBoxes) {
    minX = Math.min(minX, g.x);
    minY = Math.min(minY, g.y);
    maxX = Math.max(maxX, g.x + g.w);
    maxY = Math.max(maxY, g.y + g.h);
  }
  // 连线通道可能超出节点包围盒，需一并纳入画布范围
  for (const r of routes) {
    for (const [x, y] of r.pts) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  const dx = o.margin - minX;
  const dy = o.margin - minY;
  for (const p of pos.values()) {
    p.x += dx;
    p.y += dy;
  }
  for (const g of groupBoxes) {
    g.x += dx;
    g.y += dy;
  }
  for (const r of routes) {
    r.pts = r.pts.map(([x, y]) => [x + dx, y + dy]);
  }

  const width = maxX - minX + o.margin * 2;
  const height = maxY - minY + o.margin * 2;

  return { pos, routes, groupBoxes, width, height, ranks, rankOf: rank };
}

/**
 * 结构画像：用于自动选择排版方向。
 * 长链条（层数多、每层窄）横排更好看；宽扇形（层少、每层宽）竖排更好看。
 */
export function rankNodes(nodes, edges) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const valid = edges.filter((e) => byId.has(e.from) && byId.has(e.to) && e.from !== e.to);
  const back = detectBackEdges(nodes, valid);
  return assignRanks(nodes, valid.filter((e) => !back.has(e)), new Map());
}

export function graphProfile(nodes, edges) {
  const rank = rankNodes(nodes, edges);
  const counts = new Map();
  for (const n of nodes) {
    const r = rank.get(n.id) || 0;
    counts.set(r, (counts.get(r) || 0) + 1);
  }
  return {
    depth: Math.max(1, counts.size),
    maxWidth: Math.max(0, ...counts.values()),
  };
}

/** 依据结构画像给出默认方向 */
export function autoDirection(profile) {
  if (profile.depth >= 6 && profile.maxWidth <= 3) return 'LR';
  if (profile.maxWidth >= 5 && profile.depth <= 4) return 'TB';
  return profile.depth > profile.maxWidth * 1.6 ? 'LR' : 'TB';
}

/* ------------------------------- 方向变换 --------------------------------- *//** 把 TB 布局变换到目标方向，返回新的 pos/routes/尺寸 */
export function applyDirection(result, direction, nodeSizes) {
  const dir = direction || 'TB';
  if (dir === 'TB') return result;

  const { pos, routes, groupBoxes, width, height } = result;
  const outPos = new Map();
  const outRoutes = [];
  const outGroups = [];
  let W = width;
  let H = height;

  const mapPoint = (x, y, p) => {
    if (dir === 'LR') return [y, x];
    if (dir === 'BT') return [x, H - y];
    if (dir === 'RL') return [W - x, y];
    return [x, y];
  };

  for (const [id, p] of pos) {
    if (dir === 'LR') {
      outPos.set(id, { x: p.y, y: p.x, w: p.h, h: p.w, rank: p.rank });
    } else if (dir === 'BT') {
      outPos.set(id, { x: p.x, y: H - p.y - p.h, w: p.w, h: p.h, rank: p.rank });
    } else {
      outPos.set(id, { x: W - p.x - p.w, y: p.y, w: p.w, h: p.h, rank: p.rank });
    }
  }
  for (const g of groupBoxes) {
    if (dir === 'LR') outGroups.push({ ...g, x: g.y, y: g.x, w: g.h, h: g.w });
    else if (dir === 'BT') outGroups.push({ ...g, y: H - g.y - g.h });
    else outGroups.push({ ...g, x: W - g.x - g.w });
  }
  for (const r of routes) {
    const pts = r.pts.map(([x, y]) => mapPoint(x, y));
    outRoutes.push({ ...r, pts });
  }
  if (dir === 'LR') {
    W = height;
    H = width;
  }
  return { pos: outPos, routes: outRoutes, groupBoxes: outGroups, width: W, height: H, ranks: result.ranks, rankOf: result.rankOf };
}

/* --------------------------------- 内部步骤 -------------------------------- */

function detectBackEdges(nodes, edges) {
  const adj = new Map(nodes.map((n) => [n.id, []]));
  for (const e of edges) adj.get(e.from)?.push(e);
  const state = new Map();
  const back = new Set();
  const stack = [];

  const dfs = (id) => {
    state.set(id, 1);
    for (const e of adj.get(id) || []) {
      const s = state.get(e.to) || 0;
      if (s === 1) back.add(e);
      else if (s === 0) dfs(e.to);
    }
    state.set(id, 2);
    stack.pop();
  };
  for (const n of nodes) if ((state.get(n.id) || 0) === 0) dfs(n.id);
  return back;
}

function assignRanks(nodes, edges, idx) {
  const indeg = new Map(nodes.map((n) => [n.id, 0]));
  const adj = new Map(nodes.map((n) => [n.id, []]));
  for (const e of edges) {
    if (!indeg.has(e.from) || !indeg.has(e.to)) continue;
    adj.get(e.from).push(e.to);
    indeg.set(e.to, indeg.get(e.to) + 1);
  }
  const rank = new Map(nodes.map((n) => [n.id, 0]));
  const queue = nodes.filter((n) => indeg.get(n.id) === 0).map((n) => n.id);
  const deg = new Map(indeg);
  while (queue.length) {
    const id = queue.shift();
    for (const to of adj.get(id) || []) {
      rank.set(to, Math.max(rank.get(to) || 0, (rank.get(id) || 0) + 1));
      deg.set(to, deg.get(to) - 1);
      if (deg.get(to) === 0) queue.push(to);
    }
  }
  return rank;
}

function orderByBarycenter(ranks, edges, sweeps) {
  const pred = new Map();
  const succ = new Map();
  for (const e of edges) {
    if (!pred.has(e.to)) pred.set(e.to, []);
    pred.get(e.to).push(e.from);
    if (!succ.has(e.from)) succ.set(e.from, []);
    succ.get(e.from).push(e.to);
  }
  const positionOf = () => {
    const p = new Map();
    ranks.forEach((ids, r) => ids.forEach((id, i) => p.set(id, { r, i })));
    return p;
  };

  for (let s = 0; s < sweeps; s += 1) {
    const down = s % 2 === 0;
    const order = down ? ranks.map((_, i) => i) : ranks.map((_, i) => ranks.length - 1 - i);
    for (const r of order) {
      const ids = ranks[r];
      if (ids.length < 2) continue;
      const posMap = positionOf();
      const keyed = ids.map((id) => {
        const rel = down ? pred.get(id) || [] : succ.get(id) || [];
        const vals = rel.map((x) => posMap.get(x)).filter(Boolean).map((p) => p.i);
        const bc = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : posMap.get(id).i;
        return { id, bc, orig: posMap.get(id).i };
      });
      keyed.sort((a, b) => (a.bc === b.bc ? a.orig - b.orig : a.bc - b.bc));
      ranks[r] = keyed.map((k) => k.id);
    }
  }
}
