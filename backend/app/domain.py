import base64, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from .db import connect

KEY_PATH = Path(os.getenv('CREDENTIA_SIGNING_KEY', 'data/credentia-dev-ed25519.pem'))
EXTERNAL_PROVIDERS = {}
def now(): return datetime.now(timezone.utc).isoformat()
def canonical(row):
    return json.dumps({k: row[k] for k in ('id','learner_id','course_id','issuer_id','issued_at')}, sort_keys=True, separators=(',', ':'))
def digest(row): return hashlib.sha256(canonical(row).encode()).hexdigest()
def private_key():
    """Create a local-development key on first run; it is intentionally gitignored."""
    if KEY_PATH.exists():
        return serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    key=Ed25519PrivateKey.generate()
    KEY_PATH.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try: os.chmod(KEY_PATH,0o600)
    except OSError: pass
    return key
def public_key_text():
    return base64.b64encode(private_key().public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
def sign(payload_hash): return base64.b64encode(private_key().sign(payload_hash.encode())).decode()
def signature_valid(payload_hash, signature, public_key):
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(base64.b64decode(signature),payload_hash.encode())
        return True
    except Exception: return False
def audit(c, kind, entity_type, entity_id, actor='system', metadata='{}', occurred_at=None):
    c.execute('INSERT INTO audit_events(event_type,entity_type,entity_id,actor,occurred_at,metadata) VALUES(?,?,?,?,?,?)',(kind,entity_type,entity_id,actor,occurred_at or now(),metadata))
def eligible(c, learner_id, course_id, at):
    rule=c.execute("SELECT * FROM credential_rules WHERE course_id=? AND active=1 AND effective_from<=? AND (effective_until IS NULL OR effective_until>=?) ORDER BY version DESC LIMIT 1",(course_id,at,at)).fetchone()
    completion=c.execute("SELECT * FROM completions WHERE learner_id=? AND course_id=? ORDER BY completed_on DESC LIMIT 1",(learner_id,course_id)).fetchone()
    if not rule or not completion: return False, rule, completion, 'Missing applicable rule or completion'
    if completion['status'] != rule['required_status'] or completion['score'] < rule['min_score']: return False,rule,completion,'Completion does not meet rule threshold'
    return True,rule,completion,'Eligible'
def issue(learner_id, course_id, actor='admin', issued_at=None, audit_at=None):
    with connect() as c:
        timestamp=issued_at or now()
        ok,rule,completion,message=eligible(c,learner_id,course_id,timestamp[:10])
        if not ok: raise ValueError(message)
        if completion['completed_on'] > timestamp[:10]: raise ValueError('Credential cannot be issued before completion')
        issuer=c.execute("SELECT id,active FROM issuers WHERE id='ISS-PRIMARY'").fetchone()
        if not issuer or not issuer['active']: raise ValueError('No active issuer is available')
        existing=c.execute('SELECT id FROM credentials WHERE completion_id=?',(completion['id'],)).fetchone()
        if existing: return existing['id'], True
        # SQLite allocates this sequence atomically; COUNT(*) was unsafe under concurrent issuance.
        seq=c.execute('INSERT INTO credential_sequence DEFAULT VALUES').lastrowid; cid=f'CRD-2026-{seq:06d}'
        row={'id':cid,'learner_id':learner_id,'course_id':course_id,'issuer_id':'ISS-PRIMARY','issued_at':timestamp}
        c.execute('INSERT INTO credentials VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,learner_id,course_id,completion['id'],'ISS-PRIMARY',rule['id'],row['issued_at'],digest(row),sign(digest(row)),'ISSUED'))
        audit(c,'CREDENTIAL_ISSUED','credential',cid,actor,json.dumps({'rule_id':rule['id'],'completion_id':completion['id']}),audit_at); return cid,False
def verify(cid, requested_at=None):
    with connect() as c:
        row=c.execute('SELECT c.*,i.active issuer_active,i.public_key FROM credentials c JOIN issuers i ON i.id=c.issuer_id WHERE c.id=?',(cid,)).fetchone(); decision='UNKNOWN'; details={}
        if row:
            # Precedence: unknown > invalid issuer > tampered > revoked > valid
            if not row['issuer_active']: decision='INVALID_ISSUER'
            elif row['payload_hash'] != digest(row) or not signature_valid(row['payload_hash'],row['signature'],row['public_key']): decision='TAMPERED'
            elif row['status']=='REVOKED': decision='REVOKED'
            else: decision='VALID'
            details={'course_id':row['course_id'],'issued_at':row['issued_at']}
        n=c.execute('SELECT COUNT(*) FROM verification_requests').fetchone()[0]+1
        timestamp=requested_at or now()
        c.execute('INSERT INTO verification_requests VALUES(?,?,?,?,?)',(f'VER-2026-{n:06d}',cid if row else None,decision,timestamp,'local')); audit(c,'CREDENTIAL_VERIFIED','credential',cid,'public',json.dumps({'decision':decision}),timestamp)
        return decision,details

def register_external_provider(provider_id, verifier, *, authorized=False):
    """Register an explicitly authorized provider adapter.

    No adapter is registered in local CREDENTIA. Adapters are deliberately
    code/configuration owned, never inferred from a PDF, image, QR payload, or
    a submitted certificate number.
    """
    if not authorized:
        raise ValueError('External provider registration requires explicit authorization')
    EXTERNAL_PROVIDERS[provider_id] = verifier

def verify_external(provider_id, certificate_reference):
    """Verify only through an authorized integration; never guess authenticity."""
    verifier = EXTERNAL_PROVIDERS.get(provider_id)
    if not verifier:
        return 'EXTERNAL_UNSUPPORTED', {
            'provider_id': provider_id,
            'message': 'No trusted verification integration is configured for this provider.'
        }
    result = verifier(certificate_reference)
    if result is True:
        return 'EXTERNAL_VERIFIED', {
            'provider_id': provider_id,
            'message': 'The authorized provider integration verified this certificate.'
        }
    return 'EXTERNAL_UNVERIFIED', {
        'provider_id': provider_id,
        'message': 'The authorized provider integration could not verify this certificate.'
    }
def revoke(cid, reason_code, explanation, actor='admin'):
    with connect() as c:
        row=c.execute('SELECT status FROM credentials WHERE id=?',(cid,)).fetchone()
        if not row: raise LookupError('Credential not found')
        if row['status']=='REVOKED': return False
        c.execute("UPDATE credentials SET status='REVOKED' WHERE id=?",(cid,)); rid=f'REV-{cid}-01'
        c.execute('INSERT INTO revocations VALUES(?,?,?,?,?,?)',(rid,cid,reason_code,explanation,now(),actor)); audit(c,'CREDENTIAL_REVOKED','credential',cid,actor,json.dumps({'reason_code':reason_code})); return True
