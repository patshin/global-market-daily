#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LENS=ROOT/'docs/data/trends/rolling-30d.json'
POLICY=ROOT/'docs/data/trends/policy-events.json'
def main():
  lens=json.loads(LENS.read_text(encoding='utf-8'))
  policy=json.loads(POLICY.read_text(encoding='utf-8'))
  days=lens.get('days',[])
  by_date={d.get('date'):d for d in days if isinstance(d,dict)}
  accepted=[]
  for event in policy.get('events',[]):
    if not isinstance(event,dict) or event.get('date') not in by_date: continue
    item={
      'id':event.get('id') or f"policy-{event['date']}",
      'rank':'P','marker_type':'confirmed_policy','importance':event.get('importance',4),
      'theme_id':event.get('theme_id','china_trade_policy'),'category':'china_trade_policy',
      'title':event.get('title','Policy milestone'),'event':event.get('title','Policy milestone'),
      'status':event.get('status','Confirmed / Released'),'market_bias':event.get('market_bias','mixed'),
      'evidence':event.get('evidence',''),'transmission':event.get('transmission',''),
      'confirmation':event.get('confirmation',''),'invalidation':event.get('invalidation',''),
      'source_url':event.get('source_url'),'source_name':event.get('source_name'),
      'provenance':'primary_policy_source'
    }
    bucket=by_date[event['date']].setdefault('catalysts',[])
    if not any(isinstance(x,dict) and x.get('id')==item['id'] for x in bucket): bucket.append(item)
    accepted.append(item)
  lens['policy_monitor']={
    'category':'china_trade_policy','events_in_window':len(accepted),
    'empty_state':policy.get('empty_state','本窗口无重大政策节点'),
    'marker':'P','marker_label':'已确认政策节点'
  }
  # Scores may be useful diagnostics internally, but must never be a published black-box metric.
  def strip_scores(value):
    if isinstance(value,dict):
      value.pop('risk_score',None)
      for child in value.values(): strip_scores(child)
    elif isinstance(value,list):
      for child in value: strip_scores(child)
  strip_scores(lens)
  LENS.write_text(json.dumps(lens,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
