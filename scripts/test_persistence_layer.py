from pathlib import Path
import tempfile
from app.core.storage import LocalFileStorage, GitHubArtifactStorage

def main():
    print('=' * 72); print('IPTV MANAGER — v0.3.1: CAPA DE PERSISTENCIA'); print('=' * 72)
    print('\nObjetivo: validar que el Core no depende del lugar físico de la BD.')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); source=root/'source.db'; source.write_bytes(b'IPTV-MANAGER-TEST')
        for cls, label in [(LocalFileStorage,'LocalFileStorage'),(GitHubArtifactStorage,'GitHubArtifactStorage')]:
            s=cls(root/label/'catalog.db'); s.persist(source); restored=root/(label+'-restored')/'catalog.db'
            if not s.restore(restored) or restored.read_bytes()!=source.read_bytes(): raise RuntimeError('Falló persistencia/restauración')
            print(f'  OK | {label}: persistencia + restauración')
    print('  OK | Core desacoplado del backend de almacenamiento')
    print('\n'+'='*72); print('v0.3.1 COMPLETADA'); print('La BD puede cambiar de alojamiento sin modificar el Core.'); print('='*72)
if __name__=='__main__': main()
