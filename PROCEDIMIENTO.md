# Tarea diaria: poner al día extras.json y revisar las fuentes

Datos siempre reales: nada inventado ni estimado. Si algo no se puede comprobar, no se apunta.

Para gastar pocos tokens, la tarea diaria hace de una vez todo lo que no hay que buscar con
`python3 -I herramientas/diario.py extras.json` (puntos 2b, 2c y 2h sin argumentos, 2d, 2e, 2f, 2g y 3; quita también los sorteos
acabados): imprime una sola línea JSON con lo que ha ido mal, las fuentes ROTAS y cuántas actividades, colectas, sorteos y cortes
hay. Lo único que hace a mano es buscar (vuelos, sorteos, agenda y colectas de sangre) y apuntar lo que encuentre.
Con Jev (sección 7) también deja en extras.json los cortes de los titulares, la receta del día y las etiquetas del SAS, y trae en
«sortea2» los sorteos de la zona de sortea2.com ya filtrados: son los primeros que se miran para el punto 2.

## 1. Vuelos baratos (Kiwi.com)

Una búsqueda por aeropuerto, todas el mismo día, con el conector de Kiwi.com:

- Aeropuertos: Almería (LEI), Granada (GRX), Málaga (AGP) y Murcia (RMU).
- `flyTo: "Europe"`, `one_for_city: true`, `max_sector_stopovers: 0` (solo directos),
  `nights_in_dst_from: 2`, `nights_in_dst_to: 5`, `sort: "price"`, `locale: "es"`.
- **Salida con al menos 3 días de antelación**: `departureDate` = día de la búsqueda + 3 días como mínimo
  y `departureDateTo` unas 4–5 semanas después. Nunca vuelos que salgan antes.
- `python3 -I herramientas/vuelos.py extras.json --sesion --busqueda "…"` toma las respuestas de Kiwi del registro de la sesión
  (la última de cada aeropuerto) y guarda hasta 6 por aeropuerto con su enlace (la tele dibuja el QR del más barato): no hace falta
  copiar nada. Si no las encuentra, cada resultado se apunta en un fichero por aeropuerto, una línea por vuelo
  (`precio|bookingUrl|destino IATA|ciudad destino|ida AAAA-MM-DD|origen vuelta IATA|vuelta AAAA-MM-DD|compañía ida|compañía vuelta`)
  y `python3 herramientas/vuelos.py extras.json LEI=lei.txt GRX=grx.txt AGP=agp.txt RMU=rmu.txt --buscado AAAA-MM-DD --busqueda "…"`.

## 2. Sorteos de Instagram (de Motril a Almería capital)

Zona: Motril, Torrenueva, Calahonda, Castell de Ferro, La Mamola, Albuñol, La Rábita, Adra, Berja, Dalías,
El Ejido, Almerimar, Balanegra, Vícar, La Mojonera, Roquetas, Aguadulce, Almería. Fuera: los de toda España.

- **Nunca** entrar en Instagram con ninguna cuenta, ni leerlo con un navegador automatizado, ni saltarse
  robots.txt o comprobaciones anti-bots.
- Dónde buscar: primero los candidatos de sortea2.com que trae `diario.py` («sortea2»: su RSS, ya filtrado por pueblos y, con Jev, por
  sorteo de un comercio de la zona que dice cuándo acaba; no hace falta leer sortea2.com entero) y después la búsqueda web pública
  (comercios, centros comerciales, ayuntamientos, medios locales, con sus bases).
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
  sorteos (mismas reglas para apuntarlas, con su enlace). Necesita el token de la página en la variable `IG_TOKEN`
  de las «Variables de entorno» del entorno en la nube; el id de la cuenta se averigua solo. Sin el token sale con código 3 y
  no hace nada. `--probar` comprueba si deja leer cuentas
  ajenas. El token no se escribe nunca en el repositorio ni en la salida.

## 2b. Cortes anunciados en redes del Ayuntamiento

Los avisos de cortes que el Ayuntamiento publica en sus redes no se leen automáticamente (Instagram no se lee).
Cuando llegue uno (enlace o captura), se apunta con
`python3 herramientas/cortes.py extras.json --tipo luz|agua|trafico --titulo … --hasta AAAA-MM-DD --enlace …`.
La tarea diaria solo ejecuta `python3 herramientas/cortes.py extras.json` para quitar los que ya pasaron.

