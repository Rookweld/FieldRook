"""Generate a completely offline reviewer page from anonymous M033-D packets."""
from __future__ import annotations

import json
from typing import Any

TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; form-action 'none'; object-src 'none'; base-uri 'none'">
<title>FieldRook — Blinded Diagnostic Review</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0e141b;color:#e4edf4}
*{box-sizing:border-box}body{margin:0;line-height:1.5}
header{position:sticky;top:0;z-index:10;background:#121f29;border-bottom:1px solid #2e414e;padding:14px max(18px,4vw);display:flex;align-items:center;gap:14px;flex-wrap:wrap}
h1{font-size:1.2rem;margin:0}header p{margin:0;color:#99b7c3;font-size:.83rem;flex:1 1 250px}
button,.file-btn{border:1px solid #426477;border-radius:9px;background:#183849;color:#e8f5fb;padding:10px 14px;cursor:pointer;font-weight:600}
button:hover,.file-btn:hover{background:#235267}button:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #46d0db}
button.primary{background:#146a74;border-color:#2ca7ab}
main{max-width:1550px;margin:auto;padding:25px max(16px,3vw)}
section{margin:0 0 38px;padding:20px;border:1px solid #334553;border-radius:16px;background:#17222d}
h2{margin:0 0 5px;font-size:1.16rem}h3{margin:0 0 13px;font-size:1rem}
.meta{color:#abc6d0;font-size:.89rem}.reference{margin:12px 0 18px;border-left:3px solid #69abb5;padding:10px 15px;background:#172e39;color:#d3e9eb}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.panel{padding:16px;border-radius:11px;background:#0e1a23;border:1px solid #304956;min-width:0}
pre{font:12.5px/1.52 Consolas,ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;color:#c9dfeb;margin:8px 0 20px;max-height:450px;overflow-y:auto;padding:10px;border:1px solid #263e4a;background:#09141d;border-radius:8px}
.scores{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:flex;flex-direction:column;gap:5px;font-size:.85rem;color:#acc8d2}
select,textarea{background:#10232f;color:#eaf5fa;padding:8px;border:1px solid #436174;border-radius:7px;font:inherit;width:100%}
textarea{min-height:75px;resize:vertical}.rationale{margin-top:12px}
.small{font-size:.78rem;color:#b6d0d9}
#notice{color:#ecc27e;font-size:.85rem}
@media(max-width:850px){.grid{grid-template-columns:1fr}.scores{grid-template-columns:1fr 1fr}header{position:static}}
</style></head><body>
<header><h1>FieldRook / M033-D</h1><p>Blind technician review. Six A/B pairs · 12 real diagnostic transcripts · offline only.</p>
<strong id="progress" aria-live="polite">0 / 12 rated</strong>
<button id="export" class="primary">Export scores.json</button>
<label class="file-btn" for="import" style="display:block">Import scores.json</label><input id="import" type="file" accept=".json,application/json" hidden>
<span id="notice" role="status"></span>
</header>
<main><p class="meta">The model names, experimental modes, timings and automated pass/fail scores are intentionally hidden. Grade whether each suggested diagnostic step distinguishes useful outcomes, preserves evidence, is safe, and handles uncertainty. Do not open the private answer key before scoring.</p><div id="content"></div></main>
<script id="packet" type="application/json">__PACKET_JSON__</script>
<script>
"use strict";
const PACKET=JSON.parse(document.getElementById("packet").textContent);
const RANGES={discrimination:3,fidelity:3,actionability:2,calibration:2};
const ratings={};
const pairs=PACKET.pairs;
function el(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node}
function completed(r){return Object.keys(RANGES).every(k=>Number.isInteger(r[k])&&r[k]>=0&&r[k]<=RANGES[k])&&r.rationale.trim().length>=12}
function update(){
  const count=Object.values(ratings).filter(completed).length;
  document.getElementById("progress").textContent=count+" / 12 rated";
  document.getElementById("notice").textContent=count===12?"All ratings complete. Export and evaluate to unblind.":"Complete every axis and a brief rationale for all 12.";
}
for(const pair of pairs){
  const sec=el("section");sec.append(el("h2",null,pair.id+" · "+pair.case));
  const ref=el("div","reference");
  for(const v of ["probe","outcome_1","outcome_2","note"]){ref.append(el("p",null,pair.counterfactuals[v]))}
  sec.append(ref);
  const grid=el("div","grid");
  for(const item of pair.candidates){
    ratings[item.id]={discrimination:null,fidelity:null,actionability:null,calibration:null,rationale:""};
    const panel=el("article","panel");
    panel.append(el("h3",null,item.id),el("pre",null,item.transcript));
    const scores=el("div","scores");
    for(const [axis,maxScore] of Object.entries(RANGES)){
      const label=el("label",null,axis.replaceAll("_"," ")+" · 0–"+maxScore);
      const select=el("select");select.setAttribute("aria-label",item.id+" "+axis);
      const empty=el("option",null,"Choose score");empty.value="";select.append(empty);
      for(let i=0;i<=maxScore;i++){const op=el("option",null,String(i));op.value=String(i);select.append(op)}
      select.dataset.case=item.id;select.dataset.axis=axis;
      select.addEventListener("change",()=>{ratings[item.id][axis]=select.value===""?null:Number(select.value);update()});
      label.append(select);scores.append(label);
    }
    panel.append(scores);
    const lab=el("label","rationale","Reason / concrete observation (at least 12 characters)");
    const area=el("textarea");area.setAttribute("aria-label",item.id+" rationale");
    area.dataset.case=item.id;area.addEventListener("input",()=>{ratings[item.id].rationale=area.value;update()});
    lab.append(area);panel.append(lab);grid.append(panel);
  }
  sec.append(grid);document.getElementById("content").append(sec);
}
document.getElementById("export").addEventListener("click",()=>{
  const data={schema:"m033d.1",status:Object.values(ratings).every(completed)?"HUMAN_RATED":"UNRATED",ratings};
  const blob=new Blob([JSON.stringify(data,null,2)+"\n"],{type:"application/json"});
  const url=URL.createObjectURL(blob);const anchor=document.createElement("a");
  anchor.href=url;anchor.download="scores.json";document.body.append(anchor);anchor.click();
  anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
  document.getElementById("notice").textContent="Scores exported. Replace review/scores.json with the downloaded file.";
});
document.getElementById("import").addEventListener("change",async(event)=>{
  const file=event.target.files?.[0];if(!file)return;
  try {
    if(file.size>300000)throw Error("Input file too large");
    const incoming=JSON.parse(await file.text());
    if(incoming.schema!=="m033d.1"||!incoming.ratings||Object.keys(incoming.ratings).sort().join("|")!==Object.keys(ratings).sort().join("|"))
      throw Error("Score IDs or schema do not match this review");
    for(const [id,r] of Object.entries(incoming.ratings)){
      if(!r||typeof r!=="object")throw Error("Bad rating");
      for(const [metric,max] of Object.entries(RANGES)){
        const value=r[metric];if(value!==null&&(!Number.isInteger(value)||value<0||value>max))throw Error("Invalid score");
        ratings[id][metric]=value;
        document.querySelector('select[data-case="'+id+'"][data-axis="'+metric+'"]').value=value===null?"":String(value);
      }
      if(typeof r.rationale!=="string")throw Error("Invalid rationale");
      ratings[id].rationale=r.rationale;
      document.querySelector('textarea[data-case="'+id+'"]').value=r.rationale;
    }
    update();document.getElementById("notice").textContent="Review scores imported.";
  } catch(err){document.getElementById("notice").textContent="Import rejected: "+err.message}
  event.target.value="";
});
update();
</script></body></html>
"""

def render_html(packet: dict[str, Any]) -> str:
    # Avoid inline-script closure even when an adversarial model emits markup.
    encoded = json.dumps(packet, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.replace("__PACKET_JSON__", encoded)
