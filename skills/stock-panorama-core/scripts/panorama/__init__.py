"""个股全景诊断引擎（Panorama Diagnostics Engine）。

本包只做三件事：
1. 把用户/工具给出的原始数据规范化、算指标；
2. 用公开、可复核的规则打分，并明确标注缺失项；
3. 把结果渲染成结构化报告。

刻意不依赖任何第三方库（无 numpy / pandas / requests），便于在任意
WorkBuddy 环境里直接跑；也不内嵌任何外部数据源，取数交给上层工具适配层。
"""

__version__ = "1.0.0"
__all__ = ["indicators", "schema", "scorecard", "levels", "qa", "report"]
