from pathlib import Path

p = Path('docs/ratio-history.html')
s = p.read_text(encoding='utf-8')

repls = [
("<header class=\"hero\"><div class=\"eyebrow\">SYNCHRONIZED MARKET BREADTH / RETURN VIEW</div><h1>指数涨跌幅 × K线涨跌比</h1><p class=\"lead\">上图显示同一周期的指数涨跌幅，下图显示上涨日K数量 ÷ 下跌日K数量。两张图共用同一时间窗、缩放、拖动和底部历史导航；美股盘中加载5分钟级实时快照。</p>",
 "<header class=\"hero\"><div class=\"eyebrow\">SYNCHRONIZED MARKET BREADTH / RETURN VIEW</div><h1>指数累计涨跌幅 × K线涨跌比</h1><p class=\"lead\">上图显示指数从所选研究区间起点开始的累计涨跌幅，下图显示上涨日K数量 ÷ 下跌日K数量。两张图共用同一时间窗、缩放、拖动和底部历史导航；美股盘中加载5分钟级实时快照。</p>"),
("<div class=\"subhead\">同期指数涨跌幅</div>", "<div class=\"subhead\">指数累计涨跌幅</div>"),
("<div class=\"legend\"><span>指数同期涨跌幅</span></div>", "<div class=\"legend\"><span>从所选区间起点累计涨跌</span></div>"),
("function series(){const mode=$('mode').value,sym=$('idx').value,w=+$('window').value,a=$('from').value,b=$('to').value;return(mode==='R'?rolling(sym,w):grouped(sym,mode)).filter(x=>x.date>=a&&x.date<=b)}",
 "function series(){const mode=$('mode').value,sym=$('idx').value,w=+$('window').value,a=$('from').value,b=$('to').value;const rows=(mode==='R'?rolling(sym,w):grouped(sym,mode)).filter(x=>x.date>=a&&x.date<=b);if(!rows.length)return rows;const bm=new Map(barsFor(sym).map(b=>[b[0],+b[4]])),base=bm.get(rows[0].date);return rows.map(q=>{const c=bm.get(q.date);return{...q,cumRetPct:Number.isFinite(base)&&base!==0&&Number.isFinite(c)?100*(c/base-1):null}})}"),
("function fixedReturnY(){const m=$('mode').value,w=+$('window').value;if(m==='M')return{lo:-50,hi:50};if(m==='Y')return{lo:-80,hi:80};if(w<=5)return{lo:-20,hi:20};if(w<=10)return{lo:-30,hi:30};if(w<=20)return{lo:-40,hi:40};if(w<=60)return{lo:-60,hi:60};if(w<=120)return{lo:-80,hi:80};return{lo:-100,hi:100}}",
 "function cumulativeReturnAxis(){const vals=FULL.map(q=>q.cumRetPct).filter(Number.isFinite);if(!vals.length)return{lo:-10,hi:10};let lo=Math.min(0,...vals),hi=Math.max(0,...vals),span=hi-lo;if(span<2){lo-=1;hi+=1;span=hi-lo}const pad=Math.max(1,span*.08),step=span>200?50:span>100?25:span>40?10:5;lo=Math.floor((lo-pad)/step)*step;hi=Math.ceil((hi+pad)/step)*step;if(lo===hi){lo-=step;hi+=step}return{lo,hi}}"),
("function paint(){VISIBLE=visible();drawLineChart('returnChart','returnTip','retPct',fixedReturnY(),true,false);drawLineChart('ratioChart','ratioTip','ratio',ratioAxis(),false,true);drawNav();updateView()}",
 "function paint(){VISIBLE=visible();drawLineChart('returnChart','returnTip','cumRetPct',cumulativeReturnAxis(),true,false);drawLineChart('ratioChart','ratioTip','ratio',ratioAxis(),false,true);drawNav();updateView()}"),
("x.fillText(field==='retPct'?fmt(v,0)+'%':fmt(v,2),6,y+4)", "x.fillText(field==='cumRetPct'?fmt(v,0)+'%':fmt(v,2),6,y+4)"),
("tip.innerHTML=p.field==='retPct'?`<b>${esc(q.key)}</b><br>同期指数涨跌幅 <b>${fmt(q.retPct,2)}%</b>${q.provisional?'<br><span class=\"ok\">盘中临时点</span>':''}`:",
 "tip.innerHTML=p.field==='cumRetPct'?`<b>${esc(q.key)}</b><br>自所选区间起点累计涨跌 <b>${fmt(q.cumRetPct,2)}%</b>${q.provisional?'<br><span class=\"ok\">盘中临时点</span>':''}`:"),
("function stats(s){let up=0,down=0,flat=0;s.forEach(q=>{up+=q.up;down+=q.down;flat+=q.flat});const ret=s.map(q=>q.retPct).filter(Number.isFinite),last=ret.at(-1);return{points:s.length,up,down,flat,overall:down?up/down:(up?Infinity:null),upShare:(up+down)?100*up/(up+down):null,lastRet:last}}",
 "function stats(s){let up=0,down=0,flat=0;s.forEach(q=>{up+=q.up;down+=q.down;flat+=q.flat});const cum=s.map(q=>q.cumRetPct).filter(Number.isFinite),last=cum.at(-1);return{points:s.length,up,down,flat,overall:down?up/down:(up?Infinity:null),upShare:(up+down)?100*up/(up+down):null,lastCum:last}}"),
("['最新同期指数涨跌',z.lastRet==null?'—':fmt(z.lastRet,2)+'%']", "['区间累计涨跌',z.lastCum==null?'—':fmt(z.lastCum,2)+'%']"),
("$('chartTitle').textContent=`${DATA.instruments[$('idx').value].name} · 同期涨跌幅 × 涨跌比`", "$('chartTitle').textContent=`${DATA.instruments[$('idx').value].name} · 累计涨跌幅 × 涨跌比`"),
("<p>月度/年度显示同期指数涨跌幅与涨跌比；滚动日数据只在图上查看。</p>", "<p>上方主图显示所选区间累计涨跌幅；本表中的月度/年度涨跌幅仍表示各自周期内涨跌幅。</p>")
]

for old,new in repls:
    if old not in s:
        raise SystemExit(f'missing target: {old[:120]}')
    s=s.replace(old,new,1)

# Update visible summary text without touching zoom/pan implementation.
s=s.replace("$('chartSub').textContent=s.length?`${name} · ${m==='M'?'逐月':m==='Y'?'逐年':$('window').value+'交易日滚动'} · 上下图同步 · 真实涨跌比`:'—'",
            "$('chartSub').textContent=s.length?`${name} · 上图=区间起点累计涨跌 · 下图=${m==='M'?'逐月':m==='Y'?'逐年':$('window').value+'交易日滚动'}涨跌比 · 上下图同步`:'—'",1)

p.write_text(s, encoding='utf-8')
print('patched cumulative index return chart')
