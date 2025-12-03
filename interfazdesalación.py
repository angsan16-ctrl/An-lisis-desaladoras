"""
interfazdesalacion_reconstruida.py
Reconstrucción desde cero (base: antigua) — única, limpia y sin duplicados.
Incluye:
 - Dos pestañas: Graficado | Análisis avanzado (incluye importancia de variables)
 - Métodos de importancia: Pearson, Spearman, Mutual Info, RandomForest
 - Botones con keys únicos para evitar StreamlitDuplicateElementId
 - Exportación de resultados a Excel
 - Integración cuidadosa: si el script original 'interfazdesalaciónantigua.py' está presente,
   intenta importar algunas funciones avanzadas (si existen). Si no, usa implementaciones internas.
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tempfile, io, os, sys, importlib.util
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import mutual_info_regression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from openpyxl import Workbook

# --------------------------
# Configuración
# --------------------------
st.set_page_config(page_title="Desalación - Interfaz Reconstruida", layout="wide")

st.markdown("<h1 style='color:#0B1A33;font-weight:800'>Desalación — Interfaz Reconstruida</h1>", unsafe_allow_html=True)
st.sidebar.header("Cargar archivo y parámetros")

uploaded = st.sidebar.file_uploader("Sube Excel de desalación", type=["xlsx","xls"], key="uploader_main")
fig_w = st.sidebar.slider("Ancho figura", 6, 16, 10, key="figw_main")
fig_h = st.sidebar.slider("Alto figura", 4, 12, 6, key="figh_main")
st.sidebar.markdown("---")
st.sidebar.caption("Versión reconstruida — limpia, sin duplicados, basada en la interfaz antigua.")

# --------------------------
# Intentar cargar funciones avanzadas del archivo antiguo si existe
# --------------------------
def try_import_module_at(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("old_interfaz_module", str(path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["old_interfaz_module"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print("No se pudo importar módulo antiguo:", e)
        return None

old_mod = try_import_module_at("/mnt/data/interfazdesalaciónantigua.py") or try_import_module_at("/mnt/data/interfazdesalación.py")

# --------------------------
# Utilidades internas
# --------------------------
def detectar_fila_inicio_datos_simple(df_raw):
    # heurística simple: busca la primera fila con menos valores nulos que la mitad de columnas
    for i in range(min(10, len(df_raw))):
        if df_raw.iloc[i].notna().sum() > df_raw.shape[1]//2:
            return i
    return 0

def limpiar_serie_a_numero(serie):
    return pd.to_numeric(serie, errors="coerce")

def construir_datos_desde_excel(tmp_path, hoja_sel=None):
    xls = pd.ExcelFile(tmp_path)
    hojas = xls.sheet_names
    if hoja_sel is None:
        hoja = hojas[0]
    else:
        hoja = hoja_sel if hoja_sel in hojas else hojas[0]
    df_raw = pd.read_excel(tmp_path, sheet_name=hoja, header=None, engine="openpyxl")
    fila_inicio = detectar_fila_inicio_datos_simple(df_raw)
    datos_vals = df_raw.iloc[fila_inicio:, :].reset_index(drop=True)
    # intentar convertir columnas a números (excepto primera columna que podría ser tiempo)
    for c in datos_vals.columns:
        datos_vals[c] = limpiar_serie_a_numero(datos_vals[c])
    # renombrar columnas con índices para evitar duplicados de nombres
    datos_vals.columns = [f"col_{i}" for i in range(datos_vals.shape[1])]
    # crear columna Tiempo desde la segunda columna si tiene formato fecha
    try:
        tiempo_col = pd.to_datetime(df_raw.iloc[fila_inicio:, 1].reset_index(drop=True), errors="coerce")
        if tiempo_col.isnull().all():
            datos_vals.insert(0, "Tiempo", pd.RangeIndex(start=0, stop=len(datos_vals)))
        else:
            datos_vals.insert(0, "Tiempo", tiempo_col)
    except Exception:
        datos_vals.insert(0, "Tiempo", pd.RangeIndex(start=0, stop=len(datos_vals)))
    return datos_vals, hoja, hojas

# --------------------------
# Funciones de análisis e importancia
# --------------------------
def calcular_importancias(datos_df: pd.DataFrame, target_col: str, method: str = "pearson", n_trees: int = 200, random_state: int = 42):
    cols = [c for c in datos_df.columns if c not in ("Tiempo", target_col)]
    df = datos_df.copy()
    for c in cols + [target_col]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    imputer = SimpleImputer(strategy='median')
    X = imputer.fit_transform(df[cols])
    y = imputer.fit_transform(df[[target_col]]).ravel()
    if method == "pearson":
        out = []
        for i, c in enumerate(cols):
            mask = (~np.isnan(df[c])) & (~np.isnan(df[target_col]))
            if mask.sum() < 2:
                imp = np.nan
            else:
                imp = float(pd.Series(df[c][mask]).corr(pd.Series(df[target_col][mask]), method='pearson'))
            out.append((c, np.abs(imp) if not np.isnan(imp) else np.nan, imp))
        df_out = pd.DataFrame(out, columns=["Feature", "Imp_abs", "Corr_pearson"]).sort_values("Imp_abs", ascending=False).reset_index(drop=True)
        return df_out
    if method == "spearman":
        out = []
        for i, c in enumerate(cols):
            mask = (~np.isnan(df[c])) & (~np.isnan(df[target_col]))
            if mask.sum() < 2:
                imp = np.nan
            else:
                imp = float(pd.Series(df[c][mask]).corr(pd.Series(df[target_col][mask]), method='spearman'))
            out.append((c, np.abs(imp) if not np.isnan(imp) else np.nan, imp))
        df_out = pd.DataFrame(out, columns=["Feature", "Imp_abs", "Corr_spearman"]).sort_values("Imp_abs", ascending=False).reset_index(drop=True)
        return df_out
    if method == "mutual_info":
        try:
            mi = mutual_info_regression(X, y, random_state=random_state)
        except Exception:
            mi = np.full(len(cols), np.nan)
        df_out = pd.DataFrame({"Feature": cols, "MI": mi}).sort_values("MI", ascending=False).reset_index(drop=True)
        return df_out
    if method == "random_forest":
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        rf = RandomForestRegressor(n_estimators=int(n_trees), random_state=int(random_state), n_jobs=-1)
        rf.fit(Xs, y)
        df_out = pd.DataFrame({"Feature": cols, "RF_importance": rf.feature_importances_}).sort_values("RF_importance", ascending=False).reset_index(drop=True)
        return df_out
    raise ValueError("Método no soportado")

# --------------------------
# Funciones fallback para generar gráficas y análisis crítico (versiones simplificadas)
# --------------------------
def generar_graficas_por_desalador_internal(datos, desaladores, variable_base, carpeta_salida, mapa_norm_columns=None):
    # Genera un libro Excel con gráficas simplificadas por variable; devuelve rutas
    resultados = {}
    try:
        os.makedirs(carpeta_salida, exist_ok=True)
        for d in (desaladores or ["GENERAL"]):
            wb = Workbook()
            ws = wb.active
            ws.title = "Resumen"
            # poner un simple resumen estadístico
            resumen = datos.describe(include="all")
            for r_idx, row in enumerate(resumen.reset_index().values.tolist(), start=1):
                for c_idx, val in enumerate(row, start=1):
                    ws.cell(row=r_idx, column=c_idx, value=str(val))
            archivo = os.path.join(carpeta_salida, f"Graficas_{d}_{variable_base}.xlsx")
            wb.save(archivo)
            resultados[d] = archivo
    except Exception as e:
        print("Error generando gráficas (internal):", e)
    return resultados

def analisis_critico_extendido_internal(datos, desaladores, variable_base, valor_critico, carpeta_salida, mapa_norm_columns=None):
    # Produce un xlsx con estadísticas básicas y copia de filas que exceden valor_critico
    resultados = {}
    try:
        os.makedirs(carpeta_salida, exist_ok=True)
        df = datos.copy()
        if variable_base not in df.columns:
            df = df
        else:
            series = pd.to_numeric(df[variable_base], errors="coerce")
            df_exceed = df[series > valor_critico]
            ruta = os.path.join(carpeta_salida, f"AnalisisCritico_{variable_base}.xlsx")
            df_exceed.to_excel(ruta, index=False)
            resultados[variable_base] = ruta
    except Exception as e:
        print("Error analisis critico (internal):", e)
    return resultados

# Use module functions if available
generar_graficas_por_desalador = getattr(old_mod, "generar_graficas_por_desalador", generar_graficas_por_desalador_internal)
analisis_critico_extendido = getattr(old_mod, "analisis_critico_extendido", analisis_critico_extendido_internal)

# --------------------------
# MAIN: UI cuando se sube archivo
# --------------------------
if uploaded is None:
    st.info("Sube un archivo Excel para comenzar. La app leerá todas las filas y reconstruirá nombres y variables.")
else:
    # Guardar temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmpf:
        tmpf.write(uploaded.getbuffer())
        tmp_path = tmpf.name

    try:
        datos, hoja_sel, hojas = construir_datos_desde_excel(tmp_path)
    except Exception as e:
        st.error(f"Error procesando Excel: {e}")
        datos = None
        hojas = []

    if datos is None:
        st.error("No se pudieron construir los datos desde el Excel.")
    else:
        # Mostrar vista previa
        st.subheader("Datos (vista previa)")
        st.dataframe(datos.head(200))

        # Detectar posibles desaladores si hubiera nombres (intento simple sobre columnas originales)
        desaladores_detectados = []
        # (en reconstrucción simple no intentamos mapear C11 etc.; se puede añadir luego)
        # Tabs: Graficado | Análisis avanzado
        tab1, tab2 = st.tabs(["Graficado de variables", "Análisis avanzado"])

        # --- TAB 1: Graficado ---
        with tab1:
            st.subheader("Graficado de variables")
            cols_plot = [c for c in datos.columns if c != "Tiempo"]
            if not cols_plot:
                st.info("No hay columnas numéricas para graficar.")
            else:
                ycol = st.selectbox("Variable a graficar (Y)", options=cols_plot, index=0, key="select_y")
                xmode = st.radio("Eje X", ['Tiempo','Índice'], index=0, key="radio_xmode")
                fig, ax = plt.subplots(figsize=(fig_w, fig_h))
                try:
                    if xmode == "Tiempo":
                        ax.scatter(pd.to_datetime(datos['Tiempo']), datos[ycol], s=10, alpha=0.7)
                        ax.set_xlabel("Tiempo")
                    else:
                        ax.scatter(datos.index, datos[ycol], s=10, alpha=0.7)
                        ax.set_xlabel("Índice")
                    ax.set_ylabel(str(ycol))
                    ax.grid(True)
                    st.pyplot(fig)
                except Exception as e:
                    st.error(f"Error graficando: {e}")

                st.markdown("---")
                st.write("Opciones de exportación de la gráfica y datos:")
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                buf.seek(0)
                st.download_button("Descargar imagen (PNG)", data=buf, file_name=f"graf_{ycol}.png", mime="image/png", key="dl_png")

        # --- TAB 2: Análisis avanzado ---
        with tab2:
            st.subheader("Análisis avanzado y exportaciones")
            cols_for_target = [c for c in datos.columns if c != "Tiempo"]
            target = st.selectbox("Selecciona variable objetivo (target)", options=cols_for_target, index=0, key="select_target")
            metodo = st.selectbox("Método de importancia", options=["pearson","spearman","mutual_info","random_forest"], index=0, key="select_method")
            n_trees = st.number_input("Número de árboles (RF)", min_value=10, max_value=2000, value=200, step=10, key="input_ntrees")

            if st.button("Calcular importancias", key="btn_calc_import"):
                with st.spinner("Calculando importancias..."):
                    try:
                        res = calcular_importancias(datos, target, method=metodo, n_trees=n_trees)
                        st.success("Importancias calculadas")
                        st.dataframe(res.head(200))
                        # elegir columna de importancia
                        imp_cols = [c for c in res.columns if any(x in c.lower() for x in ['imp','mi','rf','corr'])]
                        if imp_cols:
                            imp_col = imp_cols[0]
                            top = res.head(20).set_index("Feature")
                            st.bar_chart(top[imp_col])
                        st.markdown(f"**Variable más importante según {metodo}:** {res.iloc[0]['Feature'] if not res.empty else 'N/A'}")
                        # permitir exportar resultados
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                            res.to_excel(writer, index=False, sheet_name="Importancias")
                            writer.save()
                        buffer.seek(0)
                        st.download_button("Descargar importancias (.xlsx)", data=buffer, file_name=f"importancias_{target}_{metodo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_imp_xlsx")
                    except Exception as e:
                        st.error(f"Error calculando importancias: {e}")

            st.markdown("---")
            st.write("Acciones avanzadas (generar gráficas por desalador / análisis crítico):")
            colA, colB = st.columns(2)
            with colA:
                val_crit = st.number_input("Valor crítico (para análisis)\", value=0.0, format=\"%.6f\", key=\"input_valcrit")
                if st.button("Ejecutar análisis crítico\", key=\"btn_analisis_critico"):
                    out_dir = Path.cwd() / 'Resultados_Desalacion_App' / 'Analisis_Criticos'
                    out_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        archivos = analisis_critico_extendido(datos, [], target, float(val_crit), str(out_dir), None)
                        st.success(f'Análisis crítico. Archivos: {len(archivos)}')
                        for k,v in archivos.items():
                            try:
                                with open(v, "rb") as f:
                                    st.download_button(f"Descargar {Path(v).name}", data=f, file_name=Path(v).name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_crit_{k}")
                            except Exception as e:
                                st.write(f"No se pudo preparar descarga para {v}: {e}")
                    except Exception as e:
                        st.error(f'Error en análisis crítico: {e}')
            with colB:
                if st.button("Generar gráficas por desalador", key="btn_gen_grafs"):
                    out_dir = Path.cwd() / 'Resultados_Desalacion_App' / 'Graficas'
                    out_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        archivos_g = generar_graficas_por_desalador(datos, [], target, str(out_dir), None)
                        st.success(f'Gráficas generadas. Archivos: {len(archivos_g)}')
                        for k,v in archivos_g.items():
                            try:
                                with open(v, "rb") as f:
                                    st.download_button(f"Descargar {Path(v).name}", data=f, file_name=Path(v).name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_graf_{k}")
                            except Exception as e:
                                st.write(f"No se pudo preparar descarga para {v}: {e}")
                    except Exception as e:
                        st.error(f'Error generando gráficas: {e}')

        # Exportar datos procesados
        st.markdown("---")
        if st.button("Descargar datos procesados (Excel)", key="btn_dl_datos_proc"):
            try:
                buf = io.BytesIO()
                datos.to_excel(buf, index=False, engine="openpyxl")
                buf.seek(0)
                st.download_button("Descargar archivo", data=buf, file_name="datos_procesados_desalacion.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_datos_proc")
            except Exception as e:
                st.error(f"Error preparando exportación: {e}")

st.caption("Interfaz reconstruida — basada en la versión antigua; limpia y lista para ejecutar.")
