# Evaluación de Impacto PERTE VEC1

Repositorio de trabajo del equipo técnico de evaluación del primer PERTE del Vehículo Eléctrico y Conectado (PERTE VEC1). Contiene toda la documentación metodológica, los datos de trabajo, el código de estimación y los resultados de las distintas fases de la evaluación.

---

## Estructura del repositorio

```
PERTE_VEC_Evaluacion_Impacto/
│
├── docs/                          # Documentación del proyecto
│   ├── 01_metodologia/            # Informe metodológico y versiones
│   ├── 02_resultados/             # Documentos de resultados por fase
│   ├── 03_plan_trabajo/           # Hoja de ruta, cronograma y actas
│   ├── 04_fichas_variables/       # Fichas de constructos e indicadores
│   └── 05_informes_finales/       # Versiones finales para distribución
│
├── data/                          # Datos (nunca se suben datos sensibles en claro)
│   ├── raw/                       # Datos originales sin modificar (solo lectura)
│   ├── processed/                 # Datos transformados listos para estimación
│   └── external/                  # Datos externos: SABI, ORBIS, OEPM, etc.
│
├── code/                          # Scripts de estimación y análisis
│   ├── 01_preparacion/            # Limpieza, construcción de indicadores, merge
│   ├── 02_estimacion_interna/     # Sistema de ecuaciones, MC2E, efectos fijos
│   ├── 03_control_sintetico/      # Análisis externo, contrafactual, placebos
│   ├── 04_visualizacion/          # Gráficos y tablas para informes
│   └── utils/                     # Funciones auxiliares reutilizables
│
├── outputs/                       # Resultados generados por el código
│   ├── tablas/                    # Tablas de resultados en .tex, .xlsx o .csv
│   ├── figuras/                   # Gráficos en .pdf o .png
│   └── presentaciones/            # Presentaciones del equipo
│
├── admin/                         # Gestión del proyecto
│   └── ...                        # Actas, comunicaciones, control de versiones
│
├── README.md                      # Este archivo
├── CONVENIOS.md                   # Convenciones de nomenclatura del equipo
└── .gitignore                     # Exclusiones del repositorio
```

---

## Diseño de la evaluación

La evaluación responde a dos preguntas complementarias que se abordan con métodos distintos pero integrados.

**¿Qué está cambiando dentro de las empresas beneficiarias?** El análisis interno utiliza un panel de 242 empresas mercantiles con datos del cuestionario 2022–2024, estimado mediante efectos fijos de empresa y año (estimador *within*). El modelo sigue una lógica causal encadenada que parte de la capacidad de absorción (ABSCAP), pasa por la digitalización (DIGINT), la automatización (AUTO4) y la sostenibilidad operativa (SUSTOP), y llega al resultado final de ecosistema productivo (ECOS).

**¿Esos cambios son atribuibles al programa?** El análisis externo construye un contrafactual mediante control sintético con datos de SABI (series 2019–2024), comparando la trayectoria de las beneficiarias con la de empresas similares no tratadas, e infiriendo el impacto mediante tests placebo.

### Estructura temporal

| Período | Años | Rol |
|---|---|---|
| Pretratamiento | 2019–2022 | Verificación del paralelismo pretratamiento |
| Año de tratamiento | 2023 | Concesión de subvenciones PERTE VEC1 |
| Post-tratamiento 1ª evaluación | 2023–2024 | Evaluación actual |
| Post-tratamiento 2ª evaluación | 2023–2025 | Evaluación futura (datos 2025 pendientes) |

### Variables de dosis

Las dosis se miden como importe concedido (proxy del ejecutado, pendiente de actualización) normalizado por el empleo de 2022 (año base pretratamiento):

- **DoseINV** — Investigación industrial
- **DoseDEV** — Desarrollo experimental
- **DoseABS** — Formación / Absorción
- **DoseINNO** — Innovación en organización y procesos (especificación ampliada)

---

## Estado actual del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| F1 — Base analítica | Diccionario de variables, indicadores sintéticos, limpieza | ✅ Completada |
| F2a — Estimación interna (preliminar) | Forma reducida ECOS + sistema MC2E ABSCAP→ECOS con dosis binarias | ✅ Completada |
| F2b — Estimación interna (definitiva) | Reestimación con dosis monetarias continuas | 🔄 En curso |
| F3 — Incorporación SABI | Obtención datos, fusión, grupo de comparación | ⏳ Pendiente |
| F4 — Control sintético | Contrafactual, inferencia por placebos | ⏳ Pendiente |
| F5 — Integración y comunicación | Informes finales, conclusiones para gestión | ⏳ Pendiente |

---

## Documentos clave

| Documento | Ubicación | Descripción |
|---|---|---|
| Informe metodológico v2 | `docs/01_metodologia/` | Marco metodológico completo con Anexos A–D |
| Resultados preliminares v2 | `docs/02_resultados/` | Estimaciones con dosis binarias, fase actual |
| Fichas de constructos | `docs/04_fichas_variables/` | Definición detallada de ABSCAP, DIGINT, AUTO4, SUSTOP, ECOS |

---

## Convenciones

Antes de subir cualquier archivo al repositorio, consulta el documento `CONVENIOS.md`, que recoge las reglas de nomenclatura, versionado y organización acordadas por el equipo.

---

## Contacto y coordinación

Este repositorio es de uso **exclusivo del equipo técnico evaluador**. Para cualquier consulta sobre el proyecto, contactar con el responsable de evaluación indicado en los documentos de la carpeta `admin/`.
