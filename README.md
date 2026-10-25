# tiempo-datos

Datos del día para una app personal del tiempo en una Fire TV («Tiempo y Radar»).
La tele descarga `extras.json` cada hora; una tarea programada lo pone al día cada mañana.

- **Vuelos baratos** desde Almería, Granada, Málaga y Murcia (búsqueda en Kiwi.com: ida y vuelta, directos,
  de 2 a 5 noches, salida al menos 3 días después de la búsqueda), con el enlace de cada vuelo.
- **Sorteos de Instagram** de la zona de Motril a Almería, solo los vistos en la publicación o en sus bases,
  con fecha de fin; se quitan solos al acabar.
- **Cortes anunciados** (luz, agua, tráfico) que no salen en los periódicos, con su enlace; se quitan al pasar.
- **Embalses** de la cuenca Mediterránea Andaluza y precio de la bombona de butano.

No contiene datos personales. Cómo se hace cada cosa: [PROCEDIMIENTO.md](PROCEDIMIENTO.md).
Herramientas: `herramientas/vuelos.py`, `herramientas/sorteos.py`, `herramientas/cortes.py` y `herramientas/revisar_fuentes.py`.
