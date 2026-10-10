const $ = (id) => document.getElementById(id);
const stages = ["阶段 A", "阶段 B", "阶段 C", "阶段 D", "阶段 E", "阶段 F", "阶段 G"];
const projects = {
  east: {
    name: "东安隧道", metric: "超挖面积", unit: "㎡", threshold: "超挖面积 ≥ 6.0 ㎡ 为橙色、≥ 5.0 ㎡ 为黄色", ruleLine: 145,
    summary: "113 个分析断面；最大超挖面积 6.710 ㎡（DK082+498.000）；79 条预警为历史汇总。",
    segments: [
      ["DK082+498.000", [3.2,4.1,5.0,5.6,6.1,6.4,6.710], "最大值为公开汇总，其余阶段模拟"],
      ["DK082+510.000", [2.8,3.2,4.2,4.8,5.2,5.7,6.3], "模拟区段及数值"],
      ["DK082+522.000", [2.1,2.5,3.4,3.9,4.5,5.1,5.5], "模拟区段及数值"],
      ["DK082+534.000", [1.6,2.0,2.4,2.7,3.0,3.3,3.7], "模拟区段及数值"],
      ["DK082+546.000", [2.1,2.3,2.9,3.8,4.6,5.0,5.2], "模拟区段及数值"],
      ["DK082+558.000", [1.5,1.9,2.4,2.8,3.0,3.5,3.8], "模拟区段及数值"],
      ["DK082+570.000", [2.2,2.9,3.4,4.2,4.8,5.3,5.8], "模拟区段及数值"],
      ["DK082+582.000", [1.8,2.1,2.4,2.8,3.1,3.5,4.0], "模拟区段及数值"]
    ]
  },
  douli: {
    name: "豆里冲隧道", metric: "拱顶下沉", unit: "mm", threshold: "拱顶下沉 ≥ 15.0 mm 为红色、≥ 10.0 mm 为橙色", ruleLine: 173,
    summary: "241 条监控量测记录；最大变形值 16.40 mm（拱顶下沉）；16 条预警为历史汇总。",
    segments: [
      ["示例测点 A", [2.3,4.5,6.8,9.4,12.0,14.5,16.40], "最大值为公开汇总，测点与过程模拟"],
      ["示例测点 B", [1.4,2.3,3.0,4.1,5.5,7.4,10.2], "模拟测点及数值"],
      ["示例测点 C", [2.1,3.1,4.5,5.8,7.2,9.1,11.6], "模拟测点及数值"],
      ["示例测点 D", [1.3,1.8,2.4,3.1,3.6,4.2,4.7], "模拟测点及数值"],
      ["示例测点 E", [1.5,2.4,3.6,4.8,6.5,8.0,9.4], "模拟测点及数值"],
      ["示例测点 F", [2.3,3.9,5.7,8.2,10.1,12.2,15.1], "模拟测点及数值"],
      ["示例测点 G", [1.4,2.0,3.0,4.6,6.1,7.0,8.8], "模拟测点及数值"],
      ["示例测点 H", [1.1,1.9,2.5,3.1,3.8,4.4,5.3], "模拟测点及数值"]
    ]
  }
};

