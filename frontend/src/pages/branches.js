import {state} from '../stores/session.js';import {esc} from '../utils/html.js';import {table} from '../components/common/table.js';import {field} from '../components/common/fields.js';import {badge} from '../components/common/status.js';import {CORRECTION_FIELDS,BRANCH_STATES} from '../constants/enums.js';
const b=()=>state.selectedBranch;
const statusBadge=s=>`<span class="tag ${s==='published'?'ok':s==='conflict'||s==='trial_failed'||s==='publish_failed'?'bad':''}">${esc(BRANCH_STATES[s]||s)}</span>`;
function trialPanel(){
 let x=b();if(!x)return '<p class="notice">先建立分支，再按小时批量修订工况或耗电。</p>';
 let tr=x.trial_result;
 if(x.status==='trialing')return '<p class="notice">试算进行中，稍后刷新。试算与正式训练隔离，不影响正式样本。</p>';
 if(!tr)return `<p class="notice">${x.status==='trial_failed'?esc(x.error||'试算失败'):'分支已有修订后可发起试算。基线与分支共用同一时间窗，各自仅用训练段选 alpha。'}</p>`;
 return `<h3>试算对比 · 共用时间窗 ${esc(tr.window.start)} 至 ${esc(tr.window.end)}（${tr.window.hours} 小时）</h3>
 <div class="metrics">${tr.metrics.map(m=>`<div><strong>${m.branch.toFixed(3)}</strong>${esc(m.label)}<br><span class="eyebrow">基线 ${m.baseline.toFixed(3)} · 差 ${m.delta>=0?'+':''}${m.delta.toFixed(3)}</span></div>`).join('')}</div>
 <div class="result-grid"><div><h4>基线选参与系数</h4>${table(['α','CV RMSE'],[[tr.baseline.selected_alpha,tr.baseline.cv_rmse.toFixed(4)]])}${table(['特征','标准化','原单位'],tr.baseline.coefficients.map(c=>[CORRECTION_FIELDS[c.feature],c.standardized.toFixed(4),c.original_unit.toFixed(4)]))}</div>
 <div><h4>分支选参与系数</h4>${table(['α','CV RMSE'],[[tr.branch.selected_alpha,tr.branch.cv_rmse.toFixed(4)]])}${table(['特征','标准化','原单位'],tr.branch.coefficients.map(c=>[CORRECTION_FIELDS[c.feature],c.standardized.toFixed(4),c.original_unit.toFixed(4)]))}</div></div>`;
}
function diffPanel(){
 let x=b();if(!x||!x.diff?.length)return '<p class="notice">尚无字段差异。</p>';
 return `<h3>逐字段差异核对（基线 / 分支 / 当前正式）</h3>${table(['小时','字段','基线','分支试算','当前正式','状态'],x.diff.map(d=>[d.hour,CORRECTION_FIELDS[d.field],d.baseline,d.branch,d.current,d.conflict?'冲突':'待发布']))}`;
}
function conflictPanel(){
 let x=b();if(x.status!=='conflict'||!x.error)return '';
 let list=[];try{list=JSON.parse(x.error)}catch(e){}
 if(!list.length)return `<p class="notice">${esc(x.error)}</p>`;
 return `<h3 class="bad">发布被拒：检测到 ${list.length} 处字段冲突</h3>${table(['小时','字段','基线','分支值','当前正式','原因'],list.map(c=>[c.hour,CORRECTION_FIELDS[c.field]||c.field,c.baseline,c.branch,c.current,c.reason]))}<p class="notice">双方同字段异值，已拒绝发布。请协调后新建分支或修订当前样本再试。</p>`;
}
export function render(){
 let x=b();let readonly=state.user.role==='viewer';
 return `<div class="split"><section class="panel">
 <h2>仪表纠偏 · 试算先行，发布隔离</h2>
 <p class="notice">分支保留基线快照，修订只在试算视图生效；正式训练始终读取正式样本。发布按基线/分支/当前三方逐字段合并，同字段异值即冲突拒绝。</p>
 <h3>修订分支</h3>
 <div class="branch-list">${state.branches.map(z=>`<button class="study ${x?.id===z.id?'active':''}" data-branch="${z.id}">#${z.id} ${esc(z.name)} ${statusBadge(z.status)} <span class="eyebrow">${z.change_count}项修订</span></button>`).join('')||'<p class="notice">暂无分支。</p>'}</div>
 ${x?`<div class="result-head"><h2>#${x.id} ${esc(x.name)} ${statusBadge(x.status)}</h2><span>${x.published_run_id?`已生成正式版本 #${x.published_run_id}`:''}</span></div>
 ${conflictPanel()}${diffPanel()}${trialPanel()}
 <div class="actions">${(x.status==='ready'||x.status==='publish_failed')&&!readonly?`<button class="primary" data-publish="${x.id}">核对无误，发布到正式样本</button>`:''}
 ${x.status!=='published'&&x.status!=='publishing'&&x.status!=='trialing'&&!readonly?`<button data-trial="${x.id}">发起 / 重新试算</button><button data-reset="${x.id}">清空修订回基线</button>`:''}
 ${x.status==='published'?`<button data-run="${x.published_run_id}">查看发布产生的新版本</button>`:''}</div>`:''}
 </section>
 <aside class="side">
 <h2>1. 建立修订分支</h2><form id="branch">${field('分支名称','name','text','required value="ZX-A01电表纠偏"')}<button class="primary">基于当前正式样本建分支</button></form>
 ${x&&x.status!=='published'&&x.status!=='publishing'&&x.status!=='trialing'&&!readonly?`<h2>2. 按小时批量改数</h2><form id="batch">
 <p class="eyebrow">每行一条：小时、字段、新值、原因；可粘贴多行。仅工况与耗电字段。</p>
 <label>批量修订（每行：小时|字段|新值|原因）<textarea name="bulk" rows="6" placeholder="2026-11-03T08:00|kwh|198.5|电表异常复核&#10;2026-11-03T09:00|pressure|6.8|压力变送器纠偏"></textarea></label>
 <p class="eyebrow">字段：${Object.keys(CORRECTION_FIELDS).join(' / ')}</p>
 <button class="primary">保存批量修订</button></form>
 <h2>3. 试算配置</h2><form id="trialcfg">${field('特征（逗号分隔）','features','text','value="pressure,flow,temperature,machines"')}${field('alpha候选','alphas','text','value="0.01,0.1,1,10,100"')}<p class="eyebrow">在左侧发起试算。基线与分支各自仅用训练段选参。</p></form>`:''}
 ${readonly?'<p class="notice">观察员只读。</p>':''}
 </aside></div>`;
}
export function parseBulk(text){
 let changes=[];
 for(let line of text.split('\n').map(s=>s.trim()).filter(Boolean)){
  let [hour,fieldName,newValue,reason='']=line.split('|').map(s=>s.trim());
  if(!hour||!fieldName||newValue==='')throw Error('行格式应为 小时|字段|新值|原因：'+line);
  if(!CORRECTION_FIELDS[fieldName])throw Error('未知字段 '+fieldName);
  let v=Number(newValue);if(!Number.isFinite(v))throw Error('新值不是数字：'+newValue);
  changes.push({hour,field:fieldName,new_value:v,reason});
 }
 if(!changes.length)throw Error('请至少填写一行修订');
 return changes;
}
