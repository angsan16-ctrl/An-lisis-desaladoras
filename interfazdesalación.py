# app_desalacion_ml_streamlit.py
# Interfaz Streamlit para análisis y modelos (Random Forest, GBM) + SHAP + Permutation
# Genera pestañas: (1) Gráficas interactivas, (2) Análisis ML avanzado
# Salidas descargables: tablas de importancias (Excel/CSV), figuras (ZIP), reportes (Excel)
# Uso: instalar dependencias y ejecutar: streamlit run app_desalacion_ml_streamlit.py

import io
import os
import zipfile
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import streamlit as st

# ML
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.inspection import permutation_importance

# optional: SHAP (si no está instalado, avisamos y seguimos con otras importancias)
try:
    import shap
    SHAP_AVAILABLE = True
except Exception:
    SHAP_AVAILABLE = False

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Desalación — Gráficas y ML", layout="wide")
st.title("Análisis de datos de desalación — Gráficas y ML avanzadas")

st.markdown("""
Esta aplicación carga tu Excel de datos (misma lógica de lectura que la interfaz previa) y ofrece:

- Pestaña **Gráficas**: exploración interactiva (Tiempo vs variable, scatter vs variable base)
- Pestaña **Análisis ML**: modelos Random Forest y Gradient Boosting, importancias (MDI), permutación y SHAP
- Descarga de resultados (tablas Excel/CSV, figuras en ZIP)

**Nota**: si falta `shap` la app seguirá funcionando pero sin explicadores SHAP. Instala `shap` con `pip install shap` si lo deseas.
""")

# -------------------------
# Sidebar: Upload + opciones
# -------------------------
st.sidebar.header("Entradas")
uploaded = st.sidebar.file_uploader("Sube archivo Excel (.xlsx/.xls)", type=["xlsx", "xls"]) 

st.sidebar.markdown("---")
st.sidebar.header("Parámetros ML")
test_size = st.sidebar.slider("Tamaño test (fracción)", min_value=0.05, max_value=0.5, value=0.2, step=0.05)
random_state = st.sidebar.number_input("Random seed", value=42, step=1)
rf_n_estimators = st.sidebar.number_input("RF n_estimators", value=200, step=10)
rf_max_depth = st.sidebar.number_input("RF max_depth (0 = None)", value=0, step=1)
gb_n_estimators = st.sidebar.number_input("GBM n_estimators", value=200, step=10)

st.sidebar.markdown("---")
if not SHAP_AVAILABLE:
    st.sidebar.warning("`shap` no está instalado. Explicaciones SHAP no estarán disponibles. Ejecuta `pip install shap` y reinicia la app.")

# -------------------------
# Helper functions
# -------------------------

def limpiar_serie_a_numero(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).fillna("").str.strip()
    s = s.str.replace(r"\s+", " ", regex=True)
    def to_num(x):
        if x is None or x == "":
            return np.nan
        try:
            # reemplazar coma decimal si corresponde
            x2 = str(x).replace(' ', '')
            # extraer primer número
            import re
            m = re.search(r"[-+]?\d+[\d\.,]*", x2)
            if not m:
                return np.nan
            numstr = m.group(0)
            numstr = numstr.replace('.', '').replace(',', '.') if numstr.count(',')>0 and numstr.count('.')==0 else numstr.replace(',', '')
            return float(numstr)
        except Exception:
            return np.nan
    return s.apply(to_num)


def construir_dataframe_desde_excel(path: str, sheet_name=None) -> pd.DataFrame:
    # Lee hoja, intenta localizar cabeceras; simplificado: si primera fila tiene strings considerarla header
    df_raw = pd.read_excel(path, sheet_name=sheet_name, header=None, engine="openpyxl")
    # heurística: si fila 0 contiene más de la mitad strings no nulos -> usar como header
    primera = df_raw.iloc[0].astype(str).replace('nan','')
    n_strings = sum(1 for x in primera if str(x).strip()!='' and not str(x).replace('.','',1).isdigit())
    if n_strings >= df_raw.shape[1]//2:
        df = pd.read_excel(path, sheet_name=sheet_name, header=0, engine="openpyxl")
        # convertir columnas numéricas
        for c in df.columns:
            df[c] = limpiar_serie_a_numero(df[c])
        return df
    else:
        # si no, reconstruir nombres simples
        df = pd.read_excel(path, sheet_name=sheet_name, header=None, engine="openpyxl")
        # usar columnas 1..n como datos y crear nombres genéricos
        data = df.values
        cols = [f"Var_{i}" for i in range(data.shape[1])]
        df2 = pd.DataFrame(data, columns=cols)
        for c in df2.columns:
            df2[c] = limpiar_serie_a_numero(df2[c])
        return df2


