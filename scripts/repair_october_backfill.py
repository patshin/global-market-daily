#!/usr/bin/env python3
"""Deterministic, source-backed October archive repair. No model API or production push.
Inputs: immutable repository/candidate snapshot and official Treasury/Cboe history.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
BUILT=None
N='尚无法可靠确认'
KEYS=['top_catalysts','earnings','us_macro','central_banks','geopolitics','regional_policy','index_changes','flows','etf','options','treasury','commodities','financing','breaking_news','market_impact']
TITLES=['核心催化剂','重要财报与盈利质量','美国宏观数据','央行与利率路径','地缘与供应风险','区域及产业政策','指数与成分调整','资金流与融资条件','ETF与资产配置','期权与波动率','美国国债与收益率曲线','商品与成本传导','融资与资本开支','截点内新增信息','跨资产影响与验证']
SERIES_URL='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve'
VIX_URL='https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'
SOURCES={
'S01':('U.S. Treasury','Daily Treasury Par Yield Curve Rates, 2026',SERIES_URL,'historical-series'),
'S02':('Cboe','VIX Historical Data',VIX_URL,'historical-series'),
'S03':('Federal Reserve Bank of St. Louis / S&P DJI','S&P 500 daily close','https://fred.stlouisfed.org/series/SP500','historical-series'),
'S04':('Federal Reserve Bank of St. Louis / Nasdaq','Nasdaq Composite daily close','https://fred.stlouisfed.org/series/NASDAQCOM','historical-series'),
'S05':('EIA via FRED','Europe Brent Spot Price FOB; NOT front-month futures','https://fred.stlouisfed.org/series/DCOILBRENTEU','historical-series'),
'S06':('Federal Reserve via FRED','Nominal Broad U.S. Dollar Index; NOT DXY','https://fred.stlouisfed.org/series/DTWEXBGS','historical-series'),
'S07':('ICE BofA via FRED','US High Yield Index Option-Adjusted Spread','https://fred.stlouisfed.org/series/BAMLH0A0HYM2','historical-series'),
'S10':('BLS','Consumer Price Index — September 2026','https://www.bls.gov/news.release/archives/cpi_10142026.htm','2026-10-14T08:30:00-04:00'),
'S11':('Bank of America investor relations','Third-quarter 2026 earnings release, Exhibit 99.1','https://investor.bankofamerica.com/regulatory-and-other-filings/select-sec-filings/content/0000070858-26-000481/bac09302026ex991.htm','2026-10-14'),
'S12':('Morgan Stanley','Third-quarter 2026 financial information','https://www.morganstanley.co.jp/en/about-us/financial-information','2026-10-14'),
'S13':('TSMC investor relations','2026 Q3 earnings conference schedule and previous guidance','https://investor.cld.tsmc.com/english/quarterly-results/2026/q3','schedule-known-before-cutoff'),
'S14':('BLS','Producer Price Index — September 2026','https://www.bls.gov/news.release/archives/ppi_10152026.htm','2026-10-15T08:30:00-04:00'),
'S15':('TSMC / SEC','TSMC Q3 2026 results and Q4 guidance','https://www.sec.gov/Archives/edgar/data/1046179/000104617926000726/a3q26e_withguidancexfinal.htm','2026-10-15'),
'S16':('Ministry of Commerce of China','Technology export catalogue proposal and interim registration Q&A','https://www.mofcom.gov.cn/zwgk/zcjd/art/2026/art_b11d5c1e9374421e93e85dc87eba6e38.html','2026-10-16T16:00:00+08:00'),
'S17':('Reuters','China proposes adding 40 AI, biotech and solar technologies to export-control list','https://www.reuters.com/world/asia-pacific/china-proposes-adding-40-ai-biotech-solar-technologies-export-control-list-2026-10-16/','2026-10-16'),
'S18':('DPA via Yahoo Finance','US industrial production climbs more than expected in September','https://finance.yahoo.com/economy/articles/us-industrial-production-climbs-more-141824494.html','2026-10-16T10:18:00-04:00'),
'S19':('NYSE','Markets hours and calendars','https://www.nyse.com/markets/hours-calendars','schedule-known-before-cutoff'),
'S20':('Associated Press via ABC News','How major US stock indexes fared Wednesday 10/14/2026','https://abcnews.com/Business/wireStory/major-us-stock-indexes-fared-wednesday-10142026-137270020','2026-10-14T16:19:00-04:00'),
'S21':('Associated Press','How major US stock indexes fared Thursday 10/15/2026','https://apnews.com/article/f0a4f8aa60a6a24237c419aba38f31fd','2026-10-15T20:22:16+00:00'),
'S22':('Associated Press','How major US stock indexes fared Friday 10/16/2026','https://apnews.com/article/c27809783ae3230b44c26e5ee4bea056','2026-10-16T20:17:22+00:00'),
'S23':('Zacks','TSMC Q3 earnings, revenues and management outlook','https://www.zacks.com/stock/news/3008590/taiwan-semiconductor-q3-earnings-revenues-top-estimates-margins-up','2026-10-15'),
'S24':('Transport Topics','US PPI inflation September 2026','https://www.ttnews.com/articles/ppi-inflation-september-2026','2026-10-15'),
'S25':('Republic of Türkiye Ministry of Trade','U.S. September CPI official-release summary','https://www.trade.gov.tr/news/consumer-price-index-in-the-us-increased-by-0-6-on-a-monthly-basis-in-september-2026','2026-10-14'),
'S26':('Federal Reserve','G.17 industrial production release calendar','https://www.federalreserve.gov/releases/g17/','schedule-known-before-cutoff'),
'S27':('BLS','Schedule of releases for October 2026','https://www.bls.gov/schedule/2026/10_sched.htm','schedule-known-before-cutoff')}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def refs(x):
 out=set()
 if isinstance(x,dict):
  for k,v in x.items():
   if k=='sources' and isinstance(v,list):out.update(s for s in v if isinstance(s,str))
   else:out.update(refs(v))
 elif isinstance(x,list):
  for v in x:out.update(refs(v))
 return out

def markdown(r):
 lines=[f"# Global Market Daily — {r['edition']} — {r['date']}",'- Publication Cycle: morning / official / final',f"- Cutoff: {r['data_cutoff_sgt']} / {r['data_cutoff_et']}"]
 if r.get('reconstruction',{}).get('is_reconstructed'):
  lines += [f"- 历史补档：{r['reconstruction']['reconstructed_at']} 重建，并非当日发布；禁止计入原生日报。",*['- '+x for x in r['reconstruction']['limitations']]]
 lines+=['','## Thesis',r['thesis'],'','## Dominant Narrative',r['dominant_narrative']]
 def emit(x,level=3):
  if isinstance(x,dict):
   for k,v in x.items():lines.append('#'*min(level,6)+' '+k);emit(v,level+1)
  elif isinstance(x,list):
   for v in x:
    if isinstance(v,(dict,list)):emit(v,level)
    else:lines.append('- '+str(v))
  else:lines.append(str(x))
 for key in ('market_regime','market_tape','what_changed','top_catalysts','signal_panel','scenario_matrix','upcoming_market_watch','top_risks','next_catalyst'):
  lines.extend(['','## '+key]);emit(r[key])
 for key in r['section_order']:
  s=r['sections'][key];lines.extend(['',f"## {s['number']:02d} {s['title']}"]);emit({k:v for k,v in s.items() if k not in {'number','title'}})
 lines+=['','## Source archive',r['sources_path'],', '.join(r['sources'])]
 return '\n'.join(lines)+'\n'

def source_doc(day,r):
 cutoff=datetime.fromisoformat(day+'T09:00:00+08:00');records=[]
 for sid in sorted(refs(r)):
  name,title,url,published=SOURCES[sid]
  rec=dict(id=sid,source_name=name,source_title=title,source_url=url,published_at=published,retrieved_at=BUILT,tier='Tier 1 — primary' if sid not in {'S17','S18','S20','S21','S22','S23','S24'} else 'Tier 2 — financial reporting',used_for='Source-linked fields in the canonical daily; historical point-in-time reconstruction',confidence='Historical evidence with explicitly disclosed vintage and retrieval limitations')
  if 'T' in published and re.match(r'^\d{4}-',published):
   available=datetime.fromisoformat(published);assert available<=cutoff,(day,sid,published);rec['available_by_utc']=available.astimezone(ZoneInfo('UTC')).isoformat()
  elif re.fullmatch(r'\d{4}-\d{2}-\d{2}',published):
   available=datetime.fromisoformat(published+'T00:00:00+00:00')+timedelta(days=1);assert available<=cutoff,(day,sid,published);rec['available_by_utc']=available.isoformat()
  else:rec['historical_availability_note']='Current historical-series vintage retrieved during repair, not the original database snapshot. Each observation has a prior-session date; provider publication lag and revisions may differ from the information available at the historical morning cutoff. Calendar/schedule pages are used only for scheduled-event metadata, not subsequent results.'
  rec['retrieval_note']='Official Treasury/Cboe history downloaded as audit artifacts. News/issuer facts verified from source-index excerpts and independent reporting where direct page retrieval failed; a resolvable citation is not evidence of an original saved intraday snapshot.'
  records.append(rec)
 return dict(schema_version='1.0.0',date=day,generated_at=BUILT,sources=records)

def histories(snapshot,treasury,cboe):
 result={}
 for p in (snapshot/'repository/history').glob('*.csv'):
  sid=p.stem;rows=[]
  for row in csv.DictReader(p.open(encoding='utf-8-sig')):
   try:rows.append((row['observation_date'],float(row[sid])))
   except (KeyError,ValueError,TypeError):pass
  result[sid]=dict(rows)
 ns={'a':'http://www.w3.org/2005/Atom','m':'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'}
 for y in (2,5,10,30):result['UST'+str(y)]={}
 for entry in ET.parse(treasury/'treasury.xml').findall('a:entry',ns):
  props=entry.find('a:content/m:properties',ns)
  if props is None:continue
  v={x.tag.split('}')[-1]:x.text for x in props};day=v.get('NEW_DATE','')[:10]
  for y in (2,5,10,30):
   try:result['UST'+str(y)][day]=float(v['BC_'+str(y)+'YEAR'])
   except (ValueError,KeyError,TypeError):pass
 vix={}
 for row in csv.DictReader((cboe/'cboe-vix.csv').open(encoding='utf-8-sig')):
  try:vix[datetime.strptime(row['DATE'],'%m/%d/%Y').date().isoformat()]=float(row['CLOSE'])
  except (ValueError,KeyError):pass
 result['VIXCLS']=vix
 result['NASDAQCOM']['2026-10-16']=26140.03
 result['DOW']={'2026-10-13':51670.10,'2026-10-14':51621.48,'2026-10-15':52177.69,'2026-10-16':52002.41}
 result['RUT']={'2026-10-13':2783.37,'2026-10-14':2729.53,'2026-10-15':2767.27,'2026-10-16':2721.37}
 for name,a,b in [('2s10s','UST2','UST10'),('10s30s','UST10','UST30')]:result[name]={d:(result[b][d]-v)*100 for d,v in result[a].items() if d in result[b]}
 return result

def tape(day,h):
 session=(datetime.fromisoformat(day)-timedelta(days=1)).date().isoformat();src={'2026-10-14':'S20','2026-10-15':'S21','2026-10-16':'S22'}[session]
 specs=[('SP500','S&P 500','price','S03'),('NASDAQCOM','Nasdaq Composite','price','S04'),('DOW','Dow Jones Industrial Average','price',src),('RUT','Russell 2000','price',src),('VIXCLS','VIX','price','S02'),('UST2','UST 2Y','yield','S01'),('UST5','UST 5Y','yield','S01'),('UST10','UST 10Y','yield','S01'),('UST30','UST 30Y','yield','S01'),('2s10s','UST 2s10s','spread','S01'),('10s30s','UST 10s30s','spread','S01'),('DCOILBRENTEU','Europe Brent Spot','price','S05'),('DTWEXBGS','Broad Trade-Weighted USD','price','S06'),('BAMLH0A0HYM2','US High Yield OAS','yield','S07')]
 out=[]
 for sid,asset,kind,source in specs:
  rows=sorted((d,v) for d,v in h[sid].items() if d<=session)
  if not rows:raise ValueError((day,sid,'no historical evidence'))
  d,v=rows[-1]
  def delta(n):
   if len(rows)<=n:return None
   b=rows[-n-1][1]
   return (v-b)*100 if kind=='yield' else v-b if kind=='spread' else (v/b-1)*100
  one,five=delta(1),delta(5);unit='bp' if kind in {'yield','spread'} else '%'
  def fmt(x):return f'{x:+.2f}{unit}' if x is not None else N
  level=f'{v:.2f}%' if kind=='yield' else f'{v:.2f}bp' if kind=='spread' else f'{v:,.2f}';stale=d!=session
  out.append(dict(asset=asset,level=level,change_1d=fmt(one),change_5d=fmt(five),signal='历史观测；不等于截点实时报价',driver='资金成本、风险偏好与现金流的交叉验证；不同标的和数据发布时滞分别披露。',status='历史序列/滞后观测' if stale else '历史前一交易日观测',as_of=d+' previous-session historical observation; retrieved '+BUILT,sources=[source,src] if sid in {'SP500','NASDAQCOM'} else [source],recovery_observation=dict(session_date=d,original_snapshot_recovered=False,level=round(v,8),change_1d=None if one is None else round(one,8),change_5d=None if five is None else round(five,8),change_unit=unit,series_id=sid,vintage_note='Current retrieved historical vintage, not an original contemporaneous database snapshot; same-instrument observation-to-observation returns; 5D means five observed sessions, not five calendar days.'),coverage_note='Provider observation is older than report reference session; not counted as fresh-session coverage.' if stale else 'Prior completed session; no report-date future U.S. close.'))
 q={'asset_count':len(out),'publish_status':'HISTORICAL_RECONSTRUCTION_WITH_VINTAGE_AND_LAG_DISCLOSURE','explicit_gaps':[f"{t['asset']}: 5D {N}" for t in out if t['recovery_observation']['change_5d'] is None]}
 for key,f in [('level_coverage','level'),('change_1d_coverage','change_1d'),('change_5d_coverage','change_5d')]:
  count=sum(t['recovery_observation'][f] is not None for t in out);q[key]={'count':count,'total':len(out),'pct':round(100*count/len(out),1),'target_pct':80 if f=='change_5d' else 90}
 q['fresh_session_coverage']={'count':sum(t['recovery_observation']['session_date']==session for t in out),'total':len(out),'reference_session':session,'note':'Verified historical values and same-session freshness are distinct. Lagged Brent/HY/broad USD remain dated, never filled forward.'}
 q['policy']='CMT yields are not Yahoo TNX; Europe Brent spot is not ICE futures; broad trade-weighted USD is not DXY. Missing original vintage, tape-wide synchronized snapshot and some 5D observations remain disclosed.'
 return out,q

CONFIG={
'2026-10-15':dict(thesis='9月美国CPI的能源推升与10月14日科技股回撤共同收紧估值容错空间，但长端国债并未同步上行。应分开核验通胀构成、银行利润的一次性影响及尚未公布的台积电财报，而不是将全部资产归因为同一个加息交易。',narrative='本期在10月19日补写，只使用10月15日09:00 SGT以前可获得的事实。BLS于10月14日公布9月CPI环比0.6%、同比3.7%，汽油上涨9.1%贡献过半月度增量；核心环比0.3%。美国10月14日S&P 500收于7,718.94、Nasdaq收于26,692.87，而国债2年期CMT为4.82%、10年期为5.19%，提示前端政策与长端增长风险的方向并不一致。银行利润要区分报告口径、监管费用与经常性业务；台积电10月15日财报及当晚PPI在本截点仍属待公布，不能倒灌后来结果。',regime='Risk-Off / energy inflation and growth-duration de-rating',facts=[
('9月CPI能源贡献突出，核心价格仍需独立跟踪','2026-10-14 08:30 EDT','2026-10-14 20:30 SGT','9月CPI环比上升0.6%、同比3.7%；汽油环比9.1%、能源5.2%、居住0.4%。核心环比0.3%，不能把能源冲击与核心持续性混为一谈。','能源拉高家庭成本，影响真实购买力；核心价格粘性和需求约束须通过后续数据分别确认。',['S10','S25'],'energy_inflation'),
('银行财报的利润质量与业务结构出现分化','2026-10-14 US premarket','2026-10-14 SGT evening','美国银行第三季收入299.58亿美元、净利润69.33亿美元、稀释EPS 0.91美元；摩根士丹利收入约203亿美元。不同业务及一次性费用影响，意味着不能把总收入增长直接当作全行业盈利改善。','从银行收入、费用与信用成本分拆观察资金需求，避免单一EPS数字掩盖经常性回报和资本消耗。',['S11','S12'],'credit_conditions'),
('美国科技股回落与收益率曲线变化未形成同向冲击','2026-10-14 16:00 EDT','2026-10-15 04:00 SGT','10月14日S&P 500收于7,718.94、Nasdaq为26,692.87，后者回撤更大；同日2年国债CMT升至4.82%，10年为5.19%。股价回落不能机械解释为所有期限收益率同时上升。','长久期股估值还受盈利预期和风险溢价约束；需将股指相对表现与各期限融资成本逐一对照。',['S20','S01','S03','S04'],'global_duration')],signals=['↓ 科技股与风险偏好承压','↑ 能源推升消费者价格','↕ 前端偏紧、长端回落','↕ 银行利润与待发科技财报分化','↓ 信用利差约束未消','↑ 能源价格尾部风险'],earnings='BAC',next=('TSMC Q3 2026 earnings conference','2026-10-15','02:00 EDT','14:00 SGT','S13'),macro=['S10','S25'],policy=['S10','S01']),
'2026-10-16':dict(thesis='9月PPI大幅上行扩大企业成本压力，台积电第三季度强劲结果提供先进制程需求证据；但10月15日美债长端回落与美股温和反弹说明市场同时交易增长和融资风险。供应商盈利、客户现金回报与估值折现必须分开验证。',narrative='本期历史截点为10月16日09:00 SGT。已公布的9月PPI环比1.3%、同比6.3%，说明企业成本渠道仍紧；台积电第三季美元收入467.2亿美元，Q4美元收入指引523亿至543亿美元属于预测而非订单现金已回收。10月15日S&P 500收于7,744.06、Nasdaq为26,713.03，10年CMT降至5.10%、30年降至5.43%，呈现成本风险与利率缓冲并存。当天稍后美国工业生产尚待发布；10月16日下午才发布的中国技术出口目录信息也不属于本早间截点。',regime='Event Risk / producer-cost shock versus duration relief',facts=[
('9月PPI环比1.3%令企业成本传导成为约束','2026-10-15 08:30 EDT','2026-10-15 20:30 SGT','BLS公布9月最终需求PPI环比上涨1.3%、同比6.3%；商品和服务价格均有压力。PPI衡量生产者收到的价格，不应直接替代CPI或对企业净利润作一比一推算。','产品提价能力与销量变化决定成本是否被吸收；应核验毛利、终端需求和信用利差而非机械外推。',['S14','S24'],'energy_inflation'),
('台积电Q3实绩与Q4指引强化先进制程需求证据','2026-10-15 Taiwan earnings release','2026-10-15 14:00 SGT conference','台积电第三季度美元收入467.2亿美元、净利润7,630.6亿新台币、稀释EPS29.43新台币；毛利率66.4%。Q4收入指引为523亿至543亿美元，是管理层展望，不等于客户资本开支已经实现最终现金回报。','代工实绩支持上游需求，但下游融资与利用率仍决定AI资本开支的回收；两端不能画等号。',['S15','S23'],'ai_earnings'),
('美债长端下行与美股反弹提供有限风险缓冲','2026-10-15 US market close','2026-10-16 04:00 SGT cash close','10月15日S&P 500收于7,744.06、Dow为52,177.69，Nasdaq仅温和回升至26,713.03；10年CMT较前次下行9bp至5.10%。利率缓冲存在，但成长股并未因此全面重获领先。','风险偏好修复必须同时得到股票广度与融资条件确认；只有国债收益率下行不足以证明风险出清。',['S21','S01','S02'],'global_duration')],signals=['↕ 总体股指反弹、科技修复弱','↑ 生产者价格压力明显','↓ 长端融资折现率回落','↑ 先进制程实绩较强','↕ 边际改善但周度信用偏紧','↑ 能源成本风险仍在'],earnings='TSMC',next=('US industrial production September release','2026-10-16','09:15 EDT','21:15 SGT','S26'),macro=['S14','S24','S10'],policy=['S14','S01']),
'2026-10-17':dict(thesis='科技股与波动率的10月16日价格反应显示风险溢价上升，中国技术出口目录调整的征求意见与临时登记机制又增加交易执行不确定性。美国工业生产总量改善并不等于制造业普遍加速，周末评估应保留政策阶段、部门差异和休市边界。',narrative='本期在10月19日重建10月17日09:00 SGT的信息集，没有周六美国收盘。10月16日Nasdaq收于26,140.03，S&P 500为7,659.44；Cboe VIX收于19.99。商务部已公布涉及40项技术的出口目录修订征求意见，23项AI、5项生物、12项太阳能；目录草案与过渡期登记要求不是同一法律状态，不能概括为40项技术已全面禁止出口。美国9月工业生产环比0.7%，制造业仅0.3%，公用事业3.5%贡献较大。央行与市场风险定价须结合这些结构，而不是把工业总量或单家代工财报当作统一增长信号。',regime='Risk-Off / technology repricing and policy implementation risk',facts=[
('中国40项技术出口目录草案与临时登记需要分开识别','2026-10-16 04:00 EDT','2026-10-16 16:00 SGT','商务部材料及Reuters报道涉及40项拟增技术：23项人工智能、5项生物技术、12项太阳能。征求意见中的目录调整并非全部已经生效的禁令；过渡期登记安排则可能先影响交易流程。','出口执行时间、许可适用范围与合同交付是可验证路径；不能仅凭草案推算出口数量或收入损失。',['S16','S17'],'us_china_trade_controls'),
('Nasdaq下跌约2.1%并伴随VIX升至19.99','2026-10-16 16:00 EDT','2026-10-17 04:00 SGT','10月16日Nasdaq收于26,140.03、S&P 500为7,659.44，Russell 2000为2,721.37；VIX收19.99。股票与隐含波动率显示压力，但VIX本身不是做市商gamma或未来下跌概率。','风险溢价与融资敏感资产首先承压，后续需要股票广度、信用价差及企业盈利共同确认，而非单看VIX。',['S22','S02'],'volatility_event_risk'),
('美国工业生产0.7%增幅由部门结构而非普遍扩张驱动','2026-10-16 09:15 EDT release; 10:18 EDT report','2026-10-16 21:15 SGT release','根据DPA对美联储公布数据的报道，9月工业生产环比0.7%，其中制造业0.3%、采矿0.2%、公用事业3.5%；产能利用率76.9%。总工业增幅不能替代制造业增幅或GDP判断。','需求验证应看制造业和企业订单，而非将天气敏感公用事业跳升外推为全经济加速；增长与成本须分别定价。',['S18'],'equity_risk_appetite')],signals=['↕ 工业总量与制造业增幅分化','↑ 生产成本约束仍在','↓ CMT长端较此前下行','↕ 代工需求与科技估值分化','↓ 风险溢价和融资压力','↑ 政策与交付尾部风险'],earnings='TSMC',next=('US cash equity market Monday reopening','2026-10-19','09:30 EDT','21:30 SGT','S19'),macro=['S18','S14'],policy=['S16','S17'])}

def earning(company):
 if company=='BAC':
  metrics=[('Revenue','US$29.958bn'),('Net income','US$6.933bn'),('Diluted EPS','US$0.91')];name,ticker,day,source='Bank of America','BAC','2026-10-14','S11';takeaway='报告净利润和收入必须与费用、信用成本分拆；未恢复完整一致预期及逐项调整桥，不自行计算经营性超预期。';guidance=[]
 elif company=='MS':
  metrics=[('Net revenue','US$20.3bn')];name,ticker,day,source='Morgan Stanley','MS','2026-10-14','S12';takeaway='收入提供业务活动观察，但不能仅凭收入增长外推EPS、利润率或整个银行业信用表现。';guidance=[]
 else:
  metrics=[('Revenue','US$46.72bn'),('Net income','NT$763.06bn'),('Diluted EPS','NT$29.43 / US$4.60 per ADR'),('Gross margin','66.4%')];name,ticker,day,source='Taiwan Semiconductor Manufacturing','TSM','2026-10-15','S15';takeaway='先进制程需求已在当季收入中实现；未来指引仍需交付，且不能代替下游客户的融资质量或最终投资回报。';guidance=[dict(metric='Q4 2026 revenue in USD',current='US$52.3–54.3bn',previous_or_consensus=N,change='Forward management range; not realized revenue',interpretation='管理层展望，不冒充历史共识或已到账现金。')]
 return dict(id=ticker+'-2026Q3',company=name,ticker=ticker,period='2026 Q3',status='Released/Occurred',release_date=day,release_time_et=day+' '+('US premarket; exact issuer minute not recovered' if ticker!='TSM' else '02:00 EDT conference'),release_time_sgt=day+' '+('SGT evening before historical cutoff' if ticker!='TSM' else '14:00 SGT conference'),market_session='US premarket' if ticker!='TSM' else 'Taiwan earnings-release day / U.S. premarket',key_takeaway=takeaway,metrics=[dict(metric=k,actual=v,consensus=N,previous_or_yoy=N,surprise='未恢复历史一致预期，不计算虚构surprise',notes='Issuer-reported period and currency preserved; no estimated adjustment bridge.') for k,v in metrics],guidance=guidance,market_reaction=dict(session='发布日；同一报告/交易时段区分',move=N,as_of=day+'; individual stock reaction not restored'),one_offs=['完整会计调整桥与所有一次性项目未恢复，不从缺失推断不存在。'],read_through=[dict(asset='Financials' if ticker!='TSM' else 'Semiconductor supply chain',implication=takeaway)],sources=[source]+(['S23'] if ticker=='TSM' else []))

def construct(day,h):
 c=CONFIG[day];cutoff=day+' 09:00 SGT';et=datetime.fromisoformat(day+'T09:00:00+08:00').astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M %Z');mt,quality=tape(day,h)
 limits=['2026年10月19日事后重建，不是找到原09:00稿件，分析/排序/情景是重建判断；不计原生日报。','历史信息截止为该日09:00 SGT；不使用该日之后公布的财报、宏观结果或美国现金收盘。','行情来自修复时获取的历史日度序列，并非原始盘中快照；数据版本修订及提供方发布滞后不可完全还原。','Europe Brent spot、固定月份期货、Broad USD和DXY不能拼接；落后于参考交易日的观测单独标记，未前向填充。','全量指数变更、ETF篮子、机构净流、dealer gamma、拍卖WI/尾差以及历史财报一致预期和完整会计调整桥未恢复；资料缺失不代表无事件。','原始网页部分无法直接抓取，采用可验证官方索引摘录与独立报道交叉检查；来源引用可解析不代表原网页全部归档。']
 r=dict(schema_version='1.1.0',date=day,edition='Morning Official — Historical Reconstruction / 历史补档',edition_status='official',timezone='Asia/Singapore',data_cutoff_sgt=cutoff,data_cutoff_et=et,last_updated=BUILT,source_mode='reconstructed_daily',sources_path=f'data/sources/{day}.json',publication_cycle=dict(status='official',cycle='morning',is_final=True,archive_eligible=True,market_lens_native_eligible=False),reconstruction=dict(is_reconstructed=True,reconstructed_at=BUILT,historical_cutoff_sgt=cutoff,limitations=limits,market_session=(datetime.fromisoformat(day)-timedelta(days=1)).date().isoformat()),run_timing=dict(scheduled_for_sgt=day+'T09:00:00+08:00',reconstructed_at_sgt=BUILT,historical_cutoff_sgt=cutoff,mode='historical_backfill'),thesis=c['thesis']+' 本期为历史补档，未恢复原始发表快照。',dominant_narrative=c['narrative'],market_tape=mt,market_tape_data_quality=quality,comparison_basis=dict(kind='historical_point_in_time',note='比较前一可核实交易日和已在本截点公布的结果；不是今日交易建议。'),what_changed=[f[0]+'：'+f[4] for f in c['facts']])
 catalysts=[]
 for i,(event,evt_et,evt_sgt,what,meaning,sources,theme) in enumerate(c['facts'],1):
  catalysts.append(dict(rank=i,event=event,importance='★★★★★' if i<3 else '★★★★',status='Released/Occurred',event_time_et=evt_et,event_time_sgt=evt_sgt,what_happened=what,what_changed=meaning+' 应与前一已知状态比较，不填入截点后的结果。',why_it_matters=meaning+' 对盈利质量、贴现率和风险溢价分别验证。',transmission=meaning,direction='Two-sided / conditional market impact',affected_assets=['U.S. equities','Treasury curve','Sector and credit instruments'],confirmation='只有相关资产价格、来源中的执行节点与后续经营数据一致，才加强这条传导判断；不预设数值门槛。',invalidation='如果成本、执行或融资渠道没有按上述路径变化，应撤回单一因果解释，并保留其他驱动因素的可能。',theme_id=theme,state='active',lifecycle_status='active',sources=sources))
 r['top_catalysts']=catalysts
 skeys=['growth_impulse','inflation_impulse','rates_pressure','earnings_revision','liquidity','geopolitical_risk'];labels=['Growth / demand','Inflation / costs','Rates / duration','Earnings quality','Financial conditions','Policy / geopolitical risk']
 sourcegroups=[c['facts'][2][5],c['facts'][0][5],['S01'],c['facts'][1][5],['S07','S02'],c['facts'][0][5]]
 evidence=[c['facts'][2][3],c['facts'][0][3],'; '.join(x['asset']+' '+x['level']+' ('+x['change_1d']+')' for x in mt if x['asset'] in {'UST 2Y','UST 10Y','UST 30Y'}),c['facts'][1][3],'; '.join(x['asset']+' '+x['level']+' as of '+x['recovery_observation']['session_date'] for x in mt if x['asset'] in {'VIX','US High Yield OAS'}),c['facts'][0][3]]
 reasons=['工业与权益只能提供不同需求观察，不把代理指标当作总体经济增长。','成本变化需经提价能力和终端需求影响利润，不能等同于立即的政策决定。','不同期限收益率体现政策、增长与期限溢价；曲线变化不能简化为所有利率同向。','报告收入、会计利润与现金回收不同，指引也不能当已实现收益。','信用价差与波动率用于金融条件观察，不等于已恢复基金申赎或银行准备金。','政策及供给不确定性通过许可、交付和风险溢价传导，不预判未公布执行结果。']
 if day=='2026-10-17':
  evidence[1]='BLS于10月15日公布9月PPI环比1.3%、同比6.3%；企业成本压力尚不能直接等同于消费者价格。';sourcegroups[1]=['S14','S24']
  evidence[3]='TSMC Q3美元收入467.2亿美元的已公布实绩，与10月16日Nasdaq收于26,140.03的科技估值回撤并存。';sourcegroups[3]=['S15','S23','S22']
 panel={k:dict(label=label,current=current,yesterday='前日可核实状态与本截点不同；不虚构历史评分',change_reason=reason,evidence=ev,sources=ss) for k,label,current,reason,ev,ss in zip(skeys,labels,c['signals'],reasons,evidence,sourcegroups)};r['signal_panel']=panel
 r['market_regime']={k:dict(state=x['current'],evidence=x['evidence'],sources=x['sources']) for k,x in zip(['growth','inflation','rates','earnings','liquidity','geopolitics'],panel.values())};r['market_regime']['overall']=dict(state=c['regime'],evidence=c['thesis'],sources=sorted(set(s for f in c['facts'] for s in f[5])))
 r['scenario_matrix']={}
 for key,label,trigger,market,confirm,invalidate in [('base_case','Base / 条件基准','已公布的成本与盈利分化继续存在，但执行或融资未出现新冲击。','股债可能继续分化，风险偏好修复依赖信用与盈利验证，不假设趋势直线外推。','曲线、信用价差与股指相对表现仍符合当前分化模式。','出现已确认的政策执行、成本或融资状态重大改变。'),('bull_case','Bull / 条件改善','成本压力缓和且已公布企业实绩能转化为现金回收。','长久期与周期资产可能获得支撑；需观察上涨广度，不只跟随单一龙头。','股票上涨同时有风险溢价收窄及融资条件稳定配合。','风险溢价扩大或新增现金流约束抵消折现率改善。'),('bear_case','Bear / 条件恶化','成本无法转嫁、政策交付受阻或融资压力进一步上升。','高资本开支与高估值资产更敏感；国债反应仍取决于通胀与增长主导渠道。','权益广度走弱同时信用风险补偿上升，且有基本面执行证据。','订单、经营现金流和融资安排的可靠改善否定了压力扩散。')]:r['scenario_matrix'][key]=dict(label=label,probability='条件情景，非统计概率',trigger=trigger,expected_market_reaction=market,assets_most_sensitive=['U.S. growth equities','Treasuries','Credit spreads'],what_confirms_it=confirm,what_invalidates_it=invalidate)
 event,ndate,net,nsgt,nsrc=c['next']
 r['next_catalyst']=dict(event=event,status='Confirmed Upcoming',date=ndate,et=net,sgt=nsgt,consensus=N,previous='参照本截点已经公布的数据，不将未来实际值代填',actual='待公布',why_it_matters='下一可观察窗口用于验证当前成本、盈利或市场风险假设；事件本身并不保证单边价格变化。',first_market='相关现货/期货与国债曲线',bull_interpretation='实绩或市场价格同时显示经营与融资压力缓和。',bear_interpretation='新增结果进一步压缩现金流或抬升风险补偿。',watch_first=['先核对官方发布时间与实际值，再比较市场预期；无法恢复共识时不宣称超预期。','再看权益广度、相关行业和国债曲线是否同向确认，不用单一资产价格代替完整判断。'],sources=[nsrc])
 r['upcoming_market_watch']=[{k:v for k,v in r['next_catalyst'].items() if k in {'event','status','date','et','sgt','consensus','previous','actual','why_it_matters','sources'}} | {'importance':'★★★★'}]
 if day=='2026-10-15':r['upcoming_market_watch'].append(dict(event='US September PPI release',status='Confirmed Upcoming',date='2026-10-15',et='08:30 EDT',sgt='20:30 SGT',consensus=N,previous='历史前值不完整恢复',actual='待公布',why_it_matters='检验企业成本与CPI能源冲击是否存在一致传导；本早间截点不能提前填写结果。',importance='★★★★★',sources=['S27']))
 r['top_risks']=[]
 for i,(title,theme,src) in enumerate([('成本压力与实际需求之间的利润挤压','energy_inflation',c['macro']),('利率缓冲不能覆盖信用和现金回收风险','global_duration',['S01','S07']),('事件执行与交易时段错位造成错误确认','market_structure',c['policy'])],1):r['top_risks'].append(dict(rank=i,risk=title,why_not_fully_priced='价格反应只能显示当时风险补偿，不能证明所有执行条件已兑现；部分底层资料未恢复，不能据此断言已经充分定价。',trigger='官方数据、执行安排或经营现金流出现可验证的增量变化。',transmission='事实变化→企业现金流或融资成本→风险补偿→相关资产价格；每个环节都需要独立证据。',first_asset='相关行业权益、国债曲线及信用工具',theme_id=theme,state='active',lifecycle_status='active',sources=src))
 r['sections']={}
 paragraphs={
 'top_catalysts':([f[3]+' '+f[4] for f in c['facts']],sorted(set(s for f in c['facts'] for s in f[5]))),
 'earnings':([c['facts'][1][3] if day!='2026-10-17' else '台积电10月15日已公布结果仍是半导体需求观察，但不是10月16日新财报；未恢复全面当日财报与历史一致预期，不能用单一公司外推整个产业盈利。'],['S11','S12','S13'] if c['earnings']=='BAC' else ['S15','S23']),
 'us_macro':([c['facts'][2][3] if day=='2026-10-17' else c['facts'][0][3]],c['macro']),
 'central_banks':(['市场利率变化不是央行承诺。根据可核实CMT曲线拆分前端政策与长端增长/期限溢价，截点后会议、讲话和隐含概率不补写；本次未恢复完整跨央行讲话档案。'],['S01']),
 'geopolitics':(['能源价格是风险传导观测，不是武装事件或实际减产的直接证据。未能恢复全部港口、运输和供应设施的原始时点材料，因此不将价格上涨归因于未经确认的物理供给损失。'],['S05','S02']),
 'regional_policy':([c['facts'][0][3] if day=='2026-10-17' else '中国、日本、欧洲和加拿大政策渠道应分别核实。本次只恢复可核对的美国产品价格、曲线及公司信息，未恢复这些地区完整政策增量；不把未找到公告写成政策没有变化。'],c['policy']),
 'index_changes':(['未恢复完整交易所及指数供应商的本时点成分变更档案。指数涨跌不证明出现被动调仓，亦不能据此编造纳入/剔除名单、生效时间或资金规模；相关字段保持证据缺口。'],[]),
 'flows':(['HY OAS、国债收益率与VIX显示金融条件，但不是基金净申购赎回或机构仓位。没有恢复可比的当日基金流数据，不能把价格回落写成某类投资者净卖出。'],['S07','S02','S01']),
 'etf':(['ETF价格、净值及资金流含义不同。未恢复本时点全量篮子、权重调整和一级市场申赎资料；只用底层市场观察讨论风险，不推算不存在证据的ETF流量或再平衡。'],['S03','S04']),
 'options':(['VIX取Cboe官方历史收盘并注明日期，可观察隐含波动风险。它不提供dealer gamma、0DTE仓位、max pain或期权到期钉住点，缺失这些数据时不填造阈值。'],['S02']),
 'treasury':(['本期使用美国财政部同一CMT日度曲线计算1日/5观测变化和期限利差；现金债与期货报价不得混用。10月12日无CMT观测按实际交易日跳过。本次不把曲线数字冒充拍卖高收益率、WI或尾差。'],['S01']),
 'commodities':(['Europe Brent Spot使用EIA/FRED现货口径，不与ICE某月期货拼接。能源→企业及家庭成本→需求/通胀预期→利率及权益是条件链条；提供方落后交易日已标注，没有前向填充。'],['S05']),
 'financing':(['AI供应商收入或资本开支指引与客户承诺融资、实际提款、部署现金不是同一个量。未恢复完整融资合同、抵押或偿付条款，不把宣布规模等同已到账资金或经营回报。'],['S11'] if c['earnings']=='BAC' else ['S15','S23']),
 'breaking_news':([f[1]+' / '+f[2]+'：'+f[3] for f in c['facts']],sorted(set(s for f in c['facts'] for s in f[5]))),
 'market_impact':([c['thesis'],'将主要因果解释视为可检验的条件判断：先核事实，再看权益广度与曲线/信用，最后检验经营现金流；保留资产背离，不编造单一总风险分数。'],sorted(set(s for f in c['facts'] for s in f[5])))}
 for i,k in enumerate(KEYS,1):
  paras,ss=paragraphs[k];r['sections'][k]=dict(number=i,title=TITLES[i-1],status='证据缺口 / bounded reconstruction' if k in {'index_changes','flows','etf'} else '历史时点重建 / evidence-limited',summary=paras[0],paragraphs=paras,tables=[],sources=ss)
 r['sections']['earnings']['reported']=[earning('BAC'),earning('MS')] if c['earnings']=='BAC' else [earning('TSMC')];r['sections']['earnings']['upcoming_72h']=[]
 if c['earnings']=='BAC':r['sections']['earnings']['upcoming_72h']=[dict(id='TSM-2026Q3-upcoming',company='TSMC',ticker='TSM',period='2026 Q3',status='Confirmed Upcoming',date='2026-10-15',et='02:00 EDT',sgt='14:00 SGT',market_session='Taiwan conference / US premarket',consensus=dict(revenue=N,eps=N),previous_guidance='US$44.6–45.8bn company revenue guidance; not consensus',actual='待公布',what_matters=['收入与毛利率','先进制程贡献与现金支出'],read_through_targets=['Semiconductor manufacturing','AI infrastructure'],sources=['S13'])]
 r['sections']['treasury']['tables']=[dict(title='同一财政部CMT口径的期限比较',headers=['期限/利差','水平','1日','5观测','观测日'],rows=[[x['asset'],x['level'],x['change_1d'],x['change_5d'],x['recovery_observation']['session_date']] for x in mt if x['asset'].startswith('UST')])]
 r['section_order']=KEYS;sd=source_doc(day,r);r['sources']=[x['id'] for x in sd['sources']]
 return r,sd

def run(snapshot,treasury,cboe):
 latest_path=ROOT/'docs/data/latest.json';latest_before=latest_path.read_bytes();latest=load(latest_path)
 assert latest['date']>='2026-10-18','Refuse to operate on an unexpected production baseline'
 sourceh=histories(snapshot,treasury,cboe)
 receipt=dict(status='CANDIDATE_BUILT_NOT_PUBLISHED',built_at=BUILT,latest_preserved=latest['date'],latest_sha256=hashlib.sha256(latest_before).hexdigest(),dates={},limits=['Publication recovery does not establish that a historical edition was on time.','Provider-vintage and release-lag limitations are not silently erased.'])
 for day,sha in [('2026-10-13','b522c2a732a0cefc20a4199c216e4239c8cadc53'),('2026-10-14','f4240ca83fa8dc4bd1bf49d598de32a9b7f95837')]:
  src=snapshot/'candidates'/day/'docs';paths=[f'data/daily/{day}.json',f'data/sources/{day}.json',f'reports/2026/10/{day}.md']
  for rel in paths:
   p=ROOT/'docs'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src/rel,p)
  report=load(ROOT/'docs/data/daily'/f'{day}.json');assert report['date']==day and report['publication_cycle']['is_final'] and report['publication_cycle']['market_lens_native_eligible']
  original_hashes={p:hashlib.sha256((ROOT/'docs'/p).read_bytes()).hexdigest() for p in paths};normalized=[]
  for key,value in list(report['market_regime'].items()):
   if isinstance(value,str):report['market_regime'][key]={'state':value,'evidence':value};normalized.append('market_regime.'+key+': string -> state/evidence object; identical original literal retained')
  report['publication_recovery']={'mode':'original_candidate_delayed_publication','recovered_at_sgt':BUILT,'original_commit':sha,'original_cutoff':report['data_cutoff_sgt'],'schema_normalizations':normalized,'note':'原同期候选延迟补发；不是今天重新研究或当时已经按时发布。'}
  save(ROOT/f'docs/data/daily/{day}.json',report)
  mdpath=ROOT/f'docs/reports/2026/10/{day}.md';mdpath.write_text(mdpath.read_text()+f'\n> 原同期候选延迟补发：修复于 {BUILT}，原提交 `{sha}`。研究截止与原事实保持；仅将市场状态字符串规范化为 Schema 所需对象。\n',encoding='utf-8')
  receipt['dates'][day]=dict(mode='original_contemporaneous_candidate_delayed_publication',original_commit=sha,original_cutoff=report['data_cutoff_sgt'],original_sha256=original_hashes,schema_normalizations=normalized,sha256={p:hashlib.sha256((ROOT/'docs'/p).read_bytes()).hexdigest() for p in paths})
 for day in CONFIG:
  report,sd=construct(day,sourceh);save(ROOT/f'docs/data/daily/{day}.json',report);save(ROOT/f'docs/data/sources/{day}.json',sd)
  md=ROOT/f'docs/reports/2026/10/{day}.md';md.parent.mkdir(parents=True,exist_ok=True);md.write_text(markdown(report),encoding='utf-8')
  receipt['dates'][day]=dict(mode='reconstructed_daily',historical_cutoff=report['data_cutoff_sgt'],reconstructed_at=BUILT,coverage=report['market_tape_data_quality'])
 archive=load(ROOT/'docs/data/archive.json');bydate={e['date']:e for e in archive['entries']}
 for day in receipt['dates']:
  r=load(ROOT/f'docs/data/daily/{day}.json');overall=r['market_regime']['overall'];regime=overall.get('state') if isinstance(overall,dict) else overall
  bydate[day]=dict(date=day,thesis=r['thesis'],dominant_narrative=r['dominant_narrative'],overall_regime=regime,report_path=f'reports/2026/10/{day}.md',daily_json_path=f'data/daily/{day}.json',sources_path=r['sources_path'],edition=r['edition'],edition_status='official',publication_cycle='morning',source_mode=r.get('source_mode','native_daily'),publication_note='原同期候选延迟补发' if day in {'2026-10-13','2026-10-14'} else '事后重建；非原生日报')
 archive['entries']=[bydate[d] for d in sorted(bydate,reverse=True)];archive['updated_at']=BUILT;save(ROOT/'docs/data/archive.json',archive);assert latest_path.read_bytes()==latest_before,'latest must be byte-identical'
 supplement=dict(schema_version='1.0.0',retrieved_at=BUILT,methodology='Verified provider-history cache. Available live-provider values have priority; cached records only supply absent observations. No forward-fill, no spot/futures or broad-USD/DXY splicing.',series={})
 names={'NASDAQCOM':('Nasdaq daily index via FRED','https://fred.stlouisfed.org/series/NASDAQCOM'),'SP500':('S&P 500 via FRED','https://fred.stlouisfed.org/series/SP500'),'VIXCLS':('Cboe official VIX',VIX_URL),'DGS2':('2Y Treasury constant maturity via FRED','https://fred.stlouisfed.org/series/DGS2'),'DGS10':('10Y Treasury constant maturity via FRED','https://fred.stlouisfed.org/series/DGS10'),'DCOILBRENTEU':('EIA Europe Brent spot via FRED','https://fred.stlouisfed.org/series/DCOILBRENTEU'),'DTWEXBGS':('Federal Reserve broad USD via FRED','https://fred.stlouisfed.org/series/DTWEXBGS'),'BAMLH0A0HYM2':('ICE BofA HY OAS via FRED','https://fred.stlouisfed.org/series/BAMLH0A0HYM2')}
 for sid,(name,url) in names.items():
  values=dict(sourceh[sid])
  if sid in {'DGS2','DGS10'}:values['2026-10-16']=sourceh['UST2' if sid=='DGS2' else 'UST10']['2026-10-16']
  points=[]
  for d,v in sorted(values.items()):
   if not ('2025-08-01'<=d<='2026-10-16'):continue
   source_url=SERIES_URL if sid in {'DGS2','DGS10'} and d=='2026-10-16' else SOURCES['S22'][2] if sid=='NASDAQCOM' and d=='2026-10-16' else url
   points.append(dict(date=d,value=v,source_url=source_url))
  supplement['series'][sid]=dict(source_url=url,source_name=name,points=points,last_verified_observation=points[-1]['date'])
 supplement['input_artifacts']={'audit_sha256':'ab5e5be06a19d9bd06b5816d80dc7f4b433f6b50cc5bbb33ae19c7e337954981','treasury_sha256':'a7fbf859108e2bda2015446a0479f81ba1c7f019d71da6b9e44a01746425f437','cboe_sha256':'de7ffce695c0493f9b65413ffb449bb2ce14f1648de44d0c9ad13779dc386edb'}
 save(ROOT/'docs/data/trends/historical-series-supplement.json',supplement)
 evidence={sid:[dict(date=d,value=v) for d,v in sorted(rows.items()) if '2026-09-01'<=d<='2026-10-16'] for sid,rows in sourceh.items() if sid in {'SP500','NASDAQCOM','DOW','RUT','VIXCLS','UST2','UST5','UST10','UST30','2s10s','10s30s','DCOILBRENTEU','DTWEXBGS','BAMLH0A0HYM2'}}
 save(ROOT/'docs/data/trends/october-backfill-series-evidence.json',dict(retrieved_at=BUILT,series=evidence,source_mapping={'UST*':SERIES_URL,'VIXCLS':VIX_URL,'NASDAQCOM_last':SOURCES['S22'][2]},vintage_note='Historical current vintage, not an original intraday snapshot; report-specific as_of and provider lag remain authoritative.'))
 for day in receipt['dates']:
  r=load(ROOT/f'docs/data/daily/{day}.json');md=(ROOT/f'docs/reports/2026/10/{day}.md').read_text();literals=[r['data_cutoff_sgt'],r['data_cutoff_et'],r['thesis'],r['dominant_narrative'],*[r['sections'][k]['title'] for k in r['section_order']],*[c['event'] for c in r['top_catalysts']],*[c['risk'] for c in r['top_risks']]]
  assert len(literals)==25 and all(x in md for x in literals),(day,'canonical drift');receipt['dates'][day]['canonical_parity']='25/25'
 save(ROOT/'docs/data/runs/october-backfill-2026-10-19.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--treasury',type=Path,required=True);parser.add_argument('--cboe',type=Path,required=True);parser.add_argument('--built-at',required=True);args=parser.parse_args();BUILT=args.built_at
 assert datetime.fromisoformat(BUILT).tzinfo is not None
 run(args.snapshot,args.treasury,args.cboe)
