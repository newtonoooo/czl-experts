#!/usr/bin/env node
/**
 * selftest.mjs — 自检脚本
 *
 * 逐类型渲染全部模板，校验产物结构，输出可复现的测试结果。
 * 用法：node selftest.mjs [--out 目录]
 */

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

import { normalizeModel, KINDS } from '../lib/model.mjs';
import { renderSvg, renderHtml, renderAscii, toMermaid, buildScene } from '../lib/render.mjs';
import { THEME_NAMES, getTheme } from '../lib/themes.mjs';
import { lintMermaidSource, qualityReport } from '../lib/lint.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TPL = path.join(HERE, '..', '..', 'templates');
const args = process.argv.slice(2);
const outIdx = args.indexOf('--out');
const OUT = outIdx >= 0 ? args[outIdx + 1] : path.join(os.tmpdir(), 'dg-selftest');

const results = [];
let failed = 0;

function check(name, fn) {
  try {
    const detail = fn();
    results.push({ name, ok: true, detail: detail || '' });
  } catch (e) {
    failed += 1;
    results.push({ name, ok: false, detail: e.message });
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const files = fs.readdirSync(TPL).filter((f) => f.endsWith('.json')).sort();
const kindsSeen = new Set();

for (const f of files) {
  const raw = JSON.parse(fs.readFileSync(path.join(TPL, f), 'utf-8'));
  const { model, errors, warnings } = normalizeModel(raw);
  const slug = path.basename(f, '.json');

  check(`${slug} · 模型校验`, () => {
    assert(!errors.length, errors.join('; '));
    assert(model, '模型为空');
    kindsSeen.add(model.kind);
    return `${model.kind}${warnings.length ? ` · ${warnings.length} 条警告` : ''}`;
  });
  if (!model) continue;

  check(`${slug} · 场景构建`, () => {
    const s = buildScene(model, getTheme('graphite'));
    assert(s.width > 100 && s.height > 80, `画布过小 ${s.width}x${s.height}`);
    assert(s.items.length > 5, '绘制指令过少');
    return `${Math.round(s.width)}x${Math.round(s.height)} · ${s.items.length} ops`;
  });

  check(`${slug} · SVG 输出`, () => {
    const svg = renderSvg(model, 'graphite');
    assert(svg.startsWith('<!--'), '缺少生成标记');
    assert(svg.includes('<svg'), '缺少 svg 根元素');
    assert(!/NaN|undefined|Infinity/.test(svg), 'SVG 中出现 NaN/undefined');
    assert(svg.trim().endsWith('</svg>'), 'SVG 未闭合');
    const opened = (svg.match(/<g[\s>]/g) || []).length;
    const closed = (svg.match(/<\/g>/g) || []).length;
    assert(opened === closed, `g 标签不平衡 ${opened}/${closed}`);
    return `${(svg.length / 1024).toFixed(1)} KB`;
  });

  check(`${slug} · Mermaid 导出`, () => {
    const mmd = toMermaid(model);
    assert(mmd.length > 10, '导出内容为空');
    const first = mmd.split('\n').find((l) => l.trim() && !l.startsWith('%%'));
    assert(first, '缺少图表声明');
    const lint = lintMermaidSource(mmd);
    assert(lint.ok, `导出的 Mermaid 语法检查失败：${lint.errors.map((e) => `L${e.line} ${e.msg}`).join('; ')}`);
    return first.trim().slice(0, 40);
  });

  check(`${slug} · HTML 预览`, () => {
    const html = renderHtml(model, { theme: 'graphite' });
    assert(html.includes('<svg'), '缺少内联 SVG');
    assert(html.includes('dg-theme-btn'), '缺少主题切换按钮');
    assert(!/NaN|undefined/.test(html), 'HTML 中出现 NaN/undefined');
    return `${(html.length / 1024).toFixed(1)} KB`;
  });

  check(`${slug} · 纯文本输出`, () => {
    const txt = renderAscii(model);
    assert(txt && txt.length > 5, '文本输出为空');
    assert(!/NaN|undefined/.test(txt), '文本中出现 NaN/undefined');
    return `${txt.split('\n').length} 行`;
  });

  check(`${slug} · 质量评分`, () => {
    const q = qualityReport(model);
    assert(q.score >= 0 && q.score <= 100, '分数越界');
    return `${q.score}/${q.grade}`;
  });
}

// 全主题渲染
check('全主题渲染（11 类型 × 12 主题）', () => {
  let n = 0;
  for (const f of files) {
    const { model } = normalizeModel(JSON.parse(fs.readFileSync(path.join(TPL, f), 'utf-8')));
    if (!model) continue;
    for (const t of THEME_NAMES) {
      const svg = renderSvg(model, t);
      if (/NaN|undefined/.test(svg)) throw new Error(`${f} × ${t} 出现 NaN`);
      n += 1;
    }
  }
  return `${n} 次渲染全部通过`;
});

// 非法输入处理
check('非法输入：未知类型', () => {
  const r = normalizeModel({ kind: 'unknown' });
  assert(r.errors.length > 0, '未报错');
  return r.errors[0];
});
check('非法输入：悬空边', () => {
  const r = normalizeModel({ kind: 'flow', nodes: [{ id: 'a' }], edges: [{ from: 'a', to: 'zzz' }] });
  assert(r.errors.length > 0, '未报错');
  return r.errors[0];
});
check('非法输入：xLabels 与 values 长度不一致', () => {
  const r = normalizeModel({ kind: 'xy', xLabels: ['a', 'b'], series: [{ name: 's', values: [1] }] });
  assert(r.errors.length > 0, '未报错');
  return r.errors[0];
});
check('非法输入：空图', () => {
  const r = normalizeModel({ kind: 'flow', nodes: [] });
  assert(r.errors.length > 0, '未报错');
  return r.errors[0];
});

// 语法检查器
check('语法检查：合法 Mermaid', () => {
  const r = lintMermaidSource('flowchart TD\n  A["开始"] --> B{"判断"}\n  B -->|是| C["结束"]\n');
  assert(r.ok, r.errors.map((e) => e.msg).join('; '));
  return `kind=${r.kind}`;
});
check('语法检查：括号未闭合应报错', () => {
  const r = lintMermaidSource('flowchart TD\n  A["开始" --> B\n');
  assert(!r.ok, '未检出错误');
  return r.errors[0].msg;
});
check('语法检查：subgraph 未闭合应报错', () => {
  const r = lintMermaidSource('flowchart TD\n  subgraph g1\n  A --> B\n');
  assert(!r.ok, '未检出错误');
  return r.errors[0].msg;
});

// 覆盖度
check('模板覆盖全部图表类型', () => {
  const missing = KINDS.filter((k) => !kindsSeen.has(k));
  assert(missing.length === 0, `缺少模板：${missing.join(', ')}`);
  return `${kindsSeen.size}/${KINDS.length}`;
});

// 落盘
fs.mkdirSync(OUT, { recursive: true });
for (const f of files) {
  const { model } = normalizeModel(JSON.parse(fs.readFileSync(path.join(TPL, f), 'utf-8')));
  if (!model) continue;
  const slug = path.basename(f, '.json');
  fs.writeFileSync(path.join(OUT, `${slug}.svg`), renderSvg(model, 'graphite'), 'utf-8');
}

// 报告
const pad = (s, n) => (s + ' '.repeat(n)).slice(0, n);
console.log('');
console.log('图表工坊 · 自检报告');
console.log('='.repeat(78));
for (const r of results) {
  console.log(`${r.ok ? '✅' : '❌'} ${pad(r.name, 42)} ${r.detail}`);
}
console.log('='.repeat(78));
console.log(`共 ${results.length} 项检查，通过 ${results.length - failed} 项，失败 ${failed} 项`);
console.log(`SVG 产物目录：${OUT}`);
process.exit(failed ? 1 : 0);