def guardar_excel_bytes(df_dict: dict) -> bytes:
    # df_dict: {'sheetname': dataframe}
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.utils.dataframe import dataframe_to_rows
    buf = io.BytesIO()
    wb = Workbook()
    first = True
    for sheet, df in df_dict.items():
        if first:
            ws = wb.active
            ws.title = sheet
            first = False
        else:
            ws = wb.create_sheet(sheet)
        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

# -------------------------
# Main UI
# -------------------------

if uploaded is None:
    st.info("Sube tu archivo Excel en la barra lateral para empezar.")
else:
    # guardar temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmpf:
        tmpf.write(uploaded.getbuffer())
        tmp_path = tmpf.name

    try:
        xls = pd.ExcelFile(tmp_path, engine="openpyxl")
        hojas = xls.sheet_names
    except Exception as e:
        st.error(f"Error leyendo Excel: {e}")
        hojas = []

    if not hojas:
        st.error("No se detectaron hojas en el Excel.")
    else:
        hoja = st.selectbox("Selecciona hoja", hojas)
        datos = construir_dataframe_desde_excel(tmp_path, sheet_name=hoja)
        st.success(f"Hoja '{hoja}' cargada — filas={datos.shape[0]} columnas={datos.shape[1]}")

        # Simplificar nombres
        datos.columns = [str(c).strip() for c in datos.columns]

        # Detectar columna tiempo (si hay una columna datetime o llamada 'tiempo'/'date')
        tiempo_col = None
        for c in datos.columns:
            if 'time' in c.lower() or 'fecha' in c.lower() or 'date' in c.lower():
                tiempo_col = c
                break
            if pd.api.types.is_datetime64_any_dtype(datos[c]):
                tiempo_col = c
                break
        if tiempo_col is not None:
            datos['__TIEMPO__'] = pd.to_datetime(datos[tiempo_col], errors='coerce')
        else:
            datos['__TIEMPO__'] = pd.RangeIndex(start=0, stop=len(datos))

        # Mostrar preview
        st.subheader("Vista previa de datos")
        st.dataframe(datos.head(200))

        # Pestañas
        tab1, tab2 = st.tabs(["Gráficas", "Análisis ML avanzado"])

        # -------------------------
        # TAB: Graficas
        # -------------------------
        with tab1:
            st.header("Explorador gráfico")
            numeric_cols = [c for c in datos.columns if pd.api.types.is_numeric_dtype(datos[c]) and c!='__TIEMPO__']
            if not numeric_cols:
                st.info("No se detectaron columnas numéricas para graficar.")
            else:
                ycol = st.selectbox("Variable (Y)", options=numeric_cols, index=0)
                xmode = st.radio("Eje X", ['Tiempo', 'Otra variable numérica'])
                fig, ax = plt.subplots(figsize=(10,4))
                if xmode == 'Tiempo':
                    ax.scatter(datos['__TIEMPO__'], datos[ycol], s=10, alpha=0.6)
                    ax.set_xlabel('Tiempo')
                else:
                    xcol = st.selectbox('Eje X (variable)', options=[c for c in numeric_cols if c!=ycol])
                    ax.scatter(datos[xcol], datos[ycol], s=10, alpha=0.6)
                    ax.set_xlabel(xcol)
                ax.set_ylabel(ycol)
                ax.grid(True)
                st.pyplot(fig)

                # permitir descargar figura
                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                st.download_button("Descargar figura (PNG)", data=buf, file_name=f"grafica_{ycol}.png", mime='image/png')

        # -------------------------
        # TAB: Análisis ML avanzado
        # -------------------------
        with tab2:
            st.header("Análisis de importancia de variables — Modelos y SHAP")

            # Selección objetivo y predictores
            all_numeric = [c for c in datos.columns if pd.api.types.is_numeric_dtype(datos[c])]
            if not all_numeric:
                st.info("No hay columnas numéricas para entrenar modelos.")
            else:
                target = st.selectbox("Selecciona variable objetivo (target)", options=all_numeric)
                predictors = st.multiselect("Selecciona predictores (si vacío se usarán todas las columnas numéricas menos target)", options=[c for c in all_numeric if c!=target])
                if not predictors:
                    X = datos[[c for c in all_numeric if c!=target]].copy()
                else:
                    X = datos[predictors].copy()
                y = datos[target].copy()

                # limpiar NaNs: eliminar filas sin target o con todos predictores NaN
                mask_good = y.notna() & X.notna().any(axis=1)
                X = X[mask_good]
                y = y[mask_good]

                st.write(f"Filas para ML: {len(y)} — variables: {list(X.columns)}")

                run_train = st.button("Entrenar modelos y calcular importancias")

                if run_train:
                    # dividir
                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=int(random_state))

                    results = {}

                    # Random Forest
                    rf = RandomForestRegressor(n_estimators=int(rf_n_estimators), max_depth=(None if int(rf_max_depth)==0 else int(rf_max_depth)), random_state=int(random_state), n_jobs=-1)
                    rf.fit(X_train, y_train)
                    ypred = rf.predict(X_test)
                    results['RF'] = {
                        'model': rf,
                        'r2': r2_score(y_test, ypred),
                        'rmse': mean_squared_error(y_test, ypred, squared=False)
                    }

                    # GBM
                    gb = GradientBoostingRegressor(n_estimators=int(gb_n_estimators), random_state=int(random_state))
                    gb.fit(X_train, y_train)
                    ypred_gb = gb.predict(X_test)
                    results['GB'] = {
                        'model': gb,
                        'r2': r2_score(y_test, ypred_gb),
                        'rmse': mean_squared_error(y_test, ypred_gb, squared=False)
                    }

                    st.success("Modelos entrenados — calculando importancias...")

                    # 1) Importancia MDI (feature_importances_)
                    mdi_frames = {}
                    for name, info in results.items():
                        mod = info['model']
                        if hasattr(mod, 'feature_importances_'):
                            imp = mod.feature_importances_
                            df_imp = pd.DataFrame({'feature': X.columns, f'importance_{name}': imp})
                            df_imp = df_imp.sort_values(by=f'importance_{name}', ascending=False).reset_index(drop=True)
                            mdi_frames[name] = df_imp

                    # 2) Permutation importance (on test)
                    perm_frames = {}
                    for name, info in results.items():
                        mod = info['model']
                        try:
                            p = permutation_importance(mod, X_test, y_test, n_repeats=20, random_state=int(random_state), n_jobs=-1)
                            dfp = pd.DataFrame({'feature': X.columns, f'perm_importance_{name}_mean': p.importances_mean, f'perm_importance_{name}_std': p.importances_std})
                            dfp = dfp.sort_values(by=f'perm_importance_{name}_mean', ascending=False).reset_index(drop=True)
                            perm_frames[name] = dfp
                        except Exception as e:
                            st.warning(f"Permutación falló para {name}: {e}")

                    # 3) SHAP values (if available)
                    shap_frames = {}
                    if SHAP_AVAILABLE:
                        try:
                            # usar TreeExplainer si posible
                            expl_rf = shap.TreeExplainer(results['RF']['model'])
                            shap_vals_rf = expl_rf.shap_values(X_test)
                            # shap_vals_rf shape: (n_samples, n_features) for reg
                            mean_abs = np.abs(shap_vals_rf).mean(axis=0)
                            dfsh = pd.DataFrame({'feature': X.columns, 'shap_mean_abs_RF': mean_abs}).sort_values('shap_mean_abs_RF', ascending=False).reset_index(drop=True)
                            shap_frames['RF'] = dfsh
                            expl_gb = shap.TreeExplainer(results['GB']['model'])
                            shap_vals_gb = expl_gb.shap_values(X_test)
                            mean_abs_gb = np.abs(shap_vals_gb).mean(axis=0)
                            dfsh2 = pd.DataFrame({'feature': X.columns, 'shap_mean_abs_GB': mean_abs_gb}).sort_values('shap_mean_abs_GB', ascending=False).reset_index(drop=True)
                            shap_frames['GB'] = dfsh2
                        except Exception as e:
                            st.warning(f"Cálculo SHAP falló: {e}")

                    # 4) Consolidar resumen
                    # start from features
                    resumen = pd.DataFrame({'feature': X.columns})
                    for name, df_imp in mdi_frames.items():
                        resumen = resumen.merge(df_imp, on='feature', how='left')
                    for name, dfp in perm_frames.items():
                        resumen = resumen.merge(dfp, on='feature', how='left')
                    for name, dfs in shap_frames.items():
                        resumen = resumen.merge(dfs, on='feature', how='left')

                    # show model performance
                    st.subheader('Rendimiento de modelos (test)')
                    perf = pd.DataFrame([{ 'model': k, 'r2': v['r2'], 'rmse': v['rmse'] } for k,v in results.items()])
                    st.dataframe(perf)

                    st.subheader('Tabla de importancias combinadas')
                    st.dataframe(resumen)

                    # Gráficos de importancias (MDI y Permutation)
                    st.subheader('Gráficas de importancias')
                    figs = []
                    for name, df_imp in mdi_frames.items():
                        fig, ax = plt.subplots(figsize=(8,4))
                        ax.barh(df_imp['feature'].iloc[::-1], df_imp[f'importance_{name}'].iloc[::-1])
                        ax.set_title(f'Importancia MDI — {name}')
                        ax.set_xlabel('importancia')
                        ax.grid(True)
                        st.pyplot(fig)
                        figs.append((f'mdi_{name}.png', fig))

                    for name, dfp in perm_frames.items():
                        fig, ax = plt.subplots(figsize=(8,4))
                        ax.barh(dfp['feature'].iloc[::-1], dfp[f'perm_importance_{name}_mean'].iloc[::-1])
                        ax.set_title(f'Importancia por permutación — {name}')
                        ax.set_xlabel('mean decrease in score (perm)')
                        ax.grid(True)
                        st.pyplot(fig)
                        figs.append((f'perm_{name}.png', fig))

                    if SHAP_AVAILABLE and shap_frames:
                        st.subheader('SHAP mean absolute (ranking)')
                        for name, dfs in shap_frames.items():
                            fig, ax = plt.subplots(figsize=(8,4))
                            ax.barh(dfs['feature'].iloc[::-1], dfs.iloc[::-1,1].values)
                            ax.set_title(f'SHAP mean abs — {name}')
                            ax.grid(True)
                            st.pyplot(fig)
                            figs.append((f'shap_{name}.png', fig))

                    # Preparar descargas: Excel con resumen + CSV SHAP (si existe) + ZIP con figuras
                    out_files = {}
                    bytes_excel = guardar_excel_bytes({'Importancias': resumen, 'Rendimiento': perf})
                    out_files['importancias_resumen.xlsx'] = bytes_excel

                    # SHAP per-sample matrix (opcional) — guardar si calculado
                    if SHAP_AVAILABLE and 'RF' in shap_frames:
                        try:
                            # guardar shap matrix para RF
                            expl = shap.TreeExplainer(results['RF']['model'])
                            shap_vals = expl.shap_values(X)
                            df_shap_matrix = pd.DataFrame(shap_vals, columns=X.columns)
                            out_files['shap_values_RF.csv'] = df_shap_matrix.to_csv(index=False).encode('utf-8')
                        except Exception:
                            pass

                    # ZIP figuras
                    zipbuf = io.BytesIO()
                    with zipfile.ZipFile(zipbuf, 'w') as zf:
                        for fname, fig in figs:
                            imgbuf = io.BytesIO()
                            fig.savefig(imgbuf, format='png', bbox_inches='tight')
                            imgbuf.seek(0)
                            zf.writestr(fname, imgbuf.read())
                    zipbuf.seek(0)
                    out_files['figuras.zip'] = zipbuf.getvalue()

                    # Botones de descarga
                    st.markdown('---')
                    st.subheader('Descargas')
                    for name, b in out_files.items():
                        st.download_button(label=f"Descargar {name}", data=b, file_name=name)

                    st.success('Análisis completado. Revisa gráficas y descarga los ficheros.')

# FIN
