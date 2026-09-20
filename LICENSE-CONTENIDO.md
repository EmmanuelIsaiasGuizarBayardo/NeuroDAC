# Licencia del contenido didáctico

El código de este repositorio se distribuye bajo la licencia MIT (ver
`LICENSE`). Este archivo cubre lo que **no** es código.

## Qué cubre

- **`content/divulgacion.es.json`**: todo el texto que la aplicación muestra al
  público. Explicaciones de las bandas de frecuencia y de los modos de
  visualización, descripciones de cada tipo de señal de la diadema, las
  instrucciones accionables de cada estado de la señal, y los paneles que
  explican cada juego.
- **`docs/manual-operador.md`** y cualquier documento generado desde el
  archivo de contenido.

Se describe por tipo de contenido y no por lista de archivos: una lista se
desactualiza en cuanto alguien agrega uno.

Queda fuera el logotipo de DUNNE (`assets/LOGO.jpg`), que es un identificador
de la organización. Puede reproducirse al citar o redistribuir el proyecto,
pero no para identificar trabajos derivados ni para dar a entender que DUNNE
respalda un derivado.

También queda fuera el registro EEG de demostración, que no es obra de este
proyecto: proviene de OpenNeuro `ds002778` bajo CC0 y conserva sus propios
términos. Ver `CREDITS.md`.

## Bajo qué términos

**Creative Commons Atribución 4.0 Internacional (CC BY 4.0).**

Texto legal: <https://creativecommons.org/licenses/by/4.0/legalcode.es>
Resumen: <https://creativecommons.org/licenses/by/4.0/deed.es>

Cualquier persona puede compartir y adaptar este material, con cualquier
finalidad, incluso comercial, siempre que otorgue el crédito correspondiente,
enlace a la licencia e indique si realizó cambios.

## Cómo dar el crédito

Al reutilizar el contenido didáctico, incluir una nota como esta:

> Contenido didáctico de NeuroDAC: Emmanuel Isaías Guízar Bayardo, División
> Universitaria de Neuroingeniería (DUNNE), UNAM. Bajo CC BY 4.0.
> https://github.com/EmmanuelIsaiasGuizarBayardo/NeuroDAC

Si se realizaron modificaciones, indicarlo: *"adaptado de"* en lugar de
*"por"*.

## Cómo editarlo

`content/divulgacion.es.json` es JSON plano a propósito: quien redacta no
necesita saber Python ni conocer los componentes de la interfaz. El único
marcado es el asterisco para énfasis, `*así*`.

La aplicación valida el archivo al arrancar. Si falta una entrada que la
interfaz necesita, falla de inmediato y con nombre, en lugar de dejar un hueco
en pantalla durante una demostración. `tests/test_content.py` comprueba que
exista texto para cada banda, cada modo de vista, cada tipo de señal y cada
estado que el código puede producir.

## Por qué esta combinación

Las licencias Creative Commons no son adecuadas para software, y las licencias
de software no están pensadas para textos. Separar ambas es la práctica
habitual en proyectos que, como este, contienen las dos cosas.

Se eligió CC BY antes que CC BY-SA porque la cláusula de compartir igual
obligaría a cualquier material que incorpore estos textos a adoptar la misma
licencia, lo que impediría a un museo o a otra universidad incluirlos en
materiales con licencias distintas.

Se descartó CC BY-NC porque la restricción no comercial excluye usos
legítimos, como un taller de paga o un libro de texto, y es incompatible con
la mayoría de las licencias abiertas.

En ambos casos la atribución es obligatoria, que era el requisito de fondo.

## Revisión académica

El contenido divulgativo describe fenómenos neurofisiológicos en lenguaje
accesible. Las simplificaciones son deliberadas y están dirigidas a público
general en museos, no a uso clínico ni docente formal.

Quien reutilice estos textos en un contexto académico debería contrastarlos
con la literatura primaria. El repositorio no declara revisión por
especialista.
