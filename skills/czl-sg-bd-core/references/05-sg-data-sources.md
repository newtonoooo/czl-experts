# 新加坡公开数据源目录

## 一、接入方式分层

汇报数据能力时必须区分四层，不得把"知道网址"说成"能调数据"。

| 层 | 标记 | 含义 |
|----|------|------|
| API | `[API]` | 可直接 HTTP 请求取结构化数据，无需授权 |
| 网页 | `[WEB]` | 需人工或浏览器交互查询，无法稳定自动化 |
| 授权 | `[AUTH]` | 需注册、付费或机构账号 |
| 参考 | `[REF]` | 仅作背景知识与术语校准，不用于取数 |

## 二、已验证可用的 API（2026-10-28 实测）

### 2.1 企业实体登记 — ACRA 开放数据集合

`[API]` 集合元数据（无需鉴权）：

```
GET https://api-production.data.gov.sg/v2/public/api/collections/2/metadata
```

实测返回：`collectionId=2`，名称 `ACRA Information on Corporate Entities`，含 27 个子数据集（按首字母分文件，另加 others），`lastUpdatedAt=2026-10-14`，`frequency` 为月度更新。

单表检索：

```
GET https://data.gov.sg/api/action/datastore_search?resource_id=<datasetId>&limit=50
```

实测（`resource_id=d_af2042c77ffaf0db5d75561ce9ef5688`，即 "A" 开头企业）：总记录 58,040 条；返回字段包含
`uen`、`entity_name`、`entity_type_description`、`entity_status_description`、`registration_incorporation_date`、
`primary_ssic_code`、`primary_ssic_description`、`primary_user_described_activity`、`no_of_officers`、`postal_code`、`building_name`。

过滤检索（实测可用，结果 11,821 条）：

```
GET https://data.gov.sg/api/action/datastore_search?resource_id=<datasetId>&limit=50&filters={"entity_status_description":["Live Company"]}
```

**用法**：先用 SSIC 方向筛 `primary_ssic_code`，再用 `entity_status_description=Live Company` 去掉已注销主体，最后用 `no_of_officers`、地址字段做规模与地理初筛。这是"建池"段最可靠的起点。

**局限**：仅含登记信息，不含营收、员工数、采购记录；按首字母分表，检索时必须遍历 27 个 datasetId 或先定位首字母表。

### 2.2 统计口径 — SingStat

`[WEB]` 官方统计门户与表构建器可用于核对指标口径（指标名、地理范围、时间范围、统计对象四要素）。
`[API]` SingStat 提供开发者接口，使用前需按其文档申请密钥；**本专家不预置该密钥，未做调用验证**，因此不得声称"可实时取 SingStat 数据"。

**用法**：核对"新加坡 vs 东南亚""数字经济 vs 电子商务""集团 vs 本地实体"这类口径问题时，以 SingStat 表定义为准。

## 三、机构主页与入口（`[WEB]`，可访问性抽查 2026-10-28）

抽查方式：脚本以普通 UA 请求主页，记录 HTTP 状态。403 通常为站点反爬，不代表站点不可用，人工浏览器访问正常。

| 机构 | 用途 | 地址 | 抽查 |
|------|------|------|------|
| Data.gov.sg | 开放数据总入口 | https://www.data.gov.sg/ | 200 |
| ACRA | 企业登记、主体核验 | https://www.acra.gov.sg/ | 200 |
| SingStat | 官方统计 | https://www.singstat.gov.sg/ | 200 |
| GeBIZ | 政府招标公告 | https://www.gebiz.gov.sg/ | 200 |
| MAS | 金融机构持牌目录 | https://www.mas.gov.sg/ | 200 |
| MOM | 准证、薪资门槛、雇佣规则 | https://www.mom.gov.sg/ | 200 |
| IRAS | 税率与税务规则 | https://www.iras.gov.sg/ | 200 |
| Enterprise Singapore | 企业扶持、国际化计划 | https://www.enterprisesg.gov.sg/ | 403（反爬） |
| EDB | 投资促进、行业准入 | https://www.edb.gov.sg/ | 200 |
| JTC | 工业用地与厂房 | https://www.jtc.gov.sg/ | 200 |
| URA | 城市规划与商业物业 | https://www.ura.gov.sg/ | 200 |
| SFA | 食品进口与海外认可 | https://www.sfa.gov.sg/ | 200 |
| HSA | 医疗器械与健康产品 | https://www.hsa.gov.sg/ | 200 |
| BCA | 建筑与工程承包资质 | https://www.bca.gov.sg/ | 200 |
| Singapore Customs | 关税与贸易合规 | https://www.customs.gov.sg/ | 200 |
| SBF | 新加坡工商总会（会员网络） | https://www.sbf.org.sg/ | 403（反爬） |
| SCCCI | 中华总商会（华商网络） | https://www.sccci.org.sg/ | 200 |
| CEA | 中资企业（新加坡）协会 | https://cea.org.sg/ | 200 |
| Startup SG | 初创生态目录 | https://www.startupsg.gov.sg/ | 200 |
| 驻新加坡使馆经商处 | 中文经贸与政策解读 | https://sg.mofcom.gov.cn/ | TLS 握手失败（本地网络限制） |

> 抽查仅代表"该时刻该 UA 可达"，不代表页面结构与内容不变。引用具体页面时须另行记录访问日期。

## 四、按任务选入口

| 任务 | 首选 | 次选 |
|------|------|------|
| 建候选池 | ACRA 开放数据集合 `[API]` | 协会会员目录 `[WEB]` |
| 核验主体是否存续 | ACRA 开放数据 `entity_status_description` | ACRA 官网检索 `[WEB]` |
| 判断是否持牌 | 对应监管机构持牌目录 `[WEB]` | 监管公告 |
| 找政府项目 | GeBIZ `[WEB]` | 业主官网 Tender 页 |
| 找工程/建筑类伙伴 | BCA 目录 `[WEB]` | 协会会员名录 |
| 找食品/农产品买家 | SFA 相关名录 `[WEB]` | 行业协会 |
| 核对市场规模与增速 | SingStat `[WEB]` | 官方年报 |
| 找中资企业线索 | CEA 会员动态 `[WEB]` | 中文财经媒体 `[B 级]` |
| 找华商渠道 | SCCCI 会员目录 `[WEB]` | SBF 会员目录 |
| 选址与园区 | JTC `[WEB]`、URA `[WEB]` | 园区运营方官网 |

## 五、使用规则

1. **API 有更新延迟**：企业登记为月度更新，重要决策前回查官网。
2. **不得跨口径引用**：东盟区域数据不能当作新加坡本地增长；集团全球营收不能当作本地业务体量。
3. **不得把名录当客户**：协会会员、参展商名录只证明"存在与活跃"，不证明"有采购需求"。
4. **不得把 403 当不存在**：站点反爬与站点下线是两件事，需人工复核后再下结论。
5. **记录三要素**：引用任何页面时记录"页面名 + 访问或发布日期 + URL"，缺一项则该条最高 B 级。
