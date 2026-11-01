#!/usr/bin/env node
/**
 * dg.mjs — 图表工坊命令行入口
 *
 * 用法：
 *   node dg.mjs render <model.json> [--out 目录] [--theme 主题] [--format svg,html,mmd,ascii]
 *   node dg.mjs check  <file.mmd|model.json>
 *   node dg.mjs review <model.json>
 *   node dg.mjs themes
 *   node dg.mjs new <kind>
 *   node dg.mjs spec
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { normalizeModel, KINDS, KIND_LABEL } from './lib/model.mjs';
import { renderSvg, renderHtml, renderAscii, toMermaid, buildScene } from './lib/render.mjs';
import { THEMES, THEME_NAMES, DEFAULT_THEME } from './lib/themes.mjs';
import { lintMermaidSource, qualityReport } from './lib/lint.mjs';

const VERSION = '1.0.0';
const HERE = path.dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const pos = [];
  const flags = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith('--')) {
        flags[key] = next;
        i += 1;
      } else flags[key] = true;
    } else pos.push(a);
  }
  return { pos, flags };
}

function fail(msg, code = 1) {
  console.error(`✖ ${msg}`);
  process.exit(code);
}

function readJson(p) {
  let raw;
  try {
    raw = fs.readFileSync(p, 'utf-8');
  } catch (e) {
    fail(`无法读取文件：${p}（${e.code || e.message}）`);
  }
  try {
    return JSON.parse(raw);
  } catch (e) {
    fail(`JSON 解析失败：${p}\n  ${e.message}`);
  }
}

function slugify(s) {
  const base = String(s || 'diagram')
    .trim()
    .replace(/[\\/:*?"<>|\s]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return base || 'diagram';
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

/* ---------------------------------- render --------------------------------- */

function cmdRender(pos, flags) {
  const input = pos[1];
  if (!input) fail('缺少模型文件参数。用法：dg.mjs render <model.json>');

  const raw = readJson(input);
  const { model, errors, warnings } = normalizeModel(raw);

  for (const w of warnings) console.warn(`⚠ ${w}`);
  if (errors.length) {
    console.error('✖ 模型校验未通过：');
    for (const e of errors) console.error(`   • ${e}`);
    process.exit(2);
  }

  const themeName = flags.theme || model.theme || DEFAULT_THEME;
  if (!THEMES[themeName]) fail(`未知主题 "${themeName}"，可用：${THEME_NAMES.join(', ')}`, 2);

  const formats = String(flags.format || 'svg,mmd,html')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  const outDir = flags.out || path.join(process.cwd(), 'out');
  ensureDir(outDir);
  const slug = flags.name ? slugify(flags.name) : slugify(model.title || path.basename(input, path.extname(input)));

  const written = [];
  const write = (suffix, content) => {
    const p = path.join(outDir, `${slug}${suffix}`);
    fs.writeFileSync(p, content, 'utf-8');
    written.push(p);
    return p;
  };

  let scene = null;
  if (formats.includes('svg') || formats.includes('html')) {
    scene = buildScene(model, THEMES[themeName]);
  }

  if (formats.includes('svg')) {
    write('.svg', renderSvg(model, themeName, { version: VERSION, padding: 8 }));
  }
  if (formats.includes('html')) {
    write('.html', renderHtml(model, { theme: themeName, themes: flags['all-themes'] ? THEME_NAMES : undefined }));
  }
  if (formats.includes('mmd')) {
    write('.mmd', `${toMermaid(model)}\n`);
  }
  if (formats.includes('ascii')) {
    write('.txt', `${renderAscii(model)}\n`);
  }
  if (formats.includes('model')) {
    write('.model.json', `${JSON.stringify(model, null, 2)}\n`);
  }

  const q = qualityReport(model);
  console.log(`✅ 渲染完成 · ${KIND_LABEL[model.kind]} · 主题 ${themeName}`);
  console.log(`   画布 ${Math.round(scene ? scene.width : 0)} × ${Math.round(scene ? scene.height : 0)} px`);
  console.log(`   质量分 ${q.score}（${q.grade}）· ${q.verdict}`);
  for (const p of written) console.log(`   → ${p}`);
  if (flags.json) console.log(JSON.stringify({ ok: true, files: written, quality: q }, null, 2));
  return 0;
}

/* ---------------------------------- check ---------------------------------- */

function cmdCheck(pos, flags) {
  const input = pos[1];
  if (!input) fail('缺少文件参数。用法：dg.mjs check <file.mmd|model.json>');

  const isJson = input.toLowerCase().endsWith('.json');
  if (isJson) {
    const raw = readJson(input);
    const { model, errors, warnings } = normalizeModel(raw);
    if (errors.length) {
      console.error(`✖ 模型校验失败（${errors.length} 项）`);
      for (const e of errors) console.error(`   • ${e}`);
    }
    for (const w of warnings) console.warn(`⚠ ${w}`);
    if (model) {
      const q = qualityReport(model);
      console.log(`✅ 模型校验通过 · ${KIND_LABEL[model.kind]} · 质量分 ${q.score}（${q.grade}）`);
      for (const it of q.issues) console.log(`   [${it.level}] ${it.msg}（-${it.cost}）`);
    }
    return errors.length ? 2 : 0;
  }

  const text = fs.readFileSync(input, 'utf-8');
  const r = lintMermaidSource(text);
  if (r.errors.length) {
    console.error(`✖ 发现 ${r.errors.length} 处错误`);
    for (const e of r.errors) console.error(`   第 ${e.line} 行：${e.msg}`);
  }
  for (const w of r.warnings) console.warn(`⚠ 第 ${w.line} 行：${w.msg}`);
  if (r.ok) console.log(`✅ 语法检查通过 · 类型 ${r.kind} · ${r.stats.lines} 行 · ${r.stats.edgeCount} 条连线`);
  return r.ok ? 0 : 1;
}

