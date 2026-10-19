"""Auditable source-series cache and opt-in historical price proxies.

These proxies fill presentation gaps, not original editorial judgments. They
never make a reconstructed report native or use report-date/later U.S. closes.
"""
from __future__ import annotations
import json, math, re
from datetime import date
from pathlib import Path

def supplement(root):
    path=Path(root)/'docs/data/trends/historical-series-supplement.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

def cached_points(root,sid):
    points=supplement(root).get('series',{}).get(sid,{}).get('points',[])
    seen=set()
    for point in points:
        d=point.get('date');value=point.get('value')
        if not isinstance(d,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',d) or d in seen:raise ValueError('Invalid/duplicate supplemental date')
        date.fromisoformat(d)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Invalid supplemental value')
        if not str(point.get('source_url','')).startswith('https://'):raise ValueError('Supplementary source URL required')
        seen.add(d)
    return points

def merge_history(root,sid,raw):
    """Prefer an available live provider value; only fill absent dates."""
    merged={p['date']:dict(p) for p in raw};cache=cached_points(root,sid)
    for p in cache:
        if p['date'] not in merged:merged[p['date']]=dict(p)
    return [merged[d] for d in sorted(merged)]

def direction(value,band=0.0):
    if value is None:return '?'
    return '↑' if value>band else '↓' if value<-band else '→'

def editorial_direction(text):
    text=str(text or '')
    if '↕' in text or ('↑' in text and '↓' in text):return '↕'
    if '↔' in text:return '↔'
    for symbol in ('↑','↓','→'):
        if symbol in text:return symbol
    return '?'

def historical_proxy(root,report):
    policy=Path(root)/'docs/data/trends/historical-proxy-policy.json'
    if not policy.is_file() or report.get('date') not in json.loads(policy.read_text()).get('dates',[]):return None
    if not report.get('reconstruction',{}).get('is_reconstructed'):return None
    cut=report['date'];observations={}
    for item in report.get('market_tape',[]):
        name=str(item.get('asset',''));ro=item.get('recovery_observation') or {}
        d=ro.get('session_date')
        if not d:
            found=re.search(r'\d{4}-\d{2}-\d{2}',str(item.get('as_of','')));d=found.group() if found else None
        if not d or d>=cut:continue
        value=ro.get('change_1d')
        if value is None:
            text=str(item.get('change_1d','')).strip()
            if any(k in text for k in ('近似','约','逾','未','无法')):continue
            match=re.fullmatch(r'([+-]?\d+(?:\.\d+)?)\s*(%|bp|bps|pts|points)?(?: reported.*| derived from [0-9.,]+)?',text)
            if match:value=float(match.group(1))
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):continue
        if not item.get('sources'):continue
        observations[name]={'asset':name,'session_date':d,'change_1d':value,'change_unit':ro.get('change_unit') or str(item.get('change_1d','')),'sources':item['sources'],'as_of':item.get('as_of')}
    def pick(*names):return next((observations[n] for n in names if n in observations),None)
    sp=pick('S&P 500','SP500');nas=pick('Nasdaq Composite','Nasdaq');vix=pick('VIX','CBOE VIX','Cboe VIX')
    oil=pick('Brent','Brent Dec 2026','Europe Brent Spot');rates=pick('UST 10Y','US 10Y');dollar=pick('DXY','Broad Trade-Weighted USD')
    def val(x):return x['change_1d'] if x else None
    metrics={
      'growth':(val(sp),'S&P 500 1D direction; equity-demand proxy, NOT GDP',[sp]),
      'inflation':(val(oil),'Brent same-basis 1D direction; energy-price proxy, NOT CPI',[oil]),
      'rates':(val(rates),'UST 10Y 1D yield-change direction',[rates]),
      'earnings':(val(nas)-val(sp) if nas and sp and nas['session_date']==sp['session_date'] else None,'Nasdaq 1D minus S&P 500 1D; growth-style relative return, NOT EPS revisions',[nas,sp]),
      'liquidity':(-val(dollar) if dollar else None,'Negative dollar-index 1D direction; financial-conditions proxy, NOT fund flow',[dollar]),
      'geopolitics':(val(vix),'VIX 1D direction; market risk-premium proxy, NOT proof of geopolitical events',[vix]),
    }
    details={k:{'direction':direction(v),'value':v,'formula':formula,'observations':[o for o in obs if o]} for k,(v,formula,obs) in metrics.items()}
    code='unclassified'
    if sp and vix and sp['session_date']==vix['session_date']:
        # A transparent two-input classification, not a weighted risk score.
        if val(sp)>0 and val(vix)<0:code='risk_on'
        elif val(sp)<0 and val(vix)>0:code='risk_off'
        elif val(sp)==0 and val(vix)==0:code='neutral'
        else:code='event_risk'
    return dict(basis='historical_price_proxy',regime_code=code,signals={k:v['direction'] for k,v in details.items()},details=details,regime_formula='SPX up + VIX down → risk_on; SPX down + VIX up → risk_off; both unchanged → neutral; conflicting observed directions → event_risk. Missing required data stays unclassified.',note='市场价格代理，不是恢复出的当日编辑判断：增长/盈利/流动性/地缘行分别使用权益、相对收益、美元和VIX代理，不冒充GDP、EPS修正、资金流或真实事件。只使用原补档中有来源的截点前行情。')