let state = {tunnel: "east", index: 0, stage: 6, timer: null};
let sceneApi = null;
const project = () => projects[state.tunnel];
const segment = () => project().segments[state.index];
const valueAt = (row, stage) => row[1][stage];
function riskFor(key, value) {
  if (key === "east") return value >= 6 ? {name:"橙色 · 重点跟踪", css:"orange", short:"橙色"} : value >= 5 ? {name:"黄色 · 持续关注", css:"yellow", short:"黄色"} : {name:"正常 · 常态监测", css:"green", short:"正常"};
  return value >= 15 ? {name:"红色 · 立即复核", css:"red", short:"红色"} : value >= 10 ? {name:"橙色 · 重点跟踪", css:"orange", short:"橙色"} : {name:"正常 · 常态监测", css:"green", short:"正常"};
}
function adviceFor(key, risk) {
  if (risk.css === "green") return "保持例行复测，核对测点或断面成果与现场记录。";
  if (key === "east") return "复核该断面开挖轮廓，检查钻爆参数与初支喷混凝土消耗，并跟踪邻近断面。";
  return risk.css === "red" ? "立即复核测点和初支状态，必要时组织现场会商。" : "重点跟踪该断面拱顶变形，核查支护闭合情况。";
}
function iconRefresh() { if (window.lucide) window.lucide.createIcons(); }
function make(tag, className, text) { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; }
function renderProfile() {
  const amplitude = state.tunnel === "east" ? valueAt(segment(), state.stage) * 1.6 : valueAt(segment(), state.stage) * .6;
  const observed = `M 48 88 L 48 70 C 48 ${40-amplitude} 79 ${15-amplitude/2} 140 ${16-amplitude/3} C 202 ${15-amplitude/2} 232 ${40+amplitude/3} 232 70 L 232 88`;
  $("profile").innerHTML = `<svg viewBox="0 0 280 105" role="img" aria-label="设计轮廓与模拟实测轮廓对比"><path d="M 54 89 L 54 70 C 54 38 81 22 140 22 C 199 22 226 38 226 70 L 226 89" fill="none" stroke="#78bde8" stroke-width="2" stroke-dasharray="5 4"/><path d="${observed}" fill="none" stroke="#f39a51" stroke-width="2.5"/><line x1="36" y1="89" x2="246" y2="89" stroke="#466165"/><text x="10" y="15" fill="#8fa3a6" font-size="9">设计 ···  /  模拟实测 —</text></svg>`;
}
function render() {
  const p = project(), s = segment(), value = valueAt(s, state.stage), risk = riskFor(state.tunnel, value);
  $("tunnelSelect").value = state.tunnel;
  $("segmentCount").textContent = `${p.segments.length} 区段`;
  $("segmentList").replaceChildren(...p.segments.map((row, index) => {
    const level = riskFor(state.tunnel, valueAt(row, state.stage));
    const b = make("button", `segment-btn${index === state.index ? " active" : ""}`);
    b.type = "button"; b.setAttribute("aria-label", `${row[0]}，${level.name}`); b.setAttribute("aria-pressed", index === state.index);
    const dot = make("span", `risk-dot ${level.css}`), labels = make("span");
    labels.append(make("strong", "", row[0]), make("small", "", index === 0 ? "重点区段" : `演示区段 ${index + 1}`));
    b.append(dot, labels, make("em", "", `${valueAt(row, state.stage).toFixed(1)} ${p.unit}`));
    b.addEventListener("click", () => selectSegment(index)); return b;
  }));
  $("heatline").replaceChildren(...p.segments.map((row, index) => {
    const level = riskFor(state.tunnel, valueAt(row, state.stage)); const b = make("button", `heat-cell ${level.css}${index === state.index ? " active" : ""}`);
    b.type="button"; b.title=`${row[0]} · ${level.name}`; b.setAttribute("aria-label", b.title); b.setAttribute("aria-pressed", index === state.index);
    b.addEventListener("click", () => selectSegment(index)); return b;
  }));
  $("detailStation").textContent = s[0]; $("detailTunnel").textContent = p.name; $("sceneStation").textContent = s[0];
  $("riskBadge").textContent = risk.short; $("riskBadge").className = `risk-badge ${risk.css}`;
  $("sceneRisk").textContent = risk.name; $("sceneRisk").className = risk.css;
  $("primaryLabel").textContent = p.metric; $("primaryValue").textContent = `${value.toFixed(2)} ${p.unit}`;
  const rate = state.stage ? value - valueAt(s, state.stage-1) : 0;
  $("rateValue").textContent = `${rate >= 0 ? "+" : ""}${rate.toFixed(2)} ${p.unit}/阶段`;
  $("riskReason").textContent = `${p.threshold}。当前值 ${value.toFixed(2)} ${p.unit}，按原型规则判为${risk.short}。`;
  $("riskAdvice").textContent = adviceFor(state.tunnel, risk);
  $("dataSource").textContent = `${s[2]}；阈值见 build_control_platform.py。`;
  $("explanation").hidden = true;
  $("timeSlider").value = String(state.stage); $("dateLabel").textContent = stages[state.stage];
  $("trendTitle").textContent = `${p.metric} · ${s[0]}`; $("trendValue").textContent = `${value.toFixed(2)} ${p.unit}`;
  const peak = Math.max(...s[1], 1);
  $("trendChart").replaceChildren(...s[1].map((v,i) => { const bar=make("div", `trend-bar${i === state.stage ? " current" : ""}`); bar.style.setProperty("--h", `${Math.max(7,v/peak*95)}%`); bar.title=`${stages[i]}：${v.toFixed(2)} ${p.unit}`; return bar; }));
  renderProfile(); if (sceneApi) sceneApi.update(state.index, p.segments.map(row => riskFor(state.tunnel, valueAt(row,state.stage)).css));
}
function selectSegment(index) { state.index = index; render(); }
function stopPlayback() { clearInterval(state.timer); state.timer = null; $("playButton").setAttribute("aria-label", "播放回放"); $("playButton").title="播放回放"; $("playButton").innerHTML='<i data-lucide="play"></i>'; iconRefresh(); }
function setView(id) {
  stopPlayback(); document.querySelectorAll(".view").forEach(el => el.classList.toggle("active", el.id === id));
  document.querySelectorAll(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.view === id));
  if (id === "report") { $("reportTunnel").value=state.tunnel; $("reportStage").value=String(state.stage); renderReport(); }
  if (id === "patrol") { $("patrolTunnel").value=state.tunnel; fillPatrolSegments(state.index); }
  if (id === "simulation") { $("simulationTunnel").value=state.tunnel; $("simulationStage").value=String(state.stage); renderSimulation(); }
  if (id === "cockpit" && sceneApi) sceneApi.resize();
  history.replaceState(null,"",`#${id}`); window.scrollTo(0,0);
}
function explain() {
  const p=project(), s=segment(), current=valueAt(s,state.stage), risk=riskFor(state.tunnel,current);
  const box=$("explanation"); box.replaceChildren();
  box.append(make("strong","", "规则依据 · 非 AI 生成"), make("p","",`${stages[state.stage]}，${s[0]} 的演示值为 ${current.toFixed(2)} ${p.unit}；${p.threshold}，判定为${risk.short}。`), make("p","", `数据来源：${s[2]}。${p.summary}`));
  const link=make("a","", "查看仓库中的预警规则 ↗"); link.href=`https://github.com/dytvvandrew/tunnel/blob/main/build_control_platform.py#L${p.ruleLine}`; link.target="_blank"; link.rel="noreferrer"; box.append(link); box.hidden=false;
}

