#!/usr/bin/env node
/* check_report.js — 报告页自检（不打开浏览器也能查出 90% 的渲染问题）
 *
 * 做法：取出 index.html 里的脚本，在一个极简 DOM 桩里跑一遍，
 * 检查是否抛错、各图表容器是否真的产出了内容。
 *
 * 用法：node tools/check_report.js out/index.html
 * 退出码：0 通过 / 1 失败
 */
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
if (!file) {
  console.error('用法: node tools/check_report.js <report.html>');
  process.exit(1);
}
const html = fs.readFileSync(file, 'utf8');
if (!html.includes('<script>')) {
  console.error('失败：页面里没有脚本块');
  process.exit(1);
}
const code = html.split('<script>')[1].split('</script>')[0];

function makeEl(tag) {
  const el = {
    tagName: tag, children: [], className: '', style: {}, _html: '', _text: '',
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); },
    remove() {},
    setAttribute() {}, addEventListener() {},
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); },
    get outerHTML() { return this._html; },
    set outerHTML(v) { this._html = String(v); },
    get classList() { return { add() {}, remove() {}, toggle() {} }; },
  };
  return el;
}

const store = new Map();
const document = {
  getElementById(id) {
    if (!store.has(id)) store.set(id, makeEl('div'));
    return store.get(id);
  },
  createElement(tag) { return makeEl(tag); },
  querySelector() { return makeEl('div'); },
  addEventListener() {},
};

const sandbox = { document, console, window: {}, JSON, Math, Number, Date, Map, Set, Array, Object, String };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

let error = null;
try {
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { timeout: 10000 });
} catch (e) {
  error = e;
}

const checks = [];
const get = id => (store.get(id) || { _html: '', children: [] })._html || '';
const kids = id => (store.get(id) || { children: [] }).children.length;

checks.push(['脚本无异常', !error, error ? String(error && error.stack || error).slice(0, 400) : '']);
checks.push(['标题已填充', ((store.get('title') || {})._text || '').length > 0, '']);
checks.push(['KPI 卡片 >= 4', kids('kpis') >= 4, '实际 ' + kids('kpis')]);
checks.push(['净值图有 SVG', get('eqChart').includes('<svg'), '']);
checks.push(['回撤图有 SVG', get('ddChart').includes('<svg'), '']);
checks.push(['单笔盈亏图有 SVG', get('pnlChart').includes('<svg'), '']);
checks.push(['月度表有行或已隐藏', get('monChart').includes('<tr') || ((store.get('monCard') || {}).style || {}).display === 'none', '']);
checks.push(['成交表有行', get('trTable').includes('<tr'), '']);
checks.push(['页脚含声明', get('footer').length > 20, '']);

let bad = 0;
checks.forEach(([name, ok, extra]) => {
  if (!ok) bad++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? '  → ' + extra : ''}`);
});
console.log(bad === 0 ? '\n报告渲染自检：全部通过' : `\n报告渲染自检：${bad} 项失败`);
process.exit(bad === 0 ? 0 : 1);
