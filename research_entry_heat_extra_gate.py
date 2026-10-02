"""Research an entry-heat gate for discretionary extra buying.

Core contribution is always invested monthly. A separate opportunity contribution is
handled three ways with identical total cash contributions:
1) MECHANICAL_EXTRA: invest opportunity cash every month immediately.
2) HEAT_BLOCK: invest opportunity cash monthly unless positive heat is active; blocked
   cash is released when heat clears.
3) BULL_RESERVE: keep opportunity cash in reserve and deploy the whole reserve only
   when a negative-divergence / internal-repair signal appears.

All decisions use information available at the prior close; execution is next session open.
"""
from __future__ import annotations

import json, math
from pathlib import Path
from statistics import mean

import research_entry_heat_dca as base

ROOT=Path(__file__).resolve().parent
DATA_PATH=ROOT/'docs/data/structure_lab.json'
OUT_PATH=ROOT/'docs/data/updown_entry_heat_extra_gate.json'
SYMBOLS=['^GSPC','^IXIC','^DJI']
START='1992-01-02'
CORE=1000.0
EXTRA=500.0
THRESHOLDS=[1.0,1.5,2.0]
FORWARD_H=[20,40]


def near_low_flags(bars):
    out=[False]*len(bars)
    w=base.RATIO_WINDOW
    closes=[b['close'] for b in bars]
    for i in range(w,len(bars)):
        xs=closes[i-w+1:i+1]
        out[i]=closes[i] <= 1.03*min(xs)
    return out


def bull_signal(f,near_low,i,threshold,mode,lead_cache):
    if i<0:return False
    d=f['div'][i];r=f['ret20'][i]
    ok=base.finite(d) and base.finite(r) and d<=-threshold and r<0 and near_low[i]
    if not ok:return False
    if mode=='DIV':return True
    c=f['corr'][i]
    if not base.finite(c) or c<.25:return False
    if i not in lead_cache:lead_cache[i]=base.best_positive_lead(f,i)
    best=lead_cache[i]
    return bool(best and best[1]>=.25)


def buy(shares,cash,amount,px):
    if amount<=0:return shares,cash
    return shares+amount/px,cash-amount


def run(bars,f,monthly_idx,kind,threshold=1.5,mode='BOTH'):
    monthly_set=set(monthly_idx)
    near_low=near_low_flags(bars)
    lead_cache={}
    shares=0.0;cash=0.0;reserve=0.0
    total_contrib=0.0;index_alloc=0.0
    flows=[];events=[]
    heat_months=0;bull_releases=0;heat_releases=0
    reserve_peak=0.0;reserve_days=0;reserve_day_count=0
    twr=1.0;peak=1.0;maxdd=0.0;prev_value=None

    for i,b in enumerate(bars):
        external_flow=0.0
        # Release previously accumulated reserve before today's new monthly contribution.
        if reserve>0 and i>0:
            do_release=False;reason=None
            if kind=='HEAT_BLOCK':
                if not base.is_heat(f,i-1,threshold,mode,lead_cache):
                    do_release=True;reason='heat_clear'
            elif kind=='BULL_RESERVE':
                if bull_signal(f,near_low,i-1,threshold,mode,lead_cache):
                    do_release=True;reason='bull_repair'
            if do_release:
                amt=reserve
                shares,cash=buy(shares,cash,amt,b['open'])
                index_alloc+=amt;reserve=0.0
                events.append((i,amt,reason))
                if reason=='bull_repair':bull_releases+=1
                else:heat_releases+=1

        if i in monthly_set:
            external_flow=CORE+EXTRA
            cash+=external_flow;total_contrib+=external_flow;flows.append((b['date'],-external_flow))
            # Core always invested.
            shares,cash=buy(shares,cash,CORE,b['open']);index_alloc+=CORE;events.append((i,CORE,'core'))
            if kind=='MECHANICAL_EXTRA':
                shares,cash=buy(shares,cash,EXTRA,b['open']);index_alloc+=EXTRA;events.append((i,EXTRA,'mechanical_extra'))
            elif kind=='HEAT_BLOCK':
                hot=base.is_heat(f,i-1,threshold,mode,lead_cache)
                if hot:
                    heat_months+=1;reserve+=EXTRA
                else:
                    shares,cash=buy(shares,cash,EXTRA,b['open']);index_alloc+=EXTRA;events.append((i,EXTRA,'normal_extra'))
            elif kind=='BULL_RESERVE':
                reserve+=EXTRA
            else:
                raise ValueError(kind)

        reserve_peak=max(reserve_peak,reserve)
        if reserve>0:
            reserve_days+=1;reserve_day_count+=1
        value=shares*b['close']+cash
        if prev_value is None:
            twr=1.0
        else:
            denom=prev_value+external_flow
            if denom>0:twr*=value/denom
        peak=max(peak,twr);maxdd=min(maxdd,twr/peak-1)
        prev_value=value

    terminal=shares*bars[-1]['close']+cash
    flows.append((bars[-1]['date'],terminal))
    irr=base.xirr(flows)

    fw={}
    tactical=[e for e in events if e[2] in ('mechanical_extra','normal_extra','heat_clear','bull_repair')]
    for h in FORWARD_H:
        vals=[];weights=[]
        for i,amt,_ in tactical:
            if i+h<len(bars):
                vals.append(bars[i+h]['close']/bars[i]['open']-1);weights.append(amt)
        wavg=sum(v*w for v,w in zip(vals,weights))/sum(weights) if weights else None
        fw[str(h)]={'n':len(vals),'weighted_avg_forward_return_pct':round(wavg*100,3) if wavg is not None else None}

    return {
        'ending_value':round(terminal,2),
        'total_contributed':round(total_contrib,2),
        'cash_ending':round(cash,2),
        'reserve_ending':round(reserve,2),
        'index_allocated_total':round(index_alloc,2),
        'allocation_rate_pct':round(100*index_alloc/total_contrib,2) if total_contrib else None,
        'xirr_pct':round(irr*100,3) if irr is not None else None,
        'twr_total_return_pct':round((twr-1)*100,3),
        'twr_max_drawdown_pct':round(maxdd*100,3),
        'heat_months':heat_months,
        'bull_releases':bull_releases,
        'heat_releases':heat_releases,
        'reserve_peak':round(reserve_peak,2),
        'forward_extra_entry_quality':fw,
    }