## 2c. Agenda del pueblo (pantalla Hoy)

La agenda de la web del Ayuntamiento no se mantiene, así que las actividades de los próximos 8 días se apuntan una a una
cuando se ven en una fuente oficial: la web del Ayuntamiento, sus notas de prensa, sus redes (solo por captura en el
buzón, nunca entrando en ellas) o un medio local que lo cuente citándolo. Búsqueda web pública (sin entrar en redes
sociales ni saltarse robots.txt): el nombre del pueblo con «programa», «actividades», «concierto», «exposición»,
«fin de semana», «feria», «jornadas»… Solo se apunta lo que se ha leído: qué, el día y dónde (la hora si la dice), con el
enlace a la fuente. Sin día, no se apunta; nada deducido.
`python3 herramientas/agenda.py extras.json --titulo … --fecha AAAA-MM-DD [--hora HH:MM] [--hasta AAAA-MM-DD] [--lugar …] --enlace … --fuente …`.
Sin argumentos, solo quita lo que ya pasó (lo hace la tarea diaria).

## 2d. Calendario del cielo (pantalla Espacio)

`python3 herramientas/cielo.py extras.json`: inicio de las estaciones, eclipses visibles en España y cambio de hora de la
Agenda astronómica oficial del IGN (este año y el siguiente, en cuanto la publica) y los máximos de las principales lluvias
de meteoros de la tabla del Observatorio Astronómico Nacional (fecha aproximada). Si el PDF del IGN no se puede bajar, usa la
copia oficial de `herramientas/muestras/`. Lo ejecuta la tarea diaria.

## 2e. Plagas en los invernaderos (pantalla Precios)

`python3 -I herramientas/raif.py extras.json`: de los boletines semanales oficiales de la Red de Alerta e Información
Fitosanitaria de Andalucía (RAIF, Junta de Andalucía) de la provincia de Almería, para tomate, pimiento, pepino, calabacín,
berenjena y sandía, las fechas del boletín y sus «Agentes más destacados», tal cual. La tele solo enseña los cultivos con
boletín de las dos últimas semanas (fuera de temporada, la RAIF deja el último). Si un cultivo no se puede leer, se queda el
que había. Lo ejecuta la tarea diaria.

## 2f. Virus respiratorios (pantalla Planeta)

`python3 -I herramientas/respiratorias.py extras.json`: del «Resumen» del último informe semanal de vigilancia de la infección
respiratoria aguda en Andalucía (red centinela de la Junta; página de la temporada, de la semana 40 a la 39 del año
siguiente), la tasa de infección respiratoria en atención primaria, la de los hospitales y el porcentaje de muestras positivas
de gripe, COVID-19 y VRS, con los de la semana anterior. Solo copia cifras del informe, no calcula nada. Si no hay informe
nuevo no toca nada; si falla, sale con código 2 y deja el que había. Lo ejecuta la tarea diaria.

## 2g. Sequía y escasez de agua (pantalla Semana)

`python3 -I herramientas/sequia.py extras.json`: del «Informe de escasez y sequía» mensual de la Junta (SAIH Hidrosur) para
la demarcación de las Cuencas Mediterráneas Andaluzas, el agua embalsada de la demarcación (este mes y el anterior) y el
índice y el escenario o estado de todas las unidades; la tele enseña las de Adra (UTS 12, UTE 14 y UTE 15, cambiables con
`--unidades`). Solo copia lo que dice el informe. El PDF pesa unos 14 MB y solo se baja si ha cambiado su fecha de
modificación. Si falla, sale con código 2 y deja lo que había. Lo ejecuta la tarea diaria. Necesita `pdftotext`.

## 2h. Colectas de sangre en el pueblo (pantalla Hoy)

