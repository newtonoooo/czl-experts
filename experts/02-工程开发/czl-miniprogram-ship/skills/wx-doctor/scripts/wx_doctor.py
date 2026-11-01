#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wx_doctor.py — 微信小程序工程体检与提审预检（纯标准库）

它读真实的工程文件，输出可贴进交付文档的结论。不做真机测试、不连微信后台。

子命令:
  scan      <项目>   静态体检：页面四件套、分包声明、tabBar、组件引用、隐私接口、密钥、外链域名
  budget    <项目>   体积预算：主包/各分包字节、占比、超限定位、大文件排行
  preflight <项目>   提审预检：scan + budget 汇总 + 提审材料清单 + 隐私采集清单
  scaffold  --spec <spec.json> --out <dir>   按规格生成可运行骨架

常用参数:
  --root <子目录>     手动指定小程序根目录（默认自动识别 miniprogramRoot / app.json 所在目录）
  --out <目录>        报告输出目录（默认 <项目>/docs/体检）
  --json <路径>       额外输出机器可读 JSON
  --quiet             只输出结论行，不打印逐条明细

退出码: 0 通过 / 1 有阻断项 / 2 参数或结构错误

体积口径说明：本工具按磁盘文件字节累加，不含开发者工具的上传压缩效果。
两者会有差异，以开发者工具「代码依赖分析」为准，本工具用于早期发现方向性问题。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

MAIN_LIMIT = 2 * 1024 * 1024          # 主包/单个分包上限（以微信官方「分包加载」文档为准）
TOTAL_LIMIT = 20 * 1024 * 1024        # 全部分包合计上限（同上，规则可能调整，需核实最新值）
BIG_FILE_LIMIT = 200 * 1024           # 单文件超过此值提醒
TABBAR_ICON_LIMIT = 40 * 1024         # tabBar 图标建议上限（以官方 app.json 文档为准）

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', 'miniprogram_npm', '.idea', '.vscode', 'dist', 'unpackage'}
CODE_EXT = {'.js', '.ts', '.wxml', '.wxss', '.json', '.wxs'}

# 需要在 app.json 的 requiredPrivateInfos 中声明的接口（以官方隐私接口文档为准）
REQUIRED_PRIVATE = {
    'getLocation': 'getLocation',
    'onLocationChange': 'onLocationChange',
    'startLocationUpdate': 'startLocationUpdate',
    'startLocationUpdateBackground': 'startLocationUpdateBackground',
    'chooseLocation': 'chooseLocation',
    'choosePoi': 'choosePoi',
    'chooseAddress': 'chooseAddress',
    'chooseInvoiceTitle': 'chooseInvoiceTitle',
    'getFuzzyLocation': 'getFuzzyLocation',
}

# 采集个人信息但不在 requiredPrivateInfos 内的接口：需在「用户隐私保护指引」中说明
PRIVACY_APIS = {
    'chooseImage': '选择图片', 'chooseMedia': '选择图片/视频', 'chooseVideo': '选择视频',
    'chooseMessageFile': '选择聊天文件', 'getUserProfile': '获取用户头像昵称',
    'getUserInfo': '获取用户信息', 'getPhoneNumber': '获取手机号', 'getClipboardData': '读取剪贴板',
    'setClipboardData': '写入剪贴板', 'saveImageToPhotosAlbum': '保存图片到相册',
    'saveVideoToPhotosAlbum': '保存视频到相册', 'getWeRunData': '获取微信运动数据',
    'startBluetoothDevicesDiscovery': '搜索蓝牙设备', 'chooseContact': '选择通讯录联系人',
    'addPhoneContact': '写入通讯录', 'getBeacons': '获取 Beacon 信息',
}

SECRET_PATTERNS = [
    (r'(?i)app[\s_\-]*secret\s*[:=]\s*[\'"][^\'"]{8,}[\'"]', 'AppSecret 疑似明文'),
    (r'(?i)mch[\s_\-]*key\s*[:=]\s*[\'"][^\'"]{8,}[\'"]', '支付商户密钥疑似明文'),
    (r'(?i)api[\s_\-]*v3[\s_\-]*key\s*[:=]\s*[\'"][^\'"]{8,}[\'"]', 'APIv3 密钥疑似明文'),
    (r'-----BEGIN [A-Z ]*PRIVATE KEY-----', '私钥文件片段'),
    (r'(?i)private[\s_\-]*key\s*[:=]\s*[\'"][^\'"]{16,}[\'"]', '私钥疑似明文'),
]

URL_RE = re.compile(r'https?://[A-Za-z0-9\.\-]+(?::\d+)?')


class Finding(object):
    def __init__(self, level, code, title, detail, fix=''):
        self.level = level      # P0 / P1 / P2
        self.code = code
        self.title = title
        self.detail = detail
        self.fix = fix

    def as_dict(self):
        return {'level': self.level, 'code': self.code, 'title': self.title,
                'detail': self.detail, 'fix': self.fix}


