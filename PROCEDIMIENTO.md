# Tarea diaria: poner al día extras.json y revisar las fuentes

Datos siempre reales: nada inventado ni estimado. Si algo no se puede comprobar, no se apunta.

## 1. Vuelos baratos (Kiwi.com)

Una búsqueda por aeropuerto, todas el mismo día, con el conector de Kiwi.com:

- Aeropuertos: Almería (LEI), Granada (GRX), Málaga (AGP) y Murcia (RMU).
- `flyTo: "Europe"`, `one_for_city: true`, `max_sector_stopovers: 0` (solo directos),
  `nights_in_dst_from: 2`, `nights_in_dst_to: 5`, `sort: "price"`, `locale: "es"`.
- **Salida con al menos 3 días de antelación**: `departureDate` = día de la búsqueda + 3 días como mínimo
  y `departureDateTo` unas 4–5 semanas después. Nunca vuelos que salgan antes.
- Cada resultado se apunta en un fichero por aeropuerto, una línea por vuelo:
  `precio|bookingUrl|destino IATA|ciudad destino|ida AAAA-MM-DD|origen vuelta IATA|vuelta AAAA-MM-DD|compañía ida|compañía vuelta`
- `python3 herramientas/vuelos.py extras.json LEI=lei.txt GRX=grx.txt AGP=agp.txt RMU=rmu.txt --buscado AAAA-MM-DD --busqueda "…"`
  guarda hasta 6 por aeropuerto con su enlace (la tele dibuja el QR del más barato).

## 2. Sorteos de Instagram (de Motril a Almería capital)

Zona: Motril, Torrenueva, Calahonda, Castell de Ferro, La Mamola, Albuñol, La Rábita, Adra, Berja, Dalías,
El Ejido, Almerimar, Balanegra, Vícar, La Mojonera, Roquetas, Aguadulce, Almería. Fuera: los de toda España.

- **Nunca** entrar en Instagram con ninguna cuenta, ni leerlo con un navegador automatizado, ni saltarse
  robots.txt o comprobaciones anti-bots.
- Dónde buscar: búsqueda web pública (comercios, centros comerciales, ayuntamientos, medios locales, con sus bases)
  y el agregador sortea2.com filtrando por los pueblos de la zona.
- Solo se apunta si se ha visto en la publicación o en sus bases: cuenta, premio, pueblo, fecha y hora de fin y enlace.
- `python3 herramientas/sorteos.py extras.json --anadir --cuenta … --premio … --lugar … --hasta AAAA-MM-DDTHH:MM --enlace … [--como …] [--fuente …]`;
  si no hay ninguno, `--buscado`. Quita los que ya han acabado.

## 2a. Buzón de capturas (sorteos y cortes que llegan a mano)

Las capturas de pantalla de publicaciones se dejan en una carpeta privada de Google Drive. Una tarea aparte las
revisa varias veces al día con el conector de Drive; Instagram no se abre en ningún momento.

- `download_file_content` de cada captura y luego `python3 -I herramientas/captura.py FILEID /tmp/buzon`: busca la
  descarga donde la haya dejado Claude Code (registro de la sesión o fichero aparte si es grande), la guarda como
  imagen y, si es alta, la parte en trozos que se leen bien. Se miran con Read.
- Sorteo: mismas reglas que el punto 2. La cuenta es la que publica; el enlace, el de la publicación si se ve en la
  captura o en el nombre o la descripción del fichero, y si no el del perfil (`https://www.instagram.com/<cuenta>/`,
  sin abrirlo). Si dice el día de fin sin hora, hasta las 23:59 de ese día; si no dice el año, el próximo.
  `--fuente captura`.
- Corte anunciado (agua, luz, tráfico) en Adra: con `cortes.py` (punto 2b).
- Si falta algún dato obligatorio, no se apunta y la captura se marca para revisar. Las que ya han acabado, las de
  fuera de la zona y las que no son sorteos ni cortes se archivan sin apuntar.
- Opcional, API oficial de Instagram: `python3 herramientas/instagram_oficial.py @cuenta1 @cuenta2 …` lee con
  Business Discovery las publicaciones recientes de cuentas profesionales de la zona y propone las que hablan de
  sorteos (mismas reglas para apuntarlas, con su enlace). Necesita las variables de entorno `IG_TOKEN` e
  `IG_USER_ID`; sin ellas no hace nada. El token no se escribe nunca en el repositorio ni en la salida.

## 2b. Cortes anunciados en redes del Ayuntamiento

Los avisos de cortes que el Ayuntamiento publica en sus redes no se leen automáticamente (Instagram no se lee).
Cuando llegue uno (enlace o captura), se apunta con
`python3 herramientas/cortes.py extras.json --tipo luz|agua|trafico --titulo … --hasta AAAA-MM-DD --enlace …`.
La tarea diaria solo ejecuta `python3 herramientas/cortes.py extras.json` para quitar los que ya pasaron.

## 3. Revisión de las fuentes de la app

`python3 herramientas/revisar_fuentes.py --json revision.json`: pide cada fuente como la app y comprueba la marca
de la que depende. Si alguna sale **ROTA**, avisar con el nombre de la fuente y el fallo. «NO COMPROBABLE»
(Red Eléctrica bloquea servidores en la nube) no es un fallo.

## 4. Guardar

Comprobar que `extras.json` es JSON válido y que conserva `embalses`, `butano` y los demás campos; hacer commit
(«Datos del AAAA-MM-DD») y push a `main`.
