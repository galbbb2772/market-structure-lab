from pathlib import Path

p = Path('docs/ratio-history.html')
s = p.read_text(encoding='utf-8')

if 'id="analysisMetrics"' in s:
    print('analysis panel already present')
    raise SystemExit(0)

panel = '''
<section class="panel" id="analysisPanel">
<div class="sectionTitle"><div><h2>背离性 · 相关性 · 迟滞性</h2><p>背离用“区间累计涨跌幅 vs 涨跌比”的标准化差；相关与迟滞用“同窗口收益率 vs 同窗口涨跌比”，避免把累计量和滚动量直接混算。</p></div><div class="controls"><label>统计窗口<select id="corrWindow"><option value="20">20期</option><option value="60" selected>60期</option><option value="120">120期</option></select></label><label>最大领先/滞后<select id="lagMax"><option value="20">±20</option><option value="40" selected>±40</option><option value="60">±60</option></select></label></div></div>
<div id="analysisMetrics" class="metrics"></div>

<div class="subhead">背离强度</div>
<div class="chartWrap"><canvas id="divergenceChart" class="chart"></canvas><div id="divergenceTip" class="tooltip"></div></div>
<div class="legend"><span>标准化背离：指数累计走势 − 涨跌比</span></div>
<div class="hint" style="margin-top:6px">正值：指数走势强于涨跌比；负值：涨跌比强于指数。0 附近表示两者相对同步。该值用于描述背离，不是交易信号。</div>

<div class="subhead">滚动相关性</div>
<div class="chartWrap"><canvas id="correlationChart" class="chart"></canvas><div id="correlationTip" class="tooltip"></div></div>
<div class="legend"><span>同窗口收益率 × 涨跌比 · Pearson滚动相关</span></div>

<div class="subhead">领先 / 滞后相关性</div>
<div class="chartWrap"><canvas id="lagChart" class="chart"></canvas></div>
<div class="hint" style="margin-top:8px">横轴为偏移期数：<b>正值</b> = 涨跌比领先指数收益；<b>负值</b> = 指数收益领先涨跌比。滚动日视图下 1 期≈1 个交易日。</div>
</section>

'''
needle = '<section class="panel"><div class="sectionTitle"><div><h2>逐期明细</h2>'
if needle not in s:
    raise SystemExit('detail panel anchor not found')
s = s.replace(needle, panel + needle, 1)

# Add analysis math/helpers before the existing defaultCount() function.
anchor = 'function defaultCount(){'
if anchor not in s:
    raise SystemExit('defaultCount anchor not found')
