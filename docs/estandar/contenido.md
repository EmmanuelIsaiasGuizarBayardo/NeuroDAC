<!-- Archivo del estandar DUNNE, generado por la plantilla. No se edita aqui:
     se actualiza con 'uvx copier update --trust'. -->

# Módulo: contenido didáctico

Aplica porque el proyecto incluye contenido que no es software.

## Frontera y licencia

- **REGLA DURA.** Todo el contenido no-software vive en `content/`: textos, modelos 3D, imágenes y cualquier otro activo creativo. El directorio es la frontera de la licencia: lo que está dentro es CC BY 4.0 (`content/LICENSE.md`) y el código es MIT. El logotipo de la organización nunca vive dentro.
- El material de terceros conserva sus términos y se declara en `content/LICENSE.md`, `CREDITS.md` y `references` del CFF. Las obras que el contenido cita se citan, no se reproducen.
- Un componente con creador propio, como un modelo 3D, se nombra en la línea de atribución de `content/LICENSE.md`.

## Texto

- **REGLA DURA.** Todo el texto que ve el público vive en `content/<ámbito>.<idioma>.json`, por ejemplo `divulgacion.es.json`; la interfaz no contiene texto de contenido. `tests/test_contenido.py` rechaza nombres que no sigan ese patrón.
- Cada archivo de texto se valida contra `content/esquema.json` y lo referencia con `"$schema"`, para que el editor marque los errores mientras se escribe.
- Las claves son ASCII sin diacríticos; las etiquetas visibles llevan acentuación normal. No se aplican correctores automáticos sobre archivos de datos: cambian identificadores y títulos de referencias en otros idiomas.
- El único marcado es el énfasis con asteriscos, `*así*`. **REGLA DURA:** nada de HTML, porque un sitio que inserta el texto en la página podría ejecutarlo. La prueba lo rechaza.
- Los campos para quien opera o imparte el taller se marcan en el esquema con una descripción que empieza con "Solo personal:" y nunca se muestran en el modo público.
- La aplicación valida el contenido al arrancar y, si falta una entrada, falla de inmediato y con su nombre: un hueco en pantalla durante una demostración es peor que un error al iniciar.

## Revisión académica

- **REGLA DURA.** Cada archivo de texto declara su estado en `review.status`: `sin_revision`, `en_revision` o `revisado`. La revisión no es obligatoria para publicar; declarar su estado con honestidad, sí. La prueba verifica que el estado exista y sea válido.
- Quien revisa aparece en `CREDITS.md` con el rol *Validation* o *Writing – review & editing*.

## Documentos derivados

- Los documentos que se generan desde el contenido, como un manual del operador o una versión para revisión académica, salen de un script y nunca se editan a mano; así no pueden divergir de la fuente.
- **PREFERENCIA.** El generador tiene un modo `--check` que falla si el documento está desfasado, y un workflow propio del proyecto lo corre en el CI; así la regla anterior se verifica sola.

## Lista de verificación

- [ ] Ningún texto, modelo o imagen del contenido vive fuera de `content/`.
- [ ] `uv run pytest -q` pasa, incluida la validación contra el esquema.
- [ ] `review.status` describe el estado real de la revisión.
- [ ] Los campos "Solo personal" no aparecen en el modo público.
