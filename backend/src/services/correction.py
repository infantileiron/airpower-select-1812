import json,hashlib,math
from src.constants.enums import CORRECTION_FIELDS
from src.services.analysis import choose
# 数值字段统一口径比较：浮点按 1e-9 相对容差，整数台数按精确相等
def checksum(rows):
 return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def same_value(a,b):
 if a is None or b is None:return a==b
 if isinstance(a,int) and isinstance(b,int):return a==b
 try:
  if not math.isfinite(float(a)) or not math.isfinite(float(b)):return False
  return float(a)==float(b) or abs(float(a)-float(b))<=1e-9*max(1.0,abs(float(a)),abs(float(b)))
 except (TypeError,ValueError):return a==b
def sample_row(r):
 return {'id':r.id,'hour':r.hour,'pressure':r.pressure,'flow':r.flow,'temperature':r.temperature,'machines':r.machines,'sensor_noise':r.sensor_noise,'kwh':r.kwh,'note':r.note or ''}
def baseline_map(baseline):
 return {r['hour']:r for r in baseline}
def current_map(s):
 from src.models.entities import Sample
 return {r.hour:sample_row(r) for r in s.query(Sample).order_by(Sample.hour).all()}
def change_map(branch):
 return {(c.hour,c.field):c for c in branch.changes}
def branch_rows(branch):
 # 基线 + 分支改动重建试算视图；新增/删除小时不进入分支，保证与基线共用时间窗
 base=baseline_map(branch.baseline);cm=change_map(branch)
 rows=[]
 for hour in sorted(base):
  row=dict(base[hour])
  for f in CORRECTION_FIELDS:
   ch=cm.get((hour,f))
   if ch is not None:row[f]=int(ch.new_value) if f=='machines' else float(ch.new_value)
  rows.append(row)
 return rows
def changed_hours(branch):
 return sorted({c.hour for c in branch.changes})
def diff_preview(branch,s):
 # 基线 / 分支 / 当前正式样本逐字段对照，用于页面试算前核对
 base=baseline_map(branch.baseline);cur=current_map(s);cm=change_map(branch)
 out=[]
 for hour in changed_hours(branch):
  for f in CORRECTION_FIELDS:
   ch=cm.get((hour,f))
   if ch is None:continue
   out.append({'hour':hour,'field':f,'baseline':base.get(hour,{}).get(f),'branch':int(ch.new_value) if f=='machines' else float(ch.new_value),'current':cur.get(hour,{}).get(f),'conflict':bool(hour in cur and hour in base and not same_value(cur[hour][f],base[hour][f]))})
 return out
def merge_plan(branch,s):
 # 三方合并：基线 B、分支 T、当前正式 C。共用时间窗=基线小时集合。
 base=baseline_map(branch.baseline);cur=current_map(s);cm=change_map(branch)
 conflicts=[];merged=[];touched=set()
 for hour in sorted(base):
  b=base[hour];c=cur.get(hour)
  if c is None:
   # 当前正式样本缺失该小时：拒绝发布而非静默补回
   conflicts.append({'hour':hour,'field':'<row>','baseline':b.get('hour'),'branch':None,'current':None,'reason':'当前正式样本缺少该小时，无法安全合并'})
   continue
  row=dict(c)
  for f in CORRECTION_FIELDS:
   ch=cm.get((hour,f))
   bv=b.get(f);cv=c.get(f)
   if ch is None:
    # 分支未触碰该字段：保留当前值（含并行修订）
    continue
   tv=int(ch.new_value) if f=='machines' else float(ch.new_value)
   if not same_value(cv,bv):
    # 双方同字段异值：分支要改、正式已改 → 冲突，拒绝发布
    conflicts.append({'hour':hour,'field':f,'baseline':bv,'branch':tv,'current':cv,'reason':'分支与当前正式样本同字段异值'})
    continue
   if not same_value(cv,tv):
    row[f]=tv;touched.add(hour)
  merged.append(row)
 return conflicts,merged,sorted(touched)
def run_trial(branch):
 # 共用时间窗：基线行与分支行同小时、同顺序；各自只用自己的训练段（前80%）选 alpha
 baseline=branch.baseline
 branch_view=branch_rows(branch)
 base_result=choose(baseline,branch.features,branch.alphas)
 branch_result=choose(branch_view,branch.features,branch.alphas)
 window={'start':baseline[0]['hour'],'end':baseline[-1]['hour'],'hours':len(baseline),'train_n':base_result['train_n'],'validation_n':base_result['validation_n']}
 metrics=[]
 for key,label in (('cv_rmse','训练内CV RMSE'),('validation_rmse','末段验证 RMSE'),('baseline_rmse','训练均值基线 RMSE')):
  metrics.append({'metric':key,'label':label,'baseline':base_result[key],'branch':branch_result[key],'delta':branch_result[key]-base_result[key]})
 return {'window':window,'baseline':_summary(base_result),'branch':_summary(branch_result),'metrics':metrics,'changes':diff_preview_static(branch)}
def _summary(r):
 return {'selected_alpha':r['selected_alpha'],'cv_rmse':r['cv_rmse'],'validation_rmse':r['validation_rmse'],'baseline_rmse':r['baseline_rmse'],'coefficients':r['coefficients'],'intercept_original':r['intercept_original'],'checksum':r['checksum']}
def diff_preview_static(branch):
 base=baseline_map(branch.baseline);cm=change_map(branch);out=[]
 for hour in sorted({c.hour for c in branch.changes}):
  for f in CORRECTION_FIELDS:
   ch=cm.get((hour,f))
   if ch is None:continue
   out.append({'hour':hour,'field':f,'baseline':base[hour].get(f),'branch':int(ch.new_value) if f=='machines' else float(ch.new_value)})
 return out
