#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""btcore — 日频回测内核（仅依赖 Python 标准库）

设计约定（与对外说明一致，改代码前先读这一节）
------------------------------------------------
1. 时间轴：t 日收盘后产生信号，t+1 日开盘成交。引擎内部用 pending 队列实现，
   策略回调只能看到「今天及以前」的 bar，拿不到未来数据。
2. 账户口径：equity = cash + Σ(持仓数量 × 当日收盘价)。不做汇率换算，
   多币种标的请分开跑。
3. 成本：佣金（双边，含最低收费）、印花税（仅卖出）、过户费（可关）、滑点（按比例）。
4. 手数：A 股 100 股一手；港股按传入的每手股数；美股 1 股。
5. T+1：A 股当日买入不可卖出，引擎按「当日买入锁定、次日解锁」实现。
6. 强平：样本最后一根 bar 按收盘价清仓，并记一笔 exit_reason="eod_close"。

最小用法
--------
    from btcore import load_bars, Engine, CostModel, Order

    bars = load_bars("data/demo_bars.csv")

    def strategy(ctx):
        c = ctx.closes("DEMO", 21)
        if len(c) < 21:
            return None
        fast, slow = sum(c[-5:]) / 5, sum(c) / 21
        if fast > slow and ctx.shares("DEMO") == 0:
            return [Order("DEMO", "buy", weight=0.95, reason="ma5>ma21")]
        if fast < slow and ctx.shares("DEMO") > 0:
            return [Order("DEMO", "sell", shares=None, reason="ma5<ma21")]
        return None

    eng = Engine({"DEMO": bars}, cost=CostModel.china_a(), initial_cash=1_000_000,
                 lot_size=100, t_plus_1=True, eval_start="2021-01-01", eval_end="2024-12-31")
    res = eng.run(strategy)
    res.dump("./out", "ma_cross_DEMO")
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime

__version__ = "1.0.0"
__all__ = [
    "Bar", "Order", "CostModel", "Broker", "Engine", "BacktestResult", "Context",
    "load_bars", "load_bars_multi", "compute_metrics", "monthly_table",
    "buy_and_hold", "event_study", "event_stats", "param_sweep",
]


