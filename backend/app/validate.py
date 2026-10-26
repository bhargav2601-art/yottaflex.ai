import json
from pathlib import Path
from .db import init_db, connect
from .domain import digest, signature_valid
def run():
 init_db()
 with connect() as c:
  tables=['issuers','learners','courses','credential_rules','completions','credentials','verification_requests','revocations','audit_events','anomaly_fixtures']
  counts={t:c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tables}
  bad=c.execute("SELECT COUNT(*) FROM credentials c JOIN completions p ON p.id=c.completion_id JOIN credential_rules r ON r.id=c.rule_id WHERE p.score<r.min_score OR p.status!=r.required_status").fetchone()[0]
  duplicates=c.execute('SELECT COUNT(*) FROM (SELECT id FROM credentials GROUP BY id HAVING COUNT(*) > 1)').fetchone()[0]
  credentials=c.execute('SELECT c.*,i.public_key FROM credentials c JOIN issuers i ON i.id=c.issuer_id').fetchall()
  integrity=sum(1 for row in credentials if row['payload_hash'] != digest(row) or not signature_valid(row['payload_hash'],row['signature'],row['public_key']))
  report={'row_counts':counts,'duplicate_credential_ids':duplicates,'eligibility_violations':bad,'foreign_key_violations':len(c.execute('PRAGMA foreign_key_check').fetchall()),'payload_integrity_failures':integrity,'anomaly_fixtures':counts['anomaly_fixtures']}
 Path('docs').mkdir(exist_ok=True);Path('docs/validation_report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
if __name__=='__main__':run()
