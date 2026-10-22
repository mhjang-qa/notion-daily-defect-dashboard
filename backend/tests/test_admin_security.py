import hashlib
import hmac
import time

from fastapi.testclient import TestClient
from app import main


def test_missing_password_disables_admin_even_with_signed_cookie(monkeypatch):
    monkeypatch.setattr(main.settings, 'embed_admin_password', '')
    client = TestClient(main.app)
    assert client.post('/api/embed/hanpass-renewal/admin-login', json={'password': ''}).status_code == 503
    client.cookies.set(main.ADMIN_COOKIE_NAME, main.make_embed_admin_token())
    assert client.get('/embed/hanpass-renewal-admin').status_code == 503


def test_login_cookie_authorizes_admin_and_password_change_revokes_it(monkeypatch):
    monkeypatch.setattr(main.settings, 'embed_admin_password', 'test-only-password')
    client = TestClient(main.app, base_url='https://testserver')
    assert client.get('/embed/hanpass-renewal-admin').status_code == 401
    assert client.post('/api/embed/hanpass-renewal/admin-login', json={'password': 'wrong'}).status_code == 401
    response = client.post('/api/embed/hanpass-renewal/admin-login', json={'password': 'test-only-password'})
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/embed/hanpass-renewal-admin').status_code == 200
    monkeypatch.setattr(main.settings, 'embed_admin_password', 'changed-password')
    assert client.get('/embed/hanpass-renewal-admin').status_code == 401


def test_public_database_id_cannot_forge_admin_cookie(monkeypatch):
    monkeypatch.setattr(main.settings, 'embed_admin_password', 'test-only-password')
    monkeypatch.setattr(main.settings, 'notion_token', '')
    monkeypatch.setattr(main.settings, 'notion_database_id', 'public-id')
    expiry = str(int(time.time()) + 60)
    signature = hmac.new(b'public-id', expiry.encode(), hashlib.sha256).hexdigest()
    client = TestClient(main.app)
    client.cookies.set(main.ADMIN_COOKIE_NAME, f'{expiry}:{signature}')
    assert client.get('/embed/hanpass-renewal-admin').status_code == 401


def test_expired_cookie_is_rejected(monkeypatch):
    monkeypatch.setattr(main.settings, 'embed_admin_password', 'test-only-password')
    expiry = str(int(time.time()) - 1)
    signature = hmac.new(main._embed_admin_secret(), expiry.encode(), hashlib.sha256).hexdigest()
    client = TestClient(main.app)
    client.cookies.set(main.ADMIN_COOKIE_NAME, f'{expiry}:{signature}')
    assert client.get('/embed/hanpass-renewal-admin').status_code == 401