function escapeHtml(value) { return String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[char]); }
function renderReport() {
  const key=$("reportTunnel").value, stage=Number($("reportStage").value), p=projects[key], rows=p.segments;
  const counts={red:0,orange:0,yellow:0,green:0}; rows.forEach(row => counts[riskFor(key,valueAt(row,stage)).css]++);
  const lead=rows.map(row => ({name:row[0], value:valueAt(row,stage)})).sort((a,b)=>b.value-a.value)[0];
  const note=$("reportNote").value.trim();
  $("reportPreview").innerHTML=`<div class="report-sheet"><span class="eyebrow">PUBLIC DEMO / DAILY BRIEF</span><h2>${escapeHtml(p.name)} · 工程日报</h2><div class="report-meta">${escapeHtml(stages[stage])} · 公开演示生成 · 非真实日期日报</div><div class="report-kpis"><div><small>演示区段</small><strong>${rows.length}</strong></div><div><small>重点 / 立即复核</small><strong>${counts.orange+counts.red}</strong></div><div><small>最高演示指标</small><strong>${lead.value.toFixed(2)} ${escapeHtml(p.unit)}</strong></div></div><h3>区段观察</h3><ul><li>${escapeHtml(lead.name)}：${lead.value.toFixed(2)} ${escapeHtml(p.unit)}，${escapeHtml(riskFor(key,lead.value).name)}。</li><li>${escapeHtml(p.threshold)}；规则见仓库 build_control_platform.py。</li><li>公开汇总：${escapeHtml(p.summary)}</li></ul><h3>建议</h3><p>${escapeHtml(adviceFor(key,riskFor(key,lead.value)))}</p>${note?`<h3>编制说明</h3><p>${escapeHtml(note)}</p>`:""}<p class="disclaimer">本报告的区段和阶段为模拟数据，不含原始资料，不得用于现场安全决策。现场使用须接入服务器端数据并经工程人员复核。</p></div>`;
}

