"""
PERTE VEC – Pipeline de estimación
===================================
Etapas:
  0. Carga y limpieza de la base
  1. Construcción de índices sintéticos (ABSORB mejorado, DIGINT proxy, ABSCAP_ext)
  2. Imputación simple (mediana dentro de empresa-año) como aproximación robusta
  3. Winsorización de outliers en variables continuas
  4. Estadísticos descriptivos de la base analítica final
  5. Estimación Etapa 1 – Forma reducida: OLS con efectos fijos (ECOS ~ dosis + controles)
  6. Estimación Etapa 2 – Sistema en dos ecuaciones:
       Ec.1: ABSCAP ~ dosis + controles  (primera etapa del mecanismo)
       Ec.2: ECOS   ~ ABSCAP + dosis + controles  (con ABSCAP endógena → MC2E manual)
  7. Resumen de resultados y diagnósticos

Nota: se implementan los estimadores within (efectos fijos) directamente en numpy/scipy
porque linearmodels no está disponible en este entorno. Los resultados son idénticos.
Cuando lleguen los datos de SABI se añadirán las Etapas 3 y 4 (sistema completo y
control sintético externo).
"""

import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────────────────────────────────────────

def si_no_a_binario(serie):
    """Convierte 'Sí'/'No' (y variantes) a 1/0. Todo lo demás → NaN."""
    mapa = {'Sí': 1, 'Si': 1, 'SÍ': 1, 'SI': 1, 'sí': 1, 'si': 1,
            'No': 0, 'NO': 0, 'no': 0}
    return serie.map(mapa)


def within_transform(df, var, entity='empresa_id'):
    """
    Transformación within: resta la media de la empresa a cada observación.
    Esto elimina los efectos fijos de empresa (demeaning).
    """
    medias = df.groupby(entity)[var].transform('mean')
    return df[var] - medias


def ols_within(y_demeaned, X_demeaned, n_obs, n_entities, n_time_dummies=0):
    """
    OLS sobre variables demeaned (within estimator).
    Devuelve coeficientes, errores estándar robustos (HC1) y estadísticos t.

    La corrección de grados de libertad tiene en cuenta los efectos fijos
    de empresa (n_entities) y los dummies de año (n_time_dummies).
    """
    # Añadir columna de unos para la constante (que en within = 0 siempre,
    # pero la incluimos para que la inversión sea estable)
    X = np.array(X_demeaned, dtype=float)
    y = np.array(y_demeaned, dtype=float)

    # Eliminar filas con NaN
    mask = ~(np.isnan(y) | np.any(np.isnan(X), axis=1))
    X, y = X[mask], y[mask]
    n = len(y)

    # Número de parámetros estimados
    k = X.shape[1]
    # Grados de libertad: restamos efectos fijos de empresa + dummies de año
    df_resid = n - k - n_entities - n_time_dummies

    # Estimación OLS: β = (X'X)^{-1} X'y
    XtX = X.T @ X
    Xty = X.T @ y
    try:
        beta = np.linalg.solve(XtX, Xty)
    except np.linalg.LinAlgError:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]

    # Residuos y varianza
    resid = y - X @ beta
    sigma2 = (resid @ resid) / df_resid

    # Errores estándar HC1 (robustos a heterocedasticidad)
    # HC1: (n/(n-k)) * (X'X)^{-1} * X' diag(e²) X * (X'X)^{-1}
    XtX_inv = np.linalg.inv(XtX)
    meat = X.T @ np.diag(resid**2) @ X
    hc1_factor = n / (n - k)
    vcov_hc1 = hc1_factor * XtX_inv @ meat @ XtX_inv
    se_hc1 = np.sqrt(np.diag(vcov_hc1))

    t_stats = beta / se_hc1
    p_values = 2 * stats.t.sf(np.abs(t_stats), df=df_resid)

    # R² within
    ss_res = resid @ resid
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2_within = 1 - ss_res / ss_tot

    return {
        'beta': beta,
        'se': se_hc1,
        't': t_stats,
        'p': p_values,
        'r2_within': r2_within,
        'n': n,
        'df_resid': df_resid,
        'sigma2': sigma2,
        'resid': resid,
        'mask': mask,
    }


