import pytest
from fastapi.testclient import TestClient
from backend.app import db
from backend.app.main import app
from backend.app.seed import seed
from backend.app.domain import verify, revoke, issue

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'test.db')
    seed('starter',20261022)

def test_valid_then_revoked():
    assert verify('CRD-2026-000001')[0]=='VALID'
    assert revoke('CRD-2026-000001','ADMIN','Demonstrated revocation') is True
    assert verify('CRD-2026-000001')[0]=='REVOKED'

def test_tampering_is_detected():
    with db.connect() as c:c.execute("UPDATE credentials SET payload_hash='bad' WHERE id='CRD-2026-000001'")
    assert verify('CRD-2026-000001')[0]=='TAMPERED'

def test_ineligible_issuance_rejected():
    with pytest.raises(ValueError): issue('LRN-000080','CRS-0012')

def test_issuance_before_completion_is_rejected():
    with pytest.raises(ValueError, match='before completion'):
        issue('LRN-000001','CRS-0001',issued_at='2026-01-14T00:00:00+00:00')

def test_signature_cannot_be_recomputed_from_public_data():
    with db.connect() as c:
        c.execute("UPDATE credentials SET signature='bad' WHERE id='CRD-2026-000001'")
    assert verify('CRD-2026-000001')[0]=='TAMPERED'

def test_seed_is_reproducible_but_seed_sensitive():
    with db.connect() as c:
        first=[row['score'] for row in c.execute('SELECT score FROM completions ORDER BY id')]
    seed('starter', 99)
    with db.connect() as c:
        different=[row['score'] for row in c.execute('SELECT score FROM completions ORDER BY id')]
    seed('starter', 20261022)
    with db.connect() as c:
        restored=[row['score'] for row in c.execute('SELECT score FROM completions ORDER BY id')]
    assert first != different
    assert first == restored

def test_repeated_issuance_is_idempotent():
    cid,reused=issue('LRN-000001','CRS-0001')
    assert (cid,reused)==('CRD-2026-000001',True)

def test_unknown_and_unique_identifier():
    assert verify('CRD-nope')[0]=='UNKNOWN'
    with db.connect() as c:
        with pytest.raises(Exception): c.execute("INSERT INTO credentials(id,learner_id,course_id,completion_id,issuer_id,rule_id,issued_at,payload_hash,signature,status) SELECT id,learner_id,course_id,completion_id,issuer_id,rule_id,issued_at,payload_hash,signature,status FROM credentials WHERE id='CRD-2026-000001'")

def test_operational_api_details_filters_and_validation():
    with TestClient(app) as client:
        credentials = client.get('/api/v1/credentials?page_size=5').json()
        assert credentials['total'] == 40 and len(credentials['items']) == 5
        detail = client.get('/api/v1/credentials/CRD-2026-000001').json()
        assert detail['issuer']['name'] == 'Credentia Academy'
        assert detail['completion']['status'] == 'COMPLETED'
        assert detail['rule']['version'] == 1
        audit = client.get('/api/v1/audit?event_type=CREDENTIAL_ISSUED&page_size=3').json()
        assert audit['total'] == 40 and len(audit['items']) == 3
        report = client.get('/api/v1/validation').json()
        assert report['records_checked'] > 0 and report['payload_integrity_failures'] == 0