const patrolItems = ["核对断面或测点编号与现场标识", "复测异常指标并记录原始读数", "检查初支、拱顶与周边可见变化", "留存现场照片及测量时间", "联系负责人员确认处置与复测计划"];
function storageKey() { return `tunnel-patrol-v1:${$("patrolTunnel").value}:${$("patrolSegment").value}`; }
function readPatrol() { try { return JSON.parse(localStorage.getItem(storageKey())) || {checks:[],note:""}; } catch { return {checks:[],note:""}; } }
function savePatrol() { const checks=[...$("checklist").querySelectorAll("input")].map(el=>el.checked); try { localStorage.setItem(storageKey(),JSON.stringify({checks,note:$("patrolNote").value})); } catch {} $("patrolProgress").textContent=`${checks.filter(Boolean).length} / ${checks.length} 已核查`; }
function fillPatrolSegments(selected=0) {
  const p=projects[$("patrolTunnel").value]; $("patrolSegment").replaceChildren(...p.segments.map((row,i)=>{const opt=make("option","",row[0]); opt.value=String(i); return opt;})); $("patrolSegment").value=String(selected); renderPatrol();
}
function renderPatrol() {
  const key=$("patrolTunnel").value, index=Number($("patrolSegment").value), p=projects[key], row=p.segments[index], level=riskFor(key,valueAt(row,6)), saved=readPatrol();
  $("patrolContext").textContent=`${p.name} · ${row[0]} · ${level.name}。${row[2]}，现场应重新测量确认。`;
  $("checklist").replaceChildren(...patrolItems.map((item,i)=>{const label=make("label","check-row"), input=make("input"); input.type="checkbox"; input.checked=Boolean(saved.checks[i]); input.addEventListener("change",savePatrol); label.append(input,make("span","",item)); return label;}));
  $("patrolNote").value=saved.note || ""; $("patrolProgress").textContent=`${saved.checks.filter(Boolean).length} / ${patrolItems.length} 已核查`;
}
function renderSimulation() {
  const key=$("simulationTunnel").value, stage=Number($("simulationStage").value), multiplier=1+Number($("disturbance").value)/100, p=projects[key];
  $("disturbanceValue").textContent=`+${Math.round((multiplier-1)*100)}%`;
  const rows=p.segments.map(row=>{const base=valueAt(row,stage), simulated=base*multiplier, before=riskFor(key,base), after=riskFor(key,simulated);return {row,base,simulated,before,after};});
  const changed=rows.filter(item=>item.before.css!==item.after.css).length;
  $("simulationSummary").innerHTML=`<strong>${changed}</strong><span> / ${rows.length} 个区段会发生等级变化</span><small>当前条件：${stages[stage]} · 指标增幅 +${Math.round((multiplier-1)*100)}%</small>`;
  $("simulationRows").replaceChildren(...rows.map(item=>{const line=make("div","simulation-row");const text=make("span");text.append(make("strong","",item.row[0]),make("small","",`${item.base.toFixed(2)} → ${item.simulated.toFixed(2)} ${p.unit}`));const arrow=make("b","",item.before.short===item.after.short?"→":"↗");const levels=make("span",`sim-level ${item.after.css}`,item.after.short);line.append(text,arrow,levels);return line;}));
}

