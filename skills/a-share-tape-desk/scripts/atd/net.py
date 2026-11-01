"""HTTP 层：请求、重试、主机健康度、本地缓存。

为什么单独做一层：
1. 公开行情接口有频率限制，连续请求会被临时断流，必须做主机冷却与退避。
2. 同一轮对话内多个命令会重复取同一份数据，缓存能显著降低失败率。
3. 任何一次抓取都要能回答"这份数据是什么时候的"，所以缓存记录抓取时间。
"""

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 主机失败后进入冷却的秒数
COOLDOWN = 90
# 同一主机连续失败多少次进入冷却
FAIL_THRESHOLD = 2

_host_state = {}
_memory_cache = {}


def cache_dir():
    override = os.environ.get("ATD_CACHE_DIR", "").strip()
    if override:
        base = override
    else:
        base = os.path.join(os.path.expanduser("~"), ".workbuddy", "cache", "a-share-tape-desk")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
        os.makedirs(base, exist_ok=True)
    return base


def _key(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def _cache_path(url):
    return os.path.join(cache_dir(), _key(url) + ".json")


def cache_read(url, ttl):
    """读缓存；ttl=0 表示不读。返回 (payload, fetched_at) 或 (None, None)。"""
    if ttl <= 0:
        return None, None
    hit = _memory_cache.get(url)
    if hit is None:
        path = _cache_path(url)
        if not os.path.exists(path):
            return None, None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                hit = json.load(fh)
        except (OSError, ValueError):
            return None, None
        _memory_cache[url] = hit
    if time.time() - hit.get("ts", 0) > ttl:
        return None, None
    return hit.get("body"), hit.get("ts")


_write_counter = {"n": 0}


def cache_write(url, body):
    now = time.time()
    record = {"ts": now, "url": url, "body": body}
    _memory_cache[url] = record
    try:
        with open(_cache_path(url), "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
    except OSError:
        pass
    _write_counter["n"] += 1
    if _write_counter["n"] % 200 == 0:
        prune_cache()


def prune_cache(max_age_hours=72):
    """删掉超过保留期的缓存文件，避免全市场分页缓存长期堆积。"""
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    try:
        for name in os.listdir(cache_dir()):
            if not name.endswith(".json") or name in ("amount_history.json", "board_history.json", "watchlist.json"):
                continue
            path = os.path.join(cache_dir(), name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue
    except OSError:
        pass
    return removed


def _host_of(url):
    try:
        return urllib.request.urlparse(url).netloc if hasattr(urllib.request, "urlparse") else url.split("/")[2]
    except Exception:
        return url


def host_state(url):
    host = _host_of(url)
    return _host_state.setdefault(host, {"fails": 0, "blocked_until": 0.0, "ok": 0})


def mark_fail(url):
    st = host_state(url)
    st["fails"] += 1
    if st["fails"] >= FAIL_THRESHOLD:
        st["blocked_until"] = time.time() + COOLDOWN


def mark_ok(url):
    st = host_state(url)
    st["fails"] = 0
    st["blocked_until"] = 0.0
    st["ok"] += 1


def available(url):
    st = host_state(url)
    return time.time() >= st.get("blocked_until", 0)


def fetch(url, referer=None, encoding="utf-8", ttl=0, timeout=12, retries=2):
    """抓取文本。失败抛 RuntimeError，调用方决定降级路径。"""
    cached, fetched_at = cache_read(url, ttl)
    if cached is not None:
        return cached, fetched_at, True

    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "close",
    }
    if referer:
        headers["Referer"] = referer

    last_err = None
    for attempt in range(retries + 1):
        if not available(url):
            raise RuntimeError("数据源 %s 处于冷却期（近期多次失败），已跳过" % _host_of(url))
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            if not raw:
                raise RuntimeError("空响应")
            text = raw.decode(encoding, "ignore")
            mark_ok(url)
            cache_write(url, text)
            return text, time.time(), False
        except urllib.error.HTTPError as exc:
            last_err = "HTTP %s" % exc.code
            mark_fail(url)
        except Exception as exc:  # 网络中断、超时、空响应
            last_err = "%s: %s" % (type(exc).__name__, exc)
            mark_fail(url)
        if attempt < retries:
            time.sleep(0.4 * (attempt + 1) + random.random() * 0.3)

    raise RuntimeError("抓取失败（%s）%s" % (last_err, url))


def fetch_json(url, referer=None, ttl=0, timeout=12, retries=2):
    text, ts, cached = fetch(url, referer=referer, ttl=ttl, timeout=timeout, retries=retries)
    body = text.strip().strip(";")
    if body.startswith("(") and body.endswith(")"):
        body = body[1:-1].strip()
    try:
        return json.loads(body), ts, cached
    except ValueError:
        raise RuntimeError("返回内容不是合法 JSON：%s" % url)


def health_report():
    rows = []
    for host, st in sorted(_host_state.items()):
        blocked = max(0.0, st.get("blocked_until", 0) - time.time())
        rows.append(
            {
                "host": host,
                "ok": st.get("ok", 0),
                "fails": st.get("fails", 0),
                "cooldown_left_s": round(blocked, 1),
            }
        )
    return rows