helpers = r'''
let LAG_SERIES=[],ANALYSIS_SUMMARY={};
function pearsonPairs(pairs){
 const a=pairs.filter(([x,y])=>Number.isFinite(x)&&Number.isFinite(y));if(a.length<3)return null;
 const mx=a.reduce((z,q)=>z+q[0],0)/a.length,my=a.reduce((z,q)=>z+q[1],0)/a.length;
 let num=0,dx=0,dy=0;for(const [x,y] of a){const ax=x-mx,ay=y-my;num+=ax*ay;dx+=ax*ax;dy+=ay*ay}
 return dx>0&&dy>0?num/Math.sqrt(dx*dy):null
}
function ranks(v){const a=v.map((x,i)=>[x,i]).sort((a,b)=>a[0]-b[0]),r=Array(v.length);let i=0;while(i<a.length){let j=i+1;while(j<a.length&&a[j][0]===a[i][0])j++;const rr=(i+j-1)/2+1;for(let k=i;k<j;k++)r[a[k][1]]=rr;i=j}return r}
function spearmanPairs(pairs){const a=pairs.filter(([x,y])=>Number.isFinite(x)&&Number.isFinite(y));if(a.length<3)return null;const rx=ranks(a.map(q=>q[0])),ry=ranks(a.map(q=>q[1]));return pearsonPairs(rx.map((x,i)=>[x,ry[i]]))}
function zAt(vals){const a=vals.filter(Number.isFinite);if(a.length<3)return null;const m=a.reduce((x,y)=>x+y,0)/a.length,sd=Math.sqrt(a.reduce((x,y)=>x+(y-m)**2,0)/a.length);return sd>0?(a.at(-1)-m)/sd:0}
function prepareAnalysis(){
 if(!FULL.length){LAG_SERIES=[];ANALYSIS_SUMMARY={};return}
 const w=Math.max(10,+($('corrWindow')?.value||60));
 for(let i=0;i<FULL.length;i++){
   FULL[i].divergence=null;FULL[i].rollingCorr=null;
   const st=Math.max(0,i-w+1),seg=FULL.slice(st,i+1);
   if(seg.length>=Math.min(w,10)){
     const zr=zAt(seg.map(q=>q.cumRetPct)),zb=zAt(seg.map(q=>Number.isFinite(q.ratio)?q.ratio:null));
     if(zr!=null&&zb!=null)FULL[i].divergence=zr-zb;
     FULL[i].rollingCorr=pearsonPairs(seg.map(q=>[q.ratio,q.retPct]));
   }
 }
 const pairs=FULL.map(q=>[q.ratio,q.retPct]);
 const sync=pearsonPairs(pairs),spear=spearmanPairs(pairs),lm=Math.max(1,+($('lagMax')?.value||40));
 LAG_SERIES=[];
 for(let lag=-lm;lag<=lm;lag++){
   const ps=[];
   if(lag>0){for(let i=0;i<FULL.length-lag;i++)ps.push([FULL[i].ratio,FULL[i+lag].retPct])}
   else if(lag<0){const k=-lag;for(let i=0;i<FULL.length-k;i++)ps.push([FULL[i+k].ratio,FULL[i].retPct])}
   else {for(const q of FULL)ps.push([q.ratio,q.retPct])}
   const c=pearsonPairs(ps);LAG_SERIES.push({lag,corr:c,n:ps.filter(([x,y])=>Number.isFinite(x)&&Number.isFinite(y)).length})
 }
 const valid=LAG_SERIES.filter(q=>Number.isFinite(q.corr));
 const best=valid.length?valid.reduce((a,b)=>Math.abs(b.corr)>Math.abs(a.corr)?b:a):null;
 const divs=FULL.map(q=>q.divergence).filter(Number.isFinite),lastDiv=[...FULL].reverse().find(q=>Number.isFinite(q.divergence))?.divergence??null;
 ANALYSIS_SUMMARY={sync,spear,best,lastDiv,maxDiv:divs.length?Math.max(...divs):null,minDiv:divs.length?Math.min(...divs):null};
}
function divergenceAxis(){const v=FULL.map(q=>q.divergence).filter(Number.isFinite);const m=Math.max(2,...v.map(x=>Math.abs(x))),h=Math.ceil(m);return{lo:-h,hi:h}}
function renderAnalysisMetrics(){
 const z=ANALYSIS_SUMMARY,b=z.best,unit=$('mode').value==='R'?'交易日':'期';
 const lagText=b?`${b.lag>0?'+':''}${b.lag} ${unit}`:'—';
 const rows=[['同步 Pearson',z.sync==null?'—':fmt(z.sync,3)],['同步 Spearman',z.spear==null?'—':fmt(z.spear,3)],['最强领先/滞后',lagText],['对应相关系数',b?.corr==null?'—':fmt(b.corr,3)],['当前背离强度',z.lastDiv==null?'—':fmt(z.lastDiv,2)],['背离区间',z.minDiv==null?'—':`${fmt(z.minDiv,2)} ～ ${fmt(z.maxDiv,2)}`]];
 $('analysisMetrics').innerHTML=rows.map(([k,v])=>`<div class="metric"><small>${k}</small><b>${v}</b></div>`).join('')
}
function drawLagChart(){
 const c=$('lagChart');if(!c)return;const {x,w,h}=fit(c),L=w<520?48:60,R=12,T=14,B=34,W=Math.max(10,w-L-R),H=Math.max(10,h-T-B);x.clearRect(0,0,w,h);x.fillStyle='#0b171f';x.fillRect(0,0,w,h);if(LAG_SERIES.length<2)return;
 x.font=(w<520?'11':'12')+'px system-ui';x.strokeStyle='#203744';x.lineWidth=1;for(const v of [-1,-.5,0,.5,1]){const y=T+(1-v)/2*H;x.beginPath();x.moveTo(L,y);x.lineTo(w-R,y);x.stroke();x.fillStyle='#91a6b5';x.fillText(fmt(v,1),6,y+4)}
 const lm=Math.max(...LAG_SERIES.map(q=>Math.abs(q.lag)),1);x.strokeStyle='#587080';x.setLineDash([6,5]);x.beginPath();x.moveTo(L,T+H/2);x.lineTo(w-R,T+H/2);x.stroke();x.setLineDash([]);
 x.strokeStyle='#79a9ff';x.lineWidth=w<520?1.7:2.2;x.beginPath();let on=false;for(const q of LAG_SERIES){if(!Number.isFinite(q.corr)){on=false;continue}const xx=L+(q.lag+lm)/(2*lm)*W,yy=T+(1-q.corr)/2*H;if(on)x.lineTo(xx,yy);else{x.moveTo(xx,yy);on=true}}x.stroke();
 const b=ANALYSIS_SUMMARY.best;if(b&&Number.isFinite(b.corr)){const xx=L+(b.lag+lm)/(2*lm)*W,yy=T+(1-b.corr)/2*H;x.fillStyle='#69d5b3';x.beginPath();x.arc(xx,yy,4.5,0,Math.PI*2);x.fill();x.fillStyle='#dbe7ef';x.fillText(`best ${b.lag>0?'+':''}${b.lag} / ${fmt(b.corr,2)}`,Math.max(L,Math.min(w-R-110,xx+8)),Math.max(T+12,yy-8))}
 x.fillStyle='#91a6b5';for(const lag of [-lm,Math.round(-lm/2),0,Math.round(lm/2),lm]){const xx=L+(lag+lm)/(2*lm)*W;x.fillText((lag>0?'+':'')+lag,Math.max(2,Math.min(w-38,xx-10)),h-12)}
}
'''
s = s.replace(anchor, helpers + '\n' + anchor, 1)