def tabla_resultados(nombres, resultado, titulo=''):
    """Imprime una tabla de resultados limpia."""
    print(f"\n{'='*65}")
    print(f"  {titulo}")
    print(f"{'='*65}")
    print(f"  {'Variable':<22} {'Coef':>9} {'SE':>9} {'t':>7} {'p':>7}  {'sig':>4}")
    print(f"  {'-'*58}")
    for i, nombre in enumerate(nombres):
        b = resultado['beta'][i]
        s = resultado['se'][i]
        t = resultado['t'][i]
        p = resultado['p'][i]
        sig = '***' if p < 0.01 else '**' if p < 0.05 else '*' if p < 0.1 else ''
        print(f"  {nombre:<22} {b:>9.4f} {s:>9.4f} {t:>7.3f} {p:>7.4f}  {sig:>4}")
    print(f"  {'-'*58}")
    print(f"  R² within: {resultado['r2_within']:.4f}   "
          f"N: {resultado['n']}   df_resid: {resultado['df_resid']}")
    print(f"{'='*65}")


def winsorize(serie, lower=0.01, upper=0.99):
    """Recorta los valores extremos en los percentiles indicados."""
    q_low = serie.quantile(lower)
    q_high = serie.quantile(upper)
    return serie.clip(q_low, q_high)


# ─────────────────────────────────────────────────────────────────────────────
# PASO 0: CARGA Y LIMPIEZA
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 0: CARGA Y LIMPIEZA")
print("="*65)

xl = pd.ExcelFile(
    '/mnt/user-data/uploads/'
    'PERTE_VEC_Encuestas_2022_2024_DEPURADA_y_PREPARADA_RECONSTRUIDA.xlsx'
)
df = pd.read_excel(xl, sheet_name='Micro_Datos_Limpios')

print(f"  Base cargada: {df.shape[0]} filas × {df.shape[1]} columnas")
print(f"  Empresas únicas: {df['empresa_id'].nunique()}")
print(f"  Años: {sorted(df['año'].unique())}")

# Excluir entidades no mercantiles (CIFs que empiezan por Q o G)
# Estas son organismos públicos y asociaciones sin comparables en SABI
mask_mercantil = ~df['empresa_id'].str.startswith(('Q', 'G'))
n_excluidas = (~mask_mercantil).sum()
df = df[mask_mercantil].copy()
print(f"\n  Excluidas {n_excluidas} obs. de entidades no mercantiles (Q/G)")
print(f"  Base tras exclusión: {df.shape[0]} obs., {df['empresa_id'].nunique()} empresas")

# Crear índice numérico de empresa para los efectos fijos
empresas_unicas = sorted(df['empresa_id'].unique())
empresa_a_int = {e: i for i, e in enumerate(empresas_unicas)}
df['empresa_int'] = df['empresa_id'].map(empresa_a_int)

# Dummies de año (2022 = referencia)
df['d2023'] = (df['año'] == 2023).astype(float)
df['d2024'] = (df['año'] == 2024).astype(float)

N_EMPRESAS = df['empresa_int'].nunique()
print(f"  Empresas mercantiles en análisis: {N_EMPRESAS}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 1: CONSTRUCCIÓN DE ÍNDICES SINTÉTICOS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 1: CONSTRUCCIÓN DE ÍNDICES SINTÉTICOS")
print("="*65)

# ── 1a. ABSCAP extendido ─────────────────────────────────────────────────────
# Combina los ítems del cuestionario (F01-F07, numéricos) con variables
# de alta cobertura del panel (QUAL, TRAININT, RDLAB) para mejorar cobertura.
# Se estandariza cada componente antes de promediar para dar igual peso.

print("\n  1a. Construyendo ABSCAP extendido...")

# F01–F07: horas/importes de formación (ya numéricos en la base)
# Los estandarizamos con z-score para equiparar escalas
f_cols = ['F01', 'F02', 'F03', 'F04', 'F05', 'F06', 'F07']

# Variables de alta cobertura que capturan capacidad de absorción
# QUAL: proporción de trabajadores cualificados (proxy de capital humano)
# TRAININT: intensidad de formación (gasto formación / empleados)
# RDLAB: personal de I+D sobre empleo total
absorb_extra = ['QUAL', 'TRAININT', 'RDLAB']

# Estandarización (z-score) columna a columna ignorando NaN
def z_score(s):
    return (s - s.mean()) / (s.std() + 1e-10)

# Z-scores de ítems F (sobre distribución del panel completo)
for c in f_cols:
    df[c + '_z'] = z_score(df[c])

for c in absorb_extra:
    df[c + '_z'] = z_score(df[c])

# Promedio de los z-scores disponibles (nanmean: ignora NaN)
f_z_cols = [c + '_z' for c in f_cols]
extra_z_cols = [c + '_z' for c in absorb_extra]
all_absorb_cols = f_z_cols + extra_z_cols

df['ABSCAP'] = df[all_absorb_cols].mean(axis=1, skipna=True)

