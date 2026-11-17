import os,time,json,logging
from pathlib import Path
import redis
from src.config.database import Base,engine,Session
from src.models.entities import Run,CorrectionBranch,BranchChange,Trial,Sample
from src.services.analysis import choose
from src.services import correction as cz
from src.constants.enums import RUN_QUEUE,TRIAL_QUEUE,PUBLISH_QUEUE,CORRECTION_FIELDS
ARTIFACT_DIR=os.environ.get('ARTIFACT_DIR','/artifacts')
r=redis.Redis.from_url(os.environ['REDIS_URL'])
def recover():
 # 中断可恢复：重启时把 queued/running 的任务重新入队，绝不重复发布
 with Session() as recovery:
  for pending in recovery.query(Run).filter(Run.state.in_(['queued','running'])).all():
   pending.state='queued';r.rpush(RUN_QUEUE,pending.id)
  for t in recovery.query(Trial).filter(Trial.state.in_(['queued','running'])).all():
   t.state='queued';b=recovery.get(CorrectionBranch,t.branch_id)
   if b and b.status!='published':b.status='trialing'
   r.rpush(TRIAL_QUEUE,t.id)
  for b in recovery.query(CorrectionBranch).filter(CorrectionBranch.status.in_(['publishing'])).all():
   r.rpush(PUBLISH_QUEUE,b.id)
  recovery.commit()
def handle_run(s,raw):
 row=s.get(Run,int(raw))
 if not row or row.state!='queued':return
 snapshot=row.result['snapshot'];row.state='running';s.commit()
 try:
  row.result={**choose(snapshot,row.features,row.alphas),'snapshot':snapshot};row.state='done'
  Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True)
  Path(ARTIFACT_DIR+'/'+str(row.id)+'.json').write_text(json.dumps(row.result,ensure_ascii=False))
 except Exception as e:row.state='failed';row.error=str(e)
def handle_trial(s,raw):
 t=s.get(Trial,int(raw))
 if not t or t.state!='queued':return
 b=s.get(CorrectionBranch,t.branch_id)
 if not b:t.state='failed';t.error='分支已不存在';return
 if b.status=='published':t.state='failed';t.error='分支已发布';return
 t.state='running';b.status='trialing';s.commit()
 try:
  b.features=t.features;b.alphas=t.alphas
  result=cz.run_trial(b)
  t.result=result;t.state='done'
  b.trial_id=t.id;b.trial_result=result;b.status='ready';b.error=''
 except Exception as e:
  t.state='failed';t.error=str(e);b.status='trial_failed';b.error=str(e)
def handle_publish(s,raw):
 b=s.get(CorrectionBranch,int(raw))
 if not b:return
 if b.status=='published':return  # 幂等：已发布不重复执行
 if b.status!='publishing':
  # 重启恢复时仅重新拾取发布中的分支，其他状态不受理
  return
 branch_id=b.id
 # 计算期间正式样本再被修订则拒绝发布：当前校验和须等于发起发布时冻结值
 current_rows=[cz.sample_row(x) for x in s.query(Sample).order_by(Sample.hour).all()]
 if cz.checksum(current_rows)!=b.current_checksum:
  b.status='publish_failed';b.error='计算期间正式样本已被修订，为避免覆盖请重新核对后再发布';return
 conflicts,merged,touched=cz.merge_plan(b,s)
 if conflicts:
  b.status='conflict';b.error=json.dumps(conflicts,ensure_ascii=False);return
 if not touched:
  b.status='ready';b.error='无差异可发布';return
 # 重新训练：基于合并后的正式数据快照；失败保留正式数据，不写任何样本
 features=list(b.features);alphas=list(b.alphas)
 snapshot=[{k:v for k,v in row.items() if k!='id'} for row in merged]
 run=Run(name=b.name+' · 纠偏发布',features=features,alphas=alphas,state='running',source_branch_id=branch_id,result={'snapshot':snapshot})
 s.add(run);s.flush()
 try:
  run.result={**choose(snapshot,features,alphas),'snapshot':snapshot};run.state='done'
 except Exception as e:
  # 回滚训练产生的 Run，正式样本未被触碰；分支回到发布失败可重试
  s.rollback()
  b=s.get(CorrectionBranch,branch_id);b.status='publish_failed';b.error='重新训练失败，正式数据保留：'+str(e);return
 # 训练成功后一次性落地样本改动，与新版本同一事务可见
 cur={x.hour:x for x in s.query(Sample).all()}
 cm={(c.hour,c.field):c for c in s.query(BranchChange).filter_by(branch_id=branch_id).all()}
 base={x['hour']:x for x in b.baseline}
 for row in merged:
  sample=cur.get(row['hour'])
  for f in CORRECTION_FIELDS:
   ch=cm.get((row['hour'],f))
   if ch is None:continue
   if not cz.same_value(getattr(sample,f),base[row['hour']][f]):
    # 事务内再次确认无并行修订
    s.rollback()
    b=s.get(CorrectionBranch,branch_id);b.status='conflict';b.error='发布时检测到字段冲突，已拒绝';return
   setattr(sample,f,row[f])
 b=s.get(CorrectionBranch,branch_id)
 b.status='published';b.published_run_id=run.id;b.error=''
 s.flush()
 try:
  Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True)
  Path(ARTIFACT_DIR+'/'+str(run.id)+'.json').write_text(json.dumps(run.result,ensure_ascii=False))
 except OSError:logging.exception('artifact write failed')
HANDLERS={RUN_QUEUE:handle_run,TRIAL_QUEUE:handle_trial,PUBLISH_QUEUE:handle_publish}
if __name__=='__main__':
 Base.metadata.create_all(engine);recover()
 while True:
  Path('/tmp/heartbeat').touch()
  try:
   item=r.blpop(list(HANDLERS.keys()),timeout=3)
   if not item:continue
   qname,raw=item[0].decode() if isinstance(item[0],bytes) else item[0],item[1]
   with Session() as s:
    HANDLERS[qname](s,raw);s.commit()
  except Exception:logging.exception('worker');time.sleep(2)
