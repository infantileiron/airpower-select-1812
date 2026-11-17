from datetime import datetime
from pydantic import BaseModel,Field,field_validator
from typing import Literal
from src.constants.enums import CORRECTION_FIELDS
Feature=Literal['pressure','flow','temperature','machines','sensor_noise']
class Login(BaseModel):email:str;password:str
# 各字段取值边界与正式样本录入保持一致，分支试算不得绕过计量口径
_FIELD_RANGES={'pressure':(0,20),'flow':(0,1000),'temperature':(-30,100),'machines':(0,20),'sensor_noise':(-100,100),'kwh':(0,10000)}
class SampleInput(BaseModel):
 hour:str
 pressure:float=Field(ge=0,le=20,allow_inf_nan=False)
 flow:float=Field(ge=0,le=1000,allow_inf_nan=False)
 temperature:float=Field(ge=-30,le=100,allow_inf_nan=False)
 machines:int=Field(ge=0,le=20)
 sensor_noise:float=Field(ge=-100,le=100,allow_inf_nan=False)
 kwh:float=Field(ge=0,le=10000,allow_inf_nan=False)
 note:str=Field(default='',max_length=1000)
 @field_validator('hour')
 @classmethod
 def hourly(cls,v):
  d=datetime.fromisoformat(v)
  if d.tzinfo or d.minute or d.second or d.microsecond:raise ValueError('使用工厂本地整点小时，不带时区偏移')
  return d.strftime('%Y-%m-%dT%H:00')
class RunInput(BaseModel):
 name:str=Field(min_length=2,max_length=100)
 features:list[Feature]=Field(default=['pressure','flow','temperature','machines'],min_length=1,max_length=5)
 alphas:list[float]=Field(default=[.01,.1,1.,10.,100.],min_length=1,max_length=8)
 @field_validator('features','alphas')
 @classmethod
 def unique(cls,v):
  if len(v)!=len(set(v)):raise ValueError('候选项不能重复')
  return v
 @field_validator('alphas')
 @classmethod
 def positive(cls,v):
  import math
  if any(not math.isfinite(a) or a<=0 or a>10000 for a in v):raise ValueError('alpha必须为0到10000之间的有限正数')
  return v
class ReviewInput(BaseModel):
 run_id:int=Field(gt=0)
 title:str=Field(min_length=2,max_length=100)
 finding:str=Field(min_length=8,max_length=2000)
 action:str=Field(min_length=8,max_length=2000)
class BranchCreate(BaseModel):
 name:str=Field(min_length=2,max_length=100)
class BranchChangeItem(BaseModel):
 hour:str
 field:str
 new_value:float=Field(allow_inf_nan=False)
 reason:str=Field(default='',max_length=300)
 @field_validator('hour')
 @classmethod
 def hourly(cls,v):
  d=datetime.fromisoformat(v)
  if d.tzinfo or d.minute or d.second or d.microsecond:raise ValueError('使用工厂本地整点小时，不带时区偏移')
  return d.strftime('%Y-%m-%dT%H:00')
 @field_validator('field')
 @classmethod
 def known_field(cls,v):
  if v not in CORRECTION_FIELDS:raise ValueError('仅支持工况或耗电字段：'+','.join(CORRECTION_FIELDS))
  return v
 @field_validator('new_value')
 @classmethod
 def in_range(cls,v,info):
  lo,hi=_FIELD_RANGES[info.data.get('field','kwh')]
  if not(lo<=v<=hi):raise ValueError(f'{info.data.get("field")} 取值需在 {lo} 到 {hi} 之间')
  return v
class BranchBatchInput(BaseModel):
 # 按小时批量修订；同一分支同一小时同一字段重复出现视为整批无效
 changes:list[BranchChangeItem]=Field(min_length=1,max_length=500)
 @field_validator('changes')
 @classmethod
 def no_duplicate(cls,v):
  keys=[(c.hour,c.field) for c in v]
  if len(keys)!=len(set(keys)):raise ValueError('同一小时同一字段在本批中重复，请合并后再提交')
  return v
class TrialInput(BaseModel):
 features:list[Feature]=Field(default=['pressure','flow','temperature','machines'],min_length=1,max_length=5)
 alphas:list[float]=Field(default=[.01,.1,1.,10.,100.],min_length=1,max_length=8)
 @field_validator('features')
 @classmethod
 def unique_features(cls,v):
  if len(v)!=len(set(v)):raise ValueError('特征不能重复')
  return v
 @field_validator('alphas')
 @classmethod
 def positive(cls,v):
  import math
  if len(v)!=len(set(v)):raise ValueError('alpha候选不能重复')
  if any(not math.isfinite(a) or a<=0 or a>10000 for a in v):raise ValueError('alpha必须为0到10000之间的有限正数')
  return v