# Extend paint to include the two time-series analysis charts and lag chart.
old_paint = "function paint(){VISIBLE=visible();drawLineChart('returnChart','returnTip','cumRetPct',cumulativeReturnAxis(),true,false);drawLineChart('ratioChart','ratioTip','ratio',ratioAxis(),false,true);drawNav();updateView()}"
new_paint = "function paint(){VISIBLE=visible();drawLineChart('returnChart','returnTip','cumRetPct',cumulativeReturnAxis(),true,false);drawLineChart('ratioChart','ratioTip','ratio',ratioAxis(),false,true);drawLineChart('divergenceChart','divergenceTip','divergence',divergenceAxis(),true,false);drawLineChart('correlationChart','correlationTip','rollingCorr',{lo:-1,hi:1},true,false);drawLagChart();drawNav();updateView()}"
if old_paint not in s:
    raise SystemExit('paint anchor not found')
s = s.replace(old_paint,new_paint,1)

# Tooltip: support divergence and rolling correlation.
old_tip = "tip.innerHTML=p.field==='cumRetPct'?`<b>${esc(q.key)}</b><br>自所选区间起点累计涨跌 <b>${fmt(q.cumRetPct,2)}%</b>${q.provisional?'<br><span class=\"ok\">盘中临时点</span>':''}`:`<b>${esc(q.key)}</b><br>上涨 ${q.up} · 下跌 ${q.down} · 平盘 ${q.flat}<br>涨跌比 <b>${q.ratio===Infinity?'∞':fmt(q.ratio,2)}</b><br>上涨占比 ${fmt(q.upShare,1)}%${q.provisional?'<br><span class=\"ok\">盘中临时点</span>':''}`;"
new_tip = "tip.innerHTML=p.field==='cumRetPct'?`<b>${esc(q.key)}</b><br>自所选区间起点累计涨跌 <b>${fmt(q.cumRetPct,2)}%</b>${q.provisional?'<br><span class=\"ok\">盘中临时点</span>':''}`:p.field==='divergence'?`<b>${esc(q.key)}</b><br>背离强度 <b>${fmt(q.divergence,2)}</b><br>累计涨跌 ${fmt(q.cumRetPct,2)}% · 涨跌比 ${q.ratio===Infinity?'∞':fmt(q.ratio,2)}`:p.field==='rollingCorr'?`<b>${esc(q.key)}</b><br>滚动 Pearson <b>${fmt(q.rollingCorr,3)}</b><br>同期收益 ${fmt(q.retPct,2)}% · 涨跌比 ${q.ratio===Infinity?'∞':fmt(q.ratio,2)}`:`<b>${esc(q.key)}</b><br>上涨 ${q.up} · 下跌 ${q.down} · 平盘 ${q.flat}<br>涨跌比 <b>${q.ratio===Infinity?'∞':fmt(q.ratio,2)}</b><br>上涨占比 ${fmt(q.upShare,1)}%${q.provisional?'<br><span class=\"ok\">盘中临时点</span>':''}`;"
if old_tip not in s:
    raise SystemExit('tooltip anchor not found')
