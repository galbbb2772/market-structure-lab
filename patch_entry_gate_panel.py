from pathlib import Path

p=Path('docs/ratio-history.html')
s=p.read_text(encoding='utf-8')
if 'id="entryGatePanel"' in s:
    print('Entry Gate panel already present')
    raise SystemExit(0)

css='''
.gateGrid{display:grid;grid-template-columns:1.15fr 1fr;gap:12px;margin-top:14px}.gateHero,.gateBox{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:15px}.gateHero{display:grid;gap:9px}.gateState{font-size:clamp(26px,4vw,42px);font-weight:850;line-height:1}.gateState.normal{color:var(--green)}.gateState.heat{color:var(--amber)}.gateState.repair{color:var(--blue)}.gateState.watch{color:#d7b8ff}.gateAction{font-size:17px;font-weight:750;line-height:1.45}.gateWhy{color:var(--muted);font-size:13px;line-height:1.65}.gateLevels{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:10px}.gateLevel{background:#0b171f;border:1px solid var(--line);border-radius:10px;padding:11px}.gateLevel small{display:block}.gateLevel b{display:block;font-size:20px;margin-top:4px}.gateTag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:5px 8px;font-size:12px;color:var(--muted)}.gateNote{margin-top:10px;color:var(--muted);font-size:12px;line-height:1.6}
@media(max-width:800px){.gateGrid{grid-template-columns:1fr}.gateLevels{grid-template-columns:1fr}}
'''
s=s.replace('@media(max-width:1100px)',css+'@media(max-width:1100px)',1)

html='''
<section class="panel" id="entryGatePanel">
<div class="sectionTitle"><div><h2>Entry Gate · 新增仓位状态</h2><p>固定使用我们已经验证过的20日涨跌比研究口径；核心仓位和固定定投不因本模块单独改变，主要约束“额外追仓/机会仓”。</p></div><div class="controls"><label>背离阈值<select id="gateThreshold"><option value="1">1.0σ</option><option value="1.5" selected>1.5σ</option><option value="2">2.0σ</option></select></label><span class="gateTag">20日固定口径</span></div></div>
<div class="gateGrid">
  <div class="gateHero">
    <small>当前系统状态</small>
    <div id="gateState" class="gateState normal">—</div>
    <div id="gateAction" class="gateAction">正在计算…</div>
    <div id="gateWhy" class="gateWhy">—</div>
  </div>
  <div class="gateBox">
    <div class="subhead" style="margin-top:0">当前结构</div>
    <div id="gateMetrics" class="metrics" style="grid-template-columns:repeat(2,1fr);margin:8px 0 0"></div>
  </div>
</div>
<div class="subhead">具体结构参考位</div>
<div id="gateLevels" class="gateLevels"></div>
<div id="gatePlan" class="notice" style="margin-top:12px">—</div>
<div class="gateNote">“具体点位”是按当前20日价格结构动态计算的研究参考，不是对未来底部/顶部的保证。我们前面的回测支持它作为新增仓位过滤器，但没有证明单靠它择时能稳定提高长期收益。</div>
</section>

'''
anchor='<section class="panel"><div class="sectionTitle"><div><h2>逐期明细</h2>'
if anchor not in s: raise SystemExit('HTML anchor not found')
s=s.replace(anchor,html+anchor,1)

