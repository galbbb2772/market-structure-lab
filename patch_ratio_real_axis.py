from pathlib import Path

p = Path('docs/ratio-history.html')
s = p.read_text(encoding='utf-8')

repls = []
repls.append((
"<div class=\"legend balance\"><span>历史涨跌比</span><span>1.00 平衡线</span></div>",
"<div class=\"legend balance\"><span>历史涨跌比</span><span>1.00 平衡线</span><span>1.20 平仓参考</span><span>3.00 极端参考</span></div>"
))
repls.append((
"<div class=\"hint\" style=\"margin-top:8px\">两张图完全同步。手机：单指左右拖动、双指捏合缩放；电脑：拖动平移、滚轮缩放、触控板横向平移。最少10个点，最多当前完整研究区间；纵轴固定，不因拖到不同历史片段而跳动。</div>",
"<div class=\"hint\" style=\"margin-top:8px\">两张图完全同步。手机：单指左右拖动、双指捏合缩放；电脑：拖动平移、滚轮缩放、触控板横向平移。最少10个点，最多当前完整研究区间；涨跌比纵轴按当前研究总区间的真实最大值固定，不随左右拖动或横向缩放跳动；无下跌日时以 ∞ 特殊标记显示。</div>"
))
repls.append((
"function fixedRatioY(){const m=$('mode').value,w=+$('window').value;if(m==='M')return{lo:0,hi:3};if(m==='Y')return{lo:.5,hi:1.8};if(w<=5)return{lo:0,hi:5};if(w<=10)return{lo:0,hi:4};if(w<=20)return{lo:0,hi:3};if(w<=60)return{lo:.3,hi:2.5};if(w<=120)return{lo:.4,hi:2.1};return{lo:.5,hi:1.8}}",
"function ratioAxis(){const vals=FULL.map(q=>q.ratio).filter(v=>Number.isFinite(v)&&v>=0);const mx=Math.max(3,...vals);let hi;if(mx<=3)hi=3;else if(mx<=4)hi=4;else if(mx<=6)hi=6;else if(mx<=10)hi=10;else if(mx<=20)hi=20;else hi=Math.ceil(mx/10)*10;return{lo:0,hi}}"
))
repls.append((
" const ref=balanceLine?1:zeroLine?0:null;if(ref!=null&&ref>=axis.lo&&ref<=axis.hi){const y=T+(axis.hi-ref)/(axis.hi-axis.lo)*H;x.strokeStyle=balanceLine?'#ffcc77':'#587080';x.setLineDash([6,5]);x.beginPath();x.moveTo(L,y);x.lineTo(w-R,y);x.stroke();x.setLineDash([])}",
" const ref=balanceLine?1:zeroLine?0:null;if(ref!=null&&ref>=axis.lo&&ref<=axis.hi){const y=T+(axis.hi-ref)/(axis.hi-axis.lo)*H;x.strokeStyle=balanceLine?'#ffcc77':'#587080';x.setLineDash([6,5]);x.beginPath();x.moveTo(L,y);x.lineTo(w-R,y);x.stroke();x.setLineDash([])}if(field==='ratio'){for(const [rv,col] of [[1.2,'#69d5b3'],[3,'#ff8b8b']]){if(rv>=axis.lo&&rv<=axis.hi){const y=T+(axis.hi-rv)/(axis.hi-axis.lo)*H;x.strokeStyle=col;x.setLineDash([3,5]);x.beginPath();x.moveTo(L,y);x.lineTo(w-R,y);x.stroke();x.setLineDash([]);x.fillStyle=col;x.fillText(rv.toFixed(2),Math.max(4,L-38),y-3)}}}"
))
repls.append((
" x.fillStyle='#ff8b8b';s.forEach((q,i)=>{const raw=q[field],xx=L+i*W/Math.max(1,s.length-1);if(raw===Infinity||Number.isFinite(raw)&&raw>axis.hi){x.beginPath();x.moveTo(xx-3,T+5);x.lineTo(xx+3,T+5);x.lineTo(xx,T+1);x.fill()}else if(Number.isFinite(raw)&&raw<axis.lo){x.beginPath();x.moveTo(xx-3,T+H-5);x.lineTo(xx+3,T+H-5);x.lineTo(xx,T+H-1);x.fill()}})",
" x.fillStyle='#ff8b8b';s.forEach((q,i)=>{const raw=q[field],xx=L+i*W/Math.max(1,s.length-1);if(raw===Infinity){x.beginPath();x.moveTo(xx-4,T+7);x.lineTo(xx+4,T+7);x.lineTo(xx,T+1);x.fill();if(field==='ratio'){x.font=(w<520?'10':'11')+'px system-ui';x.fillText('∞',Math.max(L,Math.min(w-R-10,xx-3)),T+18)}}else if(Number.isFinite(raw)&&raw>axis.hi){x.beginPath();x.moveTo(xx-3,T+5);x.lineTo(xx+3,T+5);x.lineTo(xx,T+1);x.fill()}else if(Number.isFinite(raw)&&raw<axis.lo){x.beginPath();x.moveTo(xx-3,T+H-5);x.lineTo(xx+3,T+H-5);x.lineTo(xx,T+H-1);x.fill()}})"
))
repls.append((
"function drawNav(){const c=$('navigator'),{x,w,h}=fit(c);x.clearRect(0,0,w,h);x.fillStyle='#0a151d';x.fillRect(0,0,w,h);if(FULL.length<2)return;const vals=FULL.map(q=>Number.isFinite(q.ratio)?q.ratio:3),lo=0,hi=Math.max(3,Math.min(5,Math.max(...vals)));x.strokeStyle='#466b82';x.lineWidth=1;x.beginPath();FULL.forEach((q,i)=>{const xx=i*(w-1)/(FULL.length-1),v=Math.max(lo,Math.min(vals[i],hi)),yy=5+(hi-v)/(hi-lo)*(h-10);i?x.lineTo(xx,yy):x.moveTo(xx,yy)});x.stroke();const a=VIEW.start/FULL.length*w,b=VIEW.end/FULL.length*w;x.fillStyle='rgba(121,169,255,.18)';x.fillRect(a,1,Math.max(3,b-a),h-2);x.strokeStyle='#79a9ff';x.lineWidth=2;x.strokeRect(a+1,2,Math.max(2,b-a-2),h-4)}",
"function drawNav(){const c=$('navigator'),{x,w,h}=fit(c);x.clearRect(0,0,w,h);x.fillStyle='#0a151d';x.fillRect(0,0,w,h);if(FULL.length<2)return;const axis=ratioAxis(),lo=axis.lo,hi=axis.hi,vals=FULL.map(q=>q.ratio===Infinity?hi:(Number.isFinite(q.ratio)?q.ratio:null));x.strokeStyle='#466b82';x.lineWidth=1;x.beginPath();let on=false;FULL.forEach((q,i)=>{const xx=i*(w-1)/(FULL.length-1),raw=vals[i];if(raw==null){on=false;return}const v=Math.max(lo,Math.min(raw,hi)),yy=5+(hi-v)/(hi-lo)*(h-10);if(on)x.lineTo(xx,yy);else{x.moveTo(xx,yy);on=true}});x.stroke();const a=VIEW.start/FULL.length*w,b=VIEW.end/FULL.length*w;x.fillStyle='rgba(121,169,255,.18)';x.fillRect(a,1,Math.max(3,b-a),h-2);x.strokeStyle='#79a9ff';x.lineWidth=2;x.strokeRect(a+1,2,Math.max(2,b-a-2),h-4)}"
))
repls.append((
"function paint(){VISIBLE=visible();drawLineChart('returnChart','returnTip','retPct',fixedReturnY(),true,false);drawLineChart('ratioChart','ratioTip','ratio',fixedRatioY(),false,true);drawNav();updateView()}",
"function paint(){VISIBLE=visible();drawLineChart('returnChart','returnTip','retPct',fixedReturnY(),true,false);drawLineChart('ratioChart','ratioTip','ratio',ratioAxis(),false,true);drawNav();updateView()}"
))
repls.append((
"function updateView(){const n=FULL.length,s=VISIBLE,m=$('mode').value,name=DATA?.instruments?.[$('idx').value]?.name||'';$('viewInfo').textContent=n&&s.length?`窗口 ${s.length}/${n} 点 · ${s[0].key} → ${s.at(-1).key}`:'—';$('chartSub').textContent=s.length?`${name} · ${m==='M'?'逐月':m==='Y'?'逐年':$('window').value+'交易日滚动'} · 上下图同步`:'—'}",
"function updateView(){const n=FULL.length,s=VISIBLE,m=$('mode').value,name=DATA?.instruments?.[$('idx').value]?.name||'',ry=ratioAxis();$('viewInfo').textContent=n&&s.length?`窗口 ${s.length}/${n} 点 · ${s[0].key} → ${s.at(-1).key} · 涨跌比Y 0～${fmt(ry.hi,0)}`:'—';$('chartSub').textContent=s.length?`${name} · ${m==='M'?'逐月':m==='Y'?'逐年':$('window').value+'交易日滚动'} · 上下图同步 · 真实涨跌比`:'—'}"
))

for old, new in repls:
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'replacement target count={count}: {old[:120]}')
    s = s.replace(old, new)

p.write_text(s, encoding='utf-8')
print('patched', p)
