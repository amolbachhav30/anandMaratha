#!/usr/bin/env python3
"""Builds index.html from data/profiles.json for the Anand Maratha interested-profiles dashboard.

Profile data is AES-256-GCM encrypted with the passcode (PBKDF2-HMAC-SHA256, 250k iters).
The passcode is NOT shipped — only encrypted ciphertext + salt + IV.
"""
import json, os, re, datetime, base64, secrets
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


def _normalize_phones(db):
    """Defensive cleanup at build time. The JS card renderer expects
    contact.phones to be a string; an upstream agent occasionally writes
    a list. Coerce to a comma-joined string, dedupe by digit-only form,
    drop entries with <7 digits (junk like '91--')."""
    for p in db.get("profiles", []):
        c = p.get("contact")
        if not isinstance(c, dict):
            continue
        ph = c.get("phones")
        if isinstance(ph, list):
            parts = ph
        elif isinstance(ph, str):
            parts = [s.strip() for s in ph.split(",") if s.strip()]
        else:
            c["phones"] = ""
            continue
        seen, out = set(), []
        for x in parts:
            x = str(x).strip()
            digits = re.sub(r"\D", "", x)
            if len(digits) < 7:
                continue
            norm = digits.lstrip("0")
            if norm in seen:
                continue
            seen.add(norm)
            out.append(x)
        c["phones"] = ", ".join(out)
    return db


