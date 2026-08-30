set -euo pipefail
rm -rf data candidates
mkdir -p data candidates

validate_db() {
  DB="$1" python - <<'PY'
import os, sqlite3, sys

db = os.environ["DB"]
required = {
    "providers", "categories", "content", "seasons", "episodes",
    "versions", "streams", "content_categories", "stream_categories",
    "series_sources", "sync_runs", "change_events", "sync_state",
}
try:
    with sqlite3.connect(db) as con:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
except Exception as exc:
    print(f"  Error validando SQLite: {exc}")
    sys.exit(1)

print("  Tablas encontradas:", ", ".join(sorted(tables)))
print("  integrity_check:", integrity)
missing = required - tables
if integrity != "ok" or missing:
    if missing:
        print("  Faltan tablas:", ", ".join(sorted(missing)))
    sys.exit(1)
print("  Esquema persistente v0.3/v0.3.1 compatible: OK")
PY
}

find_db() {
  find candidates -type f \
    \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) \
    -print -quit
}

try_artifact() {
  local run_id="$1"
  local artifact="$2"
  rm -rf candidates/*
  echo "Probando run $run_id / artifact $artifact"
  if ! gh run download "$run_id" --name "$artifact" --dir candidates; then
    echo "  No se pudo descargar el artifact."
    return 1
  fi
  local db
  db="$(find_db || true)"
  if [ -z "$db" ]; then
    echo "  El artifact no contiene una BD reconocible."
    find candidates -maxdepth 3 -type f -print || true
    return 1
  fi
  echo "  BD candidata: $db ($(du -h "$db" | cut -f1))"
  if validate_db "$db"; then
    cp "$db" data/iptv_manager.db
    echo "  BD aceptada."
    return 0
  fi
  echo "  BD descartada."
  return 1
}

FOUND=0
echo "Buscando catálogo persistente v0.3.1..."
mapfile -t RUNS < <(
  gh run list --workflow 03-1-sync-persistent.yml --status success --limit 10 \
    --json databaseId --jq '.[].databaseId'
)
for RUN in "${RUNS[@]}"; do
  [ -n "$RUN" ] || continue
  if try_artifact "$RUN" "iptv-manager-v031-catalog"; then
    FOUND=1
    break
  fi
done

if [ "$FOUND" -eq 0 ]; then
  echo "No se encontró una BD compatible en v0.3.1; probando v0.3..."
  mapfile -t RUNS < <(
    gh run list --workflow 06-sync-catalog-v03.yml --status success --limit 10 \
      --json databaseId --jq '.[].databaseId'
  )
  for RUN in "${RUNS[@]}"; do
    [ -n "$RUN" ] || continue
    if try_artifact "$RUN" "iptv-manager-v03-catalog"; then
      FOUND=1
      break
    fi
  done
fi

if [ "$FOUND" -ne 1 ]; then
  echo "ERROR: no se encontró ningún catálogo persistente compatible."
  exit 1
fi

echo "BD final: $(du -h data/iptv_manager.db | cut -f1)"
rm -rf candidates

