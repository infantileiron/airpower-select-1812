import os,json
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy.exc import IntegrityError
from src.config.database import db
from src.models.entities import User,Sample,Run,Review,Audit,CorrectionBranch,BranchChange,Trial
from src.schemas.business import Login,SampleInput,RunInput,ReviewInput,BranchCreate,BranchBatchInput,TrialInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.services import correction as cz
from src.controllers.business import ensure_run,ensure_branch,ensure_editable,ensure_trial
from src.constants.enums import RUN_QUEUE,TRIAL_QUEUE,PUBLISH_QUEUE,CORRECTION_FIELDS
router=APIRouter()
def queue():return redis.Redis.from_url(os.environ['REDIS_URL'])
def branch_detail(s,b):
 d=dump(b);d['change_count']=len(b.changes);d['diff']=cz.diff_preview(b,s);return d
@router.post('/auth/login')
def login(data:Login,s=Depends(db)):
 u=s.query(User).filter_by(email=data.email).first()
 if not u or not verify(data.password,u.password):raise HTTPException(401,'账号或密码错误')
 return {'token':token(u),'user':dump(u)}
@router.get('/me')
def me(u=Depends(current)):return dump(u)
@router.get('/samples')
def samples(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Sample).order_by(Sample.hour).all()]
@router.post('/samples')
def create(data:SampleInput,u=Depends(editor),s=Depends(db)):
 r=Sample(**data.model_dump());s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'该小时已存在，请使用修订功能')
 audit(s,u,'录入小时 '+r.hour);return dump(r)
@router.put('/samples/{i}')
def edit(i:int,data:SampleInput,u=Depends(editor),s=Depends(db)):
 r=s.get(Sample,i)
 if not r:raise HTTPException(404,'小时样本不存在')
 for k,v in data.model_dump().items():setattr(r,k,v)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'小时重复')
 audit(s,u,'修订样本 '+str(i));return dump(r)
@router.get('/runs')
def runs(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Run).order_by(Run.id.desc()).all()]
@router.post('/runs')
def train(data:RunInput,u=Depends(editor),s=Depends(db)):
 rows=[cz.sample_row(r) for r in s.query(Sample).order_by(Sample.hour).all()];r=Run(**data.model_dump(),result={'snapshot':rows});s.add(r);s.commit()
 try:queue().rpush(RUN_QUEUE,r.id)
 except redis.RedisError:r.state='failed';r.error='队列暂不可用，请稍后重试';s.commit();raise HTTPException(503,r.error)
 audit(s,u,'提交模型 '+str(r.id));return dump(r)
@router.get('/runs/{i}')
def detail(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_run(s,i))
@router.get('/runs/{i}/export')
def export(i:int,u=Depends(current),s=Depends(db)):
 r=ensure_run(s,i)
 if r.state!='done':raise HTTPException(409,'仅成功版本可导出')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="airpower-select-{i}.json"'})
@router.get('/reviews')
def reviews(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Review).order_by(Review.id.desc()).all()]
@router.post('/reviews')
def review(data:ReviewInput,u=Depends(editor),s=Depends(db)):
 if ensure_run(s,data.run_id).state!='done':raise HTTPException(409,'模型计算完成后才能起草评议')
 r=Review(**data.model_dump());s.add(r);s.commit();audit(s,u,'起草节能评议 '+str(r.id));return dump(r)
@router.put('/reviews/{i}')
def edit_review(i:int,data:ReviewInput,u=Depends(editor),s=Depends(db)):
 r=s.get(Review,i)
 if not r:raise HTTPException(404,'评议不存在')
 if r.status!='draft':raise HTTPException(409,'已签核评议冻结，请新建')
 if ensure_run(s,data.run_id).state!='done':raise HTTPException(409,'需要已成功模型')
 for k,v in data.model_dump().items():setattr(r,k,v)
 s.commit();audit(s,u,'修订评议 '+str(i));return dump(r)
@router.post('/reviews/{i}/approve')
def approve(i:int,u=Depends(admin),s=Depends(db)):
 r=s.get(Review,i)
 if not r:raise HTTPException(404,'评议不存在')
 if r.status!='draft':raise HTTPException(409,'已签核评议不能重复签核')
 r.status='approved';s.commit();audit(s,u,'签核节能评议 '+str(i));return dump(r)
@router.get('/reviews/{i}/export')
def export_review(i:int,u=Depends(current),s=Depends(db)):
 r=s.get(Review,i)
 if not r:raise HTTPException(404,'评议不存在')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="airpower-review-{i}.json"'})
@router.get('/audits')
def audits(u=Depends(admin),s=Depends(db)):return [dump(r) for r in s.query(Audit).order_by(Audit.id.desc()).limit(100)]
# ---------------- 仪表纠偏分支 ----------------
@router.get('/branches')
def list_branches(u=Depends(current),s=Depends(db)):
 return [branch_detail(s,b) for b in s.query(CorrectionBranch).order_by(CorrectionBranch.id.desc()).all()]
