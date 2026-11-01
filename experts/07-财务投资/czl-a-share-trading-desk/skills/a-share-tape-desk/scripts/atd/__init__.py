"""盘锋 · A股盘中交易参谋 数据引擎。

模块划分：
    codes       代码解析、板块归属、涨跌幅限制规则
    clock       交易时段判定、数据时效
    net         带主机健康度与本地缓存的 HTTP 层
    quotes      实时快照（腾讯主源 / 新浪备源）
    history     日线与分钟线（腾讯主源 / 东方财富备源）
    indicators  纯本地指标计算（MA/EMA/MACD/KDJ/RSI/BOLL/ATR）
    market      全市场扫描与情绪评分
    sectors     板块排行与龙头识别
    risk        仓位、止损、盈亏比计算
    watch       结构化预警清单

设计约束：仅依赖 Python 标准库，无第三方包，便于商业分发与跨平台运行。
"""

__version__ = "1.0.0"
__all__ = [
    "codes",
    "clock",
    "net",
    "quotes",
    "history",
    "indicators",
    "market",
    "sectors",
    "risk",
    "watch",
]