La tele lee sola la tabla oficial de colectas del centro de transfusión de la provincia en la web del SAS, pero solo trae los
próximos días (unos tres). Para saberlo antes, búsqueda web pública de colectas de sangre en Adra anunciadas por el Centro de
Transfusión, Tejidos y Células de Almería, la Junta, el Ayuntamiento o un medio que lo cite (Teleprensa, Noticias de Almería, Adra
Digital; La Voz de Almería, Diario de Almería y Google Noticias prohíben en su robots.txt a los agentes como Claude: no se usan),
y los carteles del buzón de capturas. Nunca redes sociales ni saltarse robots.txt. Solo se apunta si se ha leído el día y el lugar
(y el horario si lo dice), con el enlace a la fuente:
`python3 herramientas/sangre.py extras.json --fecha AAAA-MM-DD --horario HH:MM-HH:MM [--horario …] --lugar … --enlace … --fuente …`.
Sin argumentos, solo quita las que ya pasaron (lo hace la tarea diaria).

## 3. Revisión de las fuentes de la app

`python3 herramientas/revisar_fuentes.py --json revision.json`: pide cada fuente como la app y comprueba la marca
de la que depende. Si alguna sale **ROTA**, avisar con el nombre de la fuente y el fallo. «NO COMPROBABLE»
(Red Eléctrica bloquea servidores en la nube) no es un fallo.

## 4. Guardar

Comprobar que `extras.json` es JSON válido y que conserva `embalses`, `butano` y los demás campos; hacer commit
(«Datos del AAAA-MM-DD») y push a `main`.

## 5. Precio de la luz de mañana en el móvil (tarea aparte, cada tarde)

`python3 -I herramientas/luz_movil.py salida.png --esperar 50 --apk app/Tiempo.apk`: lee el PVPC de mañana de Red Eléctrica
(ESIOS, indicador 1001, península; si no, REData una sola vez) y hace una imagen de 1080×2400 con una fila por hora,
su barra y su precio, la hora más barata, la más cara, la media (comparada con hoy) y las 3 horas seguidas más baratas.
Si ESIOS responde pero aún no ha publicado, mira cada 4 minutos hasta `--esperar` minutos. Sin precios no dibuja nada
y sale con código 4. La clave de ESIOS va en la variable `ESIOS_API_KEY` de las «Variables de entorno» del entorno en la nube de la
tarea (los entornos no tienen almacén de secretos; el script la pasa a curl por la entrada): no va en el repositorio. Desde servidores en la nube Red Eléctrica suele rechazar REData.

## 6. Avisos urgentes al móvil (tarea aparte, cada 2 horas)

`python3 -I herramientas/avisos_movil.py --estado avisos_enviados.json --extras extras.json`: avisos naranja o rojo de AEMET
en la zona del pueblo o su costa; terremotos del IGN que se pueden notar (magnitud 3 a menos de 50 km, 3,5 a menos de 100 km,
4 a menos de 200 km); cortes de agua o luz apuntados en extras.json o en los titulares de Noticias de Almería (Google Noticias
y Diario de Almería prohíben en robots.txt a los agentes como este: no se usan); cortes de agua de Hidralia de su mapa de obras y
afectaciones (la capa pública de cierres de Agbar en ArcGIS, la misma que lee la app: planificados o en curso que empiezan en menos
de 36 horas o ya han empezado y no han pasado su previsión de restablecimiento). Imprime una línea JSON con los nuevos y apunta en
`avisos_enviados.json` lo enviado (30 días), para no repetir. Ese fichero solo lleva códigos de avisos públicos.

## 7. Jev (TypeSafe System One): decisiones cerradas en las tareas de la nube

`herramientas/jev.py`: el cliente (sin dependencias) y todas las preguntas y umbrales, en un solo sitio. Jev no escribe: contesta sí/no
con probabilidad o elige una opción de una lista; las fechas, las cuentas y lo exacto se hacen en el código. Nunca va en la app de la tele.

**Por el conector JEV de Composio** (desde el 29 oct 2026, lo pidió Isa: «usa ese conector de ahora en adelante»; la cuenta de Jev es la
suya, conectada en Composio). Las tareas llevan el conector JEV. Los scripts no pueden llamar a un conector, así que va en dos tiempos
(`herramientas/composio_jev.py`):
1. En el sandbox de Composio (herramienta COMPOSIO_REMOTE_WORKBENCH), una celda baja la misma versión del repositorio (el SHA del clon de
   la tarea), repite los pasos que preguntan a Jev con `run_composio_tool("JEV_EVALUATE_STATE", …)` y sube las respuestas: da una «url».
   `jev_correr("diario", SHA)` (los de diario.py que quitan lo pasado y los que preguntan a Jev, y sortea2) o `jev_correr("avisos", SHA)`
   (los titulares de avisos_movil.py); si contesta «"listo": false», `jev_esperar()` en otra celda.
