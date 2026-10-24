"""Throwaway dot-plot viewer: renders a slice of tracking.jsonl into a self-contained HTML page.

Run: uv run python scripts/dot_viewer.py data/samples/match_42 --start 85:50 --end 86:30
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Dot viewer</title>
<style>body{margin:0;background:#f8f8f8;font:13px system-ui;color:#1a1a1a}
#w{max-width:1100px;margin:16px auto;padding:0 16px}canvas{width:100%%;background:#f0f0f0;
border-radius:24px}#c{display:flex;gap:12px;align-items:center;margin:8px 0}
#ev{font-family:monospace;white-space:pre;height:160px;overflow:auto;background:#fff;
border-radius:12px;padding:8px}</style></head><body><div id="w">
<div id="c"><button id="pp">pause</button><input id="s" type="range" min="0" style="flex:1">
<span id="clk"></span></div><canvas id="cv" width="1050" height="680"></canvas>
<div id="ev"></div></div><script>
const F=%s, E=%s, H=%s;
const cv=document.getElementById('cv'),g=cv.getContext('2d'),S=10,s=document.getElementById('s');
s.max=F.length-1;let i=0,play=true;
document.getElementById('pp').onclick=e=>{play=!play;e.target.textContent=play?'pause':'play'};
s.oninput=()=>{i=+s.value;draw()};
function line(a,b,c,d){g.beginPath();g.moveTo(a*S,680-b*S);g.lineTo(c*S,680-d*S);g.stroke()}
function draw(){const f=F[i];g.clearRect(0,0,1050,680);g.strokeStyle='rgba(0,0,0,.15)';
g.lineWidth=2;g.strokeRect(0,0,1050,680);line(52.5,0,52.5,68);
g.beginPath();g.arc(525,340,91.5,0,7);g.stroke();
g.strokeRect(0,340-201.6,165,403.2);g.strokeRect(1050-165,340-201.6,165,403.2);
for(const p of f.players){const home=p.id.startsWith(H);g.beginPath();
g.arc(p.x*S,680-p.y*S,9,0,7);g.fillStyle=home?'#1a1a1a':'#fff';g.fill();
g.strokeStyle='#1a1a1a';g.lineWidth=2;g.stroke();g.fillStyle=home?'#fff':'#1a1a1a';
g.font='9px monospace';g.textAlign='center';g.fillText(p.id.slice(4),p.x*S,680-p.y*S+3)}
const b=f.ball;g.beginPath();g.arc(b.x*S,680-b.y*S,4+b.z*1.2,0,7);g.fillStyle='#ba6603';g.fill();
const t=f.t_ms/1000;document.getElementById('clk').textContent=
String(Math.floor(t/60)).padStart(2,'0')+':'+(t%%60).toFixed(1).padStart(4,'0')+
'  owner '+(b.owner_id||'-');s.value=i;
document.getElementById('ev').textContent=E.filter(e=>e.t_ms<=f.t_ms).slice(-12).reverse()
.map(e=>(e.t_ms/1000).toFixed(1)+'s '+e.type+' '+(e.player_id||'')+' '+(e.outcome||'')+
' '+(e.tags||[]).join(',')).join('\\n')}
setInterval(()=>{if(play){i=(i+1)%%F.length;draw()}},100);draw();
</script></body></html>"""


def clock(s: str) -> int:
    m, sec = s.split(":")
    return round((int(m) * 60 + float(sec)) * 1000)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("match_dir", type=Path)
    ap.add_argument("--start", default="0:00")
    ap.add_argument("--end", default="1:00")
    ap.add_argument("--out", type=Path, default=Path("view.html"))
    a = ap.parse_args()
    lo, hi = clock(a.start), clock(a.end)
    frames = []
    with (a.match_dir / "tracking.jsonl").open(encoding="utf-8") as f:
        for line in f:
            t = int(line[line.index('"t_ms":') + 7 : line.index(',"period"')])
            if t > hi:
                break
            if t >= lo:
                frames.append(json.loads(line))
    events = [
        e
        for e in map(json.loads, (a.match_dir / "events.jsonl").open(encoding="utf-8"))
        if lo <= e["t_ms"] <= hi
    ]
    home = json.loads((a.match_dir / "meta.jsonl").read_text(encoding="utf-8"))["teams"][0]
    a.out.write_text(
        PAGE % (json.dumps(frames), json.dumps(events), json.dumps(home["team_id"])),
        encoding="utf-8",
    )
    print(f"wrote {a.out} ({len(frames)} frames, {len(events)} events)")


if __name__ == "__main__":
    main()
