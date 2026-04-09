# Código de estimación — Guía de uso

Esta carpeta contiene todos los scripts del proyecto, organizados en cuatro módulos que se corresponden con las fases de análisis, más una carpeta de utilidades compartidas. Los scripts están numerados para indicar el orden de ejecución dentro de cada módulo.

---

## Lenguajes utilizados

El proyecto usa principalmente R para la estimación econométrica y Python para la preparación de datos y la visualización. Los scripts de Stata (`.do`) se conservan si algún miembro del equipo los usa para replicar resultados, pero R es el lenguaje de referencia para los outputs definitivos.

---

## Módulos y orden de ejecución

### `01_preparacion/` — Preparación de la base analítica

Este módulo transforma los datos crudos en el panel listo para la estimación. Debe ejecutarse primero y en el orden numérico indicado.

```
01_carga_cuestionario.R          # Carga y unifica los datos del cuestionario 2022-2024
02_limpieza_panel.R              # Eliminación de entidades no mercantiles, tratamiento
                                 #   de valores extremos (winsorización p1-p99)
03_construccion_indicadores.R    # Construcción de ABSCAP, DIGINT, AUTO4, SUSTOP, ECOS
                                 #   mediante AFC o media estandarizada según cobertura
04_construccion_dosis.R          # Cálculo de DoseINV, DoseDEV, DoseABS, DoseINNO
                                 #   normalizadas por empleo de 2022
05_merge_subvenciones.R          # Fusión del panel con el archivo de subvenciones
06_imputacion_multiple.R         # Imputación MICE para valores ausentes en controles
07_exportar_panel_estimacion.R   # Exporta data/processed/panel_estimacion_vX.csv
```

### `02_estimacion_interna/` — Sistema de ecuaciones interno

Este módulo contiene los scripts de la estimación econométrica interna (efectos fijos + MC2E). Requiere que `01_preparacion/` haya generado el panel.

```
01_estimacion_forma_reducida.R   # Etapa 1: forma reducida ECOS ~ dosis + controles + FE
02_estimacion_mc2e_abscap.R      # Etapa 2, ecuación 1: ABSCAP ~ dosis + controles + FE
03_estimacion_mc2e_ecos.R        # Etapa 2, ecuación 2: ECOS ~ ABSCAP_hat + controles
04_robustez.R                    # Especificaciones alternativas y análisis de sensibilidad
05_tablas_resultados.R           # Genera outputs/tablas/tab0X_*.xlsx con todos los modelos
```

### `03_control_sintetico/` — Análisis externo de impacto

Este módulo implementa el control sintético con datos de SABI. Requiere que los datos externos estén disponibles en `data/external/`.

```
01_carga_sabi.R                  # Carga y prepara los datos de SABI 2019-2024
02_seleccion_donantes.R          # Aplica filtros CNAE + tamaño + continuidad temporal
                                 #   y excluye los CIFs de las 256 beneficiarias
03_construccion_sintetico.R      # Estima los pesos del contrafactual sintético
                                 #   por tipología de proyecto (INV, DEV, ABS)
04_estimacion_impacto.R          # Calcula τ̂₁t = Y₁t - Ŷᴺ₁t para cada tipología
05_placebos.R                    # Tests placebo sobre empresas del grupo donante
06_sdid.R                        # Especificación alternativa: Synthetic DiD
                                 #   (Arkhangelsky et al., 2021)
07_tablas_figuras_externo.R      # Genera outputs correspondientes al análisis externo
```

### `04_visualizacion/` — Gráficos para informes

Scripts dedicados a producir las figuras del informe. Pueden ejecutarse de forma independiente siempre que los outputs de los módulos anteriores estén disponibles.

```
01_tendencias_pretratamiento.R   # Figura: trayectorias beneficiarias vs donantes 2019-2022
02_efectos_temporales.R          # Figura: coeficientes FE de año con IC al 95%
03_distribucion_dosis.R          # Figura: distribución de dosis monetarias por tipología
04_impacto_control_sintetico.R   # Figura: gap beneficiarias vs sintético post-tratamiento
```

### `utils/` — Funciones auxiliares

```
funciones_tablas.R               # Helpers para formatear tablas de resultados
funciones_graficos.R             # Tema ggplot y paleta de colores del proyecto
winsorize.R                      # Función de winsorización con log de casos afectados
```

---

## Cómo reproducir los resultados

Para reproducir el análisis completo desde cero, ejecutar los scripts en el orden siguiente:

1. Verificar que los datos originales están en `data/raw/` (ver `data/raw/FUENTES.md`).
2. Ejecutar todos los scripts de `01_preparacion/` en orden numérico.
3. Ejecutar todos los scripts de `02_estimacion_interna/` en orden numérico.
4. Una vez disponibles los datos de SABI, ejecutar `03_control_sintetico/`.
5. Ejecutar `04_visualizacion/` para regenerar todas las figuras.

Todos los scripts leen datos desde `data/` y escriben outputs en `outputs/`. Ningún script escribe en `data/raw/`.

---

## Gestión de dependencias

Cada script incluye al inicio un bloque de carga de librerías. Las versiones utilizadas se registran en `utils/sesion_info.txt`, generado automáticamente al ejecutar `sessionInfo()` al final de cada sesión de trabajo en R.