@router.post('/branches')
def create_branch(data:BranchCreate,u=Depends(editor),s=Depends(db)):
 rows=[cz.sample_row(r) for r in s.query(Sample).order_by(Sample.hour).all()]
 if len(rows)<60:raise HTTPException(409,'正式样本不足60小时，无法建立可试算分支')
 b=CorrectionBranch(name=data.name,baseline=rows,baseline_checksum=cz.checksum(rows),current_checksum=cz.checksum(rows))
 s.add(b);s.commit();audit(s,u,'建立纠偏分支 '+str(b.id)+' 基线'+str(len(rows))+'小时');return branch_detail(s,b)
@router.get('/branches/{i}')
def get_branch(i:int,u=Depends(current),s=Depends(db)):return branch_detail(s,ensure_branch(s,i))
@router.get('/branches/{i}/rows')
def branch_rows(i:int,u=Depends(current),s=Depends(db)):
 b=ensure_branch(s,i);return cz.branch_rows(b)
@router.put('/branches/{i}/changes')
def batch_changes(i:int,data:BranchBatchInput,u=Depends(editor),s=Depends(db)):
 b=ensure_editable(ensure_branch(s,i));base={r['hour']:r for r in b.baseline}
 existing={(c.hour,c.field) for c in b.changes};seen=set()
 for item in data.changes:
  if item.hour not in base:raise HTTPException(404,f'小时 {item.hour} 不在分支基线时间窗内，分支不新增小时')
  key=(item.hour,item.field);seen.add(key)
  old=base[item.hour][item.field]
  val=int(item.new_value) if item.field=='machines' else float(item.new_value)
  ch=s.query(BranchChange).filter_by(branch_id=b.id,hour=item.hour,field=item.field).first()
  if ch:ch.new_value=val;ch.old_value=old;ch.reason=item.reason
  else:s.add(BranchChange(branch_id=b.id,hour=item.hour,field=item.field,old_value=old,new_value=val,reason=item.reason))
 # 再次编辑后旧试算失效，回到草稿等待重新试算
 b.status='draft';b.trial_id=None;b.trial_result=None;b.error=''
 s.commit();s.refresh(b)
 audit(s,u,f'分支{b.id}批量修订 {len(data.changes)} 项，累计 {len(b.changes)} 项');return branch_detail(s,b)
@router.delete('/branches/{i}/changes')
def reset_changes(i:int,u=Depends(editor),s=Depends(db)):
 b=ensure_editable(ensure_branch(s,i))
 s.query(BranchChange).filter_by(branch_id=b.id).delete()
 b.status='draft';b.trial_id=None;b.trial_result=None;b.error=''
 s.commit();s.refresh(b)
 audit(s,u,'清空分支'+str(b.id)+'修订，回到基线');return branch_detail(s,b)
@router.post('/branches/{i}/trial')
def start_trial(i:int,data:TrialInput,u=Depends(editor),s=Depends(db)):
 b=ensure_branch(s,i)
 if b.status in ('trialing','publishing','published'):raise HTTPException(409,f'分支状态 {b.status}，不能发起试算')
 if not b.changes:raise HTTPException(409,'分支尚无修订，请先按小时批量改数再试算')
 t=Trial(branch_id=b.id,features=data.features,alphas=data.alphas,state='queued')
 s.add(t);s.flush()
 b.status='trialing';b.trial_id=t.id;b.features=data.features;b.alphas=data.alphas;b.error='';b.trial_result=None
 s.commit()
 try:queue().rpush(TRIAL_QUEUE,t.id)
 except redis.RedisError:
  t.state='failed';t.error='队列暂不可用，请稍后重试';b.status='trial_failed';s.commit();raise HTTPException(503,t.error)
 audit(s,u,f'分支{b.id}发起试算 #{t.id}');return branch_detail(s,b)
@router.get('/trials/{i}')
def get_trial(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_trial(s,i))
@router.post('/branches/{i}/publish')
def publish(i:int,u=Depends(editor),s=Depends(db)):
 b=ensure_branch(s,i)
 if b.status=='published':raise HTTPException(409,'分支已发布，不能重复发布')
 if b.status in ('trialing','publishing'):raise HTTPException(409,f'分支正在 {b.status}，请等待结束')
 if b.status not in ('ready','publish_failed') or not b.trial_result:raise HTTPException(409,'试算成功并就绪后才能发布')
 # 发布前先做一次三方合并预检；计算期间正式样本若再被修订，worker 端会再次校验并拒绝
 conflicts,merged,touched=cz.merge_plan(b,s)
 if conflicts:
  b.status='conflict';b.error=json.dumps(conflicts,ensure_ascii=False);s.commit()
  audit(s,u,f'分支{b.id}发布预检发现 {len(conflicts)} 处冲突，拒绝发布')
  raise HTTPException(409,{'message':'存在字段冲突，发布已拒绝','conflicts':conflicts})
 if not touched:raise HTTPException(409,'没有可落地的差异，无需发布')
 b.status='publishing';b.current_checksum=cz.checksum([cz.sample_row(r) for r in s.query(Sample).order_by(Sample.hour).all()]);b.error='';s.commit()
 try:queue().rpush(PUBLISH_QUEUE,b.id)
 except redis.RedisError:
  b.status='publish_failed';b.error='队列暂不可用，请稍后重试';s.commit();raise HTTPException(503,b.error)
 audit(s,u,f'分支{b.id}提交发布，涉及 {len(touched)} 个小时');return branch_detail(s,b)
