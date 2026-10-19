from fastapi.testclient import TestClient
from app import main


def test_frontend_html_is_not_cached(monkeypatch, tmp_path):
    (tmp_path / 'index.html').write_text('<html>latest-dashboard</html>', encoding='utf-8')
    monkeypatch.setattr(main.settings, 'frontend_dist', str(tmp_path))
    client = TestClient(main.app)
    for url in ['/', '/?_refresh=1234', '/dashboard']:
        response = client.get(url, headers={'If-None-Match': 'old-deployment'})
        assert response.status_code == 200
        assert 'latest-dashboard' in response.text
        assert 'no-store' in response.headers['cache-control']
        assert response.headers['pragma'] == 'no-cache'
        assert response.headers['expires'] == '0'
    assert 'no-store' in client.head('/').headers['cache-control']