db = _normalize_phones(db)

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
  header h1{margin:0;font-size:22px;font-weight:600;letter-spacing:.2px;display:flex;align-items:center;justify-content:space-between;gap:12px;}
  header h1 .gear{background:rgba(255,255,255,.2);border:none;color:#fff;width:34px;height:34px;border-radius:50%;font-size:18px;cursor:pointer;line-height:1;flex-shrink:0;}
  header h1 .gear:hover{background:rgba(255,255,255,.35);}
  header p{margin:4px 0 0;opacity:.9;font-size:13px;}
  .wrap{max-width:1180px;margin:0 auto;padding:20px 18px 60px;}
  .stats{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0;}
  .stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;min-width:100px;flex:1 1 100px;cursor:pointer;transition:transform .12s,border-color .12s;user-select:none;}
  .stat:hover{transform:translateY(-1px);border-color:var(--brown);}
  .stat.on{border-color:var(--brown);background:#fdf6ee;box-shadow:0 4px 12px rgba(160,90,44,.18);}
  .stat b{display:block;font-size:24px;color:var(--brown);}
  .stat span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;}
  /* Stage colors — match the pill colors */
  .stat[data-stage="new"] b{color:#777;} .stat[data-stage="interest"] b{color:#3c5a78;}
  .stat[data-stage="contact"] b{color:#5c4480;} .stat[data-stage="talking"] b{color:#b76e00;}
  .stat[data-stage="meeting"] b{color:#2e7d32;} .stat[data-stage="considering"] b{color:#107a6f;}
  .stat[data-stage="closed-yes"] b{color:#b88600;} .stat[data-stage="closed-no"] b{color:#9c2727;}
  /* Stage pill on cards/rows */
  .stage{display:inline-block;font-size:11px;font-weight:600;padding:2px 9px;border-radius:20px;letter-spacing:.2px;margin-right:4px;}
  .stage[data-s="new"]{background:#eee;color:#555;}
  .stage[data-s="interest"]{background:#eef3f8;color:#3c5a78;border:1px solid #d6e1ec;}
  .stage[data-s="requested"]{background:#fff0db;color:#7a4a00;border:1px solid #ecd5a9;}
  .stage[data-s="contact"]{background:#ece6f5;color:#5c4480;border:1px solid #d4c8e6;}
  .stage[data-s="talking"]{background:#fff0db;color:#7a4a00;border:1px solid #ecd5a9;}
  .stage[data-s="meeting"]{background:#e7f5e8;color:#2e7d32;border:1px solid #cfe6cf;}
  .stage[data-s="considering"]{background:#dcf3ef;color:#107a6f;border:1px solid #b5e0d6;}
  .stage[data-s="closed-yes"]{background:#fff5cc;color:#7a5a00;border:1px solid #e6d480;}
  .stage[data-s="closed-no"]{background:#fce9e9;color:#9c2727;border:1px solid #f0caca;}
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
  .row .mid{min-width:0;}  /* lets text truncate properly inside the grid */
  .row .mid .line2{font-size:13px;color:var(--ink);margin-top:4px;display:flex;gap:10px;flex-wrap:wrap;}
  .row .mid .line2 span{overflow:hidden;text-overflow:ellipsis;}
  .row .mid .meta{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
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
  /* CRM editor inside modal */
  .crm-edit{background:#f6f2ed;border-radius:10px;padding:12px 14px;margin-top:14px;}
  .crm-edit label{display:block;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;margin:8px 0 4px;}
  .crm-edit input,.crm-edit textarea,.crm-edit select{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:14px;background:#fff;font-family:inherit;}
  .crm-edit textarea{min-height:60px;resize:vertical;}
  .stage-radios{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;}
  .stage-radios label{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:600;padding:6px 10px;border-radius:20px;border:1px solid var(--line);background:#fff;cursor:pointer;margin:0;text-transform:none;letter-spacing:0;color:var(--ink);}
  .stage-radios label input{display:none;}
  .stage-radios label.sel{background:var(--brown);color:#fff;border-color:var(--brown);}
  .crm-history{margin-top:12px;font-size:12px;color:var(--ink);}
  .crm-history li{margin-bottom:4px;list-style:none;padding-left:12px;border-left:2px solid var(--line);}
  .crm-history li b{color:var(--brown2);}
  .crm-save{margin-top:12px;display:flex;gap:8px;}
  .crm-save button{flex:1;padding:10px;font-size:14px;font-weight:600;border:none;border-radius:8px;cursor:pointer;}
  .crm-save .save{background:var(--brown);color:#fff;}
  .crm-save .save[disabled]{background:var(--muted);cursor:wait;}
  .crm-save .cancel{background:#fff;color:var(--ink);border:1px solid var(--line);}
  /* Settings modal reuses #modalBack/#modal styles; just need extras for inputs */
  #settingsModal label{display:block;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;margin:14px 0 4px;}
  #settingsModal input{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;font-size:14px;font-family:monospace;}
  #settingsModal .actions{display:flex;gap:8px;margin-top:14px;}
  #settingsModal button{flex:1;padding:10px;font-size:14px;font-weight:600;border:none;border-radius:8px;cursor:pointer;background:var(--brown);color:#fff;}
  #settingsModal button.outline{background:#fff;color:var(--brown);border:1px solid var(--brown);}
  #patStatus{font-size:13px;margin-top:10px;min-height:18px;}
  #patStatus.ok{color:var(--good);}
  #patStatus.err{color:#c0392b;}
  #toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:12px 20px;border-radius:24px;font-size:14px;z-index:1100;opacity:0;transition:opacity .25s;pointer-events:none;}
  #toast.on{opacity:1;}
  /* Modal */
  #modalBack{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:900;align-items:flex-start;justify-content:center;padding:30px 16px;overflow-y:auto;}
  #modalBack.on{display:flex;}
  #modal{background:#fff;border-radius:14px;max-width:680px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.4);padding:0;overflow:hidden;}
  #modal .mhead{background:linear-gradient(to right,var(--brown),var(--brown2));color:#fff;padding:16px 22px;display:flex;align-items:center;justify-content:space-between;}
  #modal .mhead h2{margin:0;font-size:18px;font-weight:600;}
  #modal .mhead .sub{font-size:12px;opacity:.85;margin-top:2px;}
  #modal .mhead button{background:rgba(255,255,255,.15);border:none;color:#fff;font-size:20px;width:32px;height:32px;border-radius:50%;cursor:pointer;line-height:1;}
  #modal .mbody{padding:18px 22px 22px;max-height:calc(100vh - 160px);overflow-y:auto;}
  #modal .mbody h4{margin:18px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);}
  #modal .mbody h4:first-child{margin-top:0;}
  /* Compact contact summary inside the card */
  .contact-compact{background:#f1f8f1;border:1px solid #cfe6cf;border-radius:10px;padding:8px 12px;margin-top:10px;font-size:13px;color:var(--good);}
  .contact-compact b{color:var(--ink);}
  .btn-more{flex:1;text-align:center;text-decoration:none;font-size:13px;font-weight:600;padding:9px 10px;border-radius:9px;border:1px solid var(--muted);color:var(--muted);background:#fff;cursor:pointer;}
  .btn-more:hover{border-color:var(--brown);color:var(--brown);}
  .tags{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0 8px;}
  .row .right{display:flex;flex-direction:column;align-items:flex-end;gap:6px;font-size:12px;}
  .row .right .m{font-size:14px;font-weight:700;color:var(--brown);}
  .row .right .c-ok{color:var(--good);font-weight:600;}
  .row .right .c-no{color:var(--muted);}
  .row .right a{font-size:12px;color:var(--brown);text-decoration:none;border:1px solid var(--brown);padding:4px 8px;border-radius:6px;}
  @media (max-width:600px){
    .row{grid-template-columns:48px 1fr;gap:8px;padding:8px 10px;}
    .row .ph{width:48px;height:60px;}
    .row .mid .nm{font-size:14px;}
    .row .mid .meta,.row .mid .line2{font-size:12px;}
    .row .mid .line2 span{max-width:100%;display:inline-block;}
    .row .right{grid-column:1 / -1;flex-direction:row;justify-content:space-between;align-items:center;padding-top:6px;border-top:1px solid var(--line);font-size:12px;gap:6px;}
    .row .right .m{font-size:13px;}
    .row .right a{padding:4px 8px;font-size:11px;}
    .row .mid .srctag{font-size:9px;padding:1px 6px;}
    /* Status tags wrap on mobile */
    .row .htag{font-size:10px;padding:1px 6px;}
    .row .tags{margin:4px 0 6px;}
  }
  /* Edge case: even narrower screens */
  @media (max-width:360px){
    .row{grid-template-columns:40px 1fr;}
    .row .ph{width:40px;height:50px;}
    .wrap{padding:8px 6px 50px;}
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
  <h1><span>Anand Maratha — Profiles Who Expressed Interest</span><button class="gear" id="gearBtn" title="Settings">⚙</button></h1>
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
    <select id="stage">
      <option value="all">Stage: All</option>
      <option value="new">Stage: New</option>
      <option value="interest">Stage: Interest</option>
      <option value="requested">Stage: Requested</option>
      <option value="contact">Stage: Contact</option>
      <option value="talking">Stage: Talking</option>
      <option value="meeting">Stage: Meeting</option>
      <option value="considering">Stage: Considering</option>
      <option value="closed-yes">Stage: Closed — yes</option>
      <option value="closed-no">Stage: Closed — no</option>
    </select>
    <div class="viewtog" id="viewtog">
      <button data-v="card" class="on">▦ Cards</button>
      <button data-v="list">☰ List</button>
    </div>
    <button id="bulkReqBtn" class="btn-more" style="background:var(--brown);color:#fff;border-color:var(--brown);">📥 Request bulk contacts</button>
  </div>
  <div id="grid"></div>
</div>
<footer>
  Photos load directly from anandmaratha.com — if a photo is blank, open the site and sign in, then refresh this page.
  Contact details appear automatically once you have expressed interest and the office has sent them.
</footer>
</div>
<div id="modalBack" onclick="if(event.target.id==='modalBack')closeModal()">
  <div id="modal">
    <div class="mhead">
      <div><h2 id="mTitle"></h2><div class="sub" id="mSub"></div></div>
      <button onclick="closeModal()" aria-label="Close">×</button>
    </div>
    <div class="mbody" id="mBody"></div>
  </div>
</div>
<div id="settingsBack" class="modalbg" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:910;align-items:flex-start;justify-content:center;padding:30px 16px;overflow-y:auto;" onclick="if(event.target.id==='settingsBack')closeSettings()">
  <div id="settingsModal" style="background:#fff;border-radius:14px;max-width:520px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.4);overflow:hidden;">
    <div class="mhead">
      <div><h2 style="margin:0;font-size:18px">Settings</h2><div class="sub">GitHub access for editing profile stages</div></div>
      <button onclick="closeSettings()" aria-label="Close">×</button>
    </div>
    <div class="mbody">
      <p style="font-size:13px;color:var(--muted);margin:0">A GitHub Personal Access Token lets you change stages from this dashboard. Stored only in your browser's localStorage.</p>
      <label for="pat">Personal Access Token</label>
      <input type="password" id="pat" placeholder="github_pat_..." autocomplete="off"/>
      <p style="font-size:11px;color:var(--muted);margin:8px 0 0;line-height:1.5">
        Create one at <a href="https://github.com/settings/personal-access-tokens" target="_blank" style="color:var(--brown)">github.com/settings/personal-access-tokens</a><br>
        • Repository access: only <b>amolbachhav30/anandMaratha</b><br>
        • Permissions: <b>Contents → Read &amp; Write</b><br>
        • Expiration: pick what suits you (90 days is reasonable)
      </p>
      <div class="actions">
        <button class="outline" onclick="testPat()">Test connection</button>
        <button onclick="savePat()">Save</button>
      </div>
      <div id="patStatus"></div>
      <p style="font-size:11px;color:var(--muted);margin-top:18px"><a href="#" onclick="event.preventDefault();clearPat()" style="color:#c0392b">Remove saved token</a></p>
    </div>
  </div>
</div>
<div id="toast"></div>
<div id="bulkBack" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:920;align-items:flex-start;justify-content:center;padding:30px 16px;overflow-y:auto;" onclick="if(event.target.id==='bulkBack')closeBulk()">
  <div style="background:#fff;border-radius:14px;max-width:560px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.4);overflow:hidden;">
    <div class="mhead">
      <div><h2 style="margin:0;font-size:18px">Request bulk contacts</h2><div class="sub">Anand Maratha Response form · up to 10 IDs per 5 days</div></div>
      <button onclick="closeBulk()" aria-label="Close">×</button>
    </div>
    <div class="mbody">
      <p style="font-size:13px;color:var(--muted);margin:0 0 10px">Enter up to 10 Anand Maratha regnos (MGxxxxxx). Separator can be a <b>new line, space, tab, or comma</b> — any mix works. Letters are auto-uppercased.</p>
      <div style="background:#fff8e6;border:1px solid #ecd99a;border-radius:8px;padding:10px 12px;font-size:12px;margin:0 0 14px;color:#876d12">
        <b>One-time setup for fast form-fill:</b> drag this link to your bookmarks bar →
        <a id="amFillLink" style="background:var(--brown);color:#fff;text-decoration:none;padding:3px 9px;border-radius:6px;font-weight:600;font-size:11px;margin:0 4px;cursor:move" draggable="true">📥 AM Bulk Fill</a>
        Then after Submit, click that bookmark on the form page → all fields auto-fill. You only solve the CAPTCHA + submit.
      </div>
      <p style="font-size:12px;color:var(--muted);margin:0 0 14px">Suggested from your <b>Interest</b>-stage Anand Maratha profiles below. Click any to add it.</p>
      <div id="bulkSuggest" style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px;max-height:120px;overflow-y:auto;"></div>
      <textarea id="bulkInput" rows="8" style="width:100%;font-family:monospace;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:14px;text-transform:uppercase;" placeholder="MG149065 MG148979 MG148743 …"></textarea>
      <div class="actions" style="display:flex;gap:8px;margin-top:14px">
        <button class="outline" onclick="closeBulk()" style="flex:1;padding:10px;border-radius:8px;background:#fff;color:var(--ink);border:1px solid var(--line);font-weight:600;cursor:pointer">Cancel</button>
        <button onclick="submitBulk()" id="bulkSubmit" style="flex:2;padding:10px;border-radius:8px;background:var(--brown);color:#fff;border:none;font-weight:600;cursor:pointer">Submit &amp; open form →</button>
      </div>
      <div id="bulkStatus" style="font-size:13px;margin-top:10px;min-height:18px"></div>
    </div>
  </div>
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
function safeSetSession(k,v){try{sessionStorage.setItem(k,v);}catch(e){/* iOS Safari private mode etc. — ignore */}}
async function tryUnlock(pw){
  let stage='start';
  try{
    stage='derive';
    const key=await deriveKey(pw,b64bytes(SALT_B64));
    stage='decrypt';
    const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64bytes(IV_B64)},key,b64bytes(ENC_B64));
    stage='parse';
    const jsonText=new TextDecoder().decode(plain);
    DB=JSON.parse(jsonText);P=DB.profiles;
    // Cache in sessionStorage. Tolerate failure (iOS private mode, quota, etc.).
    safeSetSession('am_data',jsonText);
    safeSetSession('am_salt',SALT_B64);
    safeSetSession('am_pw',pw);
    stage='show';
    showApp();
    return true;
  }catch(e){
    // Wrong password makes AES-GCM throw an OperationError during decrypt.
    // Other stages should NOT throw. If they do, surface a hint.
    if(stage==='derive'||stage==='decrypt'){return false;}
    var el=document.getElementById('err');
    if(el){el.textContent='Unlocked, but failed to show app ('+stage+'): '+(e&&e.message||e);}
    console.error('unlock failure at stage',stage,e);
    return false;
  }
}
function showApp(){
  document.getElementById('gate').style.display='none';document.getElementById('app').style.display='block';
  try{populateSources();}catch(e){console.error('populateSources',e);}
  try{setView(currentView());}catch(e){console.error('setView',e);}
  try{stats();}catch(e){console.error('stats',e);}
  try{bindControls();}catch(e){console.error('bindControls',e);}
}
async function reveal(){
  // Try cached data only if the encrypted blob hasn't changed since we cached.
  const cached=sessionStorage.getItem('am_data');
  const cachedSalt=sessionStorage.getItem('am_salt');
  if(cached && cachedSalt===SALT_B64){
    DB=JSON.parse(cached);P=DB.profiles;
    showApp();
    return;
  }
  // Stale or no cache. Try cached password to silently re-decrypt the new build.
  const cachedPw=sessionStorage.getItem('am_pw');
  if(cachedPw){
    const ok=await tryUnlock(cachedPw);
    if(ok)return;
    sessionStorage.removeItem('am_pw');
  }
  // Otherwise clear stale cache and fall back to gate.
  sessionStorage.removeItem('am_data');
  sessionStorage.removeItem('am_salt');
}
function bindControls(){
  document.getElementById('q').addEventListener('input',render);
  document.getElementById('sort').addEventListener('change',render);
  document.getElementById('filter').addEventListener('change',render);
  document.getElementById('source').addEventListener('change',function(){highlightActiveStats();render();});
  document.getElementById('stage').addEventListener('change',function(){highlightActiveStats();render();});
  Array.prototype.forEach.call(document.querySelectorAll('#viewtog button'),function(b){b.addEventListener('click',function(){setView(b.getAttribute('data-v'));});});
  // Click a stat box → set the matching filter
  document.getElementById('stats').addEventListener('click',function(e){
    var el=e.target.closest('.stat'); if(!el)return;
    var f=el.getAttribute('data-filter'), v=el.getAttribute('data-value');
    if(f==='total'){
      document.getElementById('source').value='all';
      document.getElementById('stage').value='all';
    } else if(f==='source'){
      document.getElementById('source').value=v;
    } else if(f==='stage'){
      document.getElementById('stage').value=v;
    }
    highlightActiveStats();render();
  });
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
if(sessionStorage.getItem('am_data')||sessionStorage.getItem('am_pw'))reveal();
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
  var s=stageOf(p);
  var stage="<span class='stage' data-s='"+s+"'>"+STAGE_LABEL[s]+"</span>";
  return "<div class='tags'>"+stage+dt+dir+st+"</div>";
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
      "<div><b>"+esc(c.name||"")+"</b></div>"+
      (c.address?"<div>"+esc(c.address)+"</div>":"")+
      (phones?"<div>📞 "+phones+"</div>":"")+
      (c.email?"<div>📧 <a href='mailto:"+esc(c.email)+"'>"+esc(c.email)+"</a></div>":"")+
      "</div>";
  } else {
    var sb=statusBox(p);
    contactHtml=sb||"<div class='nocontact'>No contact yet. Click <b>Express interest</b> to open the profile and tap <b>INTERESTED</b>.</div>";
  }
  var detailsBlock = (p.details&&p.details.length || p.family&&p.family.length || p.expectation&&p.expectation.length)
    ? "<details><summary>Full profile, family &amp; expectations</summary>"+
        (p.details&&p.details.length ? "<div class='sec'><h4>Profile Details</h4>"+kvtable(p.details)+"</div>" : "")+
        (p.family&&p.family.length ? "<div class='sec'><h4>Family Background</h4>"+kvtable(p.family)+"</div>" : "")+
        (p.expectation&&p.expectation.length ? "<div class='sec'><h4>Expectation</h4>"+kvtable(p.expectation)+"</div>" : "")+
      "</details>"
    : "";
  var srcTag=p.source?"<span class='src'>"+esc(p.source)+"</span>":"";
  var matchBadge=(p.match>0)?"<span class='badge'>"+p.match+"% match</span>":"";
  var displayName=p.surname?esc(p.surname):esc(p.regno);
  var dob=gv(p.details,"Date Of Birth");
  var subRg=p.regno+(dob?" · DOB "+esc(dob):"");
  return "<div class='card' data-blob='"+esc((p.surname+" "+p.regno+" "+ed+" "+oc+" "+loc+" "+(p.source||"")).toLowerCase())+"' data-match='"+p.match+"' data-gun='"+gunNum(p.gun)+"' data-contact='"+(p.contact?1:0)+"' data-seen='"+p.firstSeen+"' data-source='"+esc(p.source||"")+"' data-stage='"+stageOf(p)+"'>"+
    "<div class='photoWrap'>"+photoHtml+srcTag+matchBadge+contactedTag+navHtml+"</div>"+
    "<div class='body'>"+
      "<p class='nm'>"+displayName+"</p>"+
      "<p class='rg'>"+subRg+"</p>"+
      statusTags(p)+
      (chips.length?"<div class='chips'>"+chips.map(function(c){return "<span class='chip'>"+esc(c)+"</span>";}).join("")+"</div>":"")+
      (oc?"<div style='font-size:13px;margin-bottom:8px'>💼 "+esc(oc)+"</div>":"")+
      (p.message?"<div style='font-size:13px;background:#f6f2ed;border-radius:8px;padding:8px 10px;margin-bottom:8px;font-style:italic;color:var(--brown2)'>💬 "+esc(p.message)+"</div>":"")+
      (p.gun?"<div class='gun' title='"+esc(p.gunBreak)+"'>★ Gun Milan: "+esc(p.gun)+" <span style='color:var(--muted)'>(hover for breakdown)</span></div>":"")+
      detailsBlock+
      contactHtml+
      "<div class='actions'><button class='btn-more' data-regno='"+esc(p.regno)+"'>View details</button><a class='btn primary' href='"+p.link+"' target='_blank'>Open live →</a></div>"+
    "</div></div>";
}
function nav(btn,dir){var w=btn.closest('.photoWrap');var imgs=w.querySelectorAll('img');var dots=w.querySelectorAll('.dot');var cur=0;imgs.forEach(function(im,i){if(im.style.display!=='none')cur=i;});var n=(cur+dir+imgs.length)%imgs.length;show(w,n);}
function go(dot,i){show(dot.closest('.photoWrap'),i);}
function show(w,n){w.querySelectorAll('img').forEach(function(im,i){im.style.display=i===n?'block':'none';});w.querySelectorAll('.dot').forEach(function(d,i){d.classList.toggle('on',i===n);});}

function row(p){
  var a=age(gv(p.details,"Date Of Birth"));
  if(!a){var ageStr=gv(p.details,"Age"); if(ageStr)a=null,ageStr=ageStr;}
  var h=gv(p.details,"Height"); var ed=gv(p.details,"Education"); var oc=gv(p.details,"Occupation");
  var loc=gv(p.family,"Parents Residing In")||gv(p.details,"Location");
  var ph=(p.photos&&p.photos.length?p.photos[0]:"https://www.anandmaratha.com/no_imgf.jpg");
  var meta=[]; if(a)meta.push(a+" yrs"); else { var aStr=gv(p.details,"Age"); if(aStr)meta.push(aStr); }
  if(h)meta.push(h); if(loc)meta.push("📍"+loc);
  var line2=[]; if(ed)line2.push("<span>🎓 "+esc(ed)+"</span>"); if(oc)line2.push("<span>💼 "+esc(oc)+"</span>");
  if(p.message)line2.push("<span style='font-style:italic;color:var(--brown2)'>💬 "+esc(p.message.length>80?p.message.slice(0,80)+"…":p.message)+"</span>");
  var contact=p.contact?"<span class='c-ok'>✓ "+esc(p.contact.name||"contact ready")+"</span>":"";
  var srcTag=p.source?"<span class='srctag'>"+esc(p.source)+"</span>":"";
  var displayName=p.surname?esc(p.surname):esc(p.regno);
  var gunInline=p.gun?"★ "+esc(p.gun):"";
  var bottom=[gunInline, contact].filter(Boolean).join(" · ");
  var matchInline=(p.match>0)?p.match+"%":"";
  return "<div class='row' data-blob='"+esc((p.surname+" "+p.regno+" "+ed+" "+oc+" "+loc+" "+(p.source||"")).toLowerCase())+"' data-match='"+p.match+"' data-gun='"+gunNum(p.gun)+"' data-contact='"+(p.contact?1:0)+"' data-source='"+esc(p.source||"")+"' data-stage='"+stageOf(p)+"'>"+
    "<div class='ph'><img src='"+ph+"' onerror=\\"this.onerror=null;this.src='https://www.anandmaratha.com/no_imgf.jpg'\\"/></div>"+
    "<div class='mid'>"+
      "<div class='top'><span class='nm'>"+displayName+"</span>"+srcTag+"</div>"+
      "<div class='meta'>"+esc(p.regno)+(meta.length?" · "+meta.join(" · "):"")+"</div>"+
      (line2.length?"<div class='line2'>"+line2.join("")+"</div>":"")+
      statusTags(p)+
      (bottom?"<div class='meta'>"+bottom+"</div>":"")+
    "</div>"+
    "<div class='right'>"+
      (matchInline?"<div class='m'>"+matchInline+"</div>":"")+
      "<button class='btn-more' data-regno='"+esc(p.regno)+"' style='padding:4px 8px;font-size:11px'>Details</button>"+
      "<a href='"+p.link+"' target='_blank'>Open →</a>"+
    "</div>"+
  "</div>";
}

function openModal(regno){
  var p=P.find(function(x){return x.regno===regno;});
  if(!p)return;
  document.getElementById('mTitle').textContent=(p.surname||p.regno);
  var sub=[];
  if(p.surname)sub.push(p.regno);
  if(p.source)sub.push(p.source);
  if(p.match>0)sub.push(p.match+"% match");
  if(p.gun)sub.push("★ "+p.gun);
  document.getElementById('mSub').textContent=sub.join(" · ");
  var body="";
  // Contact details (top, since most important)
  if(p.contact){
    var c=p.contact, phones=(c.phones||"").split(",").map(function(x){x=x.trim();return x?"<a href='tel:"+esc(x)+"'>"+esc(x)+"</a>":"";}).filter(Boolean).join(", ");
    body+="<div class='contact'><h4>Contact</h4>"+
      "<div><b>"+esc(c.name||"")+"</b></div>"+
      (c.address?"<div>"+esc(c.address)+"</div>":"")+
      (phones?"<div>📞 "+phones+"</div>":"")+
      (c.email?"<div>📧 <a href='mailto:"+esc(c.email)+"'>"+esc(c.email)+"</a></div>":"")+
      "</div>";
  }
  if(p.gunBreak){body+="<h4>Gun Milan breakdown</h4><div style='font-size:13px;color:var(--ink);background:var(--cream);padding:8px 10px;border-radius:8px;'>"+esc(p.gunBreak)+"</div>";}
  if(p.message){body+="<h4>Sent message</h4><div style='font-size:13px;color:var(--brown2);background:var(--cream);padding:8px 10px;border-radius:8px;font-style:italic'>"+esc(p.message)+"</div>";}
  if(p.details&&p.details.length){body+="<h4>Profile Details</h4>"+kvtable(p.details);}
  if(p.family&&p.family.length){body+="<h4>Family Background</h4>"+kvtable(p.family);}
  if(p.expectation&&p.expectation.length){body+="<h4>Expectation</h4>"+kvtable(p.expectation);}
  // Photos thumbnail strip
  if(p.photos&&p.photos.length>1){
    body+="<h4>Photos</h4><div style='display:flex;gap:6px;flex-wrap:wrap;'>";
    p.photos.forEach(function(u){
      body+="<a href='"+u+"' target='_blank'><img src='"+u+"' style='width:80px;height:100px;object-fit:cover;border-radius:6px;border:1px solid var(--line);' onerror=\\"this.style.display='none'\\"/></a>";
    });
    body+="</div>";
  }
  // Status info
  body+="<h4>Status</h4><div style='font-size:13px'>";
  if(p.direction)body+="Direction: <b>"+esc(p.direction)+"</b><br>";
  if(p.status)body+="Status: <b>"+esc(p.status)+"</b><br>";
  if(p.statusDate)body+="Date: "+esc(p.statusDate)+"<br>";
  if(p.firstSeen)body+="First seen: "+esc(p.firstSeen)+"<br>";
  if(p.declineReason)body+="Reason: "+esc(p.declineReason)+"<br>";
  body+="</div>";
  // CRM editor at bottom
  body+=buildCRMEditor(p);
  document.getElementById('mBody').innerHTML=body;
  document.getElementById('modalBack').classList.add('on');
}
function closeModal(){
  document.getElementById('modalBack').classList.remove('on');
}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
document.addEventListener('click',function(e){
  var b=e.target.closest('.btn-more');
  if(b && b.dataset.regno){openModal(b.dataset.regno);}
});

// ---------- Settings + GitHub API ----------
var REPO='amolbachhav30/anandMaratha';
function getPat(){return localStorage.getItem('am_gh_pat')||'';}
function openSettings(){
  document.getElementById('pat').value=getPat();
  document.getElementById('patStatus').textContent='';
  document.getElementById('patStatus').className='';
  document.getElementById('settingsBack').style.display='flex';
}
function closeSettings(){document.getElementById('settingsBack').style.display='none';}
async function testPat(){
  var pat=document.getElementById('pat').value.trim();
  var s=document.getElementById('patStatus');
  if(!pat){s.textContent='Enter a token first.';s.className='err';return;}
  s.textContent='Testing…';s.className='';
  try{
    var r=await fetch('https://api.github.com/repos/'+REPO,{headers:{Authorization:'token '+pat}});
    if(!r.ok){s.textContent='Token rejected ('+r.status+'). Check scope: Contents read+write on '+REPO+'.';s.className='err';return;}
    var j=await r.json();
    s.textContent='✓ Token works. Repo: '+j.full_name+' ('+(j.permissions&&j.permissions.push?'write':'read-only')+').';
    s.className=(j.permissions&&j.permissions.push)?'ok':'err';
    if(!(j.permissions&&j.permissions.push)){s.textContent+=' Need write access for editing.';}
  }catch(e){s.textContent='Network error: '+e.message;s.className='err';}
}
function savePat(){
  var pat=document.getElementById('pat').value.trim();
  if(!pat){localStorage.removeItem('am_gh_pat');toast('Token cleared');closeSettings();return;}
  localStorage.setItem('am_gh_pat',pat);toast('Token saved');closeSettings();
}
function clearPat(){if(confirm('Remove saved GitHub token?')){localStorage.removeItem('am_gh_pat');toast('Removed');closeSettings();}}

function toast(msg,kind){
  var t=document.getElementById('toast');
  t.textContent=msg;
  t.style.background=kind==='err'?'#9c2727':kind==='ok'?'#2e7d32':'var(--ink)';
  t.classList.add('on');
  clearTimeout(t._h);t._h=setTimeout(function(){t.classList.remove('on');},2800);
}

// UTF-8 safe base64
function b64encode(str){return btoa(unescape(encodeURIComponent(str)));}
function b64decode(b){return decodeURIComponent(escape(atob(b)));}

async function ghGetFile(path){
  var pat=getPat();if(!pat)throw new Error('No GitHub token. Open Settings first.');
  var r=await fetch('https://api.github.com/repos/'+REPO+'/contents/'+path,{headers:{Authorization:'token '+pat,Accept:'application/vnd.github.v3+json'}});
  if(!r.ok)throw new Error('GET '+path+': '+r.status);
  var j=await r.json();
  return {sha:j.sha, content:b64decode(j.content.replace(/\\n/g,''))};
}
async function ghPutFile(path, content, sha, message){
  var pat=getPat();if(!pat)throw new Error('No GitHub token.');
  var r=await fetch('https://api.github.com/repos/'+REPO+'/contents/'+path,{
    method:'PUT',
    headers:{Authorization:'token '+pat,Accept:'application/vnd.github.v3+json','Content-Type':'application/json'},
    body:JSON.stringify({message:message, content:b64encode(content), sha:sha, branch:'main'})
  });
  if(!r.ok){var t=await r.text();throw new Error('PUT '+r.status+': '+t.substring(0,200));}
  return r.json();
}

// Save a CRM change for one profile to GitHub.
// Retries once on 409 (sha conflict).
async function saveCRM(regno, stage, note, nextAction, dueDate, closedReason){
  var pat=getPat();
  if(!pat){toast('Add a GitHub token in Settings first','err');openSettings();return false;}
  for(var attempt=0; attempt<2; attempt++){
    try{
      var file=await ghGetFile('data/profiles.json');
      var db=JSON.parse(file.content);
      var found=null;
      for(var i=0;i<db.profiles.length;i++){if(db.profiles[i].regno===regno){found=db.profiles[i];break;}}
      if(!found){toast('Profile '+regno+' not found in repo','err');return false;}
      if(!found.crm)found.crm={stage:'interest',history:[],next_action:'',next_action_due:'',closed_reason:'',notes:''};
      var today=new Date().toISOString().slice(0,10);
      var prev=found.crm.stage||'interest';
      if(stage!==prev || note){
        found.crm.history=found.crm.history||[];
        found.crm.history.push({date:today, from:prev, to:stage, note:note||''});
      }
      found.crm.stage=stage;
      found.crm.next_action=nextAction||'';
      found.crm.next_action_due=dueDate||'';
      if(stage==='closed-no')found.crm.closed_reason=closedReason||found.crm.closed_reason||'';
      var newContent=JSON.stringify(db,null,2)+'\\n';
      await ghPutFile('data/profiles.json', newContent, file.sha, 'CRM: '+regno+' → '+stage);
      // Update in-memory so UI reflects immediately
      for(var k=0;k<P.length;k++){if(P[k].regno===regno){P[k]=found;break;}}
      return true;
    }catch(e){
      if(attempt===0 && /409|conflict/i.test(e.message)){continue;}
      console.error('saveCRM',e);toast('Save failed: '+e.message,'err');return false;
    }
  }
  return false;
}

// ---------- CRM Editor inside the profile modal ----------
function buildCRMEditor(p){
  var cur=stageOf(p);
  var crm=p.crm||{stage:cur,history:[],next_action:'',next_action_due:'',closed_reason:'',notes:''};
  var stages=STAGE_ORDER;
  var radios=stages.map(function(s){
    var sel=(s===cur)?'sel':'';
    return "<label class='"+sel+"' data-s='"+s+"'><input type='radio' name='crm-stage' value='"+s+"' "+(s===cur?'checked':'')+"/>"+STAGE_LABEL[s]+"</label>";
  }).join('');
  var hist=(crm.history||[]).slice().reverse().slice(0,8).map(function(h){
    return "<li><b>"+esc(h.date||'')+"</b> "+esc(h.from||'')+" → "+esc(h.to||'')+(h.note?": "+esc(h.note):"")+"</li>";
  }).join('');
  var closedRow=(cur==='closed-no')?"<label>Closed reason</label><input id='crmReason' value='"+esc(crm.closed_reason||'')+"' placeholder='e.g. Sub-caste mismatch, location, family said no'/>":"";
  return "<div class='crm-edit'>"+
    "<h4 style='margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)'>CRM stage</h4>"+
    "<div class='stage-radios' id='crmStages'>"+radios+"</div>"+
    closedRow+
    "<label>Note (optional)</label>"+
    "<textarea id='crmNote' placeholder='What happened? e.g. Spoke to her father 15 min'></textarea>"+
    "<label>Next action</label>"+
    "<input id='crmNext' value='"+esc(crm.next_action||'')+"' placeholder='e.g. Send our family photos'/>"+
    "<label>Due date</label>"+
    "<input id='crmDue' type='date' value='"+esc(crm.next_action_due||'')+"'/>"+
    "<div class='crm-save'>"+
      "<button class='cancel' onclick='closeModal()'>Cancel</button>"+
      "<button class='save' id='crmSave' data-regno='"+esc(p.regno)+"'>Save</button>"+
    "</div>"+
    (hist?"<h4 style='margin:14px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)'>History</h4><ul class='crm-history'>"+hist+"</ul>":"")+
  "</div>";
}

// Hook stage radio toggle styling
document.addEventListener('change',function(e){
  if(e.target&&e.target.name==='crm-stage'){
    var radios=document.querySelectorAll('#crmStages label');
    radios.forEach(function(l){l.classList.toggle('sel', l.querySelector('input').checked);});
    // Toggle closed-reason input visibility
    var openVal=e.target.value;
    var reasonEl=document.getElementById('crmReason');
    if(openVal==='closed-no' && !reasonEl){
      var stages=document.getElementById('crmStages');
      var lbl=document.createElement('label');lbl.textContent='Closed reason';
      var inp=document.createElement('input');inp.id='crmReason';inp.placeholder='Sub-caste, location, family said no, …';
      stages.parentNode.insertBefore(lbl, stages.nextSibling);
      stages.parentNode.insertBefore(inp, lbl.nextSibling);
    } else if(openVal!=='closed-no' && reasonEl){
      reasonEl.previousElementSibling.remove();
      reasonEl.remove();
    }
  }
});

// Hook save button
document.addEventListener('click',async function(e){
  var btn=e.target.closest('#crmSave');
  if(!btn)return;
  btn.disabled=true;btn.textContent='Saving…';
  var regno=btn.dataset.regno;
  var stage=(document.querySelector('input[name=crm-stage]:checked')||{value:'interest'}).value;
  var note=(document.getElementById('crmNote')||{value:''}).value.trim();
  var nextAct=(document.getElementById('crmNext')||{value:''}).value.trim();
  var due=(document.getElementById('crmDue')||{value:''}).value.trim();
  var reason=(document.getElementById('crmReason')||{value:''}).value.trim();
  var ok=await saveCRM(regno, stage, note, nextAct, due, reason);
  if(ok){
    toast('Saved. Live site updates in ~30s.','ok');
    closeModal();
    stats();render();  // reflect locally
  } else {
    btn.disabled=false;btn.textContent='Save';
  }
});

document.getElementById('gearBtn').addEventListener('click',openSettings);

// ---------- Bulk request flow ----------
// The bookmarklet source — kept short so the encoded URL fits in a bookmark.
var AM_FILL_JS = "(function(){var p=new URLSearchParams(location.hash.slice(1));var f=function(s,v){var e=document.querySelector(s);if(e&&v)e.value=v;};f('input[name=reg_no]',p.get('regno'));f('input[name=email]',p.get('email'));var ids=(p.get('reg')||'').split(',').filter(Boolean);document.querySelectorAll('input[name=\\\"reg[]\\\"]').forEach(function(el,i){if(ids[i])el.value=ids[i];});var c=document.querySelector('input[name=consent]');if(c)c.checked=true;var v=document.querySelector('input[name=verify]');if(v)v.focus();})();";

function setupBookmarkletLink(){
  var a=document.getElementById('amFillLink');
  if(a)a.href='javascript:'+encodeURIComponent(AM_FILL_JS);
}

function openBulk(){
  setupBookmarkletLink();
  // Build suggestions: Anand Maratha + Interest stage, sorted by match% desc
  var sug=P.filter(function(p){return p.source==='Anand Maratha' && stageOf(p)==='interest';});
  sug.sort(function(a,b){return (b.match||0)-(a.match||0);});
  var html=sug.slice(0,30).map(function(p){
    return "<button class='bulk-sug' data-regno='"+esc(p.regno)+"' style='font-size:12px;padding:4px 9px;border-radius:14px;background:#eef3f8;color:#3c5a78;border:1px solid #d6e1ec;cursor:pointer'>"+esc(p.regno)+" ("+(p.match||0)+"%)</button>";
  }).join('');
  document.getElementById('bulkSuggest').innerHTML=html||"<i style='font-size:12px;color:var(--muted)'>No Interest-stage Anand Maratha profiles to suggest.</i>";
  document.getElementById('bulkInput').value='';
  document.getElementById('bulkStatus').textContent='';
  document.getElementById('bulkBack').style.display='flex';
}
function closeBulk(){document.getElementById('bulkBack').style.display='none';}

document.getElementById('bulkReqBtn').addEventListener('click',openBulk);
document.getElementById('bulkInput').addEventListener('input',function(e){
  var pos=e.target.selectionStart;
  var up=e.target.value.toUpperCase();
  if(up!==e.target.value){e.target.value=up;e.target.setSelectionRange(pos,pos);}
});
document.addEventListener('click',function(e){
  var s=e.target.closest('.bulk-sug');
  if(s && s.dataset.regno){
    var ta=document.getElementById('bulkInput');
    var lines=ta.value.split(/[\\n,]+/).map(function(l){return l.trim();}).filter(Boolean);
    if(lines.indexOf(s.dataset.regno)<0 && lines.length<10){
      lines.push(s.dataset.regno);
      ta.value=lines.join('\\n');
    }
  }
});

async function submitBulk(){
  var pat=getPat();
  if(!pat){toast('Add a GitHub token in Settings first','err');openSettings();return;}
  var raw=document.getElementById('bulkInput').value;
  var ids=raw.split(/[\\n,\\s]+/).map(function(l){return l.trim().toUpperCase();}).filter(function(l){return /^MG\\d+$/.test(l);});
  ids=Array.from(new Set(ids));
  var status=document.getElementById('bulkStatus');
  if(ids.length===0){status.textContent='Enter at least one valid MG regno.';status.style.color='#c0392b';return;}
  if(ids.length>10){status.textContent='Max 10 IDs allowed. Trimming to 10.';ids=ids.slice(0,10);}
  status.textContent='Saving '+ids.length+' profile(s) as Requested…';status.style.color='var(--muted)';
  var btn=document.getElementById('bulkSubmit');btn.disabled=true;btn.textContent='Saving…';
  try{
    var file=await ghGetFile('data/profiles.json');
    var db=JSON.parse(file.content);
    var today=new Date().toISOString().slice(0,10);
    var marked=0, missing=[];
    ids.forEach(function(regno){
      var found=null;
      for(var i=0;i<db.profiles.length;i++){if(db.profiles[i].regno===regno){found=db.profiles[i];break;}}
      if(!found){
        // Add a stub so it shows up in dashboard with stage=requested
        db.profiles.push({
          regno:regno, surname:'', mgid:'', source:'Anand Maratha',
          link:'https://www.anandmaratha.com/',
          match:0, gun:'', gunBreak:'', photos:[], firstSeen:today,
          direction:'sent', status:'pending', statusDate:today,
          details:[], family:[], expectation:[], contact:null,
          crm:{stage:'requested', history:[{date:today,from:'new',to:'requested',note:'bulk-request submitted'}],
               next_action:'wait for Response email', next_action_due:'', closed_reason:'', notes:''}
        });
        missing.push(regno);
      } else {
        var prev=(found.crm&&found.crm.stage)||'interest';
        if(!found.crm)found.crm={stage:'interest',history:[],next_action:'',next_action_due:'',closed_reason:'',notes:''};
        found.crm.history=found.crm.history||[];
        found.crm.history.push({date:today,from:prev,to:'requested',note:'bulk-request submitted'});
        found.crm.stage='requested';
        found.crm.next_action='wait for Response email';
      }
      marked++;
    });
    var newContent=JSON.stringify(db,null,2)+'\\n';
    await ghPutFile('data/profiles.json', newContent, file.sha, 'Bulk-request: '+ids.length+' profiles marked as Requested');
    // Update in-memory
    P=db.profiles;
    closeBulk();
    stats();render();
    // Copy IDs to clipboard as a backup if bookmarklet not installed
    try{await navigator.clipboard.writeText(ids.join('\\n'));}catch(e){}
    // Build the form URL with all needed data in the URL hash so the
    // AM Bulk Fill bookmarklet can read it once the user clicks the bookmark.
    var hash='regno=MB112528'+
             '&email='+encodeURIComponent('amolbachhav@gmail.com')+
             '&reg='+encodeURIComponent(ids.join(','));
    var url='https://www.anandmaratha.com/response.php#'+hash;
    var msg='✓ Saved. '+ids.length+' marked as Requested.';
    if(missing.length)msg+=' ('+missing.length+' new stubs added.)';
    msg+=' Opening form — click your AM Bulk Fill bookmark there to auto-fill.';
    toast(msg,'ok');
    setTimeout(function(){window.open(url,'_blank');},400);
  }catch(e){
    status.textContent='Error: '+e.message;status.style.color='#c0392b';
    console.error(e);
  }
  btn.disabled=false;btn.textContent='Submit & open form →';
}

function currentView(){return localStorage.getItem('am_view')||'card';}
function setView(v){localStorage.setItem('am_view',v);Array.prototype.forEach.call(document.querySelectorAll('#viewtog button'),function(b){b.classList.toggle('on',b.getAttribute('data-v')===v);});render();}

function render(){
  var q=document.getElementById('q').value.toLowerCase().trim();
  var sort=document.getElementById('sort').value;
  var filt=document.getElementById('filter').value;
  var src=document.getElementById('source').value;
  var stg=document.getElementById('stage').value;
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
    if(stg!=='all'&&el.getAttribute('data-stage')!==stg)ok=false;
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
var STAGE_LABEL={new:'New',interest:'Interest',requested:'Requested',contact:'Contact',talking:'Talking',meeting:'Meeting',considering:'Considering','closed-yes':'Closed yes','closed-no':'Closed no'};
var STAGE_ORDER=['new','interest','requested','contact','talking','meeting','considering','closed-yes','closed-no'];

function stageOf(p){return (p.crm&&p.crm.stage)||'interest';}

function stats(){
  var bySource={}, byStage={};
  STAGE_ORDER.forEach(function(s){byStage[s]=0;});
  P.forEach(function(p){
    var s=p.source||'(unknown)'; bySource[s]=(bySource[s]||0)+1;
    byStage[stageOf(p)]=(byStage[stageOf(p)]||0)+1;
  });
  var html="<div class='stat' data-filter='total'><b>"+P.length+"</b><span>Total</span></div>";
  Object.keys(bySource).sort().forEach(function(s){
    html+="<div class='stat' data-filter='source' data-value='"+esc(s)+"'><b>"+bySource[s]+"</b><span>"+esc(s)+"</span></div>";
  });
  STAGE_ORDER.forEach(function(s){
    if(byStage[s]>0||['interest','contact','talking','meeting'].indexOf(s)>=0){
      html+="<div class='stat' data-filter='stage' data-value='"+s+"' data-stage='"+s+"'><b>"+byStage[s]+"</b><span>"+STAGE_LABEL[s]+"</span></div>";
    }
  });
  document.getElementById('stats').innerHTML=html;
  highlightActiveStats();
}

function highlightActiveStats(){
  var src=document.getElementById('source').value;
  var stg=document.getElementById('stage').value;
  Array.prototype.forEach.call(document.querySelectorAll('#stats .stat'),function(el){
    var f=el.getAttribute('data-filter'), v=el.getAttribute('data-value');
    var on=(f==='source'&&src===v)||(f==='stage'&&stg===v)||(f==='total'&&src==='all'&&stg==='all');
    el.classList.toggle('on', on);
  });
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
