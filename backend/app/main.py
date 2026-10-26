from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
from .db import init_db, connect, DB_PATH
from .domain import issue, verify, revoke
from .seed import seed

FRONTEND_DIR = Path(__file__).resolve().parents[2] / 'frontend'
app=FastAPI(title='CREDENTIA API',version='1.0.0')
# Resolve from this module, not the caller's current directory. This keeps the
# documented server URL working when Uvicorn is launched from another folder.
app.mount('/assets',StaticFiles(directory=FRONTEND_DIR),name='assets')
@app.on_event('startup')
def startup(): init_db()
class IssueIn(BaseModel): learner_id:str; course_id:str
class RevokeIn(BaseModel): reason_code:str=Field(min_length=2,max_length=64); explanation:str=Field(min_length=5,max_length=500)
class GenerateIn(BaseModel): scale:str='starter'; seed:int=20261022
def rows(q,args=()):
 with connect() as c:return [dict(x) for x in c.execute(q,args).fetchall()]
@app.get('/')
def ui(): return FileResponse(FRONTEND_DIR / 'index.html')
@app.get('/verify')
def verify_ui(): return FileResponse(FRONTEND_DIR / 'index.html')
@app.get('/api/v1/health')
def health(): return {'status':'healthy','version':'1.0.0','database':'sqlite configured'}
@app.get('/api/v1/dashboard')
def dashboard():
 with connect() as c:
  count=lambda table,where='': c.execute(f'SELECT COUNT(*) FROM {table} {where}').fetchone()[0]
  success=c.execute("SELECT COUNT(*) FROM verification_requests WHERE decision='VALID'").fetchone()[0]; total=count('verification_requests')
  return {'metrics':{'learners':count('learners'),'courses':count('courses'),'issued':count('credentials'),'valid':count('credentials',"WHERE status='ISSUED'"),'revoked':count('credentials',"WHERE status='REVOKED'"),'verifications':total,'verification_success_rate':round(success/total*100,1) if total else 0,'exceptions':count('anomaly_fixtures')},'lifecycle':rows('SELECT status, COUNT(*) count FROM credentials GROUP BY status'),'recent_audit':rows('SELECT * FROM audit_events ORDER BY id DESC LIMIT 8'),'recent_credentials':rows('SELECT c.id,c.status,c.issued_at,l.name learner_name,co.title course_title FROM credentials c JOIN learners l ON l.id=c.learner_id JOIN courses co ON co.id=c.course_id ORDER BY c.issued_at DESC LIMIT 8')}
@app.get('/api/v1/learners')
def learners(q:str='',page:int=1):
 pat=f'%{q}%'; data=rows('SELECT * FROM learners WHERE id LIKE ? OR email LIKE ? OR name LIKE ? ORDER BY id LIMIT 50 OFFSET ?', (pat,pat,pat,(page-1)*50)); return {'items':data,'page':page}
@app.get('/api/v1/courses')
def courses(): return {'items':rows('SELECT c.*,r.min_score,r.version FROM courses c LEFT JOIN credential_rules r ON r.course_id=c.id AND r.active=1 ORDER BY c.id')}
@app.get('/api/v1/credentials')
def credentials(q:str='',status:str=''):
 pat=f'%{q}%'; sql="SELECT c.*,l.name learner_name,co.title course_title FROM credentials c JOIN learners l ON l.id=c.learner_id JOIN courses co ON co.id=c.course_id WHERE (c.id LIKE ? OR l.name LIKE ? OR l.email LIKE ?)"; args=[pat,pat,pat]
 if status: sql+=' AND c.status=?';args.append(status)
 return {'items':rows(sql+' ORDER BY c.issued_at DESC LIMIT 100',args)}
@app.get('/api/v1/credentials/{cid}')
def credential(cid:str):
 data=rows("SELECT c.*,l.name learner_name,l.email,co.title course_title FROM credentials c JOIN learners l ON l.id=c.learner_id JOIN courses co ON co.id=c.course_id WHERE c.id=?",(cid,))
 if not data: raise HTTPException(404,'Credential not found')
 return {'credential':data[0],'audit':rows('SELECT * FROM audit_events WHERE entity_id=? ORDER BY id DESC',(cid,)),'revocation':rows('SELECT * FROM revocations WHERE credential_id=?',(cid,))}
@app.post('/api/v1/credentials/issue',status_code=201)
def issue_credential(body:IssueIn):
 try: cid,reused=issue(body.learner_id,body.course_id); return {'credential_id':cid,'idempotent_reuse':reused}
 except ValueError as e: raise HTTPException(422,str(e))
@app.post('/api/v1/credentials/{cid}/revoke')
def revoke_credential(cid:str,body:RevokeIn):
 try:return {'revoked':revoke(cid,body.reason_code,body.explanation)}
 except LookupError as e:raise HTTPException(404,str(e))
@app.post('/api/v1/public/verify/{cid}')
def public_verify(cid:str):
 d,details=verify(cid); return {'credential_id':cid,'decision':d,'details':details if d=='VALID' else {}}
@app.get('/api/v1/audit')
def audit():return {'items':rows('SELECT * FROM audit_events ORDER BY id DESC LIMIT 100')}
@app.get('/api/v1/anomalies')
def anomalies():return {'items':rows('SELECT * FROM anomaly_fixtures')}
@app.post('/api/v1/data/generate')
def generate(body:GenerateIn):
 if body.scale not in ('starter','full'):raise HTTPException(422,'scale must be starter or full')
 seed(body.scale,body.seed);return {'status':'complete','scale':body.scale,'seed':body.seed}