class Report(object):
    def __init__(self, name):
        self.name = name
        self.findings = []
        self.facts = {}
        self.notes = []

    def add(self, level, code, title, detail, fix=''):
        self.findings.append(Finding(level, code, title, detail, fix))

    def count(self, level):
        return len([f for f in self.findings if f.level == level])

    def blocking(self):
        return [f for f in self.findings if f.level == 'P0']


# ---------- 基础工具 ----------

def rel(path, base):
    try:
        return os.path.relpath(path, base).replace('\\', '/')
    except ValueError:
        return path


def read_json(path):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return None


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
            return f.read()
    except Exception:
        return ''


def walk_files(root, skip_dirs=None):
    skip = SKIP_DIRS | (skip_dirs or set())
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def detect_root(project, explicit=None):
    """识别小程序根目录：显式 > project.config.json 的 miniprogramRoot > 自身含 app.json > 一级子目录含 app.json"""
    if explicit:
        cand = explicit if os.path.isabs(explicit) else os.path.join(project, explicit)
        return cand if os.path.exists(os.path.join(cand, 'app.json')) else None
    pc = os.path.join(project, 'project.config.json')
    if os.path.exists(pc):
        cfg = read_json(pc) or {}
        mr = cfg.get('miniprogramRoot') or cfg.get('miniprogram_root')
        if mr:
            cand = os.path.normpath(os.path.join(project, mr))
            if os.path.exists(os.path.join(cand, 'app.json')):
                return cand
    if os.path.exists(os.path.join(project, 'app.json')):
        return project
    for name in sorted(os.listdir(project)):
        cand = os.path.join(project, name)
        if os.path.isdir(cand) and os.path.exists(os.path.join(cand, 'app.json')):
            return cand
    return None


def load_app_json(root):
    return read_json(os.path.join(root, 'app.json'))


def collect_packages(app):
    """返回 (主包页面列表, [(分包名, root, 页面列表, independent)])"""
    pages = [p for p in (app.get('pages') or []) if isinstance(p, str)]
    subs = []
    raw = app.get('subpackages') or app.get('subPackages') or []
    for sp in raw:
        if not isinstance(sp, dict):
            continue
        name = sp.get('name') or sp.get('root') or ''
        sroot = (sp.get('root') or '').strip('/')
        spages = ['%s/%s' % (sroot, p.strip('/')) for p in (sp.get('pages') or [])]
        subs.append((name, sroot, spages, bool(sp.get('independent'))))
    return pages, subs


# ---------- scan ----------

def check_pages(root, app, rep):
    pages, subs = collect_packages(app)
    if not pages:
        rep.add('P0', 'SCAN-001', 'app.json 没有 pages 或为空', '小程序至少要有一个页面', '在 app.json 的 pages 里补首屏页面路径')
        return pages, subs

    missing = []
    for p in pages + [x for _, _, sp, _ in subs for x in sp]:
        js = os.path.join(root, p + '.js')
        ts = os.path.join(root, p + '.ts')
        wxml = os.path.join(root, p + '.wxml')
        lack = []
        if not (os.path.exists(js) or os.path.exists(ts)):
            lack.append('.js')
        if not os.path.exists(wxml):
            lack.append('.wxml')
        if lack:
            missing.append('%s 缺 %s' % (p, '/'.join(lack)))
    if missing:
        rep.add('P0', 'SCAN-002', '页面四件套缺失', '；'.join(missing[:12]) + ('…共 %d 处' % len(missing) if len(missing) > 12 else ''),
                '补齐 .js/.wxml 文件；页面存在但没声明也会走不到')
    rep.facts['page_count'] = len(pages)
    rep.facts['subpackage_count'] = len(subs)
    return pages, subs