s = s.replace(old_tip,new_tip,1)

# Attach the same bounded zoom/pan logic to both new time-series charts.
old_attach = "attachChart($('returnChart'));attachChart($('ratioChart'));"
new_attach = "attachChart($('returnChart'));attachChart($('ratioChart'));attachChart($('divergenceChart'));attachChart($('correlationChart'));"
if old_attach not in s:
    raise SystemExit('attach anchor not found')
s = s.replace(old_attach,new_attach,1)

# Replace render() so analysis is prepared whenever the selected research interval changes.
old_render = "function render(){if(!DATA)return;$('windowLabel').style.display=$('mode').value==='R'?'grid':'none';FULL=series();renderMetrics();renderDetail();renderMatrix();$('chartTitle').textContent=`${DATA.instruments[$('idx').value].name} · 累计涨跌幅 × 涨跌比`;resetView()}"
if old_render not in s:
    old_render = "function render(){if(!DATA)return;$('windowLabel').style.display=$('mode').value==='R'?'grid':'none';FULL=series();renderMetrics();renderDetail();renderMatrix();$('chartTitle').textContent=`${DATA.instruments[$('idx').value].name} · 同期涨跌幅 × 涨跌比`;resetView()}"
new_render = "function render(){if(!DATA)return;$('windowLabel').style.display=$('mode').value==='R'?'grid':'none';FULL=series();prepareAnalysis();renderMetrics();renderAnalysisMetrics();renderDetail();renderMatrix();$('chartTitle').textContent=`${DATA.instruments[$('idx').value].name} · 累计涨跌幅 × 涨跌比`;resetView()}"
if old_render not in s:
    raise SystemExit('render anchor not found')
s = s.replace(old_render,new_render,1)

# Live refresh path must recalculate the derived analysis fields too.
old_live = "if(changed){FULL=series();renderMetrics();renderDetail();renderMatrix();if(wasRight)"
new_live = "if(changed){FULL=series();prepareAnalysis();renderMetrics();renderAnalysisMetrics();renderDetail();renderMatrix();if(wasRight)"
if old_live not in s:
    raise SystemExit('live refresh anchor not found')
s = s.replace(old_live,new_live,1)

# Make the summary metric agree with the cumulative-return chart.
old_stats = "function stats(s){let up=0,down=0,flat=0;s.forEach(q=>{up+=q.up;down+=q.down;flat+=q.flat});const ret=s.map(q=>q.retPct).filter(Number.isFinite),last=ret.at(-1);return{points:s.length,up,down,flat,overall:down?up/down:(up?Infinity:null),upShare:(up+down)?100*up/(up+down):null,lastRet:last}}"
new_stats = "function stats(s){let up=0,down=0,flat=0;s.forEach(q=>{up+=q.up;down+=q.down;flat+=q.flat});const lastCum=[...s].reverse().find(q=>Number.isFinite(q.cumRetPct))?.cumRetPct??null;return{points:s.length,up,down,flat,overall:down?up/down:(up?Infinity:null),upShare:(up+down)?100*up/(up+down):null,lastRet:lastCum}}"
if old_stats in s:s=s.replace(old_stats,new_stats,1)
s=s.replace("['最新同期指数涨跌',z.lastRet==null?'—':fmt(z.lastRet,2)+'%']","['区间累计涨跌',z.lastRet==null?'—':fmt(z.lastRet,2)+'%']",1)

# Wire analysis controls.
control_anchor = "$('resetView').onclick=resetView;window.addEventListener('resize',()=>requestAnimationFrame(paint));"
control_new = "$('resetView').onclick=resetView;window.addEventListener('resize',()=>requestAnimationFrame(paint));['corrWindow','lagMax'].forEach(id=>$(id)?.addEventListener('change',()=>{prepareAnalysis();renderAnalysisMetrics();paint()}));"
if control_anchor not in s:
    raise SystemExit('control anchor not found')
s = s.replace(control_anchor,control_new,1)

# Update the explanatory headline text if the old wording is still present.
s = s.replace('上图显示同一周期的指数涨跌幅，下图显示上涨日K数量 ÷ 下跌日K数量。','上图显示从所选区间起点累计的指数涨跌幅，下图显示上涨日K数量 ÷ 下跌日K数量。',1)

p.write_text(s,encoding='utf-8')
print('patched',p)
