"""网页端：贴一段英文，左边先出规则结果，右边再出模型批改。"""

from __future__ import annotations

import json
import threading
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import checks, review, store

MAX_BODY = 200_000

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>语伴 · 这句英文问题在哪</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--text:#c9d1d9;--dim:#8b949e;
--ok:#7ee787;--warn:#e3b341;--bad:#ff7b72;--blue:#79c0ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;margin:0 0 6px}
.sub{color:var(--dim);font-size:13px;margin-bottom:22px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.panel h2{font-size:14px;color:var(--dim);font-weight:400;margin:0 0 10px;letter-spacing:.5px}
textarea{width:100%;min-height:210px;background:#0b0f14;color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:12px;font:14px/1.7 ui-monospace,Consolas,monospace;resize:vertical}
.btns{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
button{background:#1f6feb;color:#fff;border:0;border-radius:7px;padding:9px 16px;font-size:14px;cursor:pointer}
button.ghost{background:#21262d;color:var(--text);border:1px solid var(--line)}
button:disabled{opacity:.45;cursor:not-allowed}
.meta{color:var(--dim);font-size:13px;margin:12px 0 4px}
ul.issues{list-style:none;margin:0;padding:0}
li{padding:7px 0;border-bottom:1px dashed #21262d;font-size:14px}
.tag{display:inline-block;font-size:12px;padding:1px 7px;border-radius:4px;margin-right:8px}
.t-rule{background:#3d2b00;color:var(--warn)}
.t-model{background:#0e3a5f;color:var(--blue)}
.span{color:#ffb3ae;font-family:ui-monospace,Consolas,monospace}
.why{color:var(--dim);font-size:13px}
.sent{background:#0b0f14;border-left:3px solid var(--line);padding:10px 12px;margin:10px 0;border-radius:0 6px 6px 0}
.sent .orig{font-size:15px}
.sent .fix{color:var(--ok);margin-top:6px;font-size:14px}
.level{display:inline-block;background:#238636;color:#fff;border-radius:5px;padding:2px 9px;font-size:13px;margin-left:8px}
.err{color:var(--bad);font-size:13px;margin-top:8px}
select{background:#0b0f14;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:6px 10px}
.spin{color:var(--dim);font-size:13px}

:root{--maxw:1080px;--bg:#f3efe5;--card:#fffdf7;--ink:#29253d;--text:#29253d;--dim:#6d687d;--line:#d8d0bd;--accent:#4b3d7a;--muted:#6d687d}
.wrap{max-width:1080px}
body{background:#f3efe5;color:#29253d;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
h1{color:#29253d}
header{max-width:1080px;margin:0 auto}
input,textarea,select{background:#fff;color:#29253d;border-color:#d8d0bd;border-radius:2px}
button:not(.ghost):not(.tab){background:#4b3d7a;color:#fff;border-radius:2px}
button.ghost{background:transparent!important;color:#4b3d7a!important;border:1px solid #d8d0bd!important}
h2,h3{color:#4b3d7a}
pre{background:#fafaf6;color:#29253d;border-color:#d8d0bd}
.item,.card{border-color:#d8d0bd;background:#fffdf7}
.k,.empty,.hint{color:#6d687d}

h1{font-size:clamp(31px,5vw,39px);line-height:1.26}
.prod{display:block;font-size:11px;line-height:1.4;letter-spacing:.18em;font-weight:650;margin-bottom:8px;opacity:.72}
.lede,.sub{max-width:62ch;line-height:1.75}
.route{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:16px auto 20px;border:1px solid var(--line);background:var(--line);max-width:var(--maxw)}
.route span{padding:11px 13px;background:var(--card);font-size:12px;line-height:1.5}
.route b{display:block;font-size:10px;letter-spacing:.1em;margin-bottom:3px;opacity:.66}
button{min-height:46px}
input,select{min-height:44px}
pre{white-space:pre-wrap}
@media(max-width:680px){
  .wrap{padding:20px 16px 56px}
  .route{grid-template-columns:1fr}
  h1{font-size:30px!important}
  .row>div{min-width:100%!important}
  button{width:100%}
}

:root{--bg:#f3efe5;--card:#fffdf7;--line:#d8d0bd;--text:#29253d;--dim:#6d687d;--accent:#4b3d7a}
body{background:#f3efe5;color:#29253d}
h1{font-size:38px;line-height:1.24;color:#29253d}
h1 span{color:#6d687d!important}
.sub{color:#6d687d;font-size:14px}
.row{display:grid!important;grid-template-columns:1fr 1fr;gap:18px}
.panel{background:#fffdf7;border:1px solid #d8d0bd;border-radius:2px;padding:20px;box-shadow:none}
button{background:#4b3d7a;color:#fff;border-radius:2px}
button:hover{background:#3d3163}
input,textarea,select{background:#fff;color:#29253d;border-color:#d4c9b4;border-radius:2px}
input:focus,textarea:focus,select:focus{border-color:#4b3d7a;box-shadow:0 0 0 2px #ddd7e7}
.issues li,.issue{border-left:3px solid #4b3d7a;background:#fbf8f1}
h2{color:#4b3d7a;font-size:14px;letter-spacing:.05em}
.meta,.spin{color:#6d687d}
@media(max-width:760px){.row{grid-template-columns:1fr}}


/* mobile-32 */

@media(max-width:760px){
  main{grid-template-columns:1fr!important}
  aside{border-right:0!important;border-bottom:1px solid #d8d0bd;width:auto!important}
  section{padding:16px!important}
  .row{flex-wrap:wrap!important}
  .row>div{min-width:100%!important}
  h1{font-size:30px!important}
  .route{grid-template-columns:1fr!important}
  button{min-height:48px}
  pre{overflow-x:auto}
}

/* mobile-height */
@media(max-width:760px){main{min-height:auto!important}aside{min-height:0!important}}
</style></head><body><div class="wrap">
<h1><span class="prod">语伴</span>这句英文，问题在哪 <span style="color:var(--dim);font-size:13px;font-weight:400">规则查硬错 · 模型看语感</span></h1>
  <div class="route" aria-label="任务步骤"><span><b>01</b>贴英文段落</span><span><b>02</b>看硬错与语气</span><span><b>03</b>生成复练题</span></div>

  <p class="sub">给常写英文工作邮件的人：逐句指出问题，保留原片段，标明是语法、语气还是可选风格；反复出现的两三个问题会变成你的复练题。</p>
<div class="sub">每条指正都必须点名原文里的片段。查不到出处的，程序当场丢掉。</div>

<div class="row">
  <div class="panel">
    <h2>你的英文</h2>
    <textarea id="text" placeholder="Paste your paragraph here…"></textarea>
    <div class="btns">
      <button id="rule">只跑规则</button>
      <button id="model" class="ghost">让模型看一遍</button>
      <select id="lvl">
        <option value="">自评水平</option><option>A2</option><option>B1</option>
        <option>B2</option><option>C1</option>
      </select>
    </div>
    <div class="meta" id="summary"></div>
    <ul class="issues" id="ruleout"></ul>
  </div>
  <div class="panel">
    <h2>批改</h2>
    <div id="review"><div class="spin">左边写完，点「让模型看一遍」。</div></div>
  </div>
</div>

<div class="panel" style="margin-top:18px">
  <h2>练习记录</h2>
  <div id="list" class="meta">…</div>
</div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function showRule(d){
  $('summary').textContent=d.summary;
  const ul=$('ruleout');
  if(!d.issues.length){ul.innerHTML='<li class="why">本地规则没查出问题。</li>';return}
  ul.innerHTML=d.issues.map(i=>`<li><span class="tag t-rule">${esc(i.type)}</span>
    <span class="span">${esc(i.span)}</span><div class="why">${esc(i.why)}</div></li>`).join('');
}

async function post(path, body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return [r.status, await r.json().catch(()=>({}))];
}

$('rule').onclick=async()=>{
  const text=$('text').value;
  if(!text.trim()) return;
  const [st,d]=await post('/api/check',{text});
  if(st!==200){$('summary').textContent=d.error||'出错了';return}
  showRule(d);
};

$('model').onclick=async()=>{
  const text=$('text').value;
  if(!text.trim()) return;
  const b=$('model'); b.disabled=true; b.textContent='模型在看…';
  $('review').innerHTML='<div class="spin">正在逐句检查，十几秒…</div>';
  try{
    const [st,d]=await post('/api/review',{text,level:$('lvl').value});
    if(st!==200){$('review').innerHTML=`<div class="err">${esc(d.error||'出错了')}</div>`;
      if(d.issues) showRule({summary:d.summary||'',issues:d.issues}); return}
    showRule(d);
    $('review').innerHTML=renderReview(d.review)+(d.piece_id?`<div class="meta">已存为第 ${d.piece_id} 篇</div>`:'');
    loadList();
  }finally{ b.disabled=false; b.textContent='让模型看一遍'; }
};

function renderReview(r){
  if(r.error) return `<div class="err">${esc(r.error)}</div>`;
  let h='';
  if(r.level) h+=`<div class="meta">水平判断 <span class="level">${esc(r.level)}</span></div>`;
  if(r.comment) h+=`<div class="why" style="margin-bottom:10px">${esc(r.comment)}</div>`;
  h+=(r.sentences||[]).map(s=>{
    const iss=(s.issues||[]).map(i=>`<li><span class="tag t-model">${esc(i.type)}</span>
      <span class="span">${esc(i.span)}</span>${i.fixed?` → ${esc(i.fixed)}`:''}
      <div class="why">${esc(i.why)}</div></li>`).join('');
    return `<div class="sent"><div class="orig">${esc(s.original)}</div>
      ${iss?`<ul class="issues">${iss}</ul>`:''}
      ${s.rewrite?`<div class="fix">改：${esc(s.rewrite)}</div>`:''}</div>`;
  }).join('');
  if(r.rewrite) h+=`<div class="meta">整段改写</div><div class="sent"><div class="orig">${esc(r.rewrite)}</div></div>`;
  if((r.notes||[]).length) h+=r.notes.map(n=>`<div class="why">! ${esc(n)}</div>`).join('');
  return h;
}

async function loadList(){
  const r=await fetch('/api/list'); const d=await r.json();
  if(!d.pieces.length){$('list').textContent='还没有记录。';return}
  $('list').innerHTML=d.pieces.slice(0,8).map(p=>
    `<div>#${p.id} ${esc(p.title)} · ${p.chars} 词 · 规则 ${p.local_count} 处 · 模型 ${p.model_count} 处</div>`).join('')
    + (d.top.length?`<div style="margin-top:8px">最常被指出：${d.top.map(t=>esc(t.type)+' '+t.n+' 次').join('、')}</div>`:'');
}
loadList();
</script></div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "yuban/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._html(PAGE)
            return
        if path == "/api/list":
            conn = self.server.conn
            self._json({"pieces": store.list_pieces(conn), "top": store.top_types(conn, 3)})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path not in ("/api/check", "/api/review"):
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json({"error": "内容太长了，200KB 以内"}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "body 不是 JSON"}, 400)
            return

        text = (payload.get("text") or "").strip()
        if not text:
            self._json({"error": "没有正文"}, 400)
            return

        conn = self.server.conn
        local = checks.issues(text)
        base = {"summary": checks.summary(text), "issues": local}

        if path == "/api/check":
            self._json(base)
            return

        result = review.review(text, local, payload.get("level") or "")
        out = dict(base)
        out["review"] = result
        if result["error"]:
            self._json(out, 502)
            return
        with self.server.lock:
            pid = store.save_piece(
                conn, text, title=payload.get("title") or "", level=result["level"],
                comment=result["comment"], rewrite=result["rewrite"],
                sentences=result["sentences"], local=local,
                created=datetime.now().strftime("%Y-%m-%d %H:%M"))
        out["piece_id"] = pid
        self._json(out)


def make_server(conn, port: int = 0, db: str = "") -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.conn = conn
    srv.db = db
    srv.lock = threading.Lock()
    return srv