def check_tabbar(root, app, pages, rep):
    tab = app.get('tabBar')
    if not tab:
        return
    lst = tab.get('list') or []
    if len(lst) < 2 or len(lst) > 5:
        rep.add('P1', 'SCAN-010', 'tabBar 项数异常', '当前 %d 项，常规为 2-5 项（以官方文档为准）' % len(lst), '调整到 2-5 项')
    for item in lst:
        if not isinstance(item, dict):
            continue
        pp = item.get('pagePath', '')
        if pp and pp not in pages:
            rep.add('P0', 'SCAN-011', 'tabBar 页面未在 pages 中声明', 'pagePath=%s' % pp, '把该页面加进 app.json 的 pages')
        for key in ('iconPath', 'selectedIconPath'):
            v = item.get(key)
            if not v:
                continue
            fp = os.path.join(root, v)
            if not os.path.exists(fp):
                rep.add('P1', 'SCAN-012', 'tabBar 图标文件不存在', '%s -> %s' % (key, v), '补文件或改路径（注意相对小程序根目录）')
            elif os.path.getsize(fp) > TABBAR_ICON_LIMIT:
                rep.add('P2', 'SCAN-013', 'tabBar 图标偏大',
                        '%s %.0fKB，超过建议的 %dKB' % (v, os.path.getsize(fp) / 1024.0, TABBAR_ICON_LIMIT // 1024),
                        '压缩图标，尺寸按官方建议处理')


def check_subpackage_declaration(root, app, subs, rep):
    declared_roots = [s[1] for s in subs if s[1]]
    for name, sroot, spages, indep in subs:
        if not os.path.isdir(os.path.join(root, sroot)):
            rep.add('P1', 'SCAN-020', '分包目录不存在', '分包 %s 的 root=%s 在磁盘上找不到' % (name or '-', sroot), '建目录或修正 root')
        if indep and not spages:
            rep.add('P1', 'SCAN-021', '独立分包没有页面', 'root=%s' % sroot, '独立分包至少要有一个页面')
    # 磁盘上有目录但未声明
    for d in os.listdir(root):
        p = os.path.join(root, d)
        if not os.path.isdir(p) or d in SKIP_DIRS:
            continue
        if d in ('pages', 'components', 'utils', 'services', 'assets', 'styles', 'static', 'images'):
            continue
        if d in declared_roots:
            continue
        has_page = any(f.endswith('.wxml') for f in os.listdir(p) if os.path.isfile(os.path.join(p, f))) or \
            any(os.path.exists(os.path.join(p, sub, sub + '.wxml')) for sub in os.listdir(p) if os.path.isdir(os.path.join(p, sub)))
        if has_page:
            rep.add('P1', 'SCAN-022', '疑似分包目录未声明',
                    '目录 %s/ 下像是有页面，但 app.json 没有对应分包声明' % d,
                    '要么在 subpackages 里声明，要么把页面并入已声明目录')

    pre = app.get('preloadRule') or {}
    for page_key, cfg in pre.items():
        if page_key not in (app.get('pages') or []):
            rep.add('P2', 'SCAN-023', 'preloadRule 的键不是已声明页面', 'key=%s' % page_key, '改成真实页面路径')
        for pk in ((cfg or {}).get('packages') or []):
            if pk == '__DEFAULT__' or pk == 'all':
                continue
            if pk not in declared_roots and pk not in [s[0] for s in subs]:
                rep.add('P2', 'SCAN-024', 'preloadRule 引用了不存在的分包', 'packages 含 %s' % pk, '改成分包 root 或 name')


def resolve_component(root, base_dir, comp_path):
    if not comp_path or comp_path.startswith('plugin://'):
        return None, True
    if comp_path.startswith('/'):
        target = os.path.join(root, comp_path.lstrip('/'))
    elif comp_path.startswith('.'):
        target = os.path.normpath(os.path.join(base_dir, comp_path))
    else:
        return None, True   # npm 包，跳过
    for ext in ('.js', '.ts'):
        if os.path.exists(target + ext):
            return target, True
    # 目录形式：xxx/index.js
    if os.path.isdir(target) and (os.path.exists(os.path.join(target, 'index.js'))):
        return target, True
    return target, False


def check_components(root, rep):
    bad = []
    for fp in walk_files(root):
        if not fp.endswith('.json'):
            continue
        if os.path.basename(fp) in ('app.json', 'project.config.json', 'sitemap.json', 'package.json', 'package-lock.json'):
            continue
        data = read_json(fp)
        if not isinstance(data, dict):
            continue
        uc = data.get('usingComponents')
        if not isinstance(uc, dict):
            continue
        base = os.path.dirname(fp)
        for name, path in uc.items():
            if not isinstance(path, str):
                continue
            target, ok = resolve_component(root, base, path)
            if target and not ok:
                bad.append('%s 里的 %s -> %s' % (rel(fp, root), name, path))
    if bad:
        rep.add('P1', 'SCAN-030', '组件引用无法解析', '；'.join(bad[:10]) + ('…共 %d 处' % len(bad) if len(bad) > 10 else ''),
                '检查 usingComponents 路径（绝对路径以 / 开头，相对以 ./ 开头）')


def check_privacy(root, app, rep):
    required = set((app.get('requiredPrivateInfos') or []))
    permission = app.get('permission') or {}
    hits = {}
    for fp in walk_files(root):
        if not fp.endswith(('.js', '.ts', '.wxml')):
            continue
        text = read_text(fp)
        if not text:
            continue
        for api, cn in PRIVACY_APIS.items():
            if re.search(r'\bwx\.%s\s*\(' % api, text) or (api == 'getPhoneNumber' and 'open-type="getPhoneNumber"' in text):
                hits.setdefault(api, {'cn': cn, 'files': []})['files'].append(rel(fp, root))
        for api in REQUIRED_PRIVATE:
            if re.search(r'\bwx\.%s\s*\(' % api, text):
                hits.setdefault(api, {'cn': REQUIRED_PRIVATE[api], 'files': []})['files'].append(rel(fp, root))

    undeclared = []
    for api in REQUIRED_PRIVATE:
        if api in hits and api not in required:
            undeclared.append('%s（出现在 %s）' % (api, ', '.join(hits[api]['files'][:3])))
    # 按接口族归并：startLocationUpdate 系列共用声明
    if undeclared:
        rep.add('P0', 'SCAN-040', '隐私接口被调用但未在 app.json 声明',
                '；'.join(undeclared),
                '在 app.json 的 requiredPrivateInfos 中补齐；权限用途在 permission 里写清楚')

    if any(a in hits for a in ('getLocation', 'getFuzzyLocation', 'startLocationUpdate', 'startLocationUpdateBackground')):
        if not permission.get('scope.userLocation'):
            rep.add('P1', 'SCAN-041', '用了定位但没有权限用途说明',
                    'app.json 的 permission.scope.userLocation 缺失', '补 desc，写明"用于…"，弹窗会展示给用户')

    if hits:
        rep.facts['privacy_apis'] = {k: sorted(set(v['files'])) for k, v in hits.items()}
        rep.add('P2', 'SCAN-042', '采集类接口清单（需在隐私保护指引中说明）',
                '；'.join('%s' % k for k in sorted(hits)),
                '逐条对照公众平台「用户隐私保护指引」，说明收集目的与使用场景；本工具只做清单，不做合规裁决')
    else:
        rep.facts['privacy_apis'] = {}


def check_secrets(root, rep):
    found = []
    for fp in walk_files(root):
        if not fp.endswith(('.js', '.ts', '.json', '.wxml', '.wxss')):
            continue
        text = read_text(fp)
        for pat, label in SECRET_PATTERNS:
            m = re.search(pat, text)
            if m:
                found.append('%s: %s' % (rel(fp, root), label))
    if found:
        rep.add('P0', 'SCAN-050', '前端出现疑似密钥明文', '；'.join(found[:8]),
                '立刻移到服务端环境变量并轮换密钥；前端只保留公开标识（如 AppID）')


def check_domains(root, rep):
    domains = {}
    api_calls = set()
    for fp in walk_files(root):
        if not fp.endswith(('.js', '.ts')):
            continue
        text = read_text(fp)
        for api in ('request', 'uploadFile', 'downloadFile', 'connectSocket'):
            if re.search(r'\bwx\.%s\s*\(' % api, text):
                api_calls.add(api)
        for m in URL_RE.finditer(text):
            host = m.group(0)
            domains.setdefault(host, set()).add(rel(fp, root))
    if domains:
        rep.facts['domains'] = {k: sorted(v)[:3] for k, v in sorted(domains.items())}
        if api_calls:
            rep.add('P2', 'SCAN-060', '需要配置服务器域名白名单',
                    '检测到 %d 个外部域名，使用接口：%s' % (len(domains), ', '.join(sorted(api_calls))),
                    '在公众平台「开发管理-服务器域名」按接口类型分别配置；域名需备案且为 https')
    if 'http://' in ''.join(domains.keys()):
        rep.add('P1', 'SCAN-061', '存在 http 明文域名', '；'.join(d for d in domains if d.startswith('http://'))[:200],
                '改成 https；正式环境不允许明文请求')


def check_code_smells(root, rep):
    setdata_bad, timer_leak, console_n = [], [], 0
    for fp in walk_files(root):
        if not fp.endswith(('.js', '.ts')):
            continue
        text = read_text(fp)
        console_n += len(re.findall(r'\bconsole\.(log|debug)\s*\(', text))
        if re.search(r'setData\s*\(\s*(this\.data|\{[^}]*\.\.\.this\.data)', text):
            setdata_bad.append(rel(fp, root))
        if re.search(r'\bsetInterval\s*\(', text) and 'clearInterval' not in text:
            timer_leak.append(rel(fp, root))
        if re.search(r'wx\.on(AccelerometerChange|CompassChange|LocationChange|NetworkStatusChange)\s*\(', text) \
                and 'wx.off' not in text:
            timer_leak.append(rel(fp, root))
    if setdata_bad:
        rep.add('P1', 'SCAN-070', 'setData 整包刷新', '；'.join(sorted(set(setdata_bad))[:8]),
                '只传变化字段，用 \'list[0].name\' 这类局部路径')
    if timer_leak:
        rep.add('P1', 'SCAN-071', '定时器/监听疑似未清理', '；'.join(sorted(set(timer_leak))[:8]),
                '在 onUnload / detached 里 clearInterval、wx.offXxx')
    if console_n > 10:
        rep.add('P2', 'SCAN-072', 'console 输出偏多', '共 %d 处' % console_n, '提审前收敛日志，避免泄露内部信息')
    if not (app_lazy := (load_app_json(root) or {}).get('lazyCodeLoading')):
        rep.add('P2', 'SCAN-073', '未开启按需注入', 'app.json 缺 lazyCodeLoading', '加 "lazyCodeLoading": "requiredComponents"，可减小启动包体')


def cmd_scan(args):
    ok, root = prepare(args, 'scan')
    if not ok:
        return 2
    app = load_app_json(root)
    rep = Report('scan')
    rep.facts['root'] = root
    pages, subs = check_pages(root, app, rep)
    check_tabbar(root, app, pages, rep)
    check_subpackage_declaration(root, app, subs, rep)
    check_components(root, rep)
    check_privacy(root, app, rep)
    check_secrets(root, rep)
    check_domains(root, rep)
    check_code_smells(root, rep)
    if not os.path.exists(os.path.join(root, 'sitemap.json')) and app.get('sitemapLocation'):
        rep.add('P2', 'SCAN-080', 'sitemap 文件缺失', 'app.json 声明了 sitemapLocation 但没有文件', '补 sitemap.json，或去掉该声明')
    write_report(args, root, rep, '体检报告')
    return 1 if rep.blocking() else 0


# ---------- budget ----------

def package_of(relpath, subs):
    for name, sroot, _, _ in subs:
        if sroot and (relpath == sroot or relpath.startswith(sroot + '/')):
            return 'sub:%s' % (name or sroot)
    return 'main'


def cmd_budget(args):
    ok, root = prepare(args, 'budget')
    if not ok:
        return 2
    app = load_app_json(root)
    pages, subs = collect_packages(app)
    sizes = {}
    files_by_pkg = {}
    offenders = []
    total = 0
    for fp in walk_files(root):
        r = rel(fp, root)
        try:
            sz = os.path.getsize(fp)
        except OSError:
            continue
        pkg = package_of(r, subs)
        sizes[pkg] = sizes.get(pkg, 0) + sz
        files_by_pkg.setdefault(pkg, []).append((sz, r))
        offenders.append((sz, r))
        total += sz

    rep = Report('budget')
    rep.facts['root'] = root
    rep.facts['packages'] = {k: v for k, v in sorted(sizes.items())}
    main_sz = sizes.get('main', 0)
    rep.facts['main_bytes'] = main_sz
    rep.facts['total_bytes'] = total

    over_main = main_sz > MAIN_LIMIT
    if over_main:
        rep.add('P0', 'BUD-001', '主包超限',
                '主包 %.0fKB，上限 %dKB，超出 %.0fKB' % (main_sz / 1024.0, MAIN_LIMIT // 1024, (main_sz - MAIN_LIMIT) / 1024.0),
                '把非 tabBar 页面移入分包；先看下面的体积排行找大户')
    elif main_sz > MAIN_LIMIT * 0.85:
        rep.add('P1', 'BUD-002', '主包余量不足',
                '主包 %.0fKB，占上限 %.0f%%' % (main_sz / 1024.0, main_sz * 100.0 / MAIN_LIMIT),
                '按 85% 红线再切一次分包，别等下次加功能卡住')

    for name, sroot, spages, indep in subs:
        key = 'sub:%s' % (name or sroot)
        sz = sizes.get(key, 0)
        if sz > MAIN_LIMIT:
            rep.add('P0', 'BUD-003', '分包超限',
                    '%s %.0fKB 超过 %dKB' % (key, sz / 1024.0, MAIN_LIMIT // 1024), '继续拆分该分包或压缩资源')
    if total > TOTAL_LIMIT:
        rep.add('P0', 'BUD-004', '总体积超限', '合计 %.1fMB 超过 %dMB' % (total / 1048576.0, TOTAL_LIMIT // 1048576),
                '核对是否有未排除的 node_modules、备份目录、源图')

    big = sorted(offenders, reverse=True)[:10]
    rep.facts['top_files'] = [{'size': s, 'path': p} for s, p in big]
    heavy = [x for x in offenders if x[0] > BIG_FILE_LIMIT]
    if heavy:
        heavy.sort(reverse=True)
        rep.add('P1', 'BUD-005', '存在大文件',
                '；'.join('%s %.0fKB' % (p, s / 1024.0) for s, p in heavy[:8]),
                '图片压缩/转 CDN，字体按需裁剪，别把源图放进包内')
    img_total = sum(s for s, p in offenders if p.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')))
    if img_total:
        rep.facts['image_bytes'] = img_total
        if img_total > MAIN_LIMIT * 0.4:
            rep.add('P1', 'BUD-006', '图片占用过高', '图片合计 %.0fKB，占主包预算的 %.0f%%'
                    % (img_total / 1024.0, img_total * 100.0 / MAIN_LIMIT),
                    '静态图走 CDN，列表图用缩略图 + 懒加载')
    write_report(args, root, rep, '体积预算')
    return 1 if rep.blocking() else 0


# ---------- preflight ----------

CATEGORY_HINTS = [
    (('wx.requestPayment', 'requestPayment'), '涉及支付：需电商/生活服务等对应类目与商户号；iOS 端虚拟商品不得用微信支付',
     '类目资质与商户号状态以公众平台后台为准'),
    (('open-type="getPhoneNumber"', 'getPhoneNumber'), '收集手机号：需在隐私指引中说明用途，且不得强制登录才能用基础功能',
     '首次进入不应出现强制授权弹窗'),
    (('getLocation', 'chooseLocation', 'getFuzzyLocation'), '使用位置：需声明 requiredPrivateInfos 与权限用途',
     '位置不得用于与功能无关的画像'),
    (('chooseMedia', 'chooseImage', 'uploadFile'), '上传用户内容：若内容对其他用户可见，需内容安全检测（如 msgSecCheck 类接口，名称与用法以官方文档为准）',
     'UGC 未做安全检测是常见驳回原因'),
    (('live-player', 'live-pusher'), '涉及直播：需直播类目与相关资质', '资质缺失会直接驳回'),
    (('web-view',), '使用 web-view：需配置业务域名并在后台校验文件', '域名需备案'),
]


def cmd_preflight(args):
    ok, root = prepare(args, 'preflight')
    if not ok:
        return 2
    app = load_app_json(root)
    rep = Report('preflight')
    rep.facts['root'] = root
    pages, subs = check_pages(root, app, rep)
    check_tabbar(root, app, pages, rep)
    check_privacy(root, app, rep)
    check_secrets(root, rep)
    check_domains(root, rep)

    # 体积
    sizes = {}
    for fp in walk_files(root):
        r = rel(fp, root)
        pkg = package_of(r, subs)
        try:
            sizes[pkg] = sizes.get(pkg, 0) + os.path.getsize(fp)
        except OSError:
            pass
    main_sz = sizes.get('main', 0)
    rep.facts['main_bytes'] = main_sz
    if main_sz > MAIN_LIMIT:
        rep.add('P0', 'BUD-001', '主包超限', '主包 %.0fKB' % (main_sz / 1024.0), '先解决体积再提审')

    # 类目提示
    alltext = ''
    for fp in walk_files(root):
        if fp.endswith(('.js', '.ts', '.wxml', '.json')):
            alltext += read_text(fp)
    hints = []
    for keys, msg, note in CATEGORY_HINTS:
        if any(k in alltext for k in keys):
            hints.append({'msg': msg, 'note': note})
    rep.facts['category_hints'] = hints

    # 提审材料清单
    materials = [
        '小程序名称、简介、头像（不含违禁词，与实际功能一致）',
        '服务类目选择与对应资质（以公众平台「类目/资质」要求为准）',
        '用户隐私保护指引（逐项填写采集目的，与代码中的采集接口一一对应）',
        '功能演示路径说明（审核员按此操作能走通主流程）',
        '测试账号（若必须登录；核心功能尽量不依赖登录）',
        '服务器域名配置（request/uploadFile/downloadFile/socket 分别配置）',
        '版本号与更新说明（改动点写清，便于审核比对）',
    ]
    rep.facts['materials'] = materials

    privacy = rep.facts.get('privacy_apis') or {}
    if privacy:
        lines = []
        for api in sorted(privacy):
            lines.append({'api': api, 'files': privacy[api][:3]})
        rep.facts['privacy_apis'] = lines

    write_report(args, root, rep, '提审预检')
    return 1 if rep.blocking() else 0


# ---------- scaffold ----------

PAGE_JS = """Page({{
  data: {{}},

  onLoad(options) {{
    // 入参: {name}  ·  验收条目见 docs/交付台账.md
  }},

  onUnload() {{
    // 清理定时器与监听，别留悬挂引用
  }},
}});
"""

PAGE_JSON = """{{
  "navigationBarTitleText": "{title}",
  "usingComponents": {{}}
}}
"""

PAGE_WXML = """<view class="{name}-page">
  <view class="state state-loading" wx:if="{{{{loading}}}}">加载中…</view>
  <view class="state state-empty" wx:elif="{{{{!list.length}}}}">暂时没有内容</view>
  <view class="state state-error" wx:elif="{{{{error}}}}">{{{{error}}}}</view>
  <block wx:else>
    <!-- 主内容：先定数据契约，再改这里 -->
    <view class="placeholder">{title}</view>
  </block>
</view>
"""

PAGE_WXSS = """.{name}-page {{
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
  background: #f6f7f8;
}}

.state {{
  padding: 120rpx 0;
  text-align: center;
  color: #8a8f99;
  font-size: 28rpx;
}}

.placeholder {{
  padding: 40rpx;
  background: #fff;
  border-radius: 16rpx;
  font-size: 30rpx;
  color: #23262b;
}}
"""


def cmd_scaffold(args):
    spec_path = args.spec
    if not spec_path or not os.path.exists(spec_path):
        sys.stderr.write('错误: --spec 指向的 JSON 不存在\n')
        return 2
    spec = read_json(spec_path)
    if not isinstance(spec, dict):
        sys.stderr.write('错误: spec JSON 解析失败\n')
        return 2
    out = args.out_dir or spec.get('out') or './miniprogram'
    os.makedirs(out, exist_ok=True)

    pages = spec.get('pages') or [{'path': 'pages/index/index', 'title': '首页', 'tab': True}]
    subs = spec.get('subpackages') or []

    def write(relpath, content):
        fp = os.path.join(out, relpath)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        if os.path.exists(fp) and not args.force:
            print('  跳过（已存在）: %s' % relpath)
            return False
        with open(fp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        print('  生成: %s' % relpath)
        return True

    print('生成骨架到: %s' % os.path.abspath(out))
    for p in pages:
        path = p['path']
        name = os.path.basename(path)
        write(path + '.js', PAGE_JS.format(name=name))
        write(path + '.json', PAGE_JSON.format(title=p.get('title', name)))
        write(path + '.wxml', PAGE_WXML.format(name=name, title=p.get('title', name)))
        write(path + '.wxss', PAGE_WXSS.format(name=name))
    for sp in subs:
        for pp in (sp.get('pages') or []):
            path = '%s/%s' % (sp['root'].strip('/'), pp.strip('/'))
            name = os.path.basename(path)
            write(path + '.js', PAGE_JS.format(name=name))
            write(path + '.json', PAGE_JSON.format(title=pp))
            write(path + '.wxml', PAGE_WXML.format(name=name, title=pp))
            write(path + '.wxss', PAGE_WXSS.format(name=name))

    app_json = {
        'pages': [p['path'] for p in pages],
        'subpackages': [{'name': s.get('name') or s['root'].strip('/'),
                         'root': s['root'].strip('/'),
                         'pages': [x.strip('/') for x in (s.get('pages') or [])]}
                        for s in subs],
        'window': {
            'navigationBarBackgroundColor': '#ffffff',
            'navigationBarTitleText': spec.get('title', '小程序'),
            'navigationBarTextStyle': 'black',
            'backgroundColor': '#f6f7f8',
        },
        'sitemapLocation': 'sitemap.json',
        'lazyCodeLoading': 'requiredComponents',
    }
    tabs = [p for p in pages if p.get('tab')]
    if len(tabs) >= 2:
        app_json['tabBar'] = {
            'color': '#8a8f99', 'selectedColor': '#1aad19', 'backgroundColor': '#ffffff',
            'list': [{'pagePath': p['path'], 'text': p.get('title', '')} for p in tabs[:5]],
        }
    write('app.json', json.dumps(app_json, ensure_ascii=False, indent=2) + '\n')
    write('app.js', 'App({\n  onLaunch() {\n    // 启动逻辑：登录态恢复、版本检查\n  },\n});\n')
    write('app.wxss', 'page {\n  --color-text: #23262b;\n  --color-muted: #8a8f99;\n  --radius: 16rpx;\n  font-size: 28rpx;\n  color: var(--color-text);\n}\n')
    write('sitemap.json', json.dumps({'desc': '搜索索引配置', 'rules': [{'action': 'allow', 'page': '*'}]},
                                     ensure_ascii=False, indent=2) + '\n')
    write('project.config.json', json.dumps({
        'description': spec.get('title', '小程序项目'),
        'compileType': 'miniprogram',
        'miniprogramRoot': './',
        'appid': spec.get('appid', 'touristappid'),
        'projectname': spec.get('name', 'miniprogram'),
        'setting': {'urlCheck': True, 'es6': True, 'postcss': True, 'minified': True},
    }, ensure_ascii=False, indent=2) + '\n')

    print('')
    print('骨架完成。注意：tabBar 只生成了文字，没有图标文件（微信允许无图标）。')
    print('要加图标：把 png 放 assets/icons/，在 app.json 的 tabBar.list 里补 iconPath 与 selectedIconPath。')
    print('下一步：')
    print('  1) python wx_doctor.py budget "%s"   —— 看主包预算' % out)
    print('  2) python wx_doctor.py scan   "%s"   —— 看有没有缺件' % out)
    return 0


# ---------- 报告输出 ----------

def prepare(args, cmd):
    project = os.path.abspath(args.project)
    if not os.path.isdir(project):
        sys.stderr.write('错误: 项目目录不存在: %s\n' % project)
        return False, None
    root = detect_root(project, getattr(args, 'root', None))
    if not root:
        sys.stderr.write('错误: 没找到 app.json。用 --root 指定小程序根目录（含 app.json 的那层）。\n')
        return False, None
    return True, root


def render_markdown(rep, root, title):
    lines = []
    lines.append('# %s · %s' % (title, datetime.now().strftime('%Y-%m-%d %H:%M')))
    lines.append('')
    lines.append('- 小程序根目录: `%s`' % root)
    p0, p1, p2 = rep.count('P0'), rep.count('P1'), rep.count('P2')
    lines.append('- 结论: **P0 %d / P1 %d / P2 %d**%s' % (p0, p1, p2, '' if p0 == 0 else '　→ 有 P0，不可提审'))
    lines.append('')
    if p0 + p1 + p2 == 0:
        lines.append('未发现本工具能识别的问题。注意：本工具不覆盖真机表现、视觉质量与审核口径，仍需人工过一遍。')
        lines.append('')
    order = {'P0': 0, 'P1': 1, 'P2': 2}
    for level, label in (('P0', '阻断项（必须改完才能提审）'), ('P1', '应修项（明显影响体验或审核）'), ('P2', '建议项')):
        items = [f for f in rep.findings if f.level == level]
        if not items:
            continue
        lines.append('## %s %s' % (level, label))
        lines.append('')
        lines.append('| 编号 | 问题 | 实测 | 整改动作 |')
        lines.append('|---|---|---|---|')
        for f in items:
            lines.append('| %s | %s | %s | %s |' % (f.code, f.title, f.detail.replace('|', '/'), f.fix.replace('|', '/')))
        lines.append('')

    if rep.name == 'budget':
        lines.append('## 体积明细')
        lines.append('')
        lines.append('| 包 | 字节 | KB | 占单包上限 |')
        lines.append('|---|---|---|---|')
        for k, v in sorted(rep.facts.get('packages', {}).items()):
            lines.append('| %s | %d | %.1f | %.0f%% |' % (k, v, v / 1024.0, v * 100.0 / MAIN_LIMIT))
        lines.append('')
        lines.append('## 体积排行 Top10')
        lines.append('')
        lines.append('| 文件 | KB |')
        lines.append('|---|---|')
        for item in rep.facts.get('top_files', []):
            lines.append('| `%s` | %.1f |' % (item['path'], item['size'] / 1024.0))
        lines.append('')

    if rep.name == 'preflight':
        lines.append('## 提审材料清单')
        lines.append('')
        for i, m in enumerate(rep.facts.get('materials', []), 1):
            lines.append('%d. [ ] %s' % (i, m))
        lines.append('')
        hints = rep.facts.get('category_hints') or []
        if hints:
            lines.append('## 类目与合规提示')
            lines.append('')
            for h in hints:
                lines.append('- %s（%s）' % (h['msg'], h['note']))
            lines.append('')
        pris = rep.facts.get('privacy_apis') or []
        if pris:
            lines.append('## 代码中的采集接口（隐私指引要逐条对应）')
            lines.append('')
            lines.append('| 接口 | 出现位置 |')
            lines.append('|---|---|')
            for p in pris:
                lines.append('| %s | %s |' % (p['api'], ', '.join(p['files'])))
            lines.append('')
        doms = rep.facts.get('domains') or {}
        if doms:
            lines.append('## 外部域名（后台需配置白名单）')
            lines.append('')
            for d in doms:
                lines.append('- `%s`' % d)
            lines.append('')

    lines.append('---')
    lines.append('')
    lines.append('口径说明：体积按磁盘字节累加，不含开发者工具压缩；平台规则、类目与审核口径以微信公众平台后台及官方文档为准。')
    lines.append('本报告只覆盖静态可判定项，真机表现与视觉质量需人工核实。')
    return '\n'.join(lines)


def emit(rep, root, title):
    text = render_markdown(rep, root, title)
    p0, p1, p2 = rep.count('P0'), rep.count('P1'), rep.count('P2')
    print('')
    print('=== %s ===' % title)
    print('根目录: %s' % root)
    print('结论: P0=%d  P1=%d  P2=%d' % (p0, p1, p2))
    for f in rep.findings:
        print('  [%s] %s  %s' % (f.level, f.code, f.title))
        print('        %s' % f.detail)
        if f.fix:
            print('        → %s' % f.fix)
    if p0 == 0:
        print('阻断项已清零。注意：真机与视觉仍需人工核实。')
    else:
        print('存在 %d 个阻断项，不可提审。' % p0)
    return text


def write_report(args, root, rep, title):
    text = emit(rep, root, title)
    out_dir = args.out or os.path.join(root, 'docs', '体检')
    try:
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        fp = os.path.join(out_dir, '%s-%s.md' % (rep.name, stamp))
        with open(fp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text + '\n')
        print('')
        print('报告已写入: %s' % fp)
        if args.json:
            jp = args.json if os.path.isabs(args.json) else os.path.join(os.getcwd(), args.json)
            payload = {'command': rep.name, 'root': root, 'generated': datetime.now().isoformat(),
                       'counts': {'P0': rep.count('P0'), 'P1': rep.count('P1'), 'P2': rep.count('P2')},
                       'findings': [f.as_dict() for f in rep.findings], 'facts': rep.facts}
            with open(jp, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write('\n')
            print('JSON 已写入: %s' % jp)
    except OSError as e:
        sys.stderr.write('警告: 报告写入失败（%s），以上为控制台输出\n' % e)


# ---------- 入口 ----------

def build_parser():
    p = argparse.ArgumentParser(description='微信小程序工程体检与提审预检')
    sub = p.add_subparsers(dest='cmd')

    for name, fn, helptext in (('scan', cmd_scan, '静态体检'),
                               ('budget', cmd_budget, '体积预算'),
                               ('preflight', cmd_preflight, '提审预检')):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument('project')
        sp.add_argument('--root', default=None)
        sp.add_argument('--out', default=None)
        sp.add_argument('--json', default=None)
        sp.add_argument('--quiet', action='store_true')
        sp.set_defaults(func=fn)

    sp = sub.add_parser('scaffold', help='按规格生成骨架')
    sp.add_argument('--spec', required=True)
    sp.add_argument('--out-dir', default=None)
    sp.add_argument('--force', action='store_true')
    sp.set_defaults(func=cmd_scaffold, project=None, root=None, out=None, json=None, quiet=False)
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, 'cmd', None):
        parser.print_help()
        return 2
    return args.func(args) or 0


if __name__ == '__main__':
    sys.exit(main())
