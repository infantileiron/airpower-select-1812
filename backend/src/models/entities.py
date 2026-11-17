from sqlalchemy import Column,Integer,String,Float,JSON,Text,ForeignKey,UniqueConstraint
from sqlalchemy.orm import relationship
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True);password=Column(String(200));role=Column(String(20))
class Sample(Base):
 __tablename__='samples'
 id=Column(Integer,primary_key=True);hour=Column(String(30),unique=True,nullable=False);pressure=Column(Float);flow=Column(Float);temperature=Column(Float);machines=Column(Integer);sensor_noise=Column(Float);kwh=Column(Float);note=Column(Text,default='')
class Run(Base):
 __tablename__='runs'
 id=Column(Integer,primary_key=True);name=Column(String(100));features=Column(JSON);alphas=Column(JSON);state=Column(String(20),default='queued');result=Column(JSON);error=Column(Text,default='');source_branch_id=Column(Integer,unique=True)
class Review(Base):
 __tablename__='reviews'
 id=Column(Integer,primary_key=True);run_id=Column(Integer,ForeignKey('runs.id'));title=Column(String(100));finding=Column(Text);action=Column(Text);status=Column(String(20),default='draft')
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
class CorrectionBranch(Base):
 __tablename__='correction_branches'
 id=Column(Integer,primary_key=True);name=Column(String(100),nullable=False);status=Column(String(20),default='draft',nullable=False);baseline=Column(JSON,nullable=False);baseline_checksum=Column(String(80));current_checksum=Column(String(80));features=Column(JSON);alphas=Column(JSON);trial_id=Column(Integer);trial_result=Column(JSON);error=Column(Text,default='');published_run_id=Column(Integer)
 changes=relationship('BranchChange',cascade='all,delete-orphan',lazy='joined')
class BranchChange(Base):
 __tablename__='branch_changes'
 id=Column(Integer,primary_key=True);branch_id=Column(Integer,ForeignKey('correction_branches.id'),nullable=False);hour=Column(String(30),nullable=False);field=Column(String(30),nullable=False);old_value=Column(Float);new_value=Column(Float);reason=Column(String(300),default='')
 __table_args__=(UniqueConstraint('branch_id','hour','field',name='uq_branch_hour_field'),)
class Trial(Base):
 __tablename__='trials'
 id=Column(Integer,primary_key=True);branch_id=Column(Integer,ForeignKey('correction_branches.id'),nullable=False);features=Column(JSON);alphas=Column(JSON);state=Column(String(20),default='queued',nullable=False);result=Column(JSON);error=Column(Text,default='')
 branch=relationship('CorrectionBranch')