function parseCsv(text) {
  const rows=[]; let row=[], value="", quoted=false;
  const source=text.replace(/^\uFEFF/,"");
  for(let i=0;i<source.length;i++) { const char=source[i];
    if(char==='"') { if(quoted && source[i+1]==='"') {value+='"';i++;} else quoted=!quoted; }
    else if(char===',' && !quoted) {row.push(value);value="";}
    else if((char==='\n'||char==='\r') && !quoted) {if(char==='\r'&&source[i+1]==='\n') i++;row.push(value);if(row.some(cell=>cell.trim())) rows.push(row);row=[];value="";}
    else value+=char;
  }
  if(quoted) throw new Error("CSV 引号未闭合");
  row.push(value); if(row.some(cell=>cell.trim())) rows.push(row);
  return rows;
}
function inspectCsv(text, name) {
  const issues=[]; let rows;
  try { rows=parseCsv(text); } catch(error) { rows=[]; issues.push({type:"warn",text:error.message}); }
  const required=["tunnel","station","date","metric","value","unit"];
  const headers=(rows[0]||[]).map(h=>h.trim().toLowerCase());
  required.filter(h=>!headers.includes(h)).forEach(h=>issues.push({type:"warn",text:`缺少字段：${h}`}));
  if(!rows.length) issues.push({type:"warn",text:"文件为空或无有效记录"});
  const seen=new Set(); let valid=0;
  if(required.every(h=>headers.includes(h))) rows.slice(1).forEach((cells,i)=>{
    const r=Object.fromEntries(required.map(h=>[h,(cells[headers.indexOf(h)]||"").trim()]));
    const line=i+2; let failed=false;
    if(cells.length!==headers.length) {issues.push({type:"warn",text:`第 ${line} 行：列数与表头不一致`});failed=true;}
    if(!r.tunnel||!r.station||!r.metric||!r.unit) {issues.push({type:"warn",text:`第 ${line} 行：关键字段为空`});failed=true;}
    const parsed=Number(r.value); if(!r.value||!Number.isFinite(parsed)||parsed<0) {issues.push({type:"warn",text:`第 ${line} 行：value 应为非负数`});failed=true;}
    if(!/^\d{4}-\d{2}-\d{2}$/.test(r.date)||Number.isNaN(Date.parse(`${r.date}T00:00:00Z`))||new Date(`${r.date}T00:00:00Z`).toISOString().slice(0,10)!==r.date) {issues.push({type:"warn",text:`第 ${line} 行：date 应为真实日期 YYYY-MM-DD`});failed=true;}
    const identity=[r.tunnel,r.station,r.date,r.metric].join("|");if(seen.has(identity)) {issues.push({type:"warn",text:`第 ${line} 行：隧道/区段/日期/指标重复`});failed=true;}seen.add(identity);
    if(!failed) valid++;
  });
  $("qualityStatus").textContent=issues.length?`${issues.length} 项待核对`:"预检通过";
  $("qualitySummary").replaceChildren(make("strong","",String(Math.max(0,rows.length-1))),make("span","",` 条记录 · ${valid} 条通过 · ${name}`));
  $("qualityIssues").replaceChildren(...(issues.length?issues.slice(0,30).map(item=>make("div",`issue ${item.type}`,item.text)):[make("div","issue ok","字段、日期、数值和重复键均通过基础检查。")]));
  if(issues.length>30) $("qualityIssues").append(make("div","issue warn",`另有 ${issues.length-30} 项，请在服务器版或本地表格继续核对。`));
}
function downloadCsv() { const content="tunnel,station,date,metric,value,unit\n"; const link=make("a"); link.href=URL.createObjectURL(new Blob(["\uFEFF",content],{type:"text/csv;charset=utf-8"})); link.download="tunnel-import-template.csv";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000); }

async function initScene() {
  const host=$("scene"), fallback=$("sceneFallback");
  try {
    const THREE=await import("three"), {OrbitControls}=await import("three/addons/controls/OrbitControls.js");
    const scene=new THREE.Scene(); scene.background=new THREE.Color(0x101b1e); scene.fog=new THREE.Fog(0x101b1e,20,52);
    const camera=new THREE.PerspectiveCamera(48,1,.1,100); camera.position.set(9,5,8);
    const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false}); renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.setSize(host.clientWidth,host.clientHeight); host.append(renderer.domElement);
    scene.add(new THREE.HemisphereLight(0xa9f0e3,0x203439,2.1)); const light=new THREE.DirectionalLight(0xf8c88a,2.3);light.position.set(-4,9,7);scene.add(light);
    const grid=new THREE.GridHelper(50,30,0x36535a,0x274045);grid.position.y=-1.72;scene.add(grid);
    const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.maxDistance=32;controls.minDistance=5;controls.target.set(0,0,-6);controls.update();
    const meshes=[], edges=[];
    function horseshoe() {
      const shape=new THREE.Shape(); shape.moveTo(-3,-1.55);shape.lineTo(-3,0);shape.absarc(0,0,3,Math.PI,0,true);shape.lineTo(3,-1.55);shape.closePath();
      const hole=new THREE.Path();hole.moveTo(-2.66,-1.3);hole.lineTo(2.66,-1.3);hole.lineTo(2.66,0);hole.absarc(0,0,2.66,0,Math.PI,false);hole.lineTo(-2.66,-1.3);shape.holes.push(hole);return shape;
    }
    const geometry=new THREE.ExtrudeGeometry(horseshoe(),{depth:1.76,bevelEnabled:false,curveSegments:32});
    for(let i=0;i<8;i++) {
      const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x304b50,roughness:.72,metalness:.18,transparent:true,opacity:.72,side:THREE.DoubleSide}));mesh.position.z=-i*1.9;mesh.userData.index=i;scene.add(mesh);meshes.push(mesh);
      const edge=new THREE.LineSegments(new THREE.EdgesGeometry(geometry,25),new THREE.LineBasicMaterial({color:0x61999a,transparent:true,opacity:.58}));edge.position.z=mesh.position.z;scene.add(edge);edges.push(edge);
    }
    for(const x of [-1.8,1.8]) {const rail=new THREE.Mesh(new THREE.BoxGeometry(.055,.055,18),new THREE.MeshStandardMaterial({color:0x72b9ba,emissive:0x166462,emissiveIntensity:.45}));rail.position.set(x,-1.58,-5.8);scene.add(rail);}
    const raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2();let down=null;
    renderer.domElement.addEventListener("pointerdown",event=>{down=[event.clientX,event.clientY]});
    renderer.domElement.addEventListener("pointerup",event=>{if(!down||Math.hypot(event.clientX-down[0],event.clientY-down[1])>5)return;const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObjects(meshes)[0];if(hit) selectSegment(hit.object.userData.index);});
    function resize(){const width=host.clientWidth,height=host.clientHeight;if(!width||!height)return;camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setSize(width,height);}
    new ResizeObserver(resize).observe(host); resize();
    function update(index, levels){meshes.forEach((mesh,i)=>{const colors={green:0x2c7775,yellow:0xb29143,orange:0xcf7040,red:0xb84450};mesh.material.color.setHex(colors[levels[i]]);mesh.material.opacity=i===index?.96:.38;edges[i].material.color.setHex(i===index?0x93eee1:0x5c9192);edges[i].material.opacity=i===index?1:.42;});controls.target.set(0,0,-index*1.9);camera.position.set(9,5,8-index*1.9);controls.update();}
    function animate(){requestAnimationFrame(animate);controls.update();renderer.render(scene,camera);}animate();
    sceneApi={update,resize,reset(){camera.position.set(9,5,8-state.index*1.9);controls.target.set(0,0,-state.index*1.9);controls.update();}};
    render();
  } catch(error) { fallback.hidden=false; console.warn("三维场景未加载：",error); }
}

