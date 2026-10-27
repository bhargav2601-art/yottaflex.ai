import pytest
from fastapi.testclient import TestClient
from backend.app import db
from backend.app.main import app
from backend.app.seed import seed
from backend.app.domain import verify, revoke, issue, EXTERNAL_PROVIDERS, register_external_provider, verify_external
from backend.app.validate import build_report

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'test.db')
    EXTERNAL_PROVIDERS.clear()
    seed('starter',20261022)

def test_valid_then_revoked():
    assert verify('CRD-2026-000001')[0]=='VALID'
    assert revoke('CRD-2026-000001','ADMIN','Demonstrated revocation') is True
    assert verify('CRD-2026-000001')[0]=='REVOKED'

def test_tampering_is_detected():
    with db.connect() as c:c.execute("UPDATE credentials SET payload_hash='bad' WHERE id='CRD-2026-000001'")
    assert verify('CRD-2026-000001')[0]=='TAMPERED'

def test_ineligible_issuance_rejected():
    with db.connect() as c:
        before=c.execute('SELECT COUNT(*) FROM credentials').fetchone()[0]
    with pytest.raises(ValueError, match='Missing applicable rule or completion'):
        issue('LRN-000080','CRS-0012')
    with db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM credentials').fetchone()[0] == before

def test_insufficient_completion_and_unknown_references_are_rejected():
    with db.connect() as c:
        c.execute("INSERT INTO completions VALUES(?,?,?,?,?,?,?)", ('CMP-LOW','LRN-000080','CRS-0012','COMPLETED',69,'2026-01-15','test'))
    with pytest.raises(ValueError, match='does not meet'):
        issue('LRN-000080','CRS-0012')
    with pytest.raises(ValueError, match='Missing applicable'):
        issue('LRN-DOES-NOT-EXIST','CRS-0012')

def test_issuance_before_completion_is_rejected():
    with pytest.raises(ValueError, match='before completion'):
        issue('LRN-000001','CRS-0001',issued_at='2026-01-14T00:00:00+00:00')

def test_signature_cannot_be_recomputed_from_public_data():
    with db.connect() as c:
        c.execute("UPDATE credentials SET signature='bad' WHERE id='CRD-2026-000001'")
    assert verify('CRD-2026-000001')[0]=='TAMPERED'

def test_validation_detects_issued_before_completion_without_corrupting_seed_data():
    with db.connect() as c:
        c.execute("UPDATE completions SET completed_on='2026-12-31' WHERE id='CMP-000001'")
    assert build_report()['issuance_before_completion'] == 1

def test_untrusted_issuer_is_distinct_from_unknown():
    with db.connect() as c:
        c.execute("UPDATE issuers SET active=0 WHERE id='ISS-PRIMARY'")
    assert verify('CRD-2026-000001')[0] == 'INVALID_ISSUER'
    assert verify('CRD-NOT-REGISTERED')[0] == 'UNKNOWN'

def test_external_provider_boundary_requires_authorized_adapter():
    EXTERNAL_PROVIDERS.clear()
    decision, details = verify_external('other-academy', 'EXT-123')
    assert decision == 'EXTERNAL_UNSUPPORTED'
    assert 'No trusted' in details['message']
    with pytest.raises(ValueError):
        register_external_provider('other-academy', lambda _: True)
    register_external_provider('other-academy', lambda ref: ref == 'EXT-123', authorized=True)
    assert verify_external('other-academy', 'EXT-123')[0] == 'EXTERNAL_VERIFIED'
    assert verify_external('other-academy', 'EXT-404')[0] == 'EXTERNAL_UNVERIFIED'

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

def test_verification_and_revocation_write_audit_history():
    verify('CRD-2026-000001')
    revoke('CRD-2026-000001','ADMIN','A test revocation reason')
    with db.connect() as c:
        events=[r['event_type'] for r in c.execute("SELECT event_type FROM audit_events WHERE entity_id='CRD-2026-000001'")]
    assert 'CREDENTIAL_VERIFIED' in events
    assert 'CREDENTIAL_REVOKED' in events

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
        unknown = client.post('/api/v1/public/verify/CRD-NOT-REGISTERED').json()
        assert unknown['decision'] == 'UNKNOWN' and unknown['classification'] == 'CREDENTIA_UNKNOWN'
        external = client.post('/api/v1/public/verify-external', json={'provider_id':'not-configured','certificate_reference':'EXT-1'}).json()
        assert external['decision'] == 'EXTERNAL_UNSUPPORTED'
        assert client.post('/api/v1/credentials/issue', json={'learner_id':'LRN-000080','course_id':'CRS-0012'}).status_code == 422
        assert client.post('/api/v1/credentials/CRD-NOT-REGISTERED/revoke', json={'reason_code':'ADMIN','explanation':'Valid explanation'}).status_code == 404
        assert client.post('/api/v1/public/verify-external', json={'provider_id':'not configured','certificate_reference':'EXT-1'}).status_code == 422

def test_verification_sequence_resilient_to_empty_sequence_table():
    with db.connect() as c:
        c.execute('DELETE FROM verification_sequence')
    db.init_db()
    d, _ = verify('CRD-2026-000001')
    assert d == 'VALID'

def test_concurrent_verification_allocates_unique_ids():
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda i: verify(f'CRD-2026-{(i%40)+1:06d}')[0], range(30)))
    assert len(results) == 30
    assert all(r == 'VALID' for r in results)
    with db.connect() as c:
        total = c.execute('SELECT COUNT(*) FROM verification_requests').fetchone()[0]
        distinct = c.execute('SELECT COUNT(DISTINCT id) FROM verification_requests').fetchone()[0]
        assert total == distinct


