from fastapi.testclient import TestClient
from app.main import app


def main() -> None:
    client = TestClient(app)
    checks = []

    r = client.get('/')
    assert r.status_code == 200 and r.json()['version'] == '0.5.0'
    checks.append('GET /')

    r = client.get('/api/catalog/movie?page=1&page_size=5')
    assert r.status_code == 200
    movie_page = r.json()
    assert movie_page['page'] == 1 and movie_page['page_size'] == 5 and 'items' in movie_page
    checks.append('paginación películas')

    r = client.get('/api/catalog/series?page=1&page_size=5')
    assert r.status_code == 200 and 'items' in r.json()
    checks.append('paginación series')

    r = client.get('/api/search?q=amz&page=1&page_size=10')
    assert r.status_code == 200 and r.json()['total'] >= len(r.json()['items'])
    checks.append('búsqueda paginada')

    if movie_page['items']:
        movie_id = movie_page['items'][0]['id']
        r = client.get(f'/api/movies/{movie_id}')
        assert r.status_code == 200 and 'versions' in r.json()
        checks.append('ficha película + versiones')

    series_page = client.get('/api/catalog/series?page=1&page_size=1').json()
    if series_page['items']:
        series_id = series_page['items'][0]['id']
        r = client.get(f'/api/series/{series_id}')
        assert r.status_code == 200 and 'seasons' in r.json()
        checks.append('ficha serie + temporadas')

    for path in ('/ui/', '/ui/style.css', '/ui/app.js'):
        r = client.get(path)
        assert r.status_code == 200
        checks.append(path)

    print('IPTV MANAGER — v0.5.0: PRUEBA DE BIBLIOTECA')
    print('=' * 72)
    for check in checks:
        print(f'  OK | {check}')
    print('=' * 72)
    print('v0.5.0 BASE COMPLETADA')


if __name__ == '__main__':
    main()
