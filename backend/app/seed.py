import argparse, random
from datetime import date, timedelta
from .db import init_db, connect
from .domain import issue, audit, public_key_text, verify
def seed(scale='starter', seed=20261022):
 init_db(); r=random.Random(seed); counts={'starter':(80,12,40,30),'full':(20000,1000,10000,5000)}; learners,courses,creds,verifications=counts[scale]
 with connect() as c:
  for t in ['anomaly_fixtures','audit_events','verification_requests','revocations','credentials','credential_sequence','completions','credential_rules','courses','learners','issuers']: c.execute(f'DELETE FROM {t}')
  c.execute('INSERT INTO issuers VALUES(?,?,?,?,?)',('ISS-PRIMARY','Credentia Academy',public_key_text(),1,'2026-01-01T00:00:00+00:00'))
  for i in range(1,courses+1):
   cid=f'CRS-{i:04d}'; c.execute('INSERT INTO courses VALUES(?,?,?,1)',(cid,f'CRED-{i:03d}',f'Credential Systems {i}')); c.execute('INSERT INTO credential_rules VALUES(?,?,?,?,?,?,?,?)',(f'RUL-{i:04d}',cid,70,'COMPLETED','2025-01-01',None,1,1))
  for i in range(1,learners+1): c.execute('INSERT INTO learners VALUES(?,?,?,?)',(f'LRN-{i:06d}',f'learner{i}@example.test',f'Learner {i:05d}','2026-01-01T00:00:00+00:00'))
  for i in range(1,creds+1):
   l=f'LRN-{((i-1)%learners)+1:06d}'; course=f'CRS-{((i-1)%courses)+1:04d}'; comp=f'CMP-{i:06d}'; score=70+r.randrange(31); c.execute('INSERT INTO completions VALUES(?,?,?,?,?,?,?)',(comp,l,course,'COMPLETED',score,'2026-01-15','synthetic'))
 audit(c,'DATASET_GENERATED','generation',f'{scale}-{seed}','generator',f'{{"seed":{seed}}}','2026-01-01T00:00:00+00:00')
 # Commit source records before the issuance service opens its own transaction.
 c.commit()
 for i in range(1,creds+1):
  timestamp=f'2026-02-{(i%28)+1:02d}T12:00:00+00:00'
  issue(f'LRN-{((i-1)%learners)+1:06d}',f'CRS-{((i-1)%courses)+1:04d}','generator',timestamp,timestamp)
 for i in range(verifications):
  timestamp=f'2026-03-{(i%28)+1:02d}T09:00:00+00:00'
  verify(f'CRD-2026-{((i%creds)+1):06d}' if i%5 else 'CRD-UNKNOWN',timestamp)
 with connect() as c:
  for x,decision in [('issued_before_completion','REJECTED'),('duplicate_credential_id','REJECTED'),('revoked_accepted_active','DETECTED'),('altered_payload_hash','DETECTED')]: c.execute('INSERT INTO anomaly_fixtures VALUES(?,?,?,?,?,?)',(f'ANM-{x}',x,decision,decision,1,'Isolated regression fixture; baseline data remains valid.'))
 print({'learners':learners,'courses':courses,'credentials':creds,'verification_requests':verifications,'seed':seed})
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--scale',default='starter',choices=['starter','full']); p.add_argument('--seed',type=int,default=20261022); a=p.parse_args(); seed(a.scale,a.seed)