js=r'''
function entryGateSnapshot(sym){
 const b=barsFor(sym),n=b.length;if(n<90)return null;
 const close=b.map(x=>+x[4]),dates=b.map(x=>x[0]),dirsA=[null];
 for(let i=1;i<n;i++)dirsA.push(close[i]>close[i-1]?1:close[i]<close[i-1]?-1:0);
 const rs=Array(n).fill(null),rr=Array(n).fill(null),ret=Array(n).fill(null),hi20=Array(n).fill(null),lo20=Array(n).fill(null),div=Array(n).fill(null),corr=Array(n).fill(null);
 for(let i=20;i<n;i++){
   const w=dirsA.slice(i-19,i+1),up=w.filter(v=>v===1).length,dn=w.filter(v=>v===-1).length;
   rr[i]=dn?up/dn:(up?Infinity:null);rs[i]=Math.log((up+.5)/(dn+.5));ret[i]=close[i]/close[i-20]-1;
   const px=close.slice(i-19,i+1);hi20[i]=Math.max(...px);lo20[i]=Math.min(...px)
 }
 for(let i=79;i<n;i++){
   const pz=zAt(ret.slice(i-59,i+1)),rz=zAt(rs.slice(i-59,i+1));if(Number.isFinite(pz)&&Number.isFinite(rz))div[i]=pz-rz;
   corr[i]=pearsonPairs(Array.from({length:60},(_,k)=>[ret[i-59+k],rs[i-59+k]]))
 }
 const i=n-1,la=Math.max(20,i-179);let best=null;
 for(let lag=1;lag<=20;lag++){
   const pairs=[];for(let j=la;j+lag<=i;j++)pairs.push([rs[j],ret[j+lag]]);
   const c=pearsonPairs(pairs);if(Number.isFinite(c)&&(!best||Math.abs(c)>Math.abs(best.corr)))best={lag,corr:c}
 }
 return{date:dates[i],close:close[i],ratio:rr[i],ret20:ret[i],high20:hi20[i],low20:lo20[i],mid20:(hi20[i]+lo20[i])/2,divergence:div[i],corr:corr[i],bestLead:best}
}
function renderEntryGate(){
 const root=$('entryGatePanel');if(!root||!DATA)return;
 const q=entryGateSnapshot($('idx').value),th=+($('gateThreshold')?.value||1.5);if(!q){$('gateState').textContent='数据不足';$('gateAction').textContent='暂不生成操作参考';return}
 const leadOK=q.bestLead&&q.bestLead.corr>=.25,corrOK=Number.isFinite(q.corr)&&q.corr>=.25,confirm=leadOK&&corrOK;
 const nearHigh=q.close>=q.high20*.97,nearLow=q.close<=q.low20*1.03;
 const heat=Number.isFinite(q.divergence)&&q.divergence>=th&&q.ret20>0&&nearHigh;
 const repair=Number.isFinite(q.divergence)&&q.divergence<=-th&&q.ret20<0&&nearLow;
 let state='正常',clsName='normal',action='核心仓位：持有；固定定投：照常；机会仓：不因本指标单独加仓。',plan='当前没有明确的过热或修复信号。若想等更好的结构位置，可把20日中位作为普通回撤观察位，把20日低点附近作为更深的修复观察区。';
 if(heat){state='过热 / 谨慎追涨';clsName='heat';action='核心仓位：继续持有；固定定投：照常；机会仓：暂停追涨，等待过热解除。';plan=`当前不建议因为上涨而额外追仓。第一观察线：≤ ${fmt(q.high20*.97,2)}；普通回撤参考：约 ${fmt(q.mid20,2)}；若进一步进入 ${fmt(q.low20,2)}～${fmt(q.low20*1.03,2)}，再检查是否转为“修复观察”。`}
 else if(repair&&confirm){state='修复确认 / 机会仓观察';clsName='repair';action='核心仓位：持有；固定定投：照常；机会仓：可进入分批研究状态，不建议一次性满仓。';plan=`已进入历史研究中的修复区。研究执行参考：下一交易时段若仍≤ ${fmt(q.low20*1.03,2)}，可考虑机会仓首批；20日低点 ${fmt(q.low20,2)} 为更深一档结构参考。若价格快速脱离修复区，不追价，重新等待。`}
 else if(repair){state='修复观察 / 待确认';clsName='watch';action='核心仓位：持有；固定定投：照常；机会仓：先观察，等待相关性/领先确认。';plan=`价格已进入修复区域 ${fmt(q.low20,2)}～${fmt(q.low20*1.03,2)}，但确认条件不足。先不把它当正式加仓触发；等滚动相关≥0.25且涨跌比领先相关≥0.25后再升级。`}
 $('gateState').className='gateState '+clsName;$('gateState').textContent=state;$('gateAction').textContent=action;
 const leadText=q.bestLead?`+${q.bestLead.lag}日 / ${fmt(q.bestLead.corr,3)}`:'—';
 $('gateWhy').textContent=`${q.date} · 背离 ${fmt(q.divergence,2)}σ · 20日收益 ${fmt(q.ret20*100,2)}% · 涨跌比 ${q.ratio===Infinity?'∞':fmt(q.ratio,2)} · 60日相关 ${fmt(q.corr,3)} · 最强正向领先 ${leadText}`;
 const ms=[['当前点位',fmt(q.close,2)],['20日收益',fmt(q.ret20*100,2)+'%'],['背离强度',fmt(q.divergence,2)+'σ'],['领先确认',leadText]];
 $('gateMetrics').innerHTML=ms.map(([k,v])=>`<div class="metric"><small>${k}</small><b>${v}</b></div>`).join('');
 const levels=[['离开过热区观察线',q.high20*.97,`20日高 ${fmt(q.high20,2)} × 97%`],['20日区间中位',q.mid20,'普通回撤结构参考'],['修复观察区',q.low20,`${fmt(q.low20,2)} ～ ${fmt(q.low20*1.03,2)}`]];
 $('gateLevels').innerHTML=levels.map(([k,v,d])=>`<div class="gateLevel"><small>${k}</small><b>${fmt(v,2)}</b><small>${d}</small></div>`).join('');$('gatePlan').innerHTML=`<b>系统操作参考：</b> ${plan}`
}
'''
js_anchor='function stats(s){'
if js_anchor not in s: raise SystemExit('JS anchor not found')
s=s.replace(js_anchor,js+'\n'+js_anchor,1)
s=s.replace('renderMetrics();renderAnalysisMetrics();renderDetail();','renderMetrics();renderAnalysisMetrics();renderEntryGate();renderDetail();')
s=s.replace("$('resetView').onclick=resetView;", "$('resetView').onclick=resetView;$('gateThreshold')?.addEventListener('change',renderEntryGate);")

p.write_text(s,encoding='utf-8')
print('Patched Entry Gate panel and operation reference')