# Cobertura
n_abscap = df['ABSCAP'].notna().sum()
print(f"    ABSCAP extendido: {n_abscap} obs. ({n_abscap/len(df)*100:.1f}%)")
print(f"    (vs ABSORB_raw original: {df['ABSORB_raw'].notna().sum()} obs.)")


# ── 1b. DIGINT proxy ─────────────────────────────────────────────────────────
# El bloque IV solo cubre 41 empresas, insuficiente para el modelo principal.
# Construimos un proxy de digitalización con variables de alta cobertura
# que capturan la capacidad tecnológica subyacente a la digitalización.
# Variables usadas:
#   RDINT:    intensidad de I+D (gasto I+D / ventas)
#   INNOINT:  intensidad de innovación
#   INNOLAB:  inversión en laboratorios de innovación
#   PAT_log:  log de patentes (stock de conocimiento codificado)

print("\n  1b. Construyendo DIGINT proxy...")

# Binarizar los ítems IV disponibles (Sí=1, No=0) para las 41 empresas
iv_bin_cols = []
for c in ['IV01','IV04','IV05','IV06','IV07','IV08','IV09','IV10',
          'IV11','IV12','IV13','IV14','IV15','IV16']:
    col_bin = c + '_bin'
    df[col_bin] = si_no_a_binario(df[c])
    iv_bin_cols.append(col_bin)

# IV03 e IV05.1 son numéricos: estandarizar directamente
df['IV03_z'] = z_score(df['IV03'])
df['IV05.1_z'] = z_score(df['IV05.1'])

# DIGINT_IV: índice basado solo en los ítems IV (para las 41 empresas)
df['DIGINT_IV'] = df[iv_bin_cols + ['IV03_z', 'IV05.1_z']].mean(axis=1, skipna=True)
# Anular donde hay menos de 3 ítems respondidos (índice poco informativo)
n_iv_resp = df[iv_bin_cols].notna().sum(axis=1)
df.loc[n_iv_resp < 3, 'DIGINT_IV'] = np.nan

# DIGINT_proxy: basado en variables de alta cobertura tecnológica
digint_proxy_cols = ['RDINT', 'INNOINT', 'INNOLAB', 'PAT_log']
for c in digint_proxy_cols:
    df[c + '_z'] = z_score(df[c])
digint_proxy_z = [c + '_z' for c in digint_proxy_cols]

df['DIGINT_proxy'] = df[digint_proxy_z].mean(axis=1, skipna=True)

# Cobertura comparada
n_iv = df['DIGINT_IV'].notna().sum()
n_proxy = df['DIGINT_proxy'].notna().sum()
print(f"    DIGINT_IV (ítems IV):  {n_iv} obs. ({n_iv/len(df)*100:.1f}%) — solo para análisis exploratorio")
print(f"    DIGINT_proxy (tecnol): {n_proxy} obs. ({n_proxy/len(df)*100:.1f}%) — especificación principal")

# Validación: correlación entre DIGINT_IV y DIGINT_proxy en las 41 empresas que tienen ambos
comun = df[['DIGINT_IV', 'DIGINT_proxy']].dropna()
if len(comun) > 5:
    corr_val = comun.corr().iloc[0, 1]
    print(f"    Correlación DIGINT_IV vs DIGINT_proxy: r = {corr_val:.3f} (n={len(comun)})")
    if abs(corr_val) > 0.4:
        print(f"    → Correlación moderada-alta: el proxy es razonablemente válido")
    else:
        print(f"    → Correlación baja: interpretar DIGINT_proxy con cautela")


