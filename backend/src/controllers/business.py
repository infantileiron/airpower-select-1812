from fastapi import HTTPException
from src.models.entities import Run,CorrectionBranch,Trial
# 只有草稿/试算失败/就绪/发布失败/冲突状态可以继续改数；计算中与已发布冻结
EDITABLE_BRANCH_STATES={'draft','trial_failed','ready','publish_failed','conflict'}
def ensure_run(s,i):
 row=s.get(Run,i)
 if not row:raise HTTPException(404,'模型版本不存在')
 return row
def ensure_branch(s,i):
 row=s.get(CorrectionBranch,i)
 if not row:raise HTTPException(404,'纠偏分支不存在')
 return row
def ensure_editable(branch):
 if branch.status not in EDITABLE_BRANCH_STATES:
  raise HTTPException(409,f'分支当前状态 {branch.status}，不能修订；请等待计算结束或基于已发布分支新建')
 return branch
def ensure_trial(s,i):
 row=s.get(Trial,i)
 if not row:raise HTTPException(404,'试算任务不存在')
 return row