/* ---------------------------------- review --------------------------------- */

function cmdReview(pos) {
  const input = pos[1];
  if (!input) fail('缺少模型文件参数。用法：dg.mjs review <model.json>');
  const raw = readJson(input);
  const { model, errors, warnings } = normalizeModel(raw);
  for (const w of warnings) console.warn(`⚠ ${w}`);
  if (errors.length) {
    console.error('✖ 模型不合法，无法评分：');
    for (const e of errors) console.error(`   • ${e}`);
    process.exit(2);
  }
  const q = qualityReport(model);
  console.log(`图表类型：${KIND_LABEL[model.kind]}`);
  console.log(`质量评分：${q.score} / 100（${q.grade}）— ${q.verdict}`);
  console.log('结构指标：');
  for (const [k, v] of Object.entries(q.metrics)) console.log(`   ${k} = ${v}`);
  if (q.issues.length) {
    console.log('改进项：');
    for (const it of q.issues) console.log(`   [${it.level}] ${it.msg}（-${it.cost} 分）`);
  } else console.log('改进项：无');
  return 0;
}

/* ---------------------------------- 其他 ----------------------------------- */

function cmdThemes() {
  console.log('可用主题：');
  for (const name of THEME_NAMES) {
    const t = THEMES[name];
    console.log(`  ${name.padEnd(12)} ${t.label.padEnd(8)} ${t.mode === 'dark' ? '深色' : '浅色'}  bg=${t.bg}  accent=${t.accent}`);
  }
  console.log(`\n默认主题：${DEFAULT_THEME}`);
  return 0;
}

function cmdNew(pos) {
  const kind = pos[1];
  if (!kind || !KINDS.includes(kind)) {
    fail(`用法：dg.mjs new <${KINDS.join('|')}>`);
  }
  const tplDir = path.join(HERE, '..', 'templates');
  const map = {
    flow: 'flow-approval.json', state: 'state-order.json', class: 'class-service.json',
    er: 'er-commerce.json', sequence: 'sequence-api.json', gantt: 'gantt-sprint.json',
    mindmap: 'mindmap-plan.json', timeline: 'timeline-release.json', pie: 'pie-budget.json',
    quadrant: 'quadrant-priority.json', xy: 'xy-growth.json',
  };
  const f = path.join(tplDir, map[kind]);
  if (!fs.existsSync(f)) fail(`模板缺失：${f}`);
  console.log(fs.readFileSync(f, 'utf-8'));
  return 0;
}

function cmdSpec() {
  const spec = {
    version: VERSION,
    kinds: KINDS.map((k) => ({ kind: k, label: KIND_LABEL[k] })),
    common: ['kind', 'title', 'subtitle', 'theme', 'direction(TB|LR|BT|RL)', 'footnote'],
    fields: {
      flow: ['nodes[{id,label,shape,role,note,emphasis}]', 'edges[{from,to,label,style,arrow}]', 'groups[{id,label,members[]}]'],
      state: '同 flow，shape 默认 round',
      class: ['classes[{id,name,stereotype,role,members[{text,kind}]}]', 'relations[{from,to,kind,label,fromCard,toCard}]'],
      er: ['entities[{id,name,role,attributes[{name,type,key}]}]', 'relations[{from,to,card,label}]'],
      sequence: ['participants[{id,label,kind,role}]', 'steps[{type:message|note|fragment|end,...}]'],
      gantt: ['sections[{name,tasks[{name,start,duration,milestone,critical,owner}]}]', 'tasks[] 可选'],
      mindmap: ['root{label,note,children[]}'],
      timeline: ['events[{date,label,detail}]'],
      pie: ['slices[{label,value}]'],
      quadrant: ['xAxis{low,high}', 'yAxis{low,high}', 'quadrants[4]', 'points[{label,x,y}]'],
      xy: ['xLabels[]', 'series[{name,values[],type:bar|line|area}]', 'unit'],
    },
    shapes: ['rect', 'round', 'stadium', 'circle', 'diamond', 'hex', 'cylinder', 'parallelogram', 'subroutine', 'note'],
    roles: ['primary', 'decision', 'data', 'external', 'success', 'danger', 'neutral'],
    themes: THEME_NAMES,
  };
  console.log(JSON.stringify(spec, null, 2));
  return 0;
}

function usage() {
  console.log(`czl-diagram-forge v${VERSION} — 图表工坊

命令：
  render <model.json>   生成 SVG / HTML / Mermaid / ASCII
       --out <dir>        输出目录（默认 ./out）
       --theme <name>     主题（默认 ${DEFAULT_THEME}）
       --format <list>    svg,html,mmd,ascii,model
       --name <slug>      输出文件名
       --all-themes       HTML 内嵌全部主题
  check <file>          校验 .mmd 语法或 .json 模型
  review <model.json>   输出质量评分与改进项
  themes                列出主题
  new <kind>            打印对应类型的模板
  spec                  打印模型规范
`);
  return 0;
}

const { pos, flags } = parseArgs(process.argv.slice(2));
const cmd = pos[0];
const table = { render: cmdRender, check: cmdCheck, review: cmdReview, themes: cmdThemes, new: cmdNew, spec: cmdSpec };
if (!cmd || flags.help) {
  usage();
  process.exit(0);
}
const fn = table[cmd];
if (!fn) fail(`未知命令 "${cmd}"。可用：${Object.keys(table).join(', ')}`);
process.exit(fn(pos, flags));