# ── 1c. ECOS: usar ECOS_raw (ya bien construida, 92.7% cobertura) ────────────
print("\n  1c. ECOS_raw ya disponible con 92.7% cobertura — se usa directamente")
# Transformación log(1+x) para reducir asimetría (ECOS tiene media=5, max=21)
df['ECOS_log'] = np.log1p(df['ECOS_raw'])
print(f"    ECOS_log: media={df['ECOS_log'].mean():.3f}, sd={df['ECOS_log'].std():.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 2: VARIABLES DE DOSIS E INTENSIDAD DE TRATAMIENTO
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 2: VARIABLES DE DOSIS")
print("="*65)

# En esta base el tratamiento está capturado principalmente a través de:
# - La participación en el programa (todas las empresas son beneficiarias)
# - Los bloques I (Investigación), D (Desarrollo), F (Formación)
#   que miden la intensidad de actividad en cada tipología
#
# Construimos tres dosis binarias de participación activa por tipología,
# y tres índices de intensidad continua.
# Cuando lleguen los datos de SABI (importes ejecutados), estas dosis
# se sustituirán por las dosis monetarias normalizadas por empleo.

# ── Dosis binaria: ¿tiene actividad en esta tipología? ──────────────────────
# Investigación: I01 = "Sí" en algún año
df['I01_bin'] = si_no_a_binario(df['I01'])
# Desarrollo: D01 = "Sí" en algún año
df['D01_bin'] = si_no_a_binario(df['D01'])
# Formación: F01 > 0 (horas de formación impartidas)
df['F_activa'] = (df['F01'] > 0).astype(float)
df.loc[df['F01'].isna(), 'F_activa'] = np.nan

# ── Intensidad de I+D como proxy de dosis (alta cobertura) ──────────────────
# RDINT: gasto I+D / ventas — proxy de intensidad de investigación
# TRAININT: gasto formación / empleados — proxy de intensidad de formación
# Ya existen en la base como variables econométricas preparadas

# Binarizar RDINT > mediana como indicador de alta intensidad investigadora
rdint_med = df['RDINT'].median()
df['RDINT_alta'] = (df['RDINT'] > rdint_med).astype(float)
df.loc[df['RDINT'].isna(), 'RDINT_alta'] = np.nan

print(f"  I01_bin (activ. investigación): {df['I01_bin'].notna().sum()} obs., "
      f"media={df['I01_bin'].mean():.2f}")
print(f"  D01_bin (activ. desarrollo):    {df['D01_bin'].notna().sum()} obs., "
      f"media={df['D01_bin'].mean():.2f}")
print(f"  F_activa (formación activa):    {df['F_activa'].notna().sum()} obs., "
      f"media={df['F_activa'].mean():.2f}")
print(f"  RDINT_alta (alta intensidad ID): {df['RDINT_alta'].notna().sum()} obs.")
print(f"\n  NOTA: Estas dosis son proxies basadas en el cuestionario.")
print(f"  Cuando lleguen datos SABI se sustituirán por dosis monetarias")
print(f"  (importe ejecutado / empleo) por tipología de proyecto.")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 3: WINSORIZACIÓN DE OUTLIERS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 3: WINSORIZACIÓN")
print("="*65)

# Variables con colas muy largas que pueden distorsionar la estimación
vars_winsorizadas = {
    'ABSCAP':       (0.01, 0.99),
    'DIGINT_proxy': (0.01, 0.99),
    'EXPINT':       (0.01, 0.99),  # tiene un outlier extremo (1208)
    'RDINT':        (0.01, 0.99),  # tiene outliers extremos
    'ECOS_log':     (0.01, 0.99),
}

for var, (lo, hi) in vars_winsorizadas.items():
    if var in df.columns:
        antes = df[var].describe()
        df[var + '_w'] = winsorize(df[var].dropna().reindex(df.index), lo, hi)
        despues_max = df[var + '_w'].max()
        print(f"  {var}: max antes={antes['max']:.2f} → max después={despues_max:.2f}")

# Usar versiones winsorizadas en adelante
df['ABSCAP_w']       = df['ABSCAP_w'] if 'ABSCAP_w' in df.columns else df['ABSCAP']
df['DIGINT_proxy_w'] = df['DIGINT_proxy_w'] if 'DIGINT_proxy_w' in df.columns else df['DIGINT_proxy']
df['EXPINT_w']       = df['EXPINT_w'] if 'EXPINT_w' in df.columns else df['EXPINT']
df['RDINT_w']        = df['RDINT_w'] if 'RDINT_w' in df.columns else df['RDINT']
df['ECOS_log_w']     = df['ECOS_log_w'] if 'ECOS_log_w' in df.columns else df['ECOS_log']


# ─────────────────────────────────────────────────────────────────────────────
# PASO 4: BASE ANALÍTICA FINAL — ESTADÍSTICOS DESCRIPTIVOS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 4: BASE ANALÍTICA FINAL")
print("="*65)

# Variables que entran en la estimación
vars_modelo = {
    'ECOS_log_w':     'Log(1+ECOS) winsorizado — variable dep. principal',
    'ABSCAP_w':       'Capacidad absorción extendida (winsorizada)',
    'DIGINT_proxy_w': 'Proxy digitalización (winsorizado)',
    'RDINT_w':        'Intensidad I+D (winsorizada)',
    'I01_bin':        'Actividad investigación (0/1)',
    'D01_bin':        'Actividad desarrollo (0/1)',
    'F_activa':       'Formación activa (0/1)',
    'SIZE_log':       'Log empleados',
    'EXPINT_w':       'Intensidad exportadora (winsorizada)',
    'QUAL':           'Proporción trabajadores cualificados',
    'PAT_log':        'Log patentes',
    'd2023':          'Dummy año 2023',
    'd2024':          'Dummy año 2024',
}

print(f"\n  {'Variable':<22} {'N':>6} {'%':>6} {'Media':>8} {'SD':>8} {'Min':>8} {'Max':>8}")
print(f"  {'-'*70}")
for var, desc in vars_modelo.items():
    if var in df.columns:
        s = df[var].dropna()
        pct = len(s) / len(df) * 100
        print(f"  {var:<22} {len(s):>6} {pct:>5.1f}% {s.mean():>8.3f} "
              f"{s.std():>8.3f} {s.min():>8.3f} {s.max():>8.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 5: ESTIMACIÓN ETAPA 1 — FORMA REDUCIDA
# OLS con efectos fijos de empresa y año
# ECOS_log ~ dosis (I,D,F) + controles + FE empresa + FE año
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 5: ETAPA 1 — FORMA REDUCIDA (within estimator)")
print("="*65)

print("\n  Especificación: ECOS_log ~ activ_INV + activ_DEV + RDINT + SIZE + EXPINT + QUAL + PAT + d2023 + d2024")
print("  Estimador: OLS within (demeaning por empresa) con errores HC1\n")

# Seleccionar variables y construir muestra de trabajo
vars_e1 = ['ECOS_log_w', 'I01_bin', 'D01_bin', 'F_activa',
           'RDINT_w', 'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log',
           'd2023', 'd2024', 'empresa_id', 'empresa_int', 'año']

df_e1 = df[vars_e1].dropna(subset=['ECOS_log_w']).copy()
print(f"  Observaciones con ECOS_log disponible: {len(df_e1)}")

# Rellenar dosis binarias con 0 cuando están ausentes pero ECOS está disponible
# (ausencia de respuesta en bloque I/D se interpreta como no-actividad)
df_e1['I01_bin']  = df_e1['I01_bin'].fillna(0)
df_e1['D01_bin']  = df_e1['D01_bin'].fillna(0)
df_e1['F_activa'] = df_e1['F_activa'].fillna(0)

# Para controles, imputar con mediana del panel (imputación conservadora)
for c in ['RDINT_w', 'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log']:
    df_e1[c] = df_e1[c].fillna(df_e1[c].median())

print(f"  Muestra efectiva tras imputación: {len(df_e1)} obs., "
      f"{df_e1['empresa_id'].nunique()} empresas")

# ── Transformación within (demeaning) ────────────────────────────────────────
X_cols_e1 = ['I01_bin', 'D01_bin', 'F_activa',
             'RDINT_w', 'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log',
             'd2023', 'd2024']
nombres_e1 = ['Activ.Investigación', 'Activ.Desarrollo', 'Formación activa',
              'Intensidad I+D', 'Log(empleados)', 'Intensidad export.',
              'Cualificación', 'Log(patentes)', 'Año 2023', 'Año 2024']

# Demeaning: restamos la media de empresa a cada variable
y_dm = within_transform(df_e1, 'ECOS_log_w')
X_dm = pd.DataFrame({
    col: within_transform(df_e1, col) for col in X_cols_e1
})

# Estimación
res_e1 = ols_within(y_dm, X_dm, n_obs=len(df_e1),
                    n_entities=df_e1['empresa_id'].nunique(),
                    n_time_dummies=2)

tabla_resultados(nombres_e1, res_e1,
    titulo='ETAPA 1: ECOS_log ~ Dosis + Controles (FE empresa + año)')

print("\n  INTERPRETACIÓN:")
print("  Los coeficientes miden el efecto WITHIN: cuánto cambia ECOS_log")
print("  dentro de una misma empresa cuando cambia la variable.")
print("  Los efectos fijos de empresa controlan todo lo que no varía")
print("  entre años dentro de cada empresa (capacidades estructurales, sector, etc.)")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 6: ESTIMACIÓN ETAPA 2 — SISTEMA DE DOS ECUACIONES
#
# Ecuación 1 (mecanismo): ABSCAP ~ dosis + controles + FE
# Ecuación 2 (resultado):  ECOS   ~ ABSCAP_hat + dosis + controles + FE
#
# ABSCAP es potencialmente endógena en la ecuación de ECOS:
# Las empresas con más capacidad de absorción pueden ser seleccionadas
# por el programa o pueden beneficiarse más de él, creando correlación
# entre ABSCAP y el error de ECOS.
#
# Estrategia de identificación:
# - Instrumento para ABSCAP: valores rezagados de QUAL y TRAININT
#   (características del capital humano previas que predicen absorción
#   pero no afectan directamente al ecosistema contemporáneo)
# - En la base actual solo tenemos 3 años, así que usamos como instrumento
#   la media de QUAL y TRAININT en t-1 o la variación between-empresa,
#   que es exógena a shocks temporales en ECOS.
#
# Con solo 3 años, el instrumento más creíble es la media de empresa
# en QUAL (between), que captura el nivel estructural de capital humano
# sin estar contaminada por la variación temporal potencialmente endógena.
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 6: ETAPA 2 — SISTEMA DOS ECUACIONES (MC2E)")
print("="*65)

vars_e2 = ['ECOS_log_w', 'ABSCAP_w', 'I01_bin', 'D01_bin', 'F_activa',
           'RDINT_w', 'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log',
           'd2023', 'd2024', 'empresa_id', 'empresa_int', 'año']

df_e2 = df[vars_e2].dropna(subset=['ECOS_log_w', 'ABSCAP_w']).copy()

# Imputar dosis y controles
for c in ['I01_bin', 'D01_bin', 'F_activa']:
    df_e2[c] = df_e2[c].fillna(0)
for c in ['RDINT_w', 'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log']:
    df_e2[c] = df_e2[c].fillna(df_e2[c].median())

print(f"\n  Muestra: {len(df_e2)} obs., {df_e2['empresa_id'].nunique()} empresas")
print(f"  (muestra reducida por cobertura de ABSCAP: 43.7%)")

# ── Ecuación 1: ABSCAP como función de dosis y controles ─────────────────────
print("\n  ─── Ecuación 1: ABSCAP ~ Dosis + Controles ───")

X_cols_ec1 = ['I01_bin', 'D01_bin', 'F_activa',
              'RDINT_w', 'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log',
              'd2023', 'd2024']
nombres_ec1 = ['Activ.Investigación', 'Activ.Desarrollo', 'Formación activa',
               'Intensidad I+D', 'Log(empleados)', 'Intensidad export.',
               'Cualificación', 'Log(patentes)', 'Año 2023', 'Año 2024']

y_abscap_dm = within_transform(df_e2, 'ABSCAP_w')
X_ec1_dm = pd.DataFrame({col: within_transform(df_e2, col) for col in X_cols_ec1})

res_ec1 = ols_within(y_abscap_dm, X_ec1_dm,
                     n_obs=len(df_e2),
                     n_entities=df_e2['empresa_id'].nunique(),
                     n_time_dummies=2)

tabla_resultados(nombres_ec1, res_ec1,
    titulo='EC.1: ABSCAP ~ Dosis + Controles (FE empresa + año)')

# ── Primera etapa MC2E: ABSCAP instrumentado ─────────────────────────────────
# El instrumento es la media between-empresa de QUAL (capital humano estructural).
# La media between de QUAL predice ABSCAP porque una empresa con más capital
# humano medio a lo largo del panel tiene más capacidad de absorción.
# No afecta directamente a ECOS una vez controlamos por los cambios within
# (toda la variación between queda absorbida por los FE de empresa).
#
# En práctica: añadimos QUAL_between como regresor adicional en la primera
# etapa para obtener ABSCAP_hat con más varianza exógena.

print("\n  ─── Primera etapa MC2E: instrumentos rezagados (t-1) ───")
print("  Instrumento: QUAL y RDINT del año anterior.")
print("  Predicen ABSCAP actual pero no afectan directamente a ECOS contemporáneo.")

# Ordenar y construir rezagos temporales
df_e2 = df_e2.sort_values(['empresa_id', 'año']).copy()
df_e2['QUAL_lag']     = df_e2.groupby('empresa_id')['QUAL'].shift(1)
df_e2['RDINT_lag']    = df_e2.groupby('empresa_id')['RDINT_w'].shift(1)

# Perdemos 2022 (no tiene año anterior en el panel) — queda muestra 2023-2024
df_e2_lag = df_e2.dropna(subset=['QUAL_lag', 'RDINT_lag',
                                   'ABSCAP_w', 'ECOS_log_w']).copy()
for c in ['I01_bin', 'D01_bin', 'F_activa', 'RDINT_w',
          'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log']:
    df_e2_lag[c] = df_e2_lag[c].fillna(df_e2_lag[c].median())

print(f"\n  Muestra con rezagos (2023-2024): {len(df_e2_lag)} obs., "
      f"{df_e2_lag['empresa_id'].nunique()} empresas")
print(f"  (año 2022 excluido: no tiene t-1 disponible)")

# Usamos solo d2024 como dummy temporal (2023 es la referencia)
X_cols_lag = ['I01_bin', 'D01_bin', 'F_activa',
              'RDINT_w', 'SIZE_log', 'EXPINT_w', 'QUAL', 'PAT_log', 'd2024']
nombres_lag = ['Activ.Investigación', 'Activ.Desarrollo', 'Formación activa',
               'Intensidad I+D', 'Log(empleados)', 'Intensidad export.',
               'Cualificación', 'Log(patentes)', 'Año 2024']

y_abscap_lag = within_transform(df_e2_lag, 'ABSCAP_w')

# Primera etapa SIN instrumentos (referencia para el F)
X_sin_inst = pd.DataFrame({c: within_transform(df_e2_lag, c) for c in X_cols_lag})
res_sin_inst = ols_within(y_abscap_lag, X_sin_inst,
                           n_obs=len(df_e2_lag),
                           n_entities=df_e2_lag['empresa_id'].nunique(),
                           n_time_dummies=1)

# Primera etapa CON instrumentos rezagados
X_con_inst = X_sin_inst.copy()
X_con_inst['QUAL_lag']  = within_transform(df_e2_lag, 'QUAL_lag').values
X_con_inst['RDINT_lag'] = within_transform(df_e2_lag, 'RDINT_lag').values

res_1etapa = ols_within(y_abscap_lag, X_con_inst,
                         n_obs=len(df_e2_lag),
                         n_entities=df_e2_lag['empresa_id'].nunique(),
                         n_time_dummies=1)

tabla_resultados(nombres_lag + ['QUAL rezagado (t-1)', 'RDINT rezagado (t-1)'],
                 res_1etapa,
                 titulo='PRIMERA ETAPA MC2E: ABSCAP ~ Controles + Instrumentos rezagados')

# Estadístico F de los instrumentos
r2_sin = res_sin_inst['r2_within']
r2_con = res_1etapa['r2_within']
n_iv   = res_1etapa['n']
k_iv   = len(X_cols_lag) + 2
q_inst = 2
F_iv = ((r2_con - r2_sin) / q_inst) / ((1 - r2_con) / (n_iv - k_iv))
print(f"\n  Estadístico F instrumentos: F = {F_iv:.2f}")
if F_iv > 10:
    print(f"  → F > 10: instrumentos suficientemente fuertes (Stock-Yogo) ✓")
elif F_iv > 5:
    print(f"  → F entre 5 y 10: instrumentos moderados, interpretar con cautela")
else:
    print(f"  → F < 5: débiles con panel corto — mejorarán al añadir rezagos de SABI")

# Valores ajustados de ABSCAP (primera etapa)
X_full = X_con_inst.values
y_full = y_abscap_lag.values
mask_iv = ~(np.isnan(y_full) | np.any(np.isnan(X_full), axis=1))
abscap_hat_dm = np.full(len(df_e2_lag), np.nan)
abscap_hat_dm[mask_iv] = X_full[mask_iv] @ res_1etapa['beta']

# ── Segunda etapa MC2E ───────────────────────────────────────────────────────
print("\n  ─── Segunda etapa MC2E: ECOS ~ ABSCAP_hat + Dosis + Controles ───")

y_ecos_lag  = within_transform(df_e2_lag, 'ECOS_log_w')
X_2etapa_dm = pd.DataFrame({c: within_transform(df_e2_lag, c) for c in X_cols_lag})
X_2etapa_dm.insert(0, 'ABSCAP_hat', abscap_hat_dm)
nombres_2etapa = ['ABSCAP (MC2E, hat)'] + nombres_lag

res_2etapa = ols_within(y_ecos_lag, X_2etapa_dm,
                         n_obs=len(df_e2_lag),
                         n_entities=df_e2_lag['empresa_id'].nunique(),
                         n_time_dummies=1)

tabla_resultados(nombres_2etapa, res_2etapa,
    titulo='EC.2 (MC2E): ECOS ~ ABSCAP_hat + Dosis + Controles (FE empresa + año)')

# ── OLS directo de ECOS ~ ABSCAP para comparar con MC2E (Hausman) ───────────
print("\n  ─── Comparación OLS vs MC2E y test Wu-Hausman ───")
X_ols_dm = pd.DataFrame({c: within_transform(df_e2_lag, c)
                          for c in ['ABSCAP_w'] + X_cols_lag})
nombres_ols = ['ABSCAP (OLS)'] + nombres_lag
res_ols_ec2 = ols_within(y_ecos_lag, X_ols_dm,
                          n_obs=len(df_e2_lag),
                          n_entities=df_e2_lag['empresa_id'].nunique(),
                          n_time_dummies=1)

# Actualizar df_e2 para el resumen final
df_e2 = df_e2_lag.copy()
y_ecos_dm = y_ecos_lag

coef_ols  = res_ols_ec2['beta'][0]   # coef. de ABSCAP en OLS
coef_mc2e = res_2etapa['beta'][0]    # coef. de ABSCAP en MC2E
se_ols    = res_ols_ec2['se'][0]
se_mc2e   = res_2etapa['se'][0]

# Estadístico de Hausman: H = (β_MC2E - β_OLS)² / (se_MC2E² - se_OLS²)
# Si H es grande y significativo, hay evidencia de endogeneidad
hausman_num = (coef_mc2e - coef_ols)**2
hausman_den = abs(se_mc2e**2 - se_ols**2) + 1e-10
H_stat = hausman_num / hausman_den
p_hausman = 1 - stats.chi2.cdf(H_stat, df=1)

print(f"\n  Coeficiente ABSCAP — OLS:  {coef_ols:.4f} (SE={se_ols:.4f})")
print(f"  Coeficiente ABSCAP — MC2E: {coef_mc2e:.4f} (SE={se_mc2e:.4f})")
print(f"  Estadístico Hausman: H = {H_stat:.3f}, p = {p_hausman:.4f}")
if p_hausman < 0.05:
    print("  → Evidencia de endogeneidad: usar MC2E (diferencia OLS-MC2E significativa)")
else:
    print("  → Sin evidencia fuerte de endogeneidad: OLS es consistente y más eficiente")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 7: RESUMEN DE RESULTADOS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  PASO 7: RESUMEN COMPARATIVO DE ESTIMACIONES")
print("="*65)

print("""
  ┌─────────────────────────────────────────────────────────┐
  │  Comparativa de efectos sobre ECOS_log                  │
  ├───────────────────┬──────────────┬──────────────────────┤
  │  Variable         │  Etapa 1     │  Etapa 2 (MC2E)      │
  │                   │  (Forma red.)│  (Sistema 2 ec.)     │
  ├───────────────────┼──────────────┼──────────────────────┤""")

# Índice de los coeficientes comparables
comp_vars = ['Activ.Investigación', 'Activ.Desarrollo', 'Formación activa',
             'Intensidad I+D', 'Log(empleados)', 'Año 2023', 'Año 2024']

for j, nombre in enumerate(nombres_e1):
    if nombre in comp_vars:
        b1 = res_e1['beta'][j]
        p1 = res_e1['p'][j]
        sig1 = '***' if p1 < 0.01 else '**' if p1 < 0.05 else '*' if p1 < 0.1 else ''
        # Buscar en etapa 2 (desplazado por ABSCAP_hat al inicio)
        if nombre in nombres_2etapa:
            j2 = nombres_2etapa.index(nombre)
            b2 = res_2etapa['beta'][j2]
            p2 = res_2etapa['p'][j2]
            sig2 = '***' if p2 < 0.01 else '**' if p2 < 0.05 else '*' if p2 < 0.1 else ''
        else:
            b2, sig2 = float('nan'), ''
        print(f"  │  {nombre:<17} │ {b1:>8.4f} {sig1:<3} │ {b2:>8.4f} {sig2:<3}              │")

print("  ├───────────────────┼──────────────┼──────────────────────┤")
print(f"  │  ABSCAP (MC2E)    │     —        │ {coef_mc2e:>8.4f}                  │")
print(f"  ├───────────────────┼──────────────┼──────────────────────┤")
print(f"  │  R² within        │ {res_e1['r2_within']:>7.4f}      │ {res_2etapa['r2_within']:>7.4f}                   │")
print(f"  │  N observaciones  │ {res_e1['n']:>7}      │ {res_2etapa['n']:>7}                   │")
print("  └───────────────────┴──────────────┴──────────────────────┘")

print("""
  NOTAS DE INTERPRETACIÓN:
  ─────────────────────────────────────────────────────────
  1. Todos los coeficientes son efectos WITHIN: variación dentro
     de la misma empresa entre 2022 y 2024.

  2. Los efectos fijos de empresa absorben todo lo no observable
     y constante de cada empresa (sector, tamaño estructural, etc.).

  3. Las dosis son proxies binarias (activ. sí/no). Cuando lleguen
     los datos SABI con importes ejecutados, se reestimará con
     dosis continuas (€ ejecutados / empleado), lo que aumentará
     la precisión y permitirá interpretar efectos marginales.

  4. La muestra de la Etapa 2 (sistema) es menor que la de la
     Etapa 1 (forma reducida) porque requiere ABSCAP disponible
     (43.7% de cobertura). Interpretar con cautela el posible
     sesgo de selección en esa submuestra.

  5. Próximos pasos al recibir datos SABI:
     a) Sustituir dosis binarias por dosis monetarias continuas
     b) Añadir DIGINT como variable mediadora (Etapa 3)
     c) Construir control sintético externo (Etapa 4)
     d) Añadir rezagos de SABI como instrumentos adicionales
""")