def main():
    raw=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    out={'schema':'UPDOWN-ENTRY-HEAT-EXTRA-GATE-V1','method':{
        'universe':SYMBOLS,'sample_start':START,
        'monthly_core_contribution':CORE,'monthly_opportunity_contribution':EXTRA,
        'total_monthly_cash_contribution':CORE+EXTRA,
        'execution':'first trading day open / next-session open; decisions use prior close only',
        'MECHANICAL_EXTRA':'core + opportunity cash invested every month',
        'HEAT_BLOCK':'core always invested; opportunity cash invested unless positive heat, blocked cash released when heat clears',
        'BULL_RESERVE':'core always invested; opportunity cash accumulates and whole reserve deploys only on negative-divergence internal-repair signal',
        'positive_heat':'positive divergence + positive 20d return + close within 3% of 20d high',
        'bull_repair':'negative divergence + negative 20d return + close within 3% of 20d low',
        'BOTH_filter':'60d contemporaneous corr>=0.25 and strongest positive-lag(1..20d) corr over prior 180d >=0.25',
        'thresholds':THRESHOLDS,'cash_interest_pct':0.0,'fees_slippage_pct':0.0,
        'lookahead':'none in signals; forward returns only used for evaluation'
    },'results':{}}

    for sym in SYMBOLS:
        inst=raw.get('instruments',{}).get(sym)
        if not inst:continue
        bars=base.load_bars(inst);f=base.features(bars);monthly=base.first_trading_days(bars,START)
        base_res=run(bars,f,monthly,'MECHANICAL_EXTRA')
        result={'name':inst.get('name',sym),'start':bars[monthly[0]]['date'],'end':bars[-1]['date'],'months':len(monthly),'baseline_mechanical':base_res,'tests':{}}
        base_end=base_res['ending_value']
        for th in THRESHOLDS:
            for mode in ('DIV','BOTH'):
                for kind in ('HEAT_BLOCK','BULL_RESERVE'):
                    k=f'{kind}_{mode}_{th:.1f}'
                    r=run(bars,f,monthly,kind,th,mode)
                    r['ending_value_vs_mechanical_pct']=round((r['ending_value']/base_end-1)*100,3)
                    result['tests'][k]=r
        out['results'][sym]=result
        print('\n',sym,result['name'],'BASE',base_res,flush=True)
        for k in ['HEAT_BLOCK_BOTH_1.5','BULL_RESERVE_BOTH_1.5']:
            print(sym,k,result['tests'][k],flush=True)

    OUT_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote',OUT_PATH)

if __name__=='__main__':main()
