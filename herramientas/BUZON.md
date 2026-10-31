# Buzón de capturas (lo lee la tarea «Avisos y buzón» solo cuando hay capturas)

Isa deja en su carpeta de Drive «Sorteos tele» capturas de publicaciones: sorteos, cortes anunciados, actividades del pueblo
(carteles) o colectas de sangre. Se apuntan en extras.json. Todo sale de lo que se lee en la captura: nada inventado, estimado
ni deducido. No se entra en Instagram (ni con cuenta ni sin ella, ni con navegador, WebFetch o curl). El repositorio es público:
nada personal (ni nombres de personas, ni correos, ni rutas, ni ids de Drive).

Para cada captura (como mucho 15 por pasada, de la más antigua a la más nueva):

1. download_file_content con su fileId. No leas ni copies el base64: en la raíz del repositorio
   `python3 -I herramientas/captura.py <fileId> /tmp/buzon` y mira con Read cada fichero que imprima (la imagen y, si es alta,
   sus trozos). Si no la encuentra o no se abre: «REVISAR (no se pudo leer)».
2. Escribe en /tmp/buzon/<fileId>.txt todo el texto que se lee, tal cual. Decide qué es: sorteo, corte, actividad o colecta (si no
   es nada de eso, «NO ES SORTEO»).
3. Antes de apuntar, compruébalo con Jev en el sandbox de Composio (la celda de composio_jev.py del paso 3 de la tarea, si aún no
   está cargada): `print(jev_captura("SHA", r"""<texto de /tmp/buzon/<fileId>.txt>""", {"cuenta": "…", "premio": "…", "lugar": "…",
   "hasta": "…"}, "<sorteo|corte|actividad|colecta>"))` con cada dato tal como se lee (actividad o colecta: titulo, fecha, horario,
   lugar). Si «ok» es false, no se apunta: «REVISAR (no cuadra <campos de «no_cuadra»>)» («tipo»: Jev ve otra cosa; dilo con su
   campo «tipo»). Sin conector o con error: `python3 -I herramientas/comprobar_captura.py --texto /tmp/buzon/<fileId>.txt --tipo …
   --dato campo=valor …` (sale con 1 si no cuadra; «sin Jev»: sigue sin comprobar).
4. Según lo que sea (sin año → el próximo a partir de la fecha de la captura, createdTime; ya pasado → «ACABADO»):
   - Sorteo de la zona (Motril, Torrenueva, Calahonda, Castell de Ferro, La Mamola, Albuñol, La Rábita, Adra, Berja, Dalías,
     El Ejido, Almerimar, Balanegra, Vícar, La Mojonera, Roquetas, Aguadulce, Almería; fuera de ahí o para toda España, «FUERA»).
     Hacen falta cuenta, premio, pueblo y fecha y hora de fin (día sin hora → 23:59). Enlace: el de la publicación si se ve en la
     captura o en el título o la descripción del fichero (get_file_metadata); si no, `https://www.instagram.com/<cuenta>/` (sin
     abrirlo). `python3 herramientas/sorteos.py extras.json --anadir --cuenta … --premio … --lugar … --hasta AAAA-MM-DDTHH:MM
     --enlace … --como "<cómo participar, breve, si se ve>" --fuente captura`
   - Corte (agua, luz o tráfico) en Adra: `python3 herramientas/cortes.py extras.json --tipo agua|luz|trafico --titulo "<qué,
     cuándo y dónde, como lo dice>" --hasta AAAA-MM-DD --enlace … --fuente "<la cuenta que lo publica>"`
   - Actividad en Adra (con el día; sin él, «REVISAR (falta el día)»): `python3 herramientas/agenda.py extras.json --titulo …
     --fecha AAAA-MM-DD [--hora HH:MM] [--hasta AAAA-MM-DD] [--lugar …] --enlace … --fuente …`
   - Colecta de sangre en Adra (con día y lugar; si no, «REVISAR (falta …)»; en otro pueblo, «FUERA»): `python3 herramientas/sangre.py
     extras.json --fecha AAAA-MM-DD [--horario HH:MM-HH:MM …] --lugar … --enlace … --fuente …`
5. Cómo acaba cada una: «OK», «REVISAR (falta …)» / «REVISAR (no cuadra …)», «ACABADO», «FUERA» o «NO ES SORTEO».

Después del push de la tarea (o si no había nada que subir), en Drive con update_file: «OK», «ACABADO», «FUERA» y «NO ES SORTEO»
se mueven a «Procesados» (parentId 1lTa7VbZA-nA0Edt5DavBzwr6Ga9ZMTIc) con el título «<estado> – <título original>»; las
«REVISAR (…)» se quedan en su sitio con eso delante del título (y la tarea las salta la próxima vez).

API oficial de Instagram (solo si la variable IG_TOKEN existe: `test -n "$IG_TOKEN"`; nunca la imprimas): lee con read_file_content el
documento «Cuentas a vigilar» (fileId 1CJM_CuvJWRE998Etx6ofOXSQzQFEDWBc0bhKfveQAUs), quédate con las líneas que empiezan por @ y
`python3 herramientas/instagram_oficial.py <cuentas> > /tmp/candidatos.json` (código 3: no configurada). Cada candidato, con las
reglas del sorteo de arriba y `--fuente "API de Instagram"`; si no trae todos los datos, no se apunta.
