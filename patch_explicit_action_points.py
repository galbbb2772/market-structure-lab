from pathlib import Path
import re

p = Path('docs/ratio-history.html')
s = p.read_text(encoding='utf-8')

s = s.replace(
    '.gateLevel b{display:block;font-size:20px;margin-top:4px}',
    '.gateLevel b{display:block;font-size:20px;margin-top:4px}.gateLevel.buy b{color:var(--green)}.gateLevel.observe b{color:var(--amber)}.gateLevel.sell b{color:var(--red)}.gateDelta{display:block;margin-top:5px;font-size:11px;color:var(--muted)}'
)

s = s.replace(
    '<div class="subhead">具体结构参考位</div>',
    '<div class="subhead">具体操作点位</div>'
)

old_note = '“具体点位”是按当前20日价格结构动态计算的研究参考，不是对未来底部/顶部的保证。我们前面的回测支持它作为新增仓位过滤器，但没有证明单靠它择时能稳定提高长期收益。'
new_note = '买入点、观察点、卖出点会随当前指数的20日价格结构动态变化。买点需要“修复确认”后执行，卖点需要“过热确认”后执行；观察点只用于等待，不机械下单。点位是研究系统的操作参考，不代表对未来顶部/底部的保证。'
s = s.replace(old_note, new_note)

