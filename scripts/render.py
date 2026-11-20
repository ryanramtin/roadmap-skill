#!/usr/bin/env python3
"""Render <out>/index.html from <out>/roadmap.json (+ optional narrative.json). Stdlib only."""
import html as _html
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect  # noqa: E402  (for the shared redaction rules)

LIGHT = """--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--line:#cfcec6;
--h1:#cde2fb;--h2:#9ec5f4;--h3:#6da7ec;--h4:#3987e5;--h5:#256abf;--h6:#184f95;
--s-exec:#3987e5;--s-explore:#8c6bd8;--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--shadow:0 1px 2px rgba(0,0,0,.06);"""
DARK = """--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--line:#44443f;
--h1:#184f95;--h2:#2163b5;--h3:#3987e5;--h4:#5f9fe9;--h5:#86b6ef;--h6:#b4d2f6;
--s-exec:#5f9fe9;--s-explore:#a78bf0;--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--shadow:none;"""

CSS = r"""
:root{__LIGHT__}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){__DARK__}}
:root[data-theme="dark"]{__DARK__}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;overflow-x:hidden}
h1,h2,h3{margin:0;line-height:1.2}
a{color:inherit}
button{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer}
button:hover{border-color:var(--ink2)}
button[aria-pressed="true"]{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 64px}
.top{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between;padding:28px 0 8px}
.top h1{font-size:32px;letter-spacing:-.02em}
.sub{color:var(--ink2);font-size:14px;margin-top:4px}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.stamp{display:inline-flex;gap:8px;align-items:center;font-size:13px;color:var(--ink2);padding:4px 10px;border:1px solid var(--line);border-radius:99px;background:var(--surface)}
.dot{width:9px;height:9px;border-radius:50%;background:var(--muted);display:inline-block}
.dot.live{background:var(--good);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(12,163,12,.5)}70%{box-shadow:0 0 0 7px rgba(12,163,12,0)}100%{box-shadow:0 0 0 0 rgba(12,163,12,0)}}
.note{font-size:13px;color:var(--ink2);margin:6px 0 0}
.note b{color:var(--ink)}
section{margin-top:32px}
section>h2{font-size:20px;letter-spacing:-.01em;margin-bottom:4px}
section>.lede{color:var(--ink2);font-size:14px;margin:0 0 12px}
.card{background:var(--surface);border:1px solid var(--grid);border-radius:12px;padding:16px;box-shadow:var(--shadow)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:20px}
.kpi{background:var(--surface);border:1px solid var(--grid);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:30px;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.kpi .l{font-size:13px;color:var(--ink2);margin-top:2px}
.kpi .d{font-size:12px;color:var(--muted);margin-top:2px}
.pill{display:inline-flex;gap:6px;align-items:center;font-size:12px;font-weight:600;border:1px solid var(--line);border-radius:99px;padding:1px 9px;white-space:nowrap}
.pill i{font-style:normal}
.g-head{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:10px}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--ink2);align-items:center}
.legend .sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:4px}
.ramp{display:inline-flex;gap:2px;vertical-align:middle;margin:0 6px}
.ramp b{width:14px;height:12px;border-radius:2px;display:inline-block}
.g-scroll{overflow-x:auto;border:1px solid var(--grid);border-radius:12px;background:var(--surface);-webkit-overflow-scrolling:touch}
.g-row{display:flex;align-items:stretch;min-width:max-content}
.g-label{position:sticky;left:0;z-index:2;background:var(--surface);flex:none;padding:2px 10px 2px 12px;display:flex;flex-direction:column;justify-content:center;border-right:1px solid var(--grid);overflow:hidden}
.g-name{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.25}
.g-st{font-size:11px;color:var(--ink2);white-space:nowrap;line-height:1.2}
.g-st i{font-style:normal;margin-right:4px}
.g-row svg{display:block;flex:none}
.g-axis text{fill:var(--muted);font-size:11px}
svg text{font-family:inherit}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th,.tbl td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--grid);white-space:nowrap}
.tbl th{color:var(--ink2);font-weight:600}
.tbl td.n,.tbl th.n{text-align:right}
.tblwrap{overflow-x:auto;border:1px solid var(--grid);border-radius:12px;background:var(--surface)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px}
.pc h3{font-size:16px;display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}
.pc h4{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:10px 0 3px}
.pc p,.pc li{font-size:13px;color:var(--ink2);margin:0}
.pc ul{margin:0;padding-left:16px}
.pc .hl{font-size:13px;color:var(--ink);margin:0 0 4px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.bar2{display:flex;gap:2px;height:14px;flex:1;min-width:80px}
.bar2 span{display:block;height:100%;border-radius:3px}
.eb{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:13px}
.eb .nm{width:110px;flex:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.eb .pc2{width:130px;flex:none;color:var(--ink2);font-size:12px;text-align:right}
.dec{list-style:none;margin:0;padding:0}
.dec li{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--grid);font-size:13px}
.dec .dt{color:var(--muted);flex:none;width:78px}
.dec .pj{color:var(--ink2);flex:none;width:96px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#tip{position:fixed;z-index:100;pointer-events:none;background:var(--ink);color:var(--surface);font-size:12px;line-height:1.35;padding:6px 9px;border-radius:6px;max-width:300px;white-space:pre-line;opacity:0;transition:opacity .08s}
#tip.on{opacity:1}
.narr{color:var(--ink2)}
.narr.stale{color:var(--serious);font-weight:600}
.narr.stale:before{content:"\26A0\00a0"}
.foot{margin-top:36px;font-size:12px;color:var(--muted)}
/* ---------- deck ---------- */
#deck{display:none;position:fixed;inset:0;z-index:20;background:var(--page)}
body.deckmode #deck{display:block}
body.deckmode #dash{display:none}
.viewport{position:absolute;inset:0 0 44px 0;overflow:hidden}
.scaler{position:absolute;left:0;top:0;width:1280px;height:720px;transform-origin:0 0}
.slide{display:none;position:absolute;inset:0;background:var(--surface);color:var(--ink);padding:52px 64px 48px;flex-direction:column;overflow:hidden}
.slide.on{display:flex}
.slide h2{font-size:42px;letter-spacing:-.025em;line-height:1.1;margin:0 0 20px;max-width:1080px}
.slide .kick{font-size:14px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:10px;font-weight:600}
.slide .body{flex:1;min-height:0;display:flex;flex-direction:column}
.sfoot{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-top:10px}
.slide.title{justify-content:flex-start;padding-top:170px}
.slide.title h2{font-size:76px;max-width:1100px}
.slide ul.big{font-size:24px;line-height:1.35;margin:0 0 20px;padding-left:26px;max-width:1050px}
.slide ul.big li{margin-bottom:10px}
.slide .kpis{margin-top:auto;grid-template-columns:repeat(6,1fr)}
.slide .kpi{background:var(--page)}
.cols3{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:16px}
.cols3 h4{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
.cols3 p,.cols3 li{font-size:16px;color:var(--ink2);margin:0 0 4px}
.cols3 ul{padding-left:18px;margin:0}
.tl{list-style:none;padding:0;margin:8px 0 0}
.tl li{display:flex;gap:12px;font-size:15px;padding:5px 0;border-bottom:1px solid var(--grid)}
.tl .dt{color:var(--muted);width:84px;flex:none}
.tl .k{width:20px;flex:none;color:var(--ink2)}
.deckbar{position:absolute;left:0;right:0;bottom:0;height:44px;display:flex;align-items:center;gap:10px;padding:0 16px;border-top:1px solid var(--grid);background:var(--page);font-size:13px;color:var(--ink2)}
.deckbar .sp{flex:1}
.mv{display:flex;gap:10px;font-size:16px;margin:6px 0;align-items:baseline}
.mv i{font-style:normal;width:20px}
.mv .nm{width:150px;font-weight:600}
@media (max-width:640px){.top h1{font-size:26px}.eb .nm{width:84px}.eb .pc2{display:none}.dec .pj{display:none}}
@media print{
 :root,:root[data-theme="dark"]{__LIGHT__}
 @page{size:1280px 720px;margin:0}
 html,body{background:#fff!important;overflow:visible!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
 #dash,.deckbar,#tip{display:none!important}
 #deck{display:block!important;position:static!important}
 .viewport{position:static!important;overflow:visible!important}
 .scaler{position:static!important;transform:none!important;width:1280px!important;height:auto!important}
 .slide,.slide.on{display:flex!important;position:relative!important;width:1280px;height:720px;break-after:page;page-break-after:always;overflow:hidden}
}
"""