2. En la tarea: `mkdir -p /tmp/jev && curl -sSL "<url>" -o /tmp/jev/cache.json` y el script con `JEV_CACHE=/tmp/jev/cache.json` delante.
   Cada pregunta igual encuentra su respuesta (la clave es el hash de la petición entera); si una no está (la fuente cambió entre una vez y
   otra), ese elemento se queda sin Jev y el resto sigue. diario.py lo dice en «jev» («N respuestas por Composio, M sin respuesta»).
En el buzón, la comprobación de cada captura va directa: `jev_captura(SHA, texto, datos)` (lo mismo que comprobar_captura.py).
Sin la caché, con la variable `TYPESAFE_API_KEY` en el entorno, directo a la API (como antes); sin nada, cada script sigue como antes de Jev.
Nunca se imprime ni se escribe ninguna clave.

- Avisos al móvil (`avisos_movil.py`): Jev dice si cada titular de Noticias de Almería que nombra el pueblo anuncia un corte de agua o de
  luz en él (y si ya está restablecido); si duda, la regla de texto de antes. La línea JSON dice «titulares»: Jev o reglas.
- `titulares.py` (diario): lo mismo para la tele: los cortes que da Jev van a extras.json «cortes» (con «jev»: true; hasta el día que dice
  el titular o el siguiente a la noticia) y los que la regla de la tele daría por corte y no lo son, a «noEsCorte».
- `receta.py` (diario): del tiempo de hoy de AEMET (en palabras: frío/templado/calor, lluvia, viento), la receta del mes que mejor pega,
  sin repetir las de los últimos 7 días ni la de ayer. extras.json «receta». La lista es `recetas.json`, copia de la de la página
  (`herramientas/exportar_recetas.py` del proyecto de la app).
- `sas.py` (diario): el BOJA (sección 2.2) y el BOE de 7 días, como la tele; Jev etiqueta cada disposición del SAS (convocatoria, lista
  provisional o definitiva, nombramiento, cese, bolsa, traslado u otra; Almería, toda Andalucía, otra o no consta). extras.json «sas».
- `sortea2.py` (diario): el RSS de sortea2.com (30 últimas promociones de todos los países), los que nombran la zona y, con Jev, los que
  son sorteos de un comercio de la zona, no para toda España, y dicen cuándo acaban. Imprime candidatos; no apunta nada.
- `titulares.py`, en la misma pregunta: si el titular anuncia una actividad o una colecta en el pueblo → candidatos para la agenda y las
  colectas (`diario.py` → «agenda_titulares», «sangre_titulares»; la tarea diaria los lee y apunta solo lo que ve).
- `etiquetas.py` (diario): extras.json «etiquetas»: el alérgeno de cada alerta de la AESAN, si el medicamento retirado se vende sin receta
  (base oficial CIMA, por su número de registro) y si hay que devolver los de casa, si el producto de Safety Gate es para niños (juguetes y
  puericultura por su categoría) y la titulación mínima y si la experiencia es requisito en cada oferta de la Junta; además, la agenda sin la
  misma actividad dos veces y en cada sorteo cómo se participa («participa»).
- `comprobar_captura.py` (buzón): antes de apuntar una captura, Jev mira dato por dato si el texto transcrito dice lo que se va a apuntar; si
  no cuadra, «REVISAR (no cuadra …)».
- `revisar_fuentes.py` revisa también Jev (`jev_`) y ESIOS (`esios`): Jev por Composio, cuántas respuestas trajo el sandbox (vacía o sin
  nada, «NO COMPROBABLE»); con clave que no vale, ROTA. La segunda mirada (abajo) solo con la clave: el sandbox no repite la revisión. Si una fuente
  sale ROTA porque falta su marca, Jev mira lo último que bajó y dice si el dato parece seguir en la página (¿cambio de formato?).
Pruebas: `herramientas/test_jev.py` (respuestas de mentira con la forma de la API y de Composio; los RSS, el XML de AEMET y los boletines,
reales), con la ida y vuelta sandbox → caché → tarea.
