# Convenciones del repositorio — Evaluación de Impacto PERTE VEC1

Este documento recoge las reglas de nomenclatura, versionado y organización que sigue todo el equipo técnico. Su objetivo es que cualquier miembro pueda orientarse en el repositorio sin necesidad de preguntar, y que los archivos sean identificables con solo leer su nombre.

---

## 1. Nomenclatura de archivos

La regla general es: **no_de_bloque_descripcion_vX.extension**. Todos los componentes van en minúsculas, separados por guiones bajos, sin espacios ni acentos.

### Documentos (`docs/`)

El prefijo numérico indica la carpeta a la que pertenece el archivo. La descripción debe ser concisa pero suficientemente informativa. Siempre se incluye el número de versión al final.

Ejemplos correctos:

```
01_informe_metodologico_v2.docx
02_resultados_estimacion_preliminar_v2.docx
03_cronograma_fases_v1.xlsx
04_ficha_constructo_ABSCAP_v1.docx
04_ficha_constructo_ECOS_v1.docx
05_informe_final_evaluacion_v1.pdf
```

### Scripts de código (`code/`)

El prefijo numérico indica el orden de ejecución dentro de su carpeta. La extensión refleja el lenguaje: `.R`, `.py` o `.do` (Stata).

```
01_carga_cuestionario.R
02_construccion_indicadores.R
03_merge_sabi.R
01_estimacion_forma_reducida.R
02_estimacion_mc2e.R
01_construccion_donantes.R
02_control_sintetico.R
03_placebos.R
```

### Datos (`data/`)

Los archivos en `raw/` nunca se modifican ni renombran: se conservan exactamente como se recibieron, con una nota en `raw/FUENTES.md` que indica la fuente, la fecha de recepción y la persona responsable. Los archivos en `processed/` y `external/` siguen la convención general.

```
data/raw/cuestionario_beneficiarias_2022_2024.xlsx     ← nombre original preservado
data/processed/panel_estimacion_v1.csv
data/external/sabi_donantes_2019_2024_v1.csv
```

### Outputs (`outputs/`)

Las tablas y figuras incluyen en el nombre la especificación o modelo que las genera, para que siempre sea posible rastrear qué script las produjo.

```
outputs/tablas/tab01_estadisticos_descriptivos_v1.xlsx
outputs/tablas/tab02_forma_reducida_ecos_v1.xlsx
outputs/tablas/tab03_mc2e_abscap_ecos_v1.xlsx
outputs/figuras/fig01_tendencias_pretratamiento_v1.pdf
outputs/figuras/fig02_efectos_temporales_v1.pdf
```

---

## 2. Versionado de documentos

El número de versión sigue el esquema `vX`, donde X es un entero que se incrementa en uno cada vez que se hace un cambio sustantivo. No se usa versionado semántico (v1.0, v1.1...) para mantener la simplicidad.

Un cambio sustantivo es cualquier modificación que altere el contenido analítico: corrección de resultados, añadir secciones, cambiar una especificación. Las correcciones tipográficas menores no justifican subir versión. Cuando se sube una nueva versión, la anterior no se elimina: se archiva en la misma carpeta con su número de versión original, de modo que el historial queda siempre disponible.

---

## 3. Commits en Git

Los mensajes de commit siguen la estructura: **[carpeta] acción breve en infinitivo**.

```
[docs] añadir informe metodológico v2
[code] corregir construcción de ABSCAP en 02_construccion_indicadores.R
[data] incorporar datos SABI 2019-2024
[outputs] actualizar tabla forma reducida con dosis monetarias
[admin] añadir acta reunión 2024-03-15
```

Los commits deben ser atómicos: un commit por cambio lógico, no acumulaciones de varios días de trabajo en un solo commit. Esto facilita la revisión y la posibilidad de revertir cambios concretos sin afectar al resto.

---

## 4. Ramas (branches)

La rama principal `main` contiene siempre versiones estables y revisadas. Cada miembro del equipo trabaja en su propia rama con el formato `nombre/descripcion-tarea`:

```
ana/estimacion-dosis-monetarias
carlos/construccion-donantes-sabi
laura/fichas-constructos
```

Una vez revisado el trabajo, se incorpora a `main` mediante un pull request con al menos una revisión de otro miembro del equipo.

---

## 5. Datos sensibles y `.gitignore`

Los microdatos de empresas (cuestionario, SABI, ORBIS) nunca se suben al repositorio Git, ya que contienen información potencialmente sensible. La carpeta `data/` completa está incluida en el `.gitignore`. Lo que sí se sube es el código que los procesa y los outputs agregados (tablas de resultados, figuras) que no permiten identificar empresas individuales.

Si en algún momento se necesita compartir un archivo de datos con el equipo, se hace a través del canal seguro acordado (servidor compartido o Drive del proyecto), nunca a través de Git.

---

## 6. Fichas de constructos (`docs/04_fichas_variables/`)

Cada constructo del modelo (ABSCAP, DIGINT, AUTO4, SUSTOP, ECOS) tiene su propia ficha en formato `.docx`. Una ficha estándar incluye: nombre y acrónimo del constructo, definición conceptual, ítems del cuestionario que lo componen, transformación recomendada, método de construcción del indicador sintético (AFC o media estandarizada), estadísticos descriptivos de la versión más reciente, y observaciones sobre cobertura o limitaciones conocidas. Las fichas se actualizan cada vez que cambia la especificación del constructo.

---

*Última actualización: versión inicial del repositorio.*
