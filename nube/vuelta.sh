#!/usr/bin/env bash
# 4.21 (lo pidió Isa el 4 nov 2026: «quiero que sea una dirección html que se pueda ver desde cualquier dispositivo»): una vuelta de la
# página en internet (https://nenita111.github.io/tiempo-datos/). La ejecuta .github/workflows/nube.yml cada media hora; a mano:
#   bash nube/vuelta.sh
# - dependencias.txt: Robolectric y lo suyo (Maven Central y Google), comprobado con su SHA-256; se guardan en la caché de GitHub.
# - tiempo-nube.jar: la parte de la app que baja los datos (la misma que en la tele) y NubeTest (lo pone tiempo-app/herramientas/publicar_nube.py).
# - estado/: lo de la vuelta anterior (caché de GitHub); web/: la página que se publica (pagina/ con datos.json y sus fotos).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p deps android estado
grep -v '^#' dependencias.txt | while read -r url sha destino tipo; do
  [ -n "$url" ] || continue
  [ -f "$destino" ] && continue
  [ -n "${MAVEN_ESPEJO:-}" ] && url="${url/https:\/\/repo1.maven.org\/maven2\//$MAVEN_ESPEJO}"
  tmp="$destino.descarga"
  curl -fsSL --retry 3 "$url" -o "$tmp"
  echo "$sha  $tmp" | sha256sum -c --quiet -
  if [ "${tipo:-}" = aar ]; then unzip -p "$tmp" classes.jar > "$destino"; rm -f "$tmp"; else mv "$tmp" "$destino"; fi
done
rm -rf web && mkdir -p web
export TZ=Europe/Madrid
java -Xmx2g -Duser.timezone=Europe/Madrid -Duser.language=es -Duser.country=ES \
  -cp "tiempo-nube.jar:deps/*:android/android-all-instrumented-14-robolectric-10818077-i7.jar" \
  -Drobolectric.offline=true -Drobolectric.dependency.dir="$PWD/android" \
  -Dnube.dir="$PWD/estado" -Dnube.salida="$PWD/web" -Dnube.limite="${NUBE_LIMITE:-600}" -Dnube.municipios="$PWD/pagina/almeria.json" \
  org.junit.runner.JUnitCore com.isa.tiempo.NubeTest > vuelta.log 2>&1 || true
grep -E "^\.?NUBE|^OK|^Tests run|^[0-9]+\) |Exception" vuelta.log | grep -v "^Picked up" | head -40 || true
grep -q "^OK (1 test)" vuelta.log && [ -s web/datos.json ] || { echo "La vuelta no ha salido bien: no se publica (queda la página anterior)"; exit 1; }
# la página: la de la tele con movil.js delante, en modo internet (NUBE), que se pueda ampliar y que no salga en los buscadores
python3 - <<'PY'
import os, shutil
for raiz, _, ficheros in os.walk("pagina"):
    for f in ficheros:
        o = os.path.join(raiz, f); d = os.path.join("web", os.path.relpath(o, "pagina"))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if f != "index.html": shutil.copyfile(o, d)
h = open("pagina/index.html", encoding="utf-8").read()
a, b = '<meta charset="utf-8">', "initial-scale=1, maximum-scale=1, user-scalable=no"
assert h.count(a) == 1 and h.count(b) == 1, "index.html ha cambiado: revisar vuelta.sh"
h = h.replace(a, a + '\n<meta name="robots" content="noindex, nofollow">\n<script>window.NUBE = 1</script>\n<script src="movil.js"></script>', 1)
h = h.replace(b, "initial-scale=1, maximum-scale=8, user-scalable=yes", 1)
open("web/index.html", "w", encoding="utf-8").write(h)
open("web/.nojekyll", "w").close()
PY
echo "Página lista: $(du -sh web | cut -f1)"
