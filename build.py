#!/usr/bin/env python3
"""Builds index.html from data/profiles.json for the Anand Maratha interested-profiles dashboard.

Profile data is AES-256-GCM encrypted with the passcode (PBKDF2-HMAC-SHA256, 250k iters).
The passcode is NOT shipped — only encrypted ciphertext + salt + IV.
"""
import json, os, datetime, base64, secrets
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "profiles.json")
OUT = os.path.join(HERE, "index.html")
PASSWORD = "134393"
PBKDF2_ITERS = 250000

with open(DATA, encoding="utf-8") as f:
    db = json.load(f)

updated = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
data_js = json.dumps(db, ensure_ascii=False)

salt = secrets.token_bytes(16)
iv = secrets.token_bytes(12)
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERS).derive(PASSWORD.encode("utf-8"))
ciphertext = AESGCM(key).encrypt(iv, data_js.encode("utf-8"), None)

enc_b64 = base64.b64encode(ciphertext).decode("ascii")
salt_b64 = base64.b64encode(salt).decode("ascii")
iv_b64 = base64.b64encode(iv).decode("ascii")

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Anand Maratha — Interested Profiles</title>
<style>
  :root{--brown:#a05a2c;--brown2:#66451c;--cream:#f6f2ed;--card:#fff;--ink:#33271c;--muted:#8a7a6c;--line:#e7dccf;--good:#2e7d32;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--cream);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;line-height:1.5;}
  header{background:linear-gradient(to right,var(--brown),var(--brown2));color:#fff;padding:22px 26px;}
  header h1{margin:0;font-size:22px;font-weight:600;letter-spacing:.2px;}
  header p{margin:4px 0 0;opacity:.9;font-size:13px;}
  .wrap{max-width:1180px;margin:0 auto;padding:20px 18px 60px;}
  .stats{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0;}
  .stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;min-width:120px;flex:1 1 120px;}
  .stat b{display:block;font-size:24px;color:var(--brown);}
  .stat span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;}
  .controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:20px;}
  .controls input,.controls select{padding:9px 12px;border:1px solid var(--line);border-radius:9px;font-size:14px;background:#fff;color:var(--ink);}
  .controls input{flex:1;min-width:180px;}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:18px;}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 4px 16px rgba(0,0,0,.05);}
  .photoWrap{position:relative;background:#efe7dd;aspect-ratio:4/5;overflow:hidden;}
  .photoWrap img{width:100%;height:100%;object-fit:cover;display:block;}
  .badge{position:absolute;top:10px;right:10px;background:rgba(160,90,44,.95);color:#fff;font-weight:600;font-size:13px;padding:5px 10px;border-radius:20px;}
  .contacted{position:absolute;top:10px;left:10px;background:rgba(46,125,50,.95);color:#fff;font-size:11px;font-weight:600;padding:4px 9px;border-radius:20px;letter-spacing:.3px;}
  .nav{position:absolute;bottom:8px;left:0;right:0;display:flex;justify-content:center;gap:6px;}
  .dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.6);border:1px solid rgba(0,0,0,.2);cursor:pointer;}
  .dot.on{background:#fff;}
  .arrow{position:absolute;top:50%;transform:translateY(-50%);background:rgba(0,0,0,.35);color:#fff;border:none;width:30px;height:30px;border-radius:50%;cursor:pointer;font-size:16px;}
  .arrow.l{left:8px;} .arrow.r{right:8px;}
  .body{padding:14px 16px 16px;}
  .nm{font-size:17px;font-weight:600;margin:0;}
  .rg{font-size:12px;color:var(--muted);margin:2px 0 10px;}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;}
  .chip{background:var(--cream);border:1px solid var(--line);border-radius:20px;padding:3px 9px;font-size:12px;}
  .gun{font-size:12px;color:var(--brown2);margin-bottom:10px;cursor:help;}
  details{border-top:1px solid var(--line);padding-top:8px;margin-top:4px;}
  details summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--brown);outline:none;list-style:none;padding:4px 0;}
  details summary::-webkit-details-marker{display:none;}
  details summary:before{content:"▸ ";}
  details[open] summary:before{content:"▾ ";}
  .sec{margin:8px 0;}
  .sec h4{margin:8px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);}
  table.kv{width:100%;border-collapse:collapse;font-size:13px;}
  table.kv td{padding:3px 4px;vertical-align:top;border-bottom:1px solid #f2ece3;}
  table.kv td.k{color:var(--muted);width:42%;}
  .contact{background:#f1f8f1;border:1px solid #cfe6cf;border-radius:10px;padding:10px 12px;margin-top:10px;font-size:13px;}
  .contact h4{margin:0 0 6px;color:var(--good);font-size:12px;text-transform:uppercase;letter-spacing:.5px;}
  .contact a{color:var(--brown2);}
  .nocontact{background:#fdf6ee;border:1px dashed var(--brown);border-radius:10px;padding:10px 12px;margin-top:10px;font-size:12px;color:var(--brown2);}
  .actions{display:flex;gap:8px;margin-top:12px;}
  .btn{flex:1;text-align:center;text-decoration:none;font-size:13px;font-weight:600;padding:9px 10px;border-radius:9px;border:1px solid var(--brown);color:var(--brown);background:#fff;}
  .btn.primary{background:var(--brown);color:#fff;}
  footer{max-width:1180px;margin:0 auto;padding:0 18px 40px;color:var(--muted);font-size:12px;}
  @media (max-width:600px){
    header{padding:16px 16px;}
    header h1{font-size:18px;}
    header p{font-size:12px;}
    .wrap{padding:14px 12px 50px;}
    .stats{gap:8px;margin:12px 0;}
    .stat{padding:10px 12px;min-width:0;flex:1 1 calc(50% - 8px);}
    .stat b{font-size:20px;}
    .controls{flex-direction:column;align-items:stretch;gap:8px;}
    .controls input,.controls select{width:100%;font-size:16px;}
    .grid{grid-template-columns:1fr;gap:14px;}
    .arrow{width:40px;height:40px;font-size:20px;}
    .dot{width:11px;height:11px;}
    details summary{padding:8px 0;font-size:14px;}
    .btn{padding:12px 10px;}
    table.kv td{padding:5px 4px;}
  }
  @media (hover:none){ .gun span{display:none;} }
  #gate{position:fixed;inset:0;background:linear-gradient(135deg,var(--brown),var(--brown2));display:flex;align-items:center;justify-content:center;z-index:1000;}
  #gate .box{background:#fff;padding:32px 28px;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.35);width:min(360px,90vw);text-align:center;}
  #gate h2{margin:0 0 6px;font-size:20px;color:var(--brown);}
  #gate p{margin:0 0 18px;font-size:13px;color:var(--muted);}
  #gate input{width:100%;padding:11px 14px;font-size:17px;border:1px solid var(--line);border-radius:9px;text-align:center;letter-spacing:4px;margin-bottom:12px;}
  #gate button{width:100%;padding:11px;font-size:15px;font-weight:600;background:var(--brown);color:#fff;border:none;border-radius:9px;cursor:pointer;}
  #gate .err{color:#c0392b;font-size:13px;margin-top:10px;min-height:18px;}
  #app{display:none;}
  .shake{animation:shake .35s;}
  @keyframes shake{0%,100%{transform:translateX(0);}25%{transform:translateX(-6px);}75%{transform:translateX(6px);}}
  /* Source chip (top-right of card) */
  .src{position:absolute;top:10px;right:10px;background:rgba(255,255,255,.92);color:var(--brown2);font-weight:600;font-size:10px;letter-spacing:.3px;padding:3px 8px;border-radius:20px;text-transform:uppercase;}
  .badge{top:38px;}  /* shift match% badge below source chip */
  /* View toggle */
  .viewtog{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:#fff;}
  .viewtog button{border:none;background:transparent;padding:8px 12px;font-size:13px;font-weight:600;color:var(--muted);cursor:pointer;}
  .viewtog button.on{background:var(--brown);color:#fff;}
  /* List view */
  .list{display:flex;flex-direction:column;gap:10px;}
  .row{display:grid;grid-template-columns:64px 1fr auto;gap:12px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 12px;align-items:center;box-shadow:0 2px 6px rgba(0,0,0,.04);}
  .row .ph{width:64px;height:80px;border-radius:8px;background:#efe7dd;overflow:hidden;}
  .row .ph img{width:100%;height:100%;object-fit:cover;}
  .row .mid .top{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
  .row .mid .nm{font-size:15px;font-weight:600;color:var(--ink);}
  .row .mid .meta{font-size:12px;color:var(--muted);margin-top:2px;}
  .row .mid .line2{font-size:13px;color:var(--ink);margin-top:4px;display:flex;gap:10px;flex-wrap:wrap;}
  .row .mid .line2 span{white-space:nowrap;}
  .row .mid .srctag{font-size:10px;font-weight:600;color:var(--brown2);background:var(--cream);border:1px solid var(--line);border-radius:10px;padding:1px 7px;letter-spacing:.3px;text-transform:uppercase;}
  /* Status hashtags shown on every card/row */
  .htag{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;letter-spacing:.2px;margin-right:4px;}
  .htag.date{background:#eef3f8;color:#3c5a78;border:1px solid #d6e1ec;}
  .htag.ok{background:#e7f5e8;color:var(--good);border:1px solid #cfe6cf;}
  .htag.bad{background:#fce9e9;color:#9c2727;border:1px solid #f0caca;}
  .htag.pending{background:#fdf6dc;color:#876d12;border:1px solid #ecd99a;}
  .htag.unknown{background:#fdf6ee;color:var(--brown2);border:1px solid #ecdec7;}
  .htag.dir{background:#ece6f5;color:#5c4480;border:1px solid #d4c8e6;}
  .reason{background:#fce9e9;border:1px solid #f0caca;border-radius:10px;padding:10px 12px;margin-top:10px;font-size:13px;color:#7a1f1f;}
  .reason b{color:#9c2727;}
  .statusbox{background:#e7f5e8;border:1px solid #cfe6cf;border-radius:10px;padding:10px 12px;margin-top:10px;font-size:13px;color:var(--good);}
  .pendingbox{background:#fdf6dc;border:1px solid #ecd99a;border-radius:10px;padding:10px 12px;margin-top:10px;font-size:13px;color:#876d12;}
  .tags{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0 8px;}
  .row .right{display:flex;flex-direction:column;align-items:flex-end;gap:6px;font-size:12px;}
  .row .right .m{font-size:14px;font-weight:700;color:var(--brown);}
  .row .right .c-ok{color:var(--good);font-weight:600;}
  .row .right .c-no{color:var(--muted);}
  .row .right a{font-size:12px;color:var(--brown);text-decoration:none;border:1px solid var(--brown);padding:4px 8px;border-radius:6px;}
  @media (max-width:600px){
    .row{grid-template-columns:48px 1fr;gap:8px;padding:8px 10px;}
    .row .ph{width:48px;height:60px;}
    .row .right{grid-column:1 / -1;flex-direction:row;justify-content:space-between;align-items:center;padding-top:6px;border-top:1px solid var(--line);}
  }
</style>
</head>
<body>
<div id="gate">
  <div class="box">
    <h2>Anand Maratha</h2>
    <p>Enter passcode to view interested profiles</p>
    <input id="pw" type="password" inputmode="numeric" autocomplete="off" autofocus maxlength="12"/>
    <button id="go">Unlock</button>
    <div class="err" id="err"></div>
  </div>
</div>
<div id="app">
<header>
  <h1>Anand Maratha — Profiles Who Expressed Interest</h1>
  <p>For __WHO__ · Updated __UPDATED__</p>
</header>
<div class="wrap">
  <div class="stats" id="stats"></div>
  <div class="controls">
    <input id="q" placeholder="Search name, education, city, occupation…"/>
    <select id="sort">
      <option value="match">Sort: Match % (high→low)</option>
      <option value="gun">Sort: Gun Milan (high→low)</option>
      <option value="new">Sort: Newest first</option>
    </select>
    <select id="filter">
      <option value="all">Show: All</option>
      <option value="contact">Show: Contact available</option>
      <option value="pending">Show: Awaiting interest</option>
    </select>
    <select id="source">
      <option value="all">Source: All</option>
    </select>
    <div class="viewtog" id="viewtog">
      <button data-v="card" class="on">▦ Cards</button>
      <button data-v="list">☰ List</button>
    </div>
  </div>
  <div id="grid"></div>
</div>
<footer>
  Photos load directly from anandmaratha.com — if a photo is blank, open the site and sign in, then refresh this page.
  Contact details appear automatically once you have expressed interest and the office has sent them.
</footer>
</div>
<script>
const ENC_B64 ="__ENC_B64__";
const SALT_B64="__SALT_B64__";
const IV_B64  ="__IV_B64__";
const PBKDF2_ITERS=__PBKDF2_ITERS__;
let DB=null, P=null;
function b64bytes(s){const bin=atob(s);const a=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);return a;}
async function deriveKey(pw,salt){
  const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt:salt,iterations:PBKDF2_ITERS,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['decrypt']);
}
async function tryUnlock(pw){
  try{
    const key=await deriveKey(pw,b64bytes(SALT_B64));
    const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64bytes(IV_B64)},key,b64bytes(ENC_B64));
    const jsonText=new TextDecoder().decode(plain);
    DB=JSON.parse(jsonText);P=DB.profiles;
    sessionStorage.setItem('am_data',jsonText);
    reveal();
    return true;
  }catch(e){return false;}
}
function reveal(){
  if(!DB){const cached=sessionStorage.getItem('am_data');if(cached){DB=JSON.parse(cached);P=DB.profiles;}else{return;}}
  document.getElementById('gate').style.display='none';document.getElementById('app').style.display='block';
  populateSources();setView(currentView());stats();bindControls();
}
function bindControls(){
  document.getElementById('q').addEventListener('input',render);
  document.getElementById('sort').addEventListener('change',render);
  document.getElementById('filter').addEventListener('change',render);
  document.getElementById('source').addEventListener('change',render);
  Array.prototype.forEach.call(document.querySelectorAll('#viewtog button'),function(b){b.addEventListener('click',function(){setView(b.getAttribute('data-v'));});});
}
document.getElementById('go').addEventListener('click',submitPw);
document.getElementById('pw').addEventListener('keydown',function(e){if(e.key==='Enter')submitPw();});
async function submitPw(){
  const pw=document.getElementById('pw').value;
  document.getElementById('err').textContent='Unlocking…';
  const ok=await tryUnlock(pw);
  if(!ok){
    const b=document.querySelector('#gate .box');b.classList.add('shake');setTimeout(function(){b.classList.remove('shake');},400);
    document.getElementById('err').textContent='Wrong passcode';document.getElementById('pw').value='';
  }
}
if(sessionStorage.getItem('am_data'))reveal();
function age(dob){var m=dob.match(/(\\d{2})\\/(\\d{2})\\/(\\d{4})/);if(!m)return null;var d=new Date(m[3],m[2]-1,m[1]);var t=new Date();var a=t.getFullYear()-d.getFullYear();if(t.getMonth()<d.getMonth()||(t.getMonth()==d.getMonth()&&t.getDate()<d.getDate()))a--;return a;}
function gv(arr,key){for(var i=0;i<arr.length;i++){if(arr[i][0]==key)return arr[i][1];}return "";}
function gunNum(g){var m=(g||"").match(/([\\d.]+)/);return m?parseFloat(m[1]):0;}
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function kvtable(arr){var r="<table class='kv'>";arr.forEach(function(p){if(p[1])r+="<tr><td class='k'>"+esc(p[0])+"</td><td>"+esc(p[1])+"</td></tr>";});return r+"</table>";}
function fmtDate(iso){if(!iso)return "";var d=new Date(iso+"T00:00:00");if(isNaN(d))return iso;return d.toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'});}
function statusTags(p){
  var dt=p.firstSeen?"<span class='htag date'>#received "+esc(fmtDate(p.firstSeen))+"</span>":"";
  var dir=p.direction?"<span class='htag dir'>#"+esc(p.direction)+"</span>":"";
  var st;
  if(p.status==='accepted')st="<span class='htag ok'>#accepted</span>";
  else if(p.status==='declined')st="<span class='htag bad'>#declined</span>";
  else if(p.status==='pending')st="<span class='htag pending'>#pending</span>";
  else st=p.contact?"<span class='htag ok'>#accepted</span>":"<span class='htag unknown'>#unknown</span>";
  return "<div class='tags'>"+dt+dir+st+"</div>";
}
function statusBox(p){
  if(p.contact)return null; // handled by contact rendering
  if(p.status==='declined'){
    return "<div class='reason'><b>Declined</b>"+(p.statusDate?" on "+esc(p.statusDate):"")+(p.declineReason?"<div>Reason: "+esc(p.declineReason)+"</div>":"")+"</div>";
  }
  if(p.status==='accepted'){
    return "<div class='statusbox'><b>✓ Accepted</b>"+(p.statusDate?" on "+esc(p.statusDate):"")+"<div>View full profile on source site for contact details.</div></div>";
  }
  if(p.status==='pending'){
    return "<div class='pendingbox'><b>⏳ Pending</b>"+(p.statusDate?" — "+esc(p.statusDate):"")+"</div>";
  }
  return null;
}

function card(p){
  var a=age(gv(p.details,"Date Of Birth"));
  var chips=[];
  if(a){chips.push(a+" yrs");}
  else { var ageStr=gv(p.details,"Age"); if(ageStr)chips.push(ageStr); }
  var h=gv(p.details,"Height"); if(h)chips.push(h);
  var ed=gv(p.details,"Education"); if(ed)chips.push(ed.length>22?ed.slice(0,22)+"…":ed);
  var oc=gv(p.details,"Occupation");
  var loc=gv(p.family,"Parents Residing In")||gv(p.details,"Location"); if(loc)chips.push("📍"+loc);
  var photoHtml="";
  var ph=p.photos&&p.photos.length?p.photos:["https://www.anandmaratha.com/no_imgf.jpg"];
  ph.forEach(function(u,i){photoHtml+="<img data-i='"+i+"' src='"+u+"' style='"+(i?"display:none":"")+"' onerror=\\"this.onerror=null;this.src='https://www.anandmaratha.com/no_imgf.jpg'\\"/>";});
  var navHtml="";
  if(ph.length>1){
    navHtml="<button class='arrow l' onclick='nav(this,-1)'>‹</button><button class='arrow r' onclick='nav(this,1)'>›</button><div class='nav'>";
    ph.forEach(function(u,i){navHtml+="<span class='dot"+(i?"":" on")+"' onclick='go(this,"+i+")'></span>";});
    navHtml+="</div>";
  }
  var contactedTag=p.contact?"<span class='contacted'>✓ CONTACT</span>":"";
  var contactHtml;
  if(p.contact){
    var c=p.contact, phones=(c.phones||"").split(",").map(function(x){x=x.trim();return x?"<a href='tel:"+x+"'>"+x+"</a>":"";}).filter(Boolean).join(", ");
    contactHtml="<div class='contact'><h4>Contact Details</h4>"+
      "<div><b>"+esc(c.name)+"</b></div>"+
      (c.address?"<div>"+esc(c.address)+"</div>":"")+
      (phones?"<div>📞 "+phones+"</div>":"")+
      (c.email?"<div>📧 <a href='mailto:"+esc(c.email)+"'>"+esc(c.email)+"</a></div>":"")+
      "</div>";
  } else {
    var sb=statusBox(p);
    contactHtml=sb||"<div class='nocontact'>No contact yet. Click <b>Express interest</b> to open the profile and tap the green <b>INTERESTED</b> button — contact details will arrive by email.</div>";
  }
  var srcTag=p.source?"<span class='src'>"+esc(p.source)+"</span>":"";
  return "<div class='card' data-blob='"+esc((p.surname+" "+p.regno+" "+ed+" "+oc+" "+loc+" "+(p.source||"")).toLowerCase())+"' data-match='"+p.match+"' data-gun='"+gunNum(p.gun)+"' data-contact='"+(p.contact?1:0)+"' data-seen='"+p.firstSeen+"' data-source='"+esc(p.source||"")+"'>"+
    "<div class='photoWrap'>"+photoHtml+srcTag+"<span class='badge'>"+p.match+"% match</span>"+contactedTag+navHtml+"</div>"+
    "<div class='body'>"+
      "<p class='nm'>"+esc(p.surname)+"</p>"+
      "<p class='rg'>"+p.regno+" · DOB "+esc(gv(p.details,"Date Of Birth"))+"</p>"+
      statusTags(p)+
      "<div class='chips'>"+chips.map(function(c){return "<span class='chip'>"+esc(c)+"</span>";}).join("")+"</div>"+
      (oc?"<div style='font-size:13px;margin-bottom:8px'>💼 "+esc(oc)+"</div>":"")+
      "<div class='gun' title='"+esc(p.gunBreak)+"'>★ Gun Milan: "+esc(p.gun)+" <span style='color:var(--muted)'>(hover for breakdown)</span></div>"+
      "<details><summary>Full profile, family &amp; expectations</summary>"+
        "<div class='sec'><h4>Profile Details</h4>"+kvtable(p.details)+"</div>"+
        "<div class='sec'><h4>Family Background</h4>"+kvtable(p.family)+"</div>"+
        "<div class='sec'><h4>Expectation</h4>"+kvtable(p.expectation)+"</div>"+
      "</details>"+
      contactHtml+
      "<div class='actions'><a class='btn' href='"+p.link+"' target='_blank'>View live profile</a><a class='btn primary' href='"+p.link+"' target='_blank'>Express interest →</a></div>"+
    "</div></div>";
}
function nav(btn,dir){var w=btn.closest('.photoWrap');var imgs=w.querySelectorAll('img');var dots=w.querySelectorAll('.dot');var cur=0;imgs.forEach(function(im,i){if(im.style.display!=='none')cur=i;});var n=(cur+dir+imgs.length)%imgs.length;show(w,n);}
function go(dot,i){show(dot.closest('.photoWrap'),i);}
function show(w,n){w.querySelectorAll('img').forEach(function(im,i){im.style.display=i===n?'block':'none';});w.querySelectorAll('.dot').forEach(function(d,i){d.classList.toggle('on',i===n);});}

function row(p){
  var a=age(gv(p.details,"Date Of Birth"));
  var h=gv(p.details,"Height"); var ed=gv(p.details,"Education"); var oc=gv(p.details,"Occupation");
  var loc=gv(p.family,"Parents Residing In");
  var ph=(p.photos&&p.photos.length?p.photos[0]:"https://www.anandmaratha.com/no_imgf.jpg");
  var meta=[]; if(a)meta.push(a+" yrs"); if(h)meta.push(h); if(loc)meta.push("📍"+loc);
  var line2=[]; if(ed)line2.push("<span>🎓 "+esc(ed)+"</span>"); if(oc)line2.push("<span>💼 "+esc(oc)+"</span>");
  var contact=p.contact?"<span class='c-ok'>✓ "+esc(p.contact.name||"contact ready")+"</span>":"<span class='c-no'>awaiting interest</span>";
  var srcTag=p.source?"<span class='srctag'>"+esc(p.source)+"</span>":"";
  return "<div class='row' data-blob='"+esc((p.surname+" "+p.regno+" "+ed+" "+oc+" "+loc+" "+(p.source||"")).toLowerCase())+"' data-match='"+p.match+"' data-gun='"+gunNum(p.gun)+"' data-contact='"+(p.contact?1:0)+"' data-source='"+esc(p.source||"")+"'>"+
    "<div class='ph'><img src='"+ph+"' onerror=\\"this.onerror=null;this.src='https://www.anandmaratha.com/no_imgf.jpg'\\"/></div>"+
    "<div class='mid'>"+
      "<div class='top'><span class='nm'>"+esc(p.surname||"(no name)")+"</span>"+srcTag+"</div>"+
      "<div class='meta'>"+esc(p.regno)+" · "+meta.join(" · ")+"</div>"+
      (line2.length?"<div class='line2'>"+line2.join("")+"</div>":"")+
      statusTags(p)+
      "<div class='meta'>★ "+esc(p.gun)+" · "+contact+"</div>"+
    "</div>"+
    "<div class='right'>"+
      "<div class='m'>"+p.match+"%</div>"+
      "<a href='"+p.link+"' target='_blank'>Open →</a>"+
    "</div>"+
  "</div>";
}

function currentView(){return localStorage.getItem('am_view')||'card';}
function setView(v){localStorage.setItem('am_view',v);Array.prototype.forEach.call(document.querySelectorAll('#viewtog button'),function(b){b.classList.toggle('on',b.getAttribute('data-v')===v);});render();}

function render(){
  var q=document.getElementById('q').value.toLowerCase().trim();
  var sort=document.getElementById('sort').value;
  var filt=document.getElementById('filter').value;
  var src=document.getElementById('source').value;
  var view=currentView();
  var list=P.slice();
  list.sort(function(a,b){
    if(sort==='match')return b.match-a.match;
    if(sort==='gun')return gunNum(b.gun)-gunNum(a.gun);
    return (b.firstSeen||'').localeCompare(a.firstSeen||'');
  });
  var g=document.getElementById('grid');
  g.className=(view==='list'?'list':'grid');
  g.innerHTML=list.map(view==='list'?row:card).join("");
  Array.prototype.forEach.call(g.children,function(el){
    var ok=true;
    if(q&&el.getAttribute('data-blob').indexOf(q)<0)ok=false;
    if(filt==='contact'&&el.getAttribute('data-contact')!=='1')ok=false;
    if(filt==='pending'&&el.getAttribute('data-contact')!=='0')ok=false;
    if(src!=='all'&&el.getAttribute('data-source')!==src)ok=false;
    el.style.display=ok?'':'none';
  });
}

function populateSources(){
  var sel=document.getElementById('source');
  var seen={};
  (DB.sources||[]).concat(P.map(function(p){return p.source||"";})).forEach(function(s){
    if(s&&!seen[s]){seen[s]=1;var o=document.createElement('option');o.value=s;o.textContent='Source: '+s;sel.appendChild(o);}
  });
}
function stats(){
  var withC=P.filter(function(p){return p.contact;}).length;
  var top=Math.max.apply(null,P.map(function(p){return p.match;}));
  document.getElementById('stats').innerHTML=
    "<div class='stat'><b>"+P.length+"</b><span>Profiles</span></div>"+
    "<div class='stat'><b>"+withC+"</b><span>Contact ready</span></div>"+
    "<div class='stat'><b>"+(P.length-withC)+"</b><span>Awaiting interest</span></div>"+
    "<div class='stat'><b>"+top+"%</b><span>Top match</span></div>";
}
</script>
</body>
</html>"""

HTML = (HTML
    .replace("__WHO__", db.get("generatedFor",""))
    .replace("__UPDATED__", updated)
    .replace("__ENC_B64__", enc_b64)
    .replace("__SALT_B64__", salt_b64)
    .replace("__IV_B64__", iv_b64)
    .replace("__PBKDF2_ITERS__", str(PBKDF2_ITERS)))
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("Wrote", OUT, "with", len(db["profiles"]), "profiles (AES-GCM encrypted)")