JS = r"""
(function(){
var BOOT=__DATA__;
var D=BOOT.roadmap, N=BOOT.narrative||{};
var SERVED=/^https?:/.test(location.protocol);
var view='dash', slideIdx=0, gTable=false, lastOk=Date.now(), liveOk=SERVED, deckCount=0;
var $=function(s){return document.querySelector(s)};
var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]})};
var fmt=function(n){return (n||0).toLocaleString('en-US')};
var DAY=864e5;
function pd(s){var a=String(s).slice(0,10).split('-').map(Number);return Date.UTC(a[0],a[1]-1,a[2])}
function iso(ms){return new Date(ms).toISOString().slice(0,10)}
function isoKey(mon){var thu=mon+3*DAY;var y=new Date(thu).getUTCFullYear();var w=Math.floor((thu-Date.UTC(y,0,1))/DAY/7)+1;return y+'-W'+(w<10?'0':'')+w}
function weekList(){var s=pd(D.meta.window_start),e=pd(D.meta.window_end);var m=s-((new Date(s).getUTCDay()+6)%7)*DAY;var out=[];for(;m<=e;m+=7*DAY)out.push({ms:m,key:isoKey(m)});return out}
var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
var ST={active:{i:'\u25CF',l:'Active',c:'--good'},cooling:{i:'\u25D0',l:'Cooling',c:'--warn'},dormant:{i:'\u25B2',l:'Dormant',c:'--serious'},archived:{i:'\u25A0',l:'Archived',c:'--muted'}};
var NP=function(p){return (N.projects&&N.projects[p.name])||{}};
var stat=function(p){var s=NP(p).status_override;return ST[s]?s:p.status};
var pill=function(s){return '<span class="pill"><i style="color:var('+ST[s].c+')">'+ST[s].i+'</i>'+ST[s].l+'</span>'};
var vol=function(p){return p.totals.obs+p.totals.commits};
var cut=function(s,n){s=String(s||'');return s.length>n?s.slice(0,n-1).trim()+'\u2026':s};
var arr=function(x){return Array.isArray(x)?x:(x?[x]:[])};

/* ---------- derived ---------- */
function agoStr(ms){var s=Math.max(0,(Date.now()-ms)/1000);if(s<60)return 'just now';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}
function sum(P,f){return P.reduce(function(a,p){return a+f(p)},0)}
function kpis(){
  var P=D.projects, sc=FOC()?(D.portfolio.scoped||{}):null, pm=(sc&&sc.momentum)||D.portfolio.momentum||{};
  var sb=(sc&&sc.ships_by_status)||D.portfolio.ships_by_status||{};
  var shipsAll=sc&&sc.ships_total!=null?sc.ships_total:(D.portfolio.ships_total!=null?D.portfolio.ships_total:sum(Object.keys(sb),function(k){return sb[k]}));
  return {active:P.filter(function(p){return stat(p)==='active'}).length,total:P.length,
    ships:shipsAll,shipped:sb.shipped||0,held:(sb.held||0)+(sb.failed||0),features:sum(P,function(p){return p.totals.features}),bugfixes:sum(P,function(p){return p.totals.bugfixes}),
    decisions:sum(P,function(p){return p.totals.decisions}),mom:pm.pct==null?null:pm.pct,l4:pm.last4||0,p4:pm.prior4||0};
}
function share(){var P=D.projects,t=sum(P,vol)||1;return P.slice().sort(function(a,b){return vol(b)-vol(a)}).map(function(p){return {p:p,pct:Math.round(vol(p)*100/t)}})}
function risks(p){
  var NPp=NP(p); if(arr(NPp.risks).length) return arr(NPp.risks);
  var r=[],t=p.totals,age=Math.round((pd(D.meta.window_end)-pd(p.last_seen))/DAY);
  if(p.status==='dormant'&&age<=60) r.push('Went quiet '+age+' days ago');
  if(t.held+t.failed>0) r.push((t.held+t.failed)+' held/failed ship'+((t.held+t.failed)>1?'s':''));
  if(t.bugfixes>=15&&t.bugfixes/(t.features+t.bugfixes||1)>0.5) r.push('Bugfix-heavy: '+Math.round(t.bugfixes*100/(t.features+t.bugfixes))+'% of feature+fix work is fixes');
  if(p.explore_ratio!=null&&p.explore_ratio>2) r.push('Exploration outweighs building ('+p.explore_ratio+':1)');
  if(p.momentum!=null&&p.momentum<=-50) r.push('Momentum down '+Math.abs(p.momentum)+'% vs its prior 4 weeks');
  return r;
}
function nowText(p){var n=NP(p).now; if(n) return n; if(p.recent_completed&&p.recent_completed[0]) return cut(p.recent_completed[0],200); var m=p.milestones.filter(function(x){return x.kind!=='ship'}).slice(-1)[0]; return m?m.title:'Last active '+p.last_seen}
function nextList(p){var n=arr(NP(p).next); return n.length?n:p.next_steps.map(function(x){return cut(x,200)})}
function pHeadline(p){
  var n=NP(p).headline; if(n) return n;
  var t=p.totals, m=p.momentum;
  if(stat(p)==='archived') return p.name+' wrapped up and is archived';
  if(stat(p)==='dormant') return p.name+' has gone quiet';
  var bits=[]; if(t.features) bits.push(fmt(t.features)+' features'); if(t.commits) bits.push(fmt(t.commits)+' commits');
  return p.name+' '+(stat(p)==='active'?'is moving':'is cooling')+': '+bits.join(', ')+(m!=null?' ('+pctStr(m)+' vs its prior 4 weeks)':'');
}
function windowLabel(){return D.meta.window_start+' \u2192 '+D.meta.window_end}
function topHeadline(){
  if(N.headline) return N.headline;
  var s=share()[0]; if(!s) return 'No recorded activity in this window';
  var k=kpis();
  return s.p.name+' carried '+s.pct+'% of the recorded work'+(k.ships?'; '+k.ships+' ships logged '+(FOC()?'in these workstreams':'across the portfolio'):'');
}
function laneTitle(P,c){
  var u=UL(),a=c('active'),q=c('dormant');
  if(q>a) return q+' '+u+' have gone quiet while '+a+' carry the work';
  if(q===0&&a===P.length&&FOC()){var s=share()[0];return 'All '+a+' '+u+' active'+(s?'; '+s.p.name+' carries most of the build':'')}
  return a+' '+u+' are live'+(q?'; '+q+' have gone quiet':'');
}
function execBullets(){
  if(arr(N.exec_bullets).length) return arr(N.exec_bullets).slice(0,3);
  var P=D.projects,k=kpis(),c=function(s){return P.filter(function(p){return stat(p)===s}).length};
  var mv=movers(); var b=[];
  b.push(P.length+' '+UL()+' tracked: '+c('active')+' active, '+c('cooling')+' cooling, '+c('dormant')+' dormant, '+c('archived')+' archived.');
  b.push(fmt(k.features)+' features, '+fmt(k.bugfixes)+' bugfixes and '+fmt(k.decisions)+' decisions recorded'+(k.mom!=null?'; '+(FOC()?'momentum':'portfolio momentum')+' '+pctStr(k.mom)+' in '+(FOC()?'memory-observation volume in these workstreams,':'memory-observation volume,')+' last 4 complete weeks vs the 4 before.':'.'));
  b.push((mv.up[0]?'Biggest climber: '+mv.up[0].p.name+'. ':'')+(mv.down[0]?'Biggest slide: '+mv.down[0].p.name+'. ':'')+Math.round((1-D.meta.coverage)*100)+'% of raw activity could not be tied to a project.');
  return b;
}
function pctStr(n){if(n==null)return 'n/a';if(n>500)return '+500%+';return (n>0?'+':(n<0?'\u2212':''))+Math.abs(n)+'%'}
/* per-project %, each vs its OWN baseline (units differ per project, so never compare raw numbers); null when prior4 < min baseline */
function movers(){
  var m=D.projects.filter(function(p){return p.momentum!=null&&stat(p)!=='archived'}).map(function(p){return {p:p,d:p.momentum}});
  return {up:m.filter(function(x){return x.d>0}).sort(function(a,b){return b.d-a.d}).slice(0,3),down:m.filter(function(x){return x.d<0}).sort(function(a,b){return a.d-b.d}).slice(0,3)};
}
var NM=BOOT.narrative_mtime||null;
function pad2(n){return (n<10?'0':'')+n}
function narrNote(){
  if(!NM||!N||!Object.keys(N).length)return '';
  var d=new Date(NM), lab=d.getFullYear()+'-'+pad2(d.getMonth()+1)+'-'+pad2(d.getDate())+' '+pad2(d.getHours())+':'+pad2(d.getMinutes());
  var stale=Date.parse(D.meta.generated_at)-NM>7*DAY;
  return '<span class="narr'+(stale?' stale':'')+'"'+(stale?' title="Narrative is more than 7 days older than the data"':'')+'>Narrative written '+lab+(stale?' (stale)':'')+'</span>';
}
function closing(){
  var c=N.closing||{}, P=D.projects;
  var dec=arr(c.decisions); if(!dec.length){
    P.forEach(function(p){risks(p).slice(0,1).forEach(function(r){if(dec.length<5&&stat(p)!=='archived'&&/quiet|held|Bugfix|Momentum/.test(r)) dec.push(p.name+': '+r+' \u2014 keep, revive or archive?')})});
    if(!dec.length) dec.push('No blocking decisions surfaced from the data.');
  }
  var nx=arr(c.next); if(!nx.length){ P.filter(function(p){return stat(p)==='active'}).slice(0,5).forEach(function(p){var n=nextList(p)[0]; if(n) nx.push(p.name+': '+cut(n,160))}); if(!nx.length) nx.push('No next steps recorded.'); }
  return {decisions:dec,next:nx};
}

/* ---------- gantt ---------- */
function lanesFor(max){
  var P=D.projects, WK=weekList(), L=P.slice(0,max).map(function(p){return {name:p.name,status:stat(p),wk:p.weeks,spans:p.spans,miles:p.milestones,detail:fmt(p.totals.obs)+' obs, '+fmt(p.totals.commits)+' commits'}});
  if(P.length>max){
    var rest=P.slice(max), wk={}, tot=0;
    rest.forEach(function(p){Object.keys(p.weeks).forEach(function(k){var w=p.weeks[k];var o=wk[k]||(wk[k]={act:0,mem:0,commits:0,by_type:{}});o.act+=w.act;o.mem+=w.mem;o.commits+=w.commits})});
    var idx=[];WK.forEach(function(w,i){if(wk[w.key]&&wk[w.key].act>0)idx.push(i)});
    var spans=[];if(idx.length){var s=idx[0],e=idx[0];idx.slice(1).forEach(function(i){if(i-e-1<=2)e=i;else{spans.push({start:iso(WK[s].ms),end:iso(WK[e].ms+6*DAY)});s=e=i}});spans.push({start:iso(WK[s].ms),end:iso(WK[e].ms+6*DAY)})}
    L.push({name:'Other ('+rest.length+')',status:null,wk:wk,spans:spans,miles:[],detail:rest.map(function(p){return p.name}).join(', ')});
  }
  return L;
}
function gantt(lanes,o){
  var WK=weekList(), n=WK.length, cw=o.cw, W=n*cw, lh=o.laneH||38, lw=o.noLabel?0:(o.labelW||150);
  var x0=WK[0].ms, end=WK[n-1].ms+7*DAY, X=function(ms){return (ms-x0)/(7*DAY)*cw};
  var months=[];var t=new Date(x0);var cur=Date.UTC(t.getUTCFullYear(),t.getUTCMonth()+1,1);
  while(cur<end){var dd=new Date(cur);months.push({x:X(cur),l:MON[dd.getUTCMonth()]+(dd.getUTCMonth()===0?' '+dd.getUTCFullYear():'')});cur=Date.UTC(dd.getUTCFullYear(),dd.getUTCMonth()+1,1)}
  var todayX=X(pd(D.meta.window_end)+DAY);
  var grid=months.map(function(m){return '<line x1="'+m.x+'" x2="'+m.x+'" y1="0" y2="'+lh+'" stroke="var(--grid)" stroke-width="1"/>'}).join('');
  var cellTop=lh>=36?16:14, cellH=lh-cellTop-6, spanTop=cellTop-3, spanH=cellH+6;
  var h='<div class="gantt">';
  h+='<div class="g-row"><div class="g-label" style="width:'+lw+'px;'+(lw?'':'display:none')+'"></div><svg class="g-axis" width="'+W+'" height="24" role="img" aria-label="Month axis">'
    +months.map(function(m){return '<line x1="'+m.x+'" x2="'+m.x+'" y1="14" y2="24" stroke="var(--grid)"/><text x="'+(m.x+4)+'" y="12">'+esc(m.l)+'</text>'}).join('')
    +'<text x="'+Math.min(todayX,W-4)+'" y="12" text-anchor="end" style="fill:var(--ink)">today</text></svg></div>';
  lanes.forEach(function(L){
    var max=0;WK.forEach(function(w){var v=L.wk[w.key];if(v&&v.act>max)max=v.act});
    var s='<svg width="'+W+'" height="'+lh+'" role="img" aria-label="'+esc(L.name)+' weekly activity">'+grid;
    (L.spans||[]).forEach(function(sp){var a=X(pd(sp.start)),b=X(pd(sp.end)+DAY);s+='<rect x="'+(a+0.5)+'" y="'+spanTop+'" width="'+Math.max(4,b-a-1)+'" height="'+spanH+'" rx="'+(spanH/2)+'" fill="none" stroke="var(--ink2)" stroke-opacity=".55" stroke-width="1"/>'});
    WK.forEach(function(w,i){var v=L.wk[w.key];if(!v||!v.act)return;var lvl=Math.min(6,Math.max(1,Math.ceil(6*v.act/max)));
      var tip=L.name+' \u00B7 week of '+iso(w.ms)+'\n'+v.act+' activity ('+(v.mem||0)+' obs, '+(v.commits||0)+' commits)';
      var bt=v.by_type||{};var bs=Object.keys(bt).map(function(k){return bt[k]+' '+k}).join(', ');if(bs)tip+='\n'+bs;
      s+='<rect data-tip="'+esc(tip)+'" x="'+(i*cw+1)+'" y="'+cellTop+'" width="'+Math.max(2,cw-2)+'" height="'+cellH+'" rx="3" fill="var(--h'+lvl+')"/>'});
    var D5=5,cy=7;
    (L.miles||[]).filter(function(m){return m.kind!=='ship'}).forEach(function(m){var x=X(pd(m.date)+DAY/2);if(x<0||x>W)return;
      s+='<path data-tip="'+esc(m.date+' \u00B7 '+m.kind+'\n'+m.title)+'" d="M'+x+' '+(cy-D5)+' L'+(x+D5)+' '+cy+' L'+x+' '+(cy+D5)+' L'+(x-D5)+' '+cy+' Z" fill="var(--surface)" stroke="var(--ink)" stroke-width="1.5"/>'});
    (L.miles||[]).filter(function(m){return m.kind==='ship'}).forEach(function(m){var x=X(pd(m.date)+DAY/2);if(x<0||x>W)return;
      s+='<path data-tip="'+esc(m.date+' \u00B7 ship\n'+m.title)+'" d="M'+x+' '+(cy-D5)+' L'+(x+D5)+' '+cy+' L'+x+' '+(cy+D5)+' L'+(x-D5)+' '+cy+' Z" fill="var(--ink)"/>'});
    s+='<line x1="'+todayX+'" x2="'+todayX+'" y1="0" y2="'+lh+'" stroke="var(--ink)" stroke-opacity=".6" stroke-dasharray="3 3"/></svg>';
    var st=L.status?'<span class="g-st"><i style="color:var('+ST[L.status].c+')">'+ST[L.status].i+'</i>'+ST[L.status].l+'</span>':'<span class="g-st">rolled up</span>';
    h+='<div class="g-row" style="height:'+lh+'px">'+(lw?'<div class="g-label" style="width:'+lw+'px" data-tip="'+esc(L.name+'\n'+(L.detail||''))+'"><span class="g-name">'+esc(L.name)+'</span>'+(o.compact?'':st)+'</div>':'')+s+'</div>';
  });
  return h+'</div>';
}
function ganttLegend(){
  return '<div class="legend"><span>Weekly activity <span class="ramp">'+[1,2,3,4,5,6].map(function(i){return '<b style="background:var(--h'+i+')"></b>'}).join('')+'</span>low \u2192 high (per lane)</span>'
   +'<span><svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:-2px"><path d="M6 1L11 6L6 11L1 6Z" fill="var(--surface)" stroke="var(--ink)" stroke-width="1.5"/></svg> milestone</span>'
   +'<span><svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:-2px"><path d="M6 1L11 6L6 11L1 6Z" fill="var(--ink)"/></svg> ship</span>'
   +'<span><svg width="22" height="12" style="vertical-align:-2px"><rect x="1" y="1" width="20" height="10" rx="5" fill="none" stroke="var(--ink2)" stroke-opacity=".55"/></svg> active span</span><span>dashed line = today</span></div>';
}
function ganttTable(){
  var h='<div class="tblwrap"><table class="tbl"><thead><tr><th>Project</th><th>Status</th><th>First seen</th><th>Last seen</th><th>Active spans</th><th class="n">Obs</th><th class="n">Commits</th><th class="n">Features</th><th class="n">Bugfixes</th><th class="n">Ships</th><th class="n">Momentum</th></tr></thead><tbody>';
  D.projects.forEach(function(p){var t=p.totals;h+='<tr><td>'+esc(p.name)+'</td><td>'+pill(stat(p))+'</td><td>'+p.first_seen+'</td><td>'+p.last_seen+'</td><td>'+p.spans.map(function(s){return s.start+' \u2192 '+s.end}).join('; ')+'</td><td class="n">'+fmt(t.obs)+'</td><td class="n">'+fmt(t.commits)+'</td><td class="n">'+fmt(t.features)+'</td><td class="n">'+fmt(t.bugfixes)+'</td><td class="n">'+t.ships+'</td><td class="n">'+pctStr(p.momentum)+'</td></tr>'});
  return h+'</tbody></table></div>';
}
function colChart(w,h){
  var WK=weekList(),wt=(FOC()&&D.portfolio.scoped&&D.portfolio.scoped.weekly_mem_total)||D.portfolio.weekly_mem_total||D.portfolio.weekly_totals||{},cur=D.meta.current_week,v=WK.map(function(x){return wt[x.key]||0}),mx=Math.max.apply(null,v.concat([1]));
  var padL=44,padB=26,padT=14,cw=(w-padL)/WK.length,ch=h-padB-padT;
  var step=Math.pow(10,Math.floor(Math.log10(mx)));var top=Math.ceil(mx/step)*step;if(top/step>5)step*=2;
  var s='<svg width="'+w+'" height="'+h+'" role="img" aria-label="Weekly portfolio activity">';
  for(var g=0;g<=top;g+=step){var y=padT+ch-g/top*ch;s+='<line x1="'+padL+'" x2="'+w+'" y1="'+y+'" y2="'+y+'" stroke="var(--grid)"/><text x="'+(padL-6)+'" y="'+(y+4)+'" text-anchor="end" style="fill:var(--muted);font-size:11px">'+fmt(g)+'</text>'}
  var mi=v.indexOf(mx);
  s+='<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--surface)"/><rect width="3" height="6" fill="var(--s-exec)" fill-opacity=".55"/></pattern></defs>';
  WK.forEach(function(x,i){var bh=v[i]/top*ch;var bx=padL+i*cw+2;var part=x.key===cur;
    s+='<rect data-tip="'+esc('Week of '+iso(x.ms)+(part?' (in progress, excluded from momentum)':'')+'\n'+fmt(v[i])+' memory observations')+'" x="'+bx+'" y="'+(padT+ch-bh)+'" width="'+Math.max(2,cw-4)+'" height="'+Math.max(0,bh)+'" rx="2" fill="'+(part?'url(#hatch)':'var(--s-exec)')+'"'+(part?' stroke="var(--s-exec)" stroke-dasharray="3 2"':'')+'/>';
    if(part)s+='<text x="'+(bx+Math.max(2,cw-4))+'" y="'+(padT+ch-bh-5)+'" text-anchor="end" style="fill:var(--ink2);font-size:11px">in progress</text>';
    if(i%4===0)s+='<text x="'+(bx)+'" y="'+(h-8)+'" style="fill:var(--muted);font-size:11px">'+iso(x.ms).slice(5)+'</text>'});
  s+='<text x="'+(padL+mi*cw+cw/2)+'" y="'+(padT+ch-v[mi]/top*ch-4)+'" text-anchor="middle" style="fill:var(--ink);font-size:12px;font-weight:600">'+fmt(mx)+'</text>';
  return s+'</svg>';
}
function kpiTiles(){
  var k=kpis(),t=function(v,l,d){return '<div class="kpi"><div class="v">'+v+'</div><div class="l">'+l+'</div>'+(d?'<div class="d">'+d+'</div>':'')+'</div>'};
  var mom=k.mom==null?'n/a':(k.mom>0?'\u25B2 ':(k.mom<0?'\u25BC ':'\u25AC '))+pctStr(k.mom);
  return '<div class="kpis">'+t(k.active+'<span style="font-size:16px;color:var(--muted)"> / '+k.total+'</span>','Active '+UL(),'touched in last 7 days')+t(fmt(k.ships),'Ships logged',(FOC()?'shiplog rows in these workstreams: ':'all shiplog rows in window: ')+fmt(k.shipped)+' shipped, '+fmt(k.held)+' held/failed')+t(fmt(k.features),'Features')+t(fmt(k.bugfixes),'Bugfixes')+t(fmt(k.decisions),'Decisions')+t(mom,'Momentum',(FOC()?'mem observations in these lanes':'mem observations')+', last 4 complete wks vs prior 4')+'</div>';
}

/* ---------- dashboard ---------- */
function renderDash(){
  var m=D.meta, cov=Math.round(m.coverage*100), h='';
  h+='<div class="top"><div><h1>'+esc(TTL())+'</h1><div class="sub">'+esc(windowLabel())+' \u00B7 derived from what agents actually did'+(narrNote()?' \u00B7 '+narrNote():'')+'</div></div><div class="tools"><span class="stamp" id="stamp"><span class="dot"></span><span></span></span>'
   +(SERVED?'<button id="btnRefresh">Refresh now</button>':'')
   +'<button id="btnDeck">Deck view</button><button id="btnTheme" title="Toggle theme">Theme</button></div></div>';
  h+='<p class="note"><b>'+(100-cov)+'% of activity is unattributed</b> ('+cov+'% tied to a project: '+fmt(m.sources.mem_obs)+' memory observations, '+fmt(m.sources.git_commits)+' commits, '+fmt(m.sources.ship_entries)+' ship entries).'
   +(m.suspect_backfill_rows?' '+fmt(m.suspect_backfill_rows)+' rows excluded as suspected backfill.':'')
   +((m.redactions&&m.redactions.total)?' '+m.redactions.total+' text items withheld by the privacy filter.':'')+'</p>';
  h+=kpiTiles();
  h+='<section><div class="g-head"><div><h2>'+esc(topHeadline())+'</h2></div><div class="tools"><button id="gChart" aria-pressed="'+!gTable+'">Chart</button><button id="gTbl" aria-pressed="'+gTable+'">Table</button></div></div>';
  h+='<p class="lede">Portfolio Gantt. Each lane is a project; cells are weeks, shaded by activity relative to that project\u2019s busiest week.</p>';
  if(gTable) h+=ganttTable(); else { h+='<div style="margin-bottom:8px">'+ganttLegend()+'</div>';
    var avail=Math.max(300,(Math.min(1200,window.innerWidth)-32)-150), n=weekList().length, cw=Math.max(14,Math.min(34,Math.floor(avail/n)));
    h+='<div class="g-scroll">'+gantt(lanesFor(14),{cw:cw,laneH:38})+'</div>'; }
  h+='</section>';
  h+='<section><h2>Now / Next / Risks</h2><p class="lede">Now comes from the latest session summaries, Next from recorded next steps, Risks from the data (quiet projects, held ships, bugfix load, exploration load).</p><div class="cards">';
  D.projects.slice().sort(function(a,b){return vol(b)-vol(a)}).slice(0,6).forEach(function(p){
    var nx=nextList(p).slice(0,3), rk=risks(p).slice(0,3);
    h+='<div class="card pc"><h3><span>'+esc(p.name)+'</span>'+pill(stat(p))+'</h3><p class="hl">'+esc(pHeadline(p))+'</p>'
     +'<h4>Now</h4><p>'+esc(cut(nowText(p),220))+'</p><h4>Next</h4>'+(nx.length?'<ul>'+nx.map(function(x){return '<li>'+esc(cut(x,200))+'</li>'}).join('')+'</ul>':'<p>No next steps recorded.</p>')
     +'<h4>Risks</h4>'+(rk.length?'<ul>'+rk.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ul>':'<p>None flagged.</p>')+'</div>';
  });
  h+='</div></section>';
  h+='<section><h2>How the work got done</h2><p class="lede">The AI-era view: how much was exploring versus building, and who did the shipping.</p><div class="two">';
  h+='<div class="card"><h3 style="font-size:15px;margin-bottom:8px">Explore vs execute</h3>';
  D.projects.slice().sort(function(a,b){return vol(b)-vol(a)}).slice(0,10).forEach(function(p){
    var t=p.totals,ex=t.discoveries,bd=t.features+t.bugfixes+t.changes+t.refactors,tt=ex+bd||1,pe=Math.round(ex*100/tt);
    h+='<div class="eb"><span class="nm">'+esc(p.name)+'</span><div class="bar2" role="img" aria-label="'+pe+'% explore, '+(100-pe)+'% build"><span style="width:'+(ex*100/tt)+'%;background:var(--s-explore)"></span><span style="width:'+(bd*100/tt)+'%;background:var(--s-exec)"></span></div><span class="pc2">'+pe+'% explore \u00B7 '+(100-pe)+'% build</span></div>'});
  h+='<div class="legend" style="margin-top:8px"><span><i class="sw" style="background:var(--s-explore)"></i>Explore (discoveries)</span><span><i class="sw" style="background:var(--s-exec)"></i>Execute (features, fixes, changes, refactors)</span></div></div>';
  var ag=(FOC()&&D.portfolio.scoped&&D.portfolio.scoped.agents)||D.portfolio.agents||{},ak=Object.keys(ag).sort(function(a,b){return ag[b]-ag[a]}),at=sum(ak,function(k){return ag[k]})||1;
  h+='<div class="card"><h3 style="font-size:15px;margin-bottom:8px">Agent mix (shiplog)</h3>'+(ak.length?ak.map(function(k){return '<div class="eb"><span class="nm">'+esc(k)+'</span><div class="bar2"><span style="width:'+(ag[k]*100/at)+'%;background:var(--s-exec)"></span></div><span class="pc2">'+ag[k]+' ships \u00B7 '+Math.round(ag[k]*100/at)+'%</span></div>'}).join(''):'<p class="note">No shiplog entries.</p>')
   +'<p class="note">'+(FOC()?'The '+at+' shiplog rows in these workstreams (same total as the Ships logged tile).':'All '+at+' shiplog rows in the window (same total as the Ships logged tile, attributed to a project or not).')+' Memory observations carry no agent tag.</p></div></div>';
  var dl=(D.portfolio.decisions||[]).slice(0,10);
  h+='<div class="card" style="margin-top:12px"><h3 style="font-size:15px;margin-bottom:6px">Decisions log</h3>'+(dl.length?'<ul class="dec">'+dl.map(function(d){return '<li><span class="dt">'+esc(d.date)+'</span><span class="pj">'+esc(d.project)+'</span><span>'+esc(d.title)+'</span></li>'}).join('')+'</ul>':'<p class="note">No decisions recorded.</p>')+'</div></section>';
  h+='<p class="foot">Generated '+esc(m.generated_at)+' \u00B7 sources: claude-mem, shiplog, git \u00B7 text is privacy-filtered at collection time.</p>';
  $('#dash').innerHTML='<div class="wrap">'+h+'</div>';
  bindDash(); updateStamp();
}
function bindDash(){
  var g=function(id,f){var e=$(id);if(e)e.addEventListener('click',f)};
  g('#gChart',function(){gTable=false;renderDash()});g('#gTbl',function(){gTable=true;renderDash()});
  g('#btnDeck',function(){setView('deck')});g('#btnTheme',cycleTheme);
  g('#btnRefresh',function(){fetch('/refresh',{cache:'no-store',headers:{'X-Roadmap':'1'}}).then(function(){return poll()}).catch(function(){})});
}

/* ---------- deck ---------- */
function slideWrap(inner,cls){return {cls:cls||'',html:inner}}
function buildSlides(){
  var S=[],k=kpis(),top=D.projects.slice().sort(function(a,b){return vol(b)-vol(a)}),P=D.projects,c=function(s){return P.filter(function(p){return stat(p)===s}).length};
  S.push(slideWrap('<div class="kick">'+esc(TTL())+'</div><h2>'+esc(N.title||topHeadline())+'</h2><p style="font-size:22px;color:var(--ink2);margin:0">'+esc(windowLabel())+' \u00B7 '+P.length+' '+UL()+' \u00B7 '+fmt(D.meta.sources.mem_obs)+' observations, '+fmt(D.meta.sources.git_commits)+' commits</p>','title'));
  S.push(slideWrap('<div class="kick">Executive summary</div><h2>'+esc(c('active')+' of '+P.length+' '+UL()+' are moving; '+(k.mom==null?'momentum is flat':'memory activity is '+(k.mom>=0?'up ':'down ')+pctStr(Math.abs(k.mom))))+'</h2><div class="body"><ul class="big">'+execBullets().map(function(b){return '<li>'+esc(b)+'</li>'}).join('')+'</ul>'+kpiTiles()+'</div>'));
  S.push(slideWrap('<div class="kick">'+esc(TTL())+'</div><h2>'+esc(laneTitle(P,c))+'</h2><div class="body"><div class="g-scroll" style="overflow:hidden">'+gantt(lanesFor(14),{cw:Math.floor((1152-150)/weekList().length),laneH:30,compact:true})+'</div><div style="margin-top:10px">'+ganttLegend()+'</div></div>'));
  var mv=movers(),li=function(a,ic){return a.length?a.map(function(x){return '<div class="mv"><i>'+ic+'</i><span class="nm">'+esc(x.p.name)+'</span><span style="color:var(--ink2)">'+pctStr(x.d)+' <span style="color:var(--muted);font-size:13px">('+x.p.prior4+' \u2192 '+x.p.recent4+' '+esc(x.p.momentum_unit||'')+')</span></span></div>'}).join(''):'<p style="color:var(--muted)">None</p>'};
  S.push(slideWrap('<div class="kick">Momentum \u00B7 '+(FOC()?'unit: mem observations in these lanes':'portfolio unit: memory observations')+'</div><h2>'+esc(k.mom==null?'Weekly activity across '+(FOC()?'these '+UL():'the portfolio'):'Memory activity is '+(k.mom>=0?'up ':'down ')+pctStr(Math.abs(k.mom))+' on the prior four weeks')+'</h2><div class="body"><div style="display:flex;gap:32px"><div style="flex:none">'+colChart(720,360)+'</div><div style="flex:1"><div class="kick">Climbing</div>'+li(mv.up,'\u25B2')+'<div class="kick" style="margin-top:20px">Sliding</div>'+li(mv.down,'\u25BC')+'<p style="font-size:12px;color:var(--muted);margin-top:18px;max-width:380px">Each project is measured against its own baseline (commits where it has a repo, otherwise memory observations): last 4 complete weeks vs the 4 before, minimum baseline '+((D.portfolio.momentum||{}).min_baseline||20)+' units, display capped at +500%. Chart: '+(FOC()?'memory observations in these lanes':'all memory observations')+' per week, hatched = current week in progress (excluded).</p></div></div></div>'));
  top.slice(0,8).forEach(function(p){
    var rk=risks(p).slice(0,3),nx=nextList(p).slice(0,3);
    var ms=p.milestones.slice().sort(function(a,b){return a.date<b.date?1:-1}).slice(0,5);
    S.push(slideWrap('<div class="kick">'+esc(p.name)+' \u00B7 '+pill(stat(p))+'</div><h2 style="font-size:36px">'+esc(pHeadline(p))+'</h2><div class="body"><div class="g-scroll" style="overflow:hidden">'+gantt([{name:p.name,status:stat(p),wk:p.weeks,spans:p.spans,miles:p.milestones}],{cw:Math.floor(1152/weekList().length),laneH:46,noLabel:true})+'</div>'
     +'<ul class="tl">'+ms.map(function(m){return '<li><span class="dt">'+esc(m.date)+'</span><span class="k">'+(m.kind==='ship'?'\u25C6':'\u25C7')+'</span><span>'+esc(cut(m.title,110))+'</span></li>'}).join('')+'</ul>'
     +'<div class="cols3"><div><h4>Now</h4><p>'+esc(cut(nowText(p),230))+'</p></div><div><h4>Next</h4>'+(nx.length?'<ul>'+nx.map(function(x){return '<li>'+esc(cut(x,120))+'</li>'}).join('')+'</ul>':'<p>None recorded</p>')+'</div><div><h4>Risks</h4>'+(rk.length?'<ul>'+rk.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ul>':'<p>None flagged</p>')+'</div></div></div>'));
  });
  var cl=closing();
  S.push(slideWrap('<div class="kick">Wrap-up</div><h2>'+esc(N.closing_title||'Decisions needed, and what happens next')+'</h2><div class="body"><div class="cols3" style="grid-template-columns:1fr 1fr;margin-top:0"><div><h4>Decisions needed</h4><ul>'+cl.decisions.map(function(x){return '<li>'+esc(cut(x,170))+'</li>'}).join('')+'</ul></div><div><h4>Next up</h4><ul>'+cl.next.map(function(x){return '<li>'+esc(cut(x,170))+'</li>'}).join('')+'</ul></div></div></div>'));
  return S;
}
function renderDeck(){
  var S=buildSlides();deckCount=S.length;if(slideIdx>=deckCount)slideIdx=deckCount-1;
  $('#deck').innerHTML='<div class="viewport" id="vp"><div class="scaler" id="scaler">'+S.map(function(s,i){return '<div class="slide '+s.cls+'" data-i="'+i+'">'+s.html+'<div class="sfoot"><span>'+esc(TTL())+' \u00B7 '+esc(windowLabel())+(narrNote()?' \u00B7 '+narrNote():'')+'</span><span>'+(i+1)+' / '+S.length+'</span></div></div>'}).join('')+'</div></div>'
   +'<div class="deckbar"><button id="dPrev">\u2190 Prev</button><button id="dNext">Next \u2192</button><span id="dCnt"></span><span class="sp"></span><button id="dPrint">Print / PDF</button><button id="dDash">Dashboard</button></div>';
  $('#dPrev').onclick=function(){go(-1)};$('#dNext').onclick=function(){go(1)};$('#dPrint').onclick=function(){window.print()};$('#dDash').onclick=function(){setView('dash')};
  $('#vp').addEventListener('click',function(e){if(e.target.closest('button'))return;var r=this.getBoundingClientRect();go(e.clientX-r.left<r.width*0.33?-1:1)});
  fit();showSlide();
}
function fit(){var vp=$('#vp'),sc=$('#scaler');if(!vp||!sc)return;var s=Math.min(vp.clientWidth/1280,vp.clientHeight/720);var ox=(vp.clientWidth-1280*s)/2,oy=(vp.clientHeight-720*s)/2;sc.style.transform='translate('+ox+'px,'+oy+'px) scale('+s+')'}
function showSlide(){document.querySelectorAll('.slide').forEach(function(e){e.classList.toggle('on',+e.dataset.i===slideIdx)});var c=$('#dCnt');if(c)c.textContent='Slide '+(slideIdx+1)+' of '+deckCount}
function go(d){slideIdx=Math.max(0,Math.min(deckCount-1,slideIdx+d));showSlide()}

/* ---------- shell ---------- */
function FOC(){return !!(D.meta&&D.meta.focus)}
function UL(){return (D.meta&&D.meta.unit_label)||'projects'}
function TTL(){return (D.meta&&D.meta.title)||'Roadmap'}
function setView(v){view=v;document.body.classList.toggle('deckmode',v==='deck');if(v==='deck'){renderDeck()}else renderDash();try{location.hash=v==='deck'?'#deck':''}catch(e){}}
function cycleTheme(){var r=document.documentElement,cur=r.getAttribute('data-theme');var nx=cur==='dark'?'light':(cur==='light'?null:'dark');if(nx)r.setAttribute('data-theme',nx);else r.removeAttribute('data-theme');try{localStorage.setItem('roadmap-theme',nx||'')}catch(e){}}
function updateStamp(){
  var e=$('#stamp');if(!e)return;var gen=Date.parse(D.meta.generated_at);var ok=SERVED&&liveOk&&(Date.now()-lastOk<180000);
  e.firstChild.className='dot'+(ok?' live':'');e.lastChild.textContent=(SERVED?(ok?'Live':'Offline'):'Snapshot')+' \u00B7 updated '+agoStr(gen);
}
function renderAll(){if(view==='deck')renderDeck();else renderDash();if(view==='deck')renderDashHidden()}
function renderDashHidden(){}
function poll(){
  return fetch('/roadmap.json?'+Date.now(),{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){
    liveOk=true;lastOk=Date.now();
    if(j.meta&&j.meta.generated_at!==D.meta.generated_at){D=j;return fetch('/narrative.json?'+Date.now(),{cache:'no-store'}).then(function(r){if(!r.ok)return null;var lm=Date.parse(r.headers.get('Last-Modified')||'');if(lm)NM=lm;return r.json()}).catch(function(){return null}).then(function(n){if(n)N=n;renderAll()})}
    updateStamp();
  }).catch(function(){liveOk=false;updateStamp()});
}
document.addEventListener('keydown',function(e){if(view!=='deck')return;
  if(['ArrowRight','PageDown',' ','Enter'].indexOf(e.key)>=0){e.preventDefault();go(1)}
  else if(['ArrowLeft','PageUp','Backspace'].indexOf(e.key)>=0){e.preventDefault();go(-1)}
  else if(e.key==='Home'){slideIdx=0;showSlide()}else if(e.key==='End'){slideIdx=deckCount-1;showSlide()}
  else if(e.key==='Escape'){setView('dash')}
  else if(e.key==='f'){var d=document.documentElement;if(document.fullscreenElement)document.exitFullscreen();else if(d.requestFullscreen)d.requestFullscreen()}
});
var tx=null;document.addEventListener('touchstart',function(e){tx=e.touches[0].clientX},{passive:true});
document.addEventListener('touchend',function(e){if(view!=='deck'||tx==null)return;var dx=e.changedTouches[0].clientX-tx;tx=null;if(Math.abs(dx)>50)go(dx<0?1:-1)},{passive:true});
var tip=$('#tip');
function showTip(t,x,y){tip.textContent=t;tip.classList.add('on');var w=tip.offsetWidth,h=tip.offsetHeight;var nx=Math.min(window.innerWidth-w-8,x+12),ny=y+16+h>window.innerHeight?y-h-10:y+16;tip.style.left=Math.max(4,nx)+'px';tip.style.top=Math.max(4,ny)+'px'}
document.addEventListener('mouseover',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');if(t)showTip(t.getAttribute('data-tip'),e.clientX,e.clientY);else tip.classList.remove('on')});
document.addEventListener('mousemove',function(e){if(tip.classList.contains('on')){var t=e.target.closest&&e.target.closest('[data-tip]');if(t)showTip(t.getAttribute('data-tip'),e.clientX,e.clientY)}});
document.addEventListener('click',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');if(t&&'ontouchstart' in window)showTip(t.getAttribute('data-tip'),e.clientX,e.clientY)});
var rt;window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(function(){if(view==='deck')fit();else renderDash()},150)});
try{var th=localStorage.getItem('roadmap-theme');if(th)document.documentElement.setAttribute('data-theme',th)}catch(e){}
var hm=/^#deck(?:-(\d+))?$/.exec(location.hash||'');if(hm&&hm[1])slideIdx=Math.max(0,+hm[1]-1);setView(hm?'deck':'dash');
window.addEventListener('hashchange',function(){var m=/^#deck(?:-(\d+))?$/.exec(location.hash||'');if(m){if(m[1])slideIdx=Math.max(0,+m[1]-1);if(view!=='deck')setView('deck');else showSlide()}else if(view==='deck')setView('dash')});
setInterval(updateStamp,30000);
if(SERVED)setInterval(poll,60000);
})();
"""

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap">
<style>__CSS__</style>
</head>
<body>
<div id="dash"></div>
<div id="deck"></div>
<div id="tip" role="tooltip"></div>
<noscript>This page needs JavaScript to draw the roadmap.</noscript>
<script>__JS__</script>
</body>
</html>
"""


def scrub(x):
    """Redact narrative text with the same rules as collect.py."""
    if isinstance(x, str):
        return collect.clean(x, "narrative") or ""
    if isinstance(x, list):
        return [y for y in (scrub(i) for i in x) if y not in ("", None, [], {})]
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items()}
    return x


def render(out, redact=True):
    out = os.path.abspath(os.path.expanduser(out))
    with open(os.path.join(out, "roadmap.json")) as f:
        roadmap = json.load(f)
    narrative = {}
    npath = os.path.join(out, "narrative.json")
    if os.path.exists(npath):
        try:
            with open(npath) as f:
                narrative = json.load(f)
            if not isinstance(narrative, dict):
                narrative = {}
        except Exception:
            narrative = {}
    collect.REDACT_ON = redact
    if redact:
        narrative = scrub(narrative)
    nmt = int(os.path.getmtime(npath) * 1000) if (narrative and os.path.exists(npath)) else None
    data = json.dumps({"roadmap": roadmap, "narrative": narrative, "narrative_mtime": nmt}, ensure_ascii=False)
    data = data.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    css = CSS.replace("__LIGHT__", LIGHT).replace("__DARK__", DARK)
    js = JS.replace("__DATA__", data)
    html = HTML.replace("__TITLE__", _html.escape((roadmap.get("meta") or {}).get("title") or "Roadmap")).replace("__CSS__", css).replace("__JS__", js)
    path = os.path.join(out, "index.html")
    collect.atomic_write(path, html)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-redact", action="store_true")
    a = ap.parse_args()
    print(render(a.out, not a.no_redact))


if __name__ == "__main__":
    main()
