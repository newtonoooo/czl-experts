/**
 * themes.mjs — 主题令牌表
 *
 * 每个主题提供一套语义令牌 + 一组角色色板。渲染器只消费令牌，
 * 不硬编码颜色，因此切换主题不需要重新布局。
 */

export const ROLE_KEYS = ['primary', 'decision', 'data', 'external', 'success', 'danger', 'neutral'];

const L = (name, label, t) => ({ name, label, mode: 'light', ...t });
const D = (name, label, t) => ({ name, label, mode: 'dark', ...t });

export const THEMES = {
  graphite: L('graphite', '石墨·浅', {
    bg: '#ffffff', surface: '#f5f7fa', surfaceAlt: '#eaeef4', fg: '#161a20', muted: '#67707d',
    line: '#8f99a6', border: '#d5dbe3', accent: '#2f6fed',
    palette: ['#2f6fed', '#c2740a', '#0e8f9b', '#7a4fd0', '#17874f', '#c8392f', '#5b6675'],
  }),
  paper: L('paper', '纸白·暖', {
    bg: '#fdfcf8', surface: '#f7f2e7', surfaceAlt: '#efe8d8', fg: '#2b2519', muted: '#7c7260',
    line: '#a99a80', border: '#e3d9c5', accent: '#b0521c',
    palette: ['#b0521c', '#8a6b12', '#2f7d68', '#7a4a86', '#4a7a1e', '#a83a34', '#6b6153'],
  }),
  ocean: L('ocean', '海雾·浅', {
    bg: '#f8fbfd', surface: '#eef5fa', surfaceAlt: '#e0edf6', fg: '#0f2231', muted: '#587083',
    line: '#93aec2', border: '#d1e2ee', accent: '#0a6ca3',
    palette: ['#0a6ca3', '#b06a10', '#12857f', '#5b57b8', '#1c7f45', '#bd3f34', '#5a6b78'],
  }),
  mint: L('mint', '薄荷·浅', {
    bg: '#f9fbfa', surface: '#eef7f1', surfaceAlt: '#e0f0e6', fg: '#0f2319', muted: '#557a66',
    line: '#9fc3b0', border: '#d3e8db', accent: '#0f8360',
    palette: ['#0f8360', '#a8680f', '#177f96', '#6a53b5', '#3f8a1d', '#bb3d38', '#5c6e64'],
  }),
  sand: L('sand', '砂砾·浅', {
    bg: '#fdfaf4', surface: '#f9f2e2', surfaceAlt: '#f1e7cf', fg: '#2b2313', muted: '#7e7051',
    line: '#bfae89', border: '#e7d9bc', accent: '#9c6a10',
    palette: ['#9c6a10', '#2f6f8f', '#7c5aa8', '#1c7f5c', '#b4532a', '#5f6b33', '#6d6455'],
  }),
  sakura: L('sakura', '樱粉·浅', {
    bg: '#fdf9fb', surface: '#faeff4', surfaceAlt: '#f4e2ea', fg: '#2c1621', muted: '#7d5a69',
    line: '#c6a2b2', border: '#eed7e0', accent: '#ad3765',
    palette: ['#ad3765', '#2f6fa8', '#8a5cb0', '#12805e', '#b06a14', '#5c6b7d', '#7a6470'],
  }),
  midnight: D('midnight', '午夜·深', {
    bg: '#12141a', surface: '#1b1f28', surfaceAlt: '#232935', fg: '#e9edf5', muted: '#96a1b2',
    line: '#46536a', border: '#2d3644', accent: '#6ea8fe',
    palette: ['#6ea8fe', '#e0a53c', '#4fc4d0', '#b58cff', '#57c98a', '#ef6f6f', '#8b97a8'],
  }),
  carbon: D('carbon', '碳灰·深', {
    bg: '#17181a', surface: '#212326', surfaceAlt: '#2a2d31', fg: '#edeff2', muted: '#9ba1a8',
    line: '#4b5158', border: '#33373c', accent: '#f0a92c',
    palette: ['#f0a92c', '#63b3ed', '#5ec9a8', '#c08cf0', '#8ec94e', '#ef6f6f', '#98a0a8'],
  }),
  nordic: D('nordic', '北境·深', {
    bg: '#0f1620', surface: '#17212d', surfaceAlt: '#1f2b39', fg: '#e6eef7', muted: '#8ea3ba',
    line: '#3a4f66', border: '#243140', accent: '#58c4dd',
    palette: ['#58c4dd', '#e0b070', '#7ad3c0', '#9d9bf0', '#6cc98a', '#e68080', '#8a9cae'],
  }),
  forest: D('forest', '深林·深', {
    bg: '#0f1714', surface: '#17221d', surfaceAlt: '#1e2c25', fg: '#e7f2ec', muted: '#89a89a',
    line: '#365144', border: '#1f2f28', accent: '#4ec9a0',
    palette: ['#4ec9a0', '#d9b26a', '#63bfd8', '#a48ce0', '#8dc45a', '#e07d7d', '#88a094'],
  }),
  plum: D('plum', '深紫·深', {
    bg: '#15111c', surface: '#1f1929', surfaceAlt: '#282036', fg: '#efe9f7', muted: '#a293bb',
    line: '#453a5c', border: '#2b2238', accent: '#b98bff',
    palette: ['#b98bff', '#e3ae62', '#6fc7d8', '#7f9bf0', '#7fce93', '#ec7f8f', '#948aa8'],
  }),
  slate: D('slate', '青岩·深', {
    bg: '#101317', surface: '#181d24', surfaceAlt: '#202730', fg: '#e9eef3', muted: '#92a1b0',
    line: '#3a4855', border: '#242d36', accent: '#7fb2e5',
    palette: ['#7fb2e5', '#d8a95f', '#5fc0b8', '#a08ce0', '#74c48a', '#e07d7d', '#8b98a6'],
  }),
};

export const DEFAULT_THEME = 'graphite';

export const THEME_NAMES = Object.keys(THEMES);

export function getTheme(name) {
  const t = THEMES[name];
  if (!t) {
    const err = new Error(`未知主题 "${name}"。可用主题：${THEME_NAMES.join(', ')}`);
    err.code = 'DG_THEME';
    throw err;
  }
  return t;
}

/** 角色 → 调色板索引 */
export function roleIndex(role) {
  const i = ROLE_KEYS.indexOf(String(role || 'primary').toLowerCase());
  return i < 0 ? 0 : i;
}

export function roleColor(theme, role) {
  return theme.palette[roleIndex(role)];
}

/** 生成 CSS 变量块（用于 SVG 内联样式或 HTML 主题切换） */
export function cssVars(theme) {
  const v = {
    '--dg-bg': theme.bg,
    '--dg-surface': theme.surface,
    '--dg-surface-alt': theme.surfaceAlt,
    '--dg-fg': theme.fg,
    '--dg-muted': theme.muted,
    '--dg-line': theme.line,
    '--dg-border': theme.border,
    '--dg-accent': theme.accent,
  };
  theme.palette.forEach((c, i) => {
    v[`--dg-p${i}`] = c;
  });
  return v;
}

export function cssVarBlock(theme, selector = ':root') {
  const v = cssVars(theme);
  const body = Object.entries(v).map(([k, val]) => `${k}:${val};`).join('');
  return `${selector}{${body}}`;
}