document.querySelectorAll(".nav-item").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
$("tunnelSelect").addEventListener("change",e=>{state.tunnel=e.target.value;state.index=0;render();});
$("timeSlider").addEventListener("input",e=>{state.stage=Number(e.target.value);render();});
$("playButton").addEventListener("click",()=>{if(state.timer){stopPlayback();return;}if(state.stage===6)state.stage=0;render();$("playButton").setAttribute("aria-label","暂停回放");$("playButton").title="暂停回放";$("playButton").innerHTML='<i data-lucide="pause"></i>';iconRefresh();state.timer=setInterval(()=>{if(state.stage>=6){stopPlayback();return;}state.stage++;render();},1100);});
$("resetCamera").addEventListener("click",()=>sceneApi?.reset());$("explainBtn").addEventListener("click",explain);
$("reportStage").replaceChildren(...stages.map((label,i)=>{const option=make("option","",label);option.value=String(i);return option;}));
$("generateReport").addEventListener("click",renderReport);$("reportTunnel").addEventListener("change",renderReport);$("reportStage").addEventListener("change",renderReport);$("printReport").addEventListener("click",()=>window.print());
$("patrolTunnel").addEventListener("change",()=>fillPatrolSegments());$("patrolSegment").addEventListener("change",renderPatrol);$("patrolNote").addEventListener("input",savePatrol);
$("openSection").addEventListener("click",()=>{state.tunnel=$("patrolTunnel").value;state.index=Number($("patrolSegment").value);state.stage=6;setView("cockpit");render();});
$("simulationStage").replaceChildren(...stages.map((label,i)=>{const option=make("option","",label);option.value=String(i);return option;}));$("simulationTunnel").addEventListener("change",renderSimulation);$("simulationStage").addEventListener("change",renderSimulation);$("disturbance").addEventListener("input",renderSimulation);
$("csvFile").addEventListener("change",async e=>{const file=e.target.files?.[0];if(!file)return;if(file.size>5*1024*1024){$("qualityStatus").textContent="文件超过 5 MB";return;}inspectCsv(await file.text(),file.name);});
$("sampleCsv").addEventListener("click",()=>inspectCsv("tunnel,station,date,metric,value,unit\n东安隧道,DK082+498,2026-10-01,超挖面积,6.710,㎡\n东安隧道,DK082+498,2026-10-01,超挖面积,6.710,㎡\n豆里冲隧道,测点A,2026-13-01,拱顶下沉,16.40,mm", "内置演示样例"));
$("downloadTemplate").addEventListener("click",downloadCsv);
render();renderReport();fillPatrolSegments();renderSimulation();iconRefresh();initScene();
if(["quality","report","patrol","simulation"].includes(location.hash.slice(1)))setView(location.hash.slice(1));
if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(error => console.warn("离线缓存未启用：", error));
