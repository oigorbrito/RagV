"""Synthetic, local sanitizer tests; no database, provider or real credentials."""
import json
import pytest
from hypothesis import given, settings, strategies as st
from app.log_safety import REDACTED, sanitize_error_message

@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    # No real environment secret is ever needed to qualify lexical redaction.
    from app.log_safety import _SECRET_ENV_NAMES
    for name in _SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

CASES = [
    ('Authorization: Bearer SYNTHETIC_BEARER_250 status=401 host=api.test', ['SYNTHETIC_BEARER_250'], ['status=401', 'host=api.test']),
    ('authorization=Bearer SYNTHETIC_BEARER_250 request_id=abc', ['SYNTHETIC_BEARER_250'], ['request_id=abc']),
    ('postgresql://worker:SYNTHETIC_DB_250@db.test:5432/rpy code=timeout', ['SYNTHETIC_DB_250'], ['worker:', 'db.test:5432/rpy', 'code=timeout']),
    ('https://u:SYNTHETIC_URI_250@hooks.test/cb?status=retry', ['SYNTHETIC_URI_250'], ['hooks.test/cb', 'status=retry']),
    ('https://hooks.test/cb?webhook_key=SYNTHETIC_HOOK_250&request_id=abc', ['SYNTHETIC_HOOK_250'], ['hooks.test/cb', 'request_id=abc']),
    ('callback-key=SYNTHETIC_CALLBACK_250; status=failed', ['SYNTHETIC_CALLBACK_250'], ['status=failed']),
    ('CALLBACK_SECRET=SYNTHETIC_CALLBACK_250, code=E123', ['SYNTHETIC_CALLBACK_250'], ['code=E123']),
    ('error credential=SYNTHETIC_CRED_250 status=403', ['SYNTHETIC_CRED_250'], ['status=403']),
    ('passwd=SYNTHETIC_PASS_250 pwd=SYNTHETIC_PWD_250 credentials=SYNTHETIC_CREDS_250', ['SYNTHETIC_PASS_250', 'SYNTHETIC_PWD_250', 'SYNTHETIC_CREDS_250'], ['passwd=', 'pwd=', 'credentials=']),
    ('rpy_SYNTHETIC_TOKEN_250 request_id=abc rpy_SYNTHETIC_TOKEN_250', ['rpy_SYNTHETIC_TOKEN_250'], ['request_id=abc']),
    ('callback_key=***SYNTHETIC_VISIBLE_250 code=E123', ['SYNTHETIC_VISIBLE_250'], ['code=E123']),
    ('pwd=[REDACTED]SYNTHETIC_VISIBLE_250 status=500', ['SYNTHETIC_VISIBLE_250'], ['status=500']),
    ('callback_key="SYNTHETIC_ALPHA_250 SYNTHETIC_BETA_250" status=500', ['SYNTHETIC_ALPHA_250', 'SYNTHETIC_BETA_250'], ['status=500']),
    ("pwd='SYNTHETIC_ALPHA_250;SYNTHETIC_BETA_250' code=E123", ['SYNTHETIC_ALPHA_250', 'SYNTHETIC_BETA_250'], ['code=E123']),
    ('{"callback_key":"SYNTHETIC_ESCAPED_250\\\"SYNTHETIC_TAIL_250", "status":500}', ['SYNTHETIC_ESCAPED_250', 'SYNTHETIC_TAIL_250'], ['"status":500']),
]

@pytest.mark.parametrize('value,secrets,preserve', CASES)
def test_sensitive_values_removed_diagnostics_retained(value, secrets, preserve):
    rendered = sanitize_error_message(value)
    for secret in secrets:
        assert secret not in rendered
    for useful in preserve:
        assert useful in rendered
    assert REDACTED in rendered

@pytest.mark.parametrize('value', [
    'GET /health status=503 request_id=abc host=db.test duration_ms=12',
    'credential_count=0 token_count=7 callback_key_count=2 password_policy=enabled',
    'The credential is unavailable; callback status failed; connection timed out.',
    'cwd=/srv/ragv result_count=0 code=ECONNREFUSED',
    'public_key_identifier=fixture-01 webhook_attempt=3 callback_status=retry',
])
def test_non_sensitive_diagnostics_unchanged(value):
    assert sanitize_error_message(value) == value

@pytest.mark.parametrize('key', ['pwd', 'passwd', 'credential', 'credentials', 'webhook_key', 'callback-key'])
def test_already_masked_values_remain_stable(key):
    value = f'{key}={REDACTED} status=403'
    assert sanitize_error_message(value) == value

@settings(max_examples=160, deadline=None, derandomize=True)
@given(key=st.sampled_from(['pwd', 'passwd', 'credential', 'credentials', 'webhook_key', 'callback_key', 'callback_token', 'webhook_secret']), quote=st.sampled_from(['', '"', "'"]), secret=st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-', min_size=12, max_size=48))
def test_generated_keys_and_token_values(key, quote, secret):
    text = f'{key}={quote}{secret}{quote} request_id=abc status=500'
    rendered = sanitize_error_message(text)
    assert secret not in rendered
    assert 'request_id=abc status=500' in rendered

@settings(max_examples=100, deadline=None, derandomize=True)
@given(secret=st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-;,', min_size=12, max_size=48))
def test_quoted_json_value_redacts_entire_value(secret):
    text = json.dumps({'callback_key': 'SYNTHETIC_PREFIX_' + secret, 'status': 'retry'})
    rendered = sanitize_error_message(text)
    assert 'SYNTHETIC_PREFIX_' not in rendered
    assert json.loads(rendered) == {'callback_key': REDACTED, 'status': 'retry'}

def test_configured_secret_with_spaces_is_removed(monkeypatch):
    monkeypatch.setenv('DATAJUD_API_KEY', 'SYNTHETIC configured secret 250')
    rendered = sanitize_error_message('DataJud error SYNTHETIC configured secret 250 status=401')
    assert 'SYNTHETIC configured secret 250' not in rendered
    assert 'DataJud error' in rendered and 'status=401' in rendered

@pytest.mark.parametrize('limit', [0, 1, 12, 80, 2000])
def test_bound_applies_after_redaction(limit):
    value = ('callback_key=SYNTHETIC_VALUE_250 request_id=abc ' * 100)
    rendered = sanitize_error_message(value, max_chars=limit)
    assert len(rendered) <= limit
    assert 'SYNTHETIC_VALUE_250' not in rendered