# --------------------------------------------------------------------------
# 数据层
# --------------------------------------------------------------------------
@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _to_float(raw, default=None):
    if raw is None:
        return default
    s = str(raw).strip().replace(",", "").replace("%", "")
    if s == "" or s.lower() in ("nan", "none", "null", "-"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _norm_date(raw):
    s = str(raw).strip().split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("无法识别的日期格式: %r（支持 YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD）" % raw)


def load_bars(path, symbol=None):
    """读取单标的日线 CSV。

    必需列：date, open, high, low, close；可选列：volume。
    列名大小写不敏感，允许 BOM，允许千分位逗号。
    """
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("CSV 为空: %s" % path)
        cols = {c.strip().lower(): c for c in reader.fieldnames}
        missing = [c for c in ("date", "open", "high", "low", "close") if c not in cols]
        if missing:
            raise ValueError("CSV 缺少列 %s；实际列: %s" % (missing, reader.fieldnames))
        for raw in reader:
            o = _to_float(raw.get(cols["open"]))
            h = _to_float(raw.get(cols["high"]))
            l = _to_float(raw.get(cols["low"]))
            c = _to_float(raw.get(cols["close"]))
            if None in (o, h, l, c):
                continue
            if min(o, h, l, c) <= 0:
                continue
            vol = _to_float(raw.get(cols["volume"]), 0.0) if "volume" in cols else 0.0
            rows.append(Bar(_norm_date(raw[cols["date"]]), o, h, l, c, vol or 0.0))
    rows.sort(key=lambda b: b.date)
    if not rows:
        raise ValueError("CSV 没有有效数据行: %s" % path)
    dedup = {}
    for b in rows:
        dedup[b.date] = b
    out = [dedup[d] for d in sorted(dedup)]
    if symbol:
        for b in out:
            b.symbol = symbol  # type: ignore[attr-defined]
    return out


def load_bars_multi(spec):
    """spec: {symbol: csv_path} -> {symbol: [Bar]}"""
    return {sym: load_bars(p, sym) for sym, p in spec.items()}


def _ohlc_issues(bars, sample=3):
    bad = []
    for b in bars:
        if b.high < max(b.open, b.close) - 1e-9 or b.low > min(b.open, b.close) + 1e-9:
            bad.append(b.date)
            if len(bad) >= sample:
                break
    return bad


# --------------------------------------------------------------------------
# 成本模型
# --------------------------------------------------------------------------
@dataclass
class CostModel:
    commission_bps: float = 2.5      # 佣金，万分之
    min_commission: float = 5.0      # 单笔最低佣金
    stamp_tax_bps: float = 5.0       # 印花税，仅卖出
    transfer_bps: float = 0.1        # 过户费，双边
    slippage_bps: float = 5.0        # 滑点，按成交价比例

    @classmethod
    def china_a(cls, commission_bps=2.5, min_commission=5.0):
        return cls(commission_bps=commission_bps, min_commission=min_commission,
                   stamp_tax_bps=5.0, transfer_bps=0.1, slippage_bps=5.0)

    @classmethod
    def us_stock(cls, commission_bps=0.0, slippage_bps=3.0):
        return cls(commission_bps=commission_bps, min_commission=0.0,
                   stamp_tax_bps=0.0, transfer_bps=0.0, slippage_bps=slippage_bps)

    @classmethod
    def hk_stock(cls, commission_bps=8.0, slippage_bps=8.0):
        # 佣金 + 交易征费/交易费打包近似，印花税按双边 0.1% 简化处理
        return cls(commission_bps=commission_bps, min_commission=0.0,
                   stamp_tax_bps=10.0, transfer_bps=0.0, slippage_bps=slippage_bps)

    @classmethod
    def zero(cls):
        return cls(0, 0, 0, 0, 0)

    def buy_cost(self, notional):
        fee = max(notional * self.commission_bps / 1e4, self.min_commission if notional > 0 else 0.0)
        fee += notional * self.transfer_bps / 1e4
        return fee

    def sell_cost(self, notional):
        fee = max(notional * self.commission_bps / 1e4, self.min_commission if notional > 0 else 0.0)
        fee += notional * (self.transfer_bps + self.stamp_tax_bps) / 1e4
        return fee

    def describe(self):
        return ("佣金 %.2fbp（最低 %.0f）｜卖出印花税 %.2fbp｜过户费 %.2fbp｜滑点 %.2fbp"
                % (self.commission_bps, self.min_commission, self.stamp_tax_bps,
                   self.transfer_bps, self.slippage_bps))


# --------------------------------------------------------------------------
# 订单与账户
# --------------------------------------------------------------------------
@dataclass
class Order:
    symbol: str
    side: str                  # "buy" / "sell"
    shares: int | None = None  # 指定股数；None 表示配合 weight 或「全部」
    weight: float | None = None  # 目标权重（按上一交易日收盘总资产计算）
    reason: str = ""


@dataclass
class _Position:
    shares: int = 0
    avg_cost: float = 0.0
    open_date: str = ""
    fees_paid: float = 0.0


class Broker:
    def __init__(self, cash, cost, lot_size=100, t_plus_1=True):
        self.cash = float(cash)
        self.cost = cost
        self.lot_size = max(1, int(lot_size))
        self.t_plus_1 = bool(t_plus_1)
        self.positions = {}
        self.locked = {}          # symbol -> 当日买入不可卖数量
        self.realized = 0.0
        self.fees_total = 0.0
        self.trades = []
        self.rejects = []
        self.buy_fills = 0
        self.sell_fills = 0

    # -- 查询
    def shares(self, symbol):
        p = self.positions.get(symbol)
        return p.shares if p else 0

    def sellable(self, symbol):
        p = self.positions.get(symbol)
        if not p:
            return 0
        return max(0, p.shares - self.locked.get(symbol, 0))

    def market_value(self, marks):
        return sum(p.shares * marks.get(s, 0.0) for s, p in self.positions.items())

    def equity(self, marks):
        return self.cash + self.market_value(marks)

    def unlock_all(self):
        if self.locked:
            self.locked = {}

    # -- 成交
    def buy(self, symbol, price, shares, date, reason=""):
        shares = int(shares)
        if shares <= 0:
            return 0
        shares = (shares // self.lot_size) * self.lot_size
        if shares <= 0:
            self.rejects.append({"date": date, "symbol": symbol, "side": "buy",
                                 "why": "不足一手"})
            return 0
        fill = price * (1 + self.cost.slippage_bps / 1e4)
        need = fill * shares
        fee = self.cost.buy_cost(need)
        if need + fee > self.cash + 1e-9:
            affordable = int(self.cash / (fill * (1 + self.cost.commission_bps / 1e4)) // self.lot_size) * self.lot_size
            if affordable <= 0:
                self.rejects.append({"date": date, "symbol": symbol, "side": "buy",
                                     "why": "现金不足"})
                return 0
            shares = min(shares, affordable)
            need = fill * shares
            fee = self.cost.buy_cost(need)
            if need + fee > self.cash + 1e-9:
                self.rejects.append({"date": date, "symbol": symbol, "side": "buy",
                                     "why": "现金不足（含费用）"})
                return 0
        self.cash -= need + fee
        self.fees_total += fee
        pos = self.positions.setdefault(symbol, _Position())
        total_shares = pos.shares + shares
        pos.avg_cost = (pos.avg_cost * pos.shares + need) / total_shares
        pos.shares = total_shares
        if not pos.open_date:
            pos.open_date = date
        pos.fees_paid += fee
        if self.t_plus_1:
            self.locked[symbol] = self.locked.get(symbol, 0) + shares
        self.buy_fills += 1
        return shares

    def sell(self, symbol, price, shares, date, reason=""):
        pos = self.positions.get(symbol)
        if not pos or pos.shares <= 0:
            return 0
        cap = self.sellable(symbol) if self.t_plus_1 else pos.shares
        shares = min(int(shares), cap)
        if shares <= 0:
            if pos.shares > 0:
                self.rejects.append({"date": date, "symbol": symbol, "side": "sell",
                                     "why": "T+1 锁定，无可卖数量"})
            return 0
        fill = price * (1 - self.cost.slippage_bps / 1e4)
        gross = fill * shares
        fee = self.cost.sell_cost(gross)
        self.cash += gross - fee
        self.fees_total += fee
        pnl = gross - fee - pos.avg_cost * shares
        self.realized += pnl
        holding = _days_between(pos.open_date, date)
        self.trades.append({
            "symbol": symbol,
            "side": "long",
            "entry_date": pos.open_date,
            "exit_date": date,
            "shares": shares,
            "entry_price": round(pos.avg_cost, 4),
            "exit_price": round(fill, 4),
            "pnl": round(pnl, 2),
            "pnl_pct": round((fill / pos.avg_cost - 1) * 100, 4) if pos.avg_cost else 0.0,
            "holding_days": holding,
            "exit_reason": reason,
        })
        pos.shares -= shares
        self.sell_fills += 1
        if pos.shares <= 0:
            self.positions.pop(symbol, None)
            self.locked.pop(symbol, None)
        return shares


def _days_between(d1, d2):
    try:
        a = datetime.strptime(d1, "%Y-%m-%d")
        b = datetime.strptime(d2, "%Y-%m-%d")
        return (b - a).days
    except Exception:
        return 0


# --------------------------------------------------------------------------
# 策略上下文
# --------------------------------------------------------------------------
class Context:
    def __init__(self, date, index, bars, history, broker, marks, pending_count=0):
        self.date = date
        self.i = index
        self.bars = bars            # {symbol: 当日 Bar}
        self._history = history     # {symbol: [Bar]} 截断到今天
        self._broker = broker
        self.marks = marks
        self.pending_count = pending_count

    # 常用便利方法，避免策略里重复写切片逻辑
    @property
    def broker(self):
        return self._broker

    def avg_cost(self, symbol):
        pos = self._broker.positions.get(symbol)
        return pos.avg_cost if pos else 0.0

    def open_date(self, symbol):
        pos = self._broker.positions.get(symbol)
        return pos.open_date if pos else ""

    def closes(self, symbol, n=None):
        h = self._history.get(symbol, [])
        vals = [b.close for b in h]
        return vals[-n:] if n else vals

    def bar(self, symbol):
        return self.bars.get(symbol)

    def history(self, symbol):
        return list(self._history.get(symbol, []))

    def shares(self, symbol):
        return self._broker.shares(symbol)

    def cash(self):
        return self._broker.cash

    def equity(self):
        return self._broker.equity(self.marks)

    def ma(self, symbol, n):
        c = self.closes(symbol, n)
        return sum(c) / len(c) if len(c) == n else None

    def atr(self, symbol, n=14):
        h = self._history.get(symbol, [])
        if len(h) < n + 1:
            return None
        trs = []
        for i in range(len(h) - n, len(h)):
            prev = h[i - 1].close
            trs.append(max(h[i].high - h[i].low, abs(h[i].high - prev), abs(h[i].low - prev)))
        return sum(trs) / len(trs)


# --------------------------------------------------------------------------
# 结果容器
# --------------------------------------------------------------------------
@dataclass
class BacktestResult:
    equity: list = field(default_factory=list)      # [{"date","value"}]
    trades: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    rejects: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    monthly: list = field(default_factory=list)

    def dump(self, outdir, prefix, language="zh"):
        """落盘三件套：<prefix>_equity.csv / _trades.csv / _summary.json"""
        os.makedirs(outdir, exist_ok=True)
        eq_path = os.path.join(outdir, "%s_equity.csv" % prefix)
        tr_path = os.path.join(outdir, "%s_trades.csv" % prefix)
        sm_path = os.path.join(outdir, "%s_summary.json" % prefix)
        with open(eq_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "value"])
            for row in self.equity:
                w.writerow([row["date"], "%.2f" % row["value"]])
        cols = ["symbol", "side", "entry_date", "exit_date", "shares", "entry_price",
                "exit_price", "pnl", "pnl_pct", "holding_days", "exit_reason"]
        with open(tr_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for t in self.trades:
                w.writerow(t)
        payload = {"meta": self.meta, "metrics": self.metrics, "warnings": self.warnings,
                   "rejects": self.rejects[:50], "language": language,
                   "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        with open(sm_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return {"equity": eq_path, "trades": tr_path, "summary": sm_path}


# --------------------------------------------------------------------------
# 引擎
# --------------------------------------------------------------------------
class Engine:
    def __init__(self, bars_by_symbol, cost=None, initial_cash=1_000_000.0,
                 lot_size=100, t_plus_1=True, eval_start=None, eval_end=None,
                 market="china_a", strategy_name="", note=""):
        if not bars_by_symbol:
            raise ValueError("bars_by_symbol 为空")
        self.bars = {s: sorted(b, key=lambda x: x.date) for s, b in bars_by_symbol.items()}
        self.lookup = {s: {b.date: b for b in v} for s, v in self.bars.items()}
        self.dates = sorted({b.date for v in self.bars.values() for b in v})
        self.cost = cost or CostModel.china_a()
        self.initial_cash = float(initial_cash)
        self.lot_size = lot_size
        self.t_plus_1 = t_plus_1
        self.eval_start = eval_start or self.dates[0]
        self.eval_end = eval_end or self.dates[-1]
        self.market = market
        self.strategy_name = strategy_name
        self.note = note
        self.broker = Broker(self.initial_cash, self.cost, lot_size, t_plus_1)
        self.marks = {}
        self.warnings = []
        self._validate()

    def _validate(self):
        for s, bars in self.bars.items():
            if len(bars) < 30:
                self.warnings.append("%s 只有 %d 根 bar，指标与统计意义有限" % (s, len(bars)))
            bad = _ohlc_issues(bars)
            if bad:
                self.warnings.append("%s 存在 OHLC 关系异常（如 high<close），已按原值使用：%s"
                                     % (s, ",".join(bad)))
        if self.bars and self.dates:
            first = self.dates[0]
            if (datetime.strptime(self.eval_start, "%Y-%m-%d")
                    - datetime.strptime(first, "%Y-%m-%d")).days < 60:
                self.warnings.append("评估区间起点距首根 bar 不足 60 个自然日，"
                                     "长周期指标可能没有足够预热数据")

    # ---- 主循环
    def run(self, strategy, warmup_bars=None):
        """strategy(ctx) -> list[Order] | None；返回 BacktestResult。"""
        dates = self.dates
        pending = []
        equity_series = []
        history = {s: [] for s in self.bars}
        in_market_bars = 0
        eval_bars = 0
        last_open_qty = 0

        for i, d in enumerate(dates):
            today = {s: self.lookup[s][d] for s in self.bars if d in self.lookup[s]}
            for s, b in today.items():
                history[s].append(b)
                self.marks[s] = b.close
            self.broker.unlock_all()

            # 1) 先执行昨日待成交单（用今日开盘价）
            still_pending = []
            for od in pending:
                bar = today.get(od.symbol)
                if bar is None:
                    od.retry = getattr(od, "retry", 0) + 1
                    if od.retry <= 5:
                        still_pending.append(od)
                    else:
                        self.warnings.append("%s 的订单在 %s 连续 5 日无成交价，已丢弃"
                                             % (od.symbol, d))
                    continue
                self._execute(od, bar, d)
            pending = still_pending

            # 2) 收盘计价
            eq = self.broker.equity(self.marks)
            if self.eval_start <= d <= self.eval_end:
                equity_series.append({"date": d, "value": eq})
                eval_bars += 1
                if self.broker.positions:
                    in_market_bars += 1

            # 3) 生成明日信号（最后一根 bar 不再下单；预热段只喂历史，不下单）
            if self.eval_start <= d <= self.eval_end and i < len(dates) - 1:
                ctx = Context(d, i, today, history, self.broker, self.marks, len(pending))
                out = strategy(ctx) or []
                if isinstance(out, Order):
                    out = [out]
                for od in out:
                    if not isinstance(od, Order):
                        raise TypeError("strategy 必须返回 Order 列表或 None，收到 %r" % type(od))
                    pending.append(od)

        # 4) 样本末强制清仓
        if self.broker.positions:
            last = dates[-1]
            for sym in list(self.broker.positions):
                bar = self.lookup[sym].get(last)
                px = bar.close if bar else self.marks.get(sym, 0.0)
                if px > 0:
                    # 强平不受 T+1 限制（样本结束，持仓已存在）
                    self.broker.t_plus_1 = False
                    self.broker.sell(sym, px, self.broker.positions[sym].shares, last, "eod_close")
                    self.broker.t_plus_1 = self.t_plus_1
            if equity_series:
                equity_series[-1]["value"] = self.broker.equity(self.marks)

        metrics = compute_metrics(equity_series, self.broker.trades, self.initial_cash)
        metrics["exposure_pct"] = round(100.0 * in_market_bars / eval_bars, 2) if eval_bars else 0.0
        metrics["buy_fills"] = self.broker.buy_fills
        metrics["sell_fills"] = self.broker.sell_fills
        metrics["evaluation_bars"] = eval_bars
        metrics["total_fees"] = round(self.broker.fees_total, 2)
        meta = {
            "strategy_name": self.strategy_name or "unnamed",
            "universe": list(self.bars.keys()),
            "market": self.market,
            "start": self.eval_start,
            "end": self.eval_end,
            "initial_cash": self.initial_cash,
            "final_value": round(equity_series[-1]["value"], 2) if equity_series else self.initial_cash,
            "cost_model": self.cost.describe(),
            "lot_size": self.lot_size,
            "t_plus_1": self.t_plus_1,
            "engine": "btcore %s" % __version__,
            "note": self.note,
        }
        return BacktestResult(equity=equity_series, trades=list(self.broker.trades),
                              metrics=metrics, meta=meta, rejects=list(self.broker.rejects),
                              warnings=self.warnings,
                              monthly=monthly_table(equity_series))

    def _execute(self, od, bar, d):
        if od.side == "buy":
            if od.weight is not None:
                target_value = od.weight * self.broker.equity(self.marks)
                px = bar.open * (1 + self.cost.slippage_bps / 1e4)
                want = int(target_value / px) if px > 0 else 0
                shares = want - self.broker.shares(od.symbol)
            else:
                shares = od.shares if od.shares is not None else 0
            if shares > 0:
                self.broker.buy(od.symbol, bar.open, shares, d, od.reason)
        else:
            if od.weight is not None:
                target_value = od.weight * self.broker.equity(self.marks)
                px = bar.open * (1 - self.cost.slippage_bps / 1e4)
                want = int(target_value / px) if px > 0 else 0
                shares = self.broker.shares(od.symbol) - want
            elif od.shares is None:
                shares = self.broker.shares(od.symbol)
            else:
                shares = od.shares
            if shares > 0:
                self.broker.sell(od.symbol, bar.open, shares, d, od.reason)


# --------------------------------------------------------------------------
# 指标
# --------------------------------------------------------------------------
def _daily_returns(values):
    return [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]


def compute_metrics(equity_series, trades, initial_cash):
    values = [r["value"] for r in equity_series]
    out = {
        "total_return_pct": 0.0, "annual_return_pct": 0.0, "max_drawdown_pct": 0.0,
        "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0, "annual_vol_pct": 0.0,
        "win_rate_pct": 0.0, "profit_factor": 0.0, "trade_count": len(trades),
        "avg_holding_days": 0.0, "best_trade_pct": 0.0, "worst_trade_pct": 0.0,
        "exposure_pct": 0.0,
    }
    if not values:
        return out
    if values[0] <= 0:
        return out
    out["total_return_pct"] = round((values[-1] / values[0] - 1) * 100, 2)
    days = max(1, _days_between(equity_series[0]["date"], equity_series[-1]["date"]))
    if values[-1] > 0 and values[0] > 0:
        out["annual_return_pct"] = round(((values[-1] / values[0]) ** (365.25 / days) - 1) * 100, 2)
    rets = _daily_returns(values)
    if len(rets) > 2:
        sd = statistics.pstdev(rets)
        mean = sum(rets) / len(rets)
        out["annual_vol_pct"] = round(sd * math.sqrt(252) * 100, 2)
        out["sharpe"] = round(mean / sd * math.sqrt(252), 2) if sd > 0 else 0.0
        downside = [r for r in rets if r < 0]
        dsd = statistics.pstdev(downside) if len(downside) > 1 else 0.0
        out["sortino"] = round(mean / dsd * math.sqrt(252), 2) if dsd > 0 else 0.0
    peak, mdd, mdd_date = values[0], 0.0, equity_series[0]["date"]
    for r in equity_series:
        peak = max(peak, r["value"])
        dd = r["value"] / peak - 1
        if dd < mdd:
            mdd, mdd_date = dd, r["date"]
    out["max_drawdown_pct"] = round(mdd * 100, 2)
    out["max_drawdown_date"] = mdd_date
    if out["max_drawdown_pct"] < 0:
        out["calmar"] = round(out["annual_return_pct"] / abs(out["max_drawdown_pct"]), 2)
    if trades:
        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        out["win_rate_pct"] = round(100.0 * len(wins) / len(pnls), 2)
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        out["profit_factor"] = round(gross_win / gross_loss, 2) if gross_loss > 0 else (
            99.0 if gross_win > 0 else 0.0)
        out["avg_holding_days"] = round(sum(t["holding_days"] for t in trades) / len(trades), 1)
        pct = [t["pnl_pct"] for t in trades]
        out["best_trade_pct"] = round(max(pct), 2)
        out["worst_trade_pct"] = round(min(pct), 2)
        out["buy_count"] = sum(1 for t in trades)
        out["avg_trade_pnl"] = round(sum(pnls) / len(pnls), 2)
    out["final_value"] = round(values[-1], 2)
    out["initial_value"] = round(values[0], 2)
    return out


def monthly_table(equity_series):
    """返回 [{year, months:[m1..m12 或 null], ytd}]，用于报告热力图。"""
    if not equity_series:
        return []
    by_month = {}
    for r in equity_series:
        y, m = int(r["date"][:4]), int(r["date"][5:7])
        by_month.setdefault(y, {})[m] = r["value"]
    years = sorted(by_month)
    rows = []
    prev_close = equity_series[0]["value"]
    for y in years:
        months = [None] * 12
        for m in range(1, 13):
            if m in by_month[y]:
                months[m - 1] = round((by_month[y][m] / prev_close - 1) * 100, 2)
                prev_close = by_month[y][m]
        ym = [v for v in months if v is not None]
        if ym:
            comp = 1.0
            for v in ym:
                comp *= (1 + v / 100)
            rows.append({"year": y, "months": months, "ytd": round((comp - 1) * 100, 2)})
    return rows


def buy_and_hold(bars, eval_start, eval_end, initial_cash=1_000_000.0):
    """买入持有基准：评估区间首日开盘全仓买入，末日收盘计价。"""
    win = [b for b in bars if eval_start <= b.date <= eval_end]
    if len(win) < 2:
        return []
    shares = int(initial_cash / win[0].open)
    return [{"date": b.date, "value": shares * b.close + (initial_cash - shares * win[0].open)}
            for b in win]


# --------------------------------------------------------------------------
# 事件研究
# --------------------------------------------------------------------------
def event_study(bars, events, hold_bars=20, entry="next_open", exit_at="close"):
    """events: [{"date": "2023-05-10", "label": "央行降息"}]；按交易日持仓 hold_bars 根。

    返回每事件一行，pnl_pct 为核心字段。
    """
    idx = {b.date: i for i, b in enumerate(bars)}
    rows = []
    for ev in events:
        d = _norm_date(ev["date"])
        if d not in idx:
            # 事件日非交易日 → 顺延到下一交易日
            nxt = [b.date for b in bars if b.date >= d]
            if not nxt:
                rows.append({"label": ev.get("label", d), "event_date": d, "status": "无后续行情"})
                continue
            d = nxt[0]
        i = idx[d]
        j_entry = i + 1 if entry == "next_open" else i
        j_exit = j_entry + hold_bars - 1
        if j_entry >= len(bars) or j_exit >= len(bars):
            rows.append({"label": ev.get("label", d), "event_date": d,
                         "status": "样本不足（需要 %d 根 bar）" % hold_bars})
            continue
        buy = bars[j_entry].open
        sell = bars[j_exit].close if exit_at == "close" else bars[j_exit].open
        rows.append({
            "label": ev.get("label", d),
            "event_date": d,
            "entry_date": bars[j_entry].date,
            "exit_date": bars[j_exit].date,
            "entry_price": round(buy, 4),
            "exit_price": round(sell, 4),
            "pnl_pct": round((sell / buy - 1) * 100, 3),
            "status": "ok",
        })
    return rows


def event_stats(rows):
    ok = [r for r in rows if r.get("status") == "ok"]
    if not ok:
        return {"event_count": 0}
    p = sorted(r["pnl_pct"] for r in ok)
    n = len(p)
    wins = [x for x in p if x > 0]
    med = p[n // 2] if n % 2 else (p[n // 2 - 1] + p[n // 2]) / 2
    return {
        "event_count": n,
        "skipped": len(rows) - n,
        "avg_pct": round(sum(p) / n, 3),
        "median_pct": round(med, 3),
        "win_rate_pct": round(100.0 * len(wins) / n, 2),
        "best_pct": round(p[-1], 3),
        "worst_pct": round(p[0], 3),
        "stdev_pct": round(statistics.pstdev(p), 3) if n > 1 else 0.0,
    }


# --------------------------------------------------------------------------
# 参数扫描
# --------------------------------------------------------------------------
def param_sweep(runner, grid):
    """runner(cfg) -> dict(metric_name -> value)

    grid: {"fast": [5, 10], "slow": [20, 60]}
    返回 [{**cfg, **result}]，供报告画稳健性表。
    """
    keys = list(grid.keys())
    combos = [{}]
    for k in keys:
        combos = [dict(c, **{k: v}) for c in combos for v in grid[k]]
    out = []
    for cfg in combos:
        try:
            res = runner(cfg) or {}
        except Exception as exc:  # 单点失败不拖垮整张表
            res = {"error": str(exc)}
        row = dict(cfg)
        row.update(res)
        out.append(row)
    return out


if __name__ == "__main__":
    print("btcore %s — 这是一个库模块，示例见 kit/examples/ 与 tools/selftest.py" % __version__)