new_fn = r'''function renderEntryGate(){
 const root=$('entryGatePanel');if(!root||!DATA)return;
 const q=entryGateSnapshot($('idx').value),th=+($('gateThreshold')?.value||1.5);if(!q){$('gateState').textContent='数据不足';$('gateAction').textContent='暂不生成操作参考';return}
 const leadOK=q.bestLead&&q.bestLead.corr>=.25,corrOK=Number.isFinite(q.corr)&&q.corr>=.25,confirm=leadOK&&corrOK;
 const nearHigh=q.close>=q.high20*.97,nearLow=q.close<=q.low20*1.03;
 const heat=Number.isFinite(q.divergence)&&q.divergence>=th&&q.ret20>0&&nearHigh;
 const repair=Number.isFinite(q.divergence)&&q.divergence<=-th&&q.ret20<0&&nearLow;

 // Explicit operating levels. The buy/sell levels sit inside the already-used 3% repair/heat bands.
 let buyPoint=q.low20*1.015,watchPoint=q.mid20,sellPoint=q.high20*.985;
 // Keep the three points ordered even during unusually narrow 20-day ranges.
 if(buyPoint>=watchPoint)buyPoint=q.low20+(watchPoint-q.low20)*.5;
 if(sellPoint<=watchPoint)sellPoint=watchPoint+(q.high20-watchPoint)*.5;
 const dist=p=>q.close?100*(p/q.close-1):null;
 const hitBuy=q.close<=buyPoint,hitSell=q.close>=sellPoint,belowWatch=q.close<=watchPoint;

 let state='持仓观望',clsName='normal',action='',plan='';
 if(hitBuy&&repair&&confirm){
   state='买入触发';clsName='repair';
   action=`当前操作：价格 ${fmt(q.close,2)} 已到建议买入点 ${fmt(buyPoint,2)} 以下，且修复确认成立 → 执行机会仓买入。`;
   plan=`买入触发已成立。若下一交易时段仍在 ${fmt(buyPoint,2)} 附近或以下且修复确认没有消失，可执行买入；若快速反弹脱离该价位，不追价。`;
 }else if(hitSell&&heat){
   state='卖出 / 减仓触发';clsName='heat';
   action=`当前操作：价格 ${fmt(q.close,2)} 已到建议卖出点 ${fmt(sellPoint,2)} 以上，且过热确认成立 → 机会仓执行卖出或减仓。`;
   plan=`卖出触发已成立。若价格仍≥ ${fmt(sellPoint,2)} 且过热条件保持，可执行机会仓卖出/减仓；核心长期仓不因本模块单独清仓。`;
 }else if(hitBuy){
   state='买入点观察';clsName='watch';
   action=`当前操作：价格已到建议买入点 ${fmt(buyPoint,2)}，但修复确认不足 → 暂不买，继续观察。`;
   plan=`价格条件已经满足，但信号条件没有同时满足。等待背离≤ -${fmt(th,1)}σ、滚动相关≥0.25、领先相关≥0.25 后再把“观察”升级为“买入”。`;
 }else if(hitSell){
   state='卖出点观察';clsName='watch';
   action=`当前操作：价格已到建议卖出点 ${fmt(sellPoint,2)}，但过热确认不足 → 暂不机械卖出，持仓观察。`;
   plan=`价格到达上沿，但没有同时形成过热结构。只有过热条件成立时，这个价位才升级为机会仓卖出/减仓触发。`;
 }else if(belowWatch){
   state='观察';clsName='watch';
   action=`当前操作：价格 ${fmt(q.close,2)} 已进入建议观察点 ${fmt(watchPoint,2)} 下方、尚未到买入点 ${fmt(buyPoint,2)} → 不追价，等待买入触发。`;
   plan=`目前位于观察区。继续看价格是否靠近 ${fmt(buyPoint,2)}，以及修复确认是否同时成立；没有同时成立前不执行新增仓位。`;
 }else{
   state='持仓观望';clsName='normal';
   action=`当前操作：持仓观望。下方建议观察点 ${fmt(watchPoint,2)}，进一步建议买入点 ${fmt(buyPoint,2)}；上方建议卖出点 ${fmt(sellPoint,2)}。`;
   plan=`当前价格处在观察点与卖出点之间：已有仓位继续持有；不到买入触发不额外加仓，到卖出点也需要过热确认后才执行减仓/卖出。`;
 }

 $('gateState').className='gateState '+clsName;$('gateState').textContent=state;$('gateAction').textContent=action;
 const leadText=q.bestLead?`+${q.bestLead.lag}日 / ${fmt(q.bestLead.corr,3)}`:'—';
 $('gateWhy').textContent=`${q.date} · 背离 ${fmt(q.divergence,2)}σ · 20日收益 ${fmt(q.ret20*100,2)}% · 涨跌比 ${q.ratio===Infinity?'∞':fmt(q.ratio,2)} · 60日相关 ${fmt(q.corr,3)} · 最强正向领先 ${leadText}`;
 const ms=[['当前点位',fmt(q.close,2)],['20日收益',fmt(q.ret20*100,2)+'%'],['背离强度',fmt(q.divergence,2)+'σ'],['领先确认',leadText]];
 $('gateMetrics').innerHTML=ms.map(([k,v])=>`<div class="metric"><small>${k}</small><b>${v}</b></div>`).join('');
 const levels=[
   ['建议买入点',buyPoint,'buy',`≤ ${fmt(buyPoint,2)} + 修复确认 → 执行买入`],
   ['建议观察点',watchPoint,'observe',`约 ${fmt(watchPoint,2)} → 只观察，不下单`],
   ['建议卖出点',sellPoint,'sell',`≥ ${fmt(sellPoint,2)} + 过热确认 → 卖出/减仓`]
 ];
 $('gateLevels').innerHTML=levels.map(([k,v,c,d])=>`<div class="gateLevel ${c}"><small>${k}</small><b>${fmt(v,2)}</b><small>${d}</small><span class="gateDelta">距当前 ${dist(v)>=0?'+':''}${fmt(dist(v),2)}%</span></div>`).join('');
 $('gatePlan').innerHTML=`<b>当前具体操作：</b> ${plan}<br><br><b>执行规则：</b> ① 到买入点且修复确认 → 买入；② 到观察点 → 只观察；③ 到卖出点且过热确认 → 卖出/减仓。`
}'''

pattern = r"function renderEntryGate\(\)\{.*?\n\}\n\nfunction stats"
ns, n = re.subn(pattern, new_fn + '\n\nfunction stats', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit(f'expected to replace renderEntryGate once, replaced {n}')

for needle in ['建议买入点','建议观察点','建议卖出点','当前具体操作：','卖出 / 减仓触发']:
    if needle not in ns:
        raise SystemExit(f'missing expected marker: {needle}')

p.write_text(ns, encoding='utf-8')
print('patched explicit action points into docs/ratio-history.html')
