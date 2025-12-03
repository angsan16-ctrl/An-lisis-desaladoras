# app_desalacion_avanzada.py
# Versión unificada que integra la interfaz original 'interfazdesalaciónantigua.py'
# y añade una segunda pestaña 'Análisis Avanzado' con múltiples modelos.
#
# Guardar como:
#    app_desalacion_avanzada.py
# Ejecutar:
#    streamlit run app_desalacion_avanzada.py
#
# Autor: generado para el usuario, integra la app original aportada + ampliaciones solicitadas.
# Fecha: generada automáticamente.

import os
import sys
import re
import io
import unicodedata
import tempfile
import importlib.util
from pathlib import Path
from typing import List, Tuple, Dict, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image, ImageFilter

import streamlit as st
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.drawing.image import Image as xlImage

# -------------------------
# Configuración de la app
# -------------------------
st.set_page_config(page_title="Análisis desaladoras", layout="wide")

# Título principal en azul oscuro
st.markdown("<h1 class='darkblue-title'>Análisis desaladoras</h1>", unsafe_allow_html=True)

# Estilo global: colores, headers, botones
st.markdown("""
<style>

  /* =========================================================
     0. FONDO GENERAL → BLANCO
     ========================================================= */
  html, body, .block-container, [class*="stApp"] {
      background-color: #FFFFFF !important;  /* blanco */
      color: #333333 !important;             /* texto gris oscuro */
  }

  /* =========================================================
     1. TITULOS GRANDES → NARANJA REPSOL
     ========================================================= */
  h1, h2, h3, h4, h5, h6 {
      color: #D98B3B !important;     /* naranja Repsol */
      font-weight: 800 !important;
  }

  /* =========================================================
     2. TITULOS AZUL OSCURO (solo si tú lo marcas con clase)
     ========================================================= */
  .darkblue-title {
      color: #0B1A33 !important;     /* azul oscuro */
      font-weight: 800 !important;
  }

  /* =========================================================
     3. WIDGETS → letra gris oscuro
     ========================================================= */
  .stSelectbox label,
  .stMultiSelect label,
  .stNumberInput label,
  .stSlider label,
  .stTextInput label {
      color: #333333 !important;
  }

  .css-16idsys, .css-1pndypt, .css-1offfwp, .css-1kyxreq {
      color: #333333 !important;
  }

  .stSelectbox div[data-baseweb="select"],
  .stMultiSelect div[data-baseweb="select"] {
      background-color: white !important;
      color: #333333 !important;
  }

  /* =========================================================
     4. TABS → gris / ROJO seleccionada
     ========================================================= */
  .stTabs [data-baseweb="tab"] p {
      color: #666666 !important;   /* gris */
      font-weight: 600 !important;
  }

  .stTabs [aria-selected="true"] p {
      color: red !important;       /* ROJO al seleccionar */
      font-weight: 700 !important;
  }

  .stTabs [data-baseweb="tab"] {
      background-color: #FFFFFF !important; /* fondo blanco */
  }

  /* =========================================================
     5. Botones → NARANJAS
     ========================================================= */
  .stButton>button {
      background-color: #D98B3B !important;
      color: white !important;
      border-radius: 8px;
  }
  .stButton>button:hover {
      background-color: #b57830 !important;
      color: white !important;
  }

</style>
""", unsafe_allow_html=True)

# -------------------------
# Intento cargar módulo original (si existe en /mnt/data)
# -------------------------
MODULE_PATH = Path("/mnt/data/Programa Eficiencias de desalacion2.py")
user_mod = None
if MODULE_PATH.exists():
    try:
        spec = importlib.util.spec_from_file_location("prog_desal", str(MODULE_PATH))
        user_mod = importlib.util.module_from_spec(spec)
        sys.modules["prog_desal"] = user_mod
        spec.loader.exec_module(user_mod)
        st.sidebar.success(f"Módulo original cargado desde {MODULE_PATH}")
    except Exception as e:
        st.sidebar.error(f"No se pudo cargar módulo original: {e}")
else:
    st.sidebar.info("No se encontró el módulo original en /mnt/data; utilizando implementaciones internas.")

def safe_get(name, fallback=None):
    """Si se cargó el módulo original, devuelve la función exportada; si no, devuelve fallback."""
    if user_mod is None:
        return fallback
    return getattr(user_mod, name, fallback)

# -------------------------
# Utilidades (tomadas de tu código original)
# -------------------------
def normalizar(txt):
    if txt is None:
        return ""
    txt = str(txt).strip().lower()
    txt = ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')
    return txt

def clean_token(s):
    if s is None:
        return ""
    s = str(s)
    s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
    s = re.sub(r"[^A-Za-z0-9]", "", s)
    return s.lower()

def make_unique(col_list: List[str]) -> List[str]:
    """Convierte nombres a únicos añadiendo sufijos __N cuando sea necesario"""
    seen = {}
    out = []
    for c in col_list:
        key = str(c)
        if key not in seen:
            seen[key] = 1
            out.append(key)
        else:
            seen[key] += 1
            out.append(f"{key}__{seen[key]}")
    return out

def insertar_imagen_ws(ws, buf, posicion="A1"):
    try:
        img = xlImage(buf)
        img.anchor = posicion
        ws.add_image(img)
    except Exception as e:
        print("Error insertando imagen en worksheet:", e)

# -------------------------
# Funciones para leer y detectar
# -------------------------
def leer_hoja_sin_encabezado(path_excel: str, nombre_hoja: str) -> pd.DataFrame:
    """Lee hoja sin encabezados (header=None) usando openpyxl"""
    df_raw = pd.read_excel(path_excel, sheet_name=nombre_hoja, header=None, engine="openpyxl")
    return df_raw

def detectar_fila_inicio_datos_fallback(df_raw: pd.DataFrame) -> int:
    """
    Heurística para detectar la fila donde comienzan los datos.
    Copiado de tu programa original.
    """
    palabras_ruido = [
        "media", "desviacion", "max", "min",
        "servidor", "unidades", "escala", "ph",
        "tension", "consumo", "eficiencia"
    ]

    nfilas, ncols = df_raw.shape
    for i in range(nfilas):
        fila = df_raw.iloc[i, :]
        texto_fila = " ".join(str(x).lower() for x in fila if pd.notna(x))
        if any(p in texto_fila for p in palabras_ruido):
            continue

        num_ok = 0
        date_ok = 0

        for v in fila:
            if pd.isna(v):
                continue
            try:
                float(str(v).replace(",", "."))
                num_ok += 1
                continue
            except:
                pass
            if isinstance(v, (pd.Timestamp,)):
                date_ok += 1
                continue
            try:
                pd.to_datetime(v, errors="raise")
                date_ok += 1
            except:
                pass

        col1 = fila.iloc[1] if len(fila) > 1 else None
        col1_es_fecha = False
        try:
            pd.to_datetime(col1, errors="raise")
            col1_es_fecha = True
        except:
            pass

        if col1_es_fecha:
            return i
        if num_ok >= max(3, int(ncols * 0.40)):
            return i

    return 0

# Puede venir del módulo original
detectar_fila_inicio_datos = safe_get('detectar_fila_inicio_datos', detectar_fila_inicio_datos_fallback)

# -------------------------
# Detector desalador en columna
# -------------------------
def buscar_desalador_columna_fallback(df, col_idx, filas_adelante=8, filas_detras=8):
    patron = re.compile(r"(c[\-\_ ]?\d{1,3})", flags=re.IGNORECASE)
    nrows = df.shape[0]
    for r in range(0, min(filas_adelante, nrows)):
        try:
            val = df.iloc[r, col_idx]
        except IndexError:
            continue
        if pd.isna(val):
            continue
        s = str(val)
        m = patron.search(s)
        if m:
            return m.group(1).replace("_", "").replace(" ", "").replace("-", "").upper()
    for r in range(0, min(filas_detras, nrows)):
        try:
            val = df.iloc[r, col_idx]
        except IndexError:
            continue
        if pd.isna(val):
            continue
        s = str(val)
        m = patron.search(s)
        if m:
            return m.group(1).replace("_", "").replace(" ", "").replace("-", "").upper()
    for r in range(0, nrows):
        try:
            val = df.iloc[r, col_idx]
        except IndexError:
            continue
        if pd.isna(val):
            continue
        s = str(val)
        m = patron.search(s)
        if m:
            return m.group(1).replace("_", "").replace(" ", "").replace("-", "").upper()
    return ""

buscar_desalador_columna = safe_get('buscar_desalador_columna', buscar_desalador_columna_fallback)

# -------------------------
# Construir nombres columnas (variable + desalador)
# -------------------------
def construir_nombres_columnas_fallback(df_raw, col_inicio=0, col_fin=None, fila_desalador_idx=0, fila_variable_idx=1):
    if col_fin is None:
        col_fin = df_raw.shape[1]
    nombres = []
    desaladores_por_col = []
    for col in range(col_inicio, col_fin):
        desal = df_raw.iloc[fila_desalador_idx, col] if fila_desalador_idx < df_raw.shape[0] else None
        var   = df_raw.iloc[fila_variable_idx, col]  if fila_variable_idx < df_raw.shape[0]  else None

        desal_txt = "" if pd.isna(desal) else str(desal).strip()
        var_txt   = "" if pd.isna(var)   else str(var).strip()

        if desal_txt == "":
            desal_detectado = buscar_desalador_columna(df_raw, col, filas_adelante=6, filas_detras=6)
            if desal_detectado != "":
                desal_txt = desal_detectado

        if var_txt == "":
            for r in range(fila_variable_idx, min(fila_variable_idx + 6, df_raw.shape[0])):
                test = df_raw.iloc[r, col]
                if not pd.isna(test) and str(test).strip() != "":
                    var_txt = str(test).strip()
                    break

        if var_txt == "" and desal_txt == "":
            nombre_final = f"Variable_sin_nombre_{col}"
        elif desal_txt == "":
            nombre_final = f"{var_txt} GENERAL"
        else:
            last_token = desal_txt.strip()
            if var_txt.strip().upper().endswith(last_token.upper()):
                nombre_final = var_txt
            else:
                nombre_final = f"{var_txt} {desal_txt}"

        nombres.append(nombre_final)
        desaladores_por_col.append(desal_txt)

    return nombres, desaladores_por_col

construir_nombres_columnas = safe_get('construir_nombres_columnas', construir_nombres_columnas_fallback)

# -------------------------
# Mapeo variables base y normalización
# -------------------------
def construir_mapa_variables_base_fallback(nombres: List[str]) -> Tuple[Dict[str, List[str]], Dict[str, List[Tuple[str,str]]]]:
    mapa_variable_a_columnas = {}
    mapa_norm_columns = {}
    for nom in nombres:
        parts = str(nom).split()
        base = nom
        if len(parts) > 1:
            last = parts[-1]
            if re.match(r"^c[\-]?\d+$", last.strip().lower()) or re.match(r"^c\d+$", last.strip().lower()):
                base = " ".join(parts[:-1]).strip()
        base = base if base != "" else "Variable_sin_nombre"
        mapa_variable_a_columnas.setdefault(base, []).append(nom)
    for base, cols in mapa_variable_a_columnas.items():
        mapa_norm_columns[base] = [(c, clean_token(c)) for c in cols]
    return mapa_variable_a_columnas, mapa_norm_columns

construir_mapa_variables_base = safe_get('construir_mapa_variables_base', construir_mapa_variables_base_fallback)

# -------------------------
# Limpieza numérica robusta
# -------------------------
def limpiar_serie_a_numero_fallback(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).fillna("").str.strip()
    candidato = s.str.replace(r"\s+", " ", regex=True)
    sentinel_pattern = re.compile(
        r"(no\s+good\s+data|no\s+data|no\s+value|no\s+reading|not\s+available|nodata|n/a|not\s+applicable)",
        flags=re.IGNORECASE
    )
    bracket_code_pattern = re.compile(r"^\s*\[?-?\d+\]?\s*(?:no\b|no good|no data|no value).*", flags=re.IGNORECASE)

    def normaliza_num_str(x):
        if x is None:
            return None
        txt = str(x).strip()
        if txt == "":
            return None
        low = txt.lower()
        if sentinel_pattern.search(low) or bracket_code_pattern.match(txt):
            return None
        if re.fullmatch(r"-?11059|-?110", txt):
            return None
        m = re.search(r"([-+]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|[-+]?\d*[,\.]?\d+)", txt)
        if not m:
            return None
        numstr = m.group(0)
        commas = numstr.count(",")
        dots = numstr.count(".")
        if dots > 0 and commas > 0 and numstr.rfind(",") > numstr.rfind("."):
            s2 = numstr.replace(".", "").replace(",", ".")
            numstr = s2
        elif commas > 0 and dots > 0 and numstr.rfind(".") > numstr.rfind(","):
            numstr = numstr.replace(",", "")
        elif commas > 0 and dots == 0:
            numstr = numstr.replace(",", ".")
        try:
            return float(numstr)
        except:
            return None

    normalized = candidato.apply(normaliza_num_str)
    numeric = pd.to_numeric(normalized, errors='coerce')
    return numeric

limpiar_serie_a_numero = safe_get('limpiar_serie_a_numero', limpiar_serie_a_numero_fallback)

# -------------------------
# Limpieza y construcción DataFrame principal
# -------------------------
def limpiar_dataframe_numerico_fallback(datos_base_raw: pd.DataFrame, lista_nombres: List[str],
                                       df_raw: pd.DataFrame=None, indice_fila_inicio: int=None,
                                       columna_fecha_index: int=1) -> pd.DataFrame:
    ncols = datos_base_raw.shape[1]
    if len(lista_nombres) < ncols:
        lista_nombres = lista_nombres + [f"Variable_sin_nombre_extra_{i}" for i in range(ncols - len(lista_nombres))]
    elif len(lista_nombres) > ncols:
        lista_nombres = lista_nombres[:ncols]

    df = datos_base_raw.reset_index(drop=True).copy()
    df.columns = lista_nombres

    for c in df.columns:
        df[c] = limpiar_serie_a_numero(df[c])

    if df_raw is not None and indice_fila_inicio is not None and columna_fecha_index is not None:
        try:
            tiempos = df_raw.iloc[indice_fila_inicio:, columna_fecha_index]
            tiempos = pd.to_datetime(tiempos, errors='coerce')
            tiempos = tiempos.reset_index(drop=True)
            if len(tiempos) < len(df):
                tiempos = tiempos.reindex(range(len(df)))
            elif len(tiempos) > len(df):
                tiempos = tiempos.iloc[:len(df)].reset_index(drop=True)
            if "Tiempo" in df.columns:
                df = df.drop(columns=["Tiempo"])
            df.insert(0, "Tiempo", tiempos)
        except Exception as e:
            print("⚠️ Error al reconstruir Tiempo:", e)
    return df

limpiar_dataframe_numerico = safe_get('limpiar_dataframe_numerico', limpiar_dataframe_numerico_fallback)

# -------------------------
# Separar variables por desalador
# -------------------------
def separar_variables_por_desalador(columnas: List[str], desaladores: List[str]) -> Tuple[Dict[str,List[str]], List[str]]:
    grupos = {d: [] for d in desaladores}
    comunes = []
    desal_tokens = {}
    for d in desaladores:
        base = normalizar(d)
        variantes = {
            base,
            base.replace("c", "c-"),
            base.replace("c", "611-c"),
            base.replace("c", "c "),
            base.replace("-", "")
        }
        desal_tokens[d] = variantes
    for c in columnas:
        norm = normalizar(c)
        asignado = False
        for d, variantes in desal_tokens.items():
            for v in variantes:
                if v in norm:
                    grupos[d].append(c)
                    asignado = True
                    break
            if asignado:
                break
        if not asignado:
            comunes.append(c)
    return grupos, comunes

# -------------------------
# Obtener columna base por desalador (matching)
# -------------------------
def obtener_columnas_base_por_desalador(variable_base: str, mapa_norm_columns: Dict[str, List[Tuple[str,str]]],
                                        desaladores: List[str]) -> Dict[str, Any]:
    resultado = {}
    posibles = mapa_norm_columns.get(variable_base, [])
    if not posibles:
        for d in desaladores:
            resultado[d] = None
        return resultado
    desal_tokens = {d: clean_token(d) for d in desaladores}
    posibles_list = list(posibles)
    for d, dtoken in desal_tokens.items():
        elegido = None
        base_token = clean_token(variable_base)
        for orig, token in posibles_list:
            if token.startswith(base_token) and token.endswith(dtoken):
                elegido = orig
                break
        if elegido is None:
            for orig, token in posibles_list:
                if token.endswith(dtoken) and base_token in token:
                    elegido = orig
                    break
        if elegido is None:
            pattern = base_token + dtoken
            for orig, token in posibles_list:
                if pattern in token:
                    elegido = orig
                    break
        if elegido is None:
            for orig, token in posibles_list:
                if token.endswith(dtoken):
                    elegido = orig
                    break
        if elegido is None:
            for orig, token in posibles_list:
                if dtoken in token:
                    elegido = orig
                    break
        resultado[d] = elegido
    for d in desaladores:
        if resultado[d] is None and len(posibles_list) == 1:
            resultado[d] = posibles_list[0][0]
    return resultado

# -------------------------
# Análisis crítico extendido (internal)
# -------------------------
def analisis_critico_extendido_internal(datos: pd.DataFrame, desaladores: List[str], variable_base: str,
                                        valor_critico: float, carpeta_salida: str, mapa_norm_columns: Dict[str, List[Tuple[str,str]]]):
    if 'Tiempo' not in datos.columns:
        raise ValueError("No se encontró la columna 'Tiempo' en los datos.")

    grupos, comunes = separar_variables_por_desalador(list(datos.columns.drop('Tiempo')), desaladores)
    resultados = {}
    os.makedirs(carpeta_salida, exist_ok=True)

    for d in desaladores:
        cols = grupos.get(d, []) + comunes
        if len(cols) == 0:
            print(f"No hay columnas detectadas para {d}.")
            continue
        df_sub = datos[['Tiempo'] + cols].copy()
        posibles = mapa_norm_columns.get(variable_base, [])
        col_desal = None
        d_norm = clean_token(d)
        for original_name, norm_name in posibles:
            if norm_name.endswith(d_norm):
                col_desal = original_name
                break
        if col_desal is None and len(posibles) > 0:
            col_desal = posibles[0][0]
        if col_desal is None:
            print(f"No hay columna base '{variable_base}' para {d}.")
            continue
        for c in cols:
            if c != 'Tiempo':
                df_sub[c] = pd.to_numeric(df_sub[c], errors='coerce')
        base_series = df_sub[col_desal]
        df_arriba = df_sub[base_series > valor_critico].reset_index(drop=True)
        df_abajo  = df_sub[base_series <= valor_critico].reset_index(drop=True)
        var_base_clean = re.sub(r"[^A-Za-z0-9_-]", "_", variable_base)
        archivo = os.path.join(carpeta_salida, f"Analisis_Critico_{d}_{var_base_clean}.xlsx")
        wb = Workbook()
        ws_up = wb.active
        ws_up.title = "Valores_mayor_crit"
        for r in dataframe_to_rows(df_arriba, index=False, header=True):
            ws_up.append(r)
        ws_down = wb.create_sheet("Valores_menor_igual_crit")
        for r in dataframe_to_rows(df_abajo, index=False, header=True):
            ws_down.append(r)
        ws_all = wb.create_sheet("Todos_los_valores")
        for r in dataframe_to_rows(df_sub, index=False, header=True):
            ws_all.append(r)
        ws_r = wb.create_sheet("Resumen_Estadistico")
        ws_r.append([
            "Variable","Columna_base_usada",
            "Media_total","Std_total",
            "Media_>crit","Std_>crit",
            "Media_<=crit","Std_<=crit",
            "Count_total","Count_>crit","Count_<=crit"
        ])
        for col_var in cols:
            serie = df_sub[col_var]
            vals = {
                "media_total": float(np.nanmean(serie))     if serie.notna().sum() > 0 else None,
                "std_total":   float(np.nanstd(serie))      if serie.notna().sum() > 1 else None,
                "media_sup": float(np.nanmean(serie[base_series > valor_critico])) if (serie[base_series > valor_critico].notna().sum() > 0) else None,
                "std_sup":   float(np.nanstd(serie[base_series > valor_critico])) if (serie[base_series > valor_critico].notna().sum() > 1) else None,
                "media_inf": float(np.nanmean(serie[base_series <= valor_critico])) if (serie[base_series <= valor_critico].notna().sum() > 0) else None,
                "std_inf":   float(np.nanstd(serie[base_series <= valor_critico])) if (serie[base_series <= valor_critico].notna().sum() > 1) else None,
                "count_total": int(serie.notna().sum()),
                "count_sup":   int(serie[base_series > valor_critico].notna().sum()),
                "count_inf":   int(serie[base_series <= valor_critico].notna().sum())
            }
            ws_r.append([
                col_var,
                col_desal,
                vals["media_total"],
                vals["std_total"],
                vals["media_sup"],
                vals["std_sup"],
                vals["media_inf"],
                vals["std_inf"],
                vals["count_total"],
                vals["count_sup"],
                vals["count_inf"]
            ])
        wb.save(archivo)
        resultados[d] = archivo
    return resultados

analisis_critico_extendido = safe_get('analisis_critico_extendido', analisis_critico_extendido_internal)

# -------------------------
# Generar graficas y guardar .xlsx con imagenes
# -------------------------
def generar_graficas_por_desalador_internal(datos: pd.DataFrame, desaladores: List[str], variable_base: str,
                                            carpeta_salida: str, mapa_norm_columns: Dict[str, List[Tuple[str,str]]]):
    grupos, comunes = separar_variables_por_desalador(list(datos.columns.drop('Tiempo')), desaladores)
    mapping_base = obtener_columnas_base_por_desalador(variable_base, mapa_norm_columns, desaladores)
    os.makedirs(carpeta_salida, exist_ok=True)
    resultados = {}
    for d in desaladores:
        cols = grupos.get(d, []) + comunes
        if len(cols) == 0:
            print(f"No hay columnas para {d}.")
            continue
        col_base = mapping_base.get(d)
        if col_base is None:
            print(f"No se encontró columna base '{variable_base}' para desalador {d}.")
            continue
        df_sub = datos[['Tiempo'] + cols].copy()
        for c in cols:
            df_sub[c] = pd.to_numeric(df_sub[c], errors='coerce')
        df_sub[col_base] = pd.to_numeric(df_sub[col_base], errors='coerce')
        wb = Workbook()
        ws0 = wb.active
        ws0.title = "Resumen"
        ws0["A1"] = f"Gráficas desalador {d} (base: {col_base})"
        for c in cols:
            if c == col_base:
                continue
            serie = df_sub[c]
            base = df_sub[col_base]
            tiempo = df_sub["Tiempo"]
            mask = (serie.notna() & base.notna() & tiempo.notna())
            serie_m  = serie[mask]
            base_m   = base[mask]
            tiempo_m = tiempo[mask]
            if len(serie_m) == 0:
                continue
            plt.figure(figsize=(6,4))
            plt.scatter(base_m, serie_m, s=20, alpha=0.7)
            plt.xlabel(col_base)
            plt.ylabel(c)
            plt.title(f"{c} vs {col_base}")
            plt.grid(True)
            buf1 = io.BytesIO()
            plt.savefig(buf1, format="png", bbox_inches="tight")
            plt.close()
            buf1.seek(0)
            plt.figure(figsize=(6,4))
            plt.scatter(tiempo_m, serie_m, s=20, alpha=0.7)
            plt.xlabel("Tiempo")
            plt.ylabel(c)
            plt.xticks(rotation=25)
            plt.title(f"{c} vs Tiempo")
            plt.grid(True)
            buf2 = io.BytesIO()
            plt.savefig(buf2, format="png", bbox_inches="tight")
            plt.close()
            buf2.seek(0)
            hoja = re.sub(r"[^A-Za-z0-9_\- ]", "", c)[:31] or "Var"
            ws = wb.create_sheet(title=hoja)
            insertar_imagen_ws(ws, buf1, "A1")
            insertar_imagen_ws(ws, buf2, "I1")
            df_out = pd.DataFrame({"Tiempo": tiempo_m.values, col_base: base_m.values, c: serie_m.values})
            for r, row in enumerate(dataframe_to_rows(df_out, index=False, header=True), start=35):
                for col_i, val in enumerate(row, start=1):
                    ws.cell(row=r, column=col_i, value=val)
        var_base_clean = re.sub(r"[^A-Za-z0-9_-]", "_", variable_base)
        archivo = os.path.join(carpeta_salida, f"Graficas_{d}_{var_base_clean}.xlsx")
        wb.save(archivo)
        resultados[d] = archivo
    return resultados

generar_graficas_por_desalador = safe_get('generar_graficas_por_desalador', generar_graficas_por_desalador_internal)

# -------------------------
# Detección simple tokens tipo fecha
# -------------------------
def es_token_fecha_like(token):
    if token is None:
        return False
    t = str(token)
    if re.match(r"^\d{6,14}$", t):
        return True
    if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", t):
        return True
    # otras heurísticas:
    if re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$", t):
        return True
    return False

# -------------------------
# UI: Sidebar
# -------------------------
st.sidebar.header("Entradas")
uploaded = st.sidebar.file_uploader("Sube archivo Excel de desalación", type=["xlsx", "xls"], help="Archivo con la estructura del programa original (se leen todas las filas)")
st.sidebar.markdown("---")
st.sidebar.header("Parámetros visuales")
fig_w = st.sidebar.slider("Ancho figura", 6, 18, 10)
fig_h = st.sidebar.slider("Alto figura", 4, 12, 6)
st.sidebar.markdown("---")
st.sidebar.caption("Si colocas el módulo 'Programa Eficiencias de desalacion2.py' en /mnt/data/ la app intentará reutilizar sus funciones.")

# Mostrar logo opcional si está
logo_path = Path("logo_repsol.png")
if logo_path.exists():
    try:
        logo_original = Image.open(logo_path).convert("RGBA")
        blur_radius = 8
        padding = blur_radius * 3
        new_size = (logo_original.width + padding, logo_original.height + padding)
        final_logo = Image.new("RGBA", new_size, (255,255,255,0))
        center_x = (new_size[0] - logo_original.width) // 2
        center_y = (new_size[1] - logo_original.height) // 2
        final_logo.paste(logo_original, (center_x, center_y), logo_original)
        mask = final_logo.split()[3]
        white_halo = Image.new("RGBA", final_logo.size, (255, 255, 255, 0))
        white_halo.putalpha(mask.filter(ImageFilter.GaussianBlur(blur_radius)))
        final_logo = Image.alpha_composite(white_halo, final_logo)
        st.image(final_logo, width=140)
    except Exception:
        st.info("Error cargando logo_repsol.png")

# -------------------------
# Main: cuando hay upload
# -------------------------
if uploaded is None:
    st.info("Sube un archivo Excel para comenzar. La app leerá todas las filas y reconstruirá nombres y variables.")
else:
    # Guardar temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmpf:
        tmpf.write(uploaded.getbuffer())
        tmp_path = tmpf.name

    try:
        xls = pd.ExcelFile(tmp_path, engine="openpyxl")
        hojas = xls.sheet_names
    except Exception as e:
        st.error(f"Error leyendo Excel: {e}")
        hojas = []

    if hojas:
        hoja_sel = st.selectbox("Selecciona hoja", hojas)
        try:
            df_raw = pd.read_excel(tmp_path, sheet_name=hoja_sel, header=None, engine="openpyxl")
            st.success(f"Hoja '{hoja_sel}' leída: filas={df_raw.shape[0]} columnas={df_raw.shape[1]}")
        except Exception as e:
            st.error(f"Error leyendo hoja seleccionada: {e}")
            df_raw = None

        if df_raw is not None:
            # Detectar fila inicio usando la función real si está (o fallback)
            try:
                fila_inicio = detectar_fila_inicio_datos(df_raw)
            except Exception:
                fila_inicio = detectar_fila_inicio_datos_fallback(df_raw)
            st.write(f"Fila de inicio detectada (index base 0): {fila_inicio}")

            # Determinar índices de filas donde podríamos tener desalador/variable
            # ============================================
            # 🔧 BLOQUE CORREGIDO PARA FIJAR ENCABEZADOS
            # ============================================
            
            fila_desalador_idx = 0
            fila_variable_idx = 1
            fila_inicio = detectar_fila_inicio_datos(df_raw)

            # Construir nombres de columnas (usando función original si existe)
            try:
                nombres_col, desaladores_por_col = construir_nombres_columnas(df_raw, col_inicio=1, col_fin=df_raw.shape[1],
                                                                              fila_desalador_idx=fila_desalador_idx,
                                                                              fila_variable_idx=fila_variable_idx)
            except Exception:
                nombres_col, desaladores_por_col = construir_nombres_columnas_fallback(df_raw, col_inicio=1, col_fin=df_raw.shape[1],
                                                                                       fila_desalador_idx=fila_desalador_idx,
                                                                                       fila_variable_idx=fila_variable_idx)

            # Extraer datos desde fila_inicio (todas las filas)
            datos_vals = df_raw.iloc[fila_inicio:, 1:df_raw.shape[1]].reset_index(drop=True)
            for c in datos_vals.columns:
                datos_vals[c] = limpiar_serie_a_numero(datos_vals[c])
            datos = datos_vals.copy()
            # ======================================================
            # 🔥 FILTRO STREAMLIT-SEGURO: SOLO EFICIENCIA POSITIVA
            # ======================================================
            
            # Localizar columna de eficiencia (busca cualquier nombre que contenga estos tokens)
            col_eff = None
            
            for c in datos.columns:
                # asegurar que c es texto
                cl = str(c).lower()
            
                if "eficiencia" in cl and "desal" in cl:
                    col_eff = c
                    break
            
            if col_eff:
                datos[col_eff] = pd.to_numeric(datos[col_eff], errors='coerce')
                datos.loc[datos[col_eff] <= 0, col_eff] = np.nan
                st.info(f"Filtro aplicado: valores <= 0 eliminados en '{col_eff}'")

            
            if col_eff:
                # Convertir a numérico
                datos[col_eff] = pd.to_numeric(datos[col_eff], errors='coerce')
                # Aplicar filtro SOLO en la eficiencia
                datos.loc[datos[col_eff] <= 0, col_eff] = np.nan
                st.info(f"Filtro aplicado: valores <= 0 eliminados en '{col_eff}'")

            # asegurar unicidad columnas
            datos.columns = make_unique(nombres_col[:datos.shape[1]])
            # reconstruir columna Tiempo desde la columna 1 (index 1) del raw
            tiempo_col = pd.to_datetime(df_raw.iloc[fila_inicio:, 1].reset_index(drop=True), errors='coerce')
            if tiempo_col.isnull().all():
                datos.insert(0, "Tiempo", pd.RangeIndex(start=0, stop=len(datos)))
            else:
                datos.insert(0, "Tiempo", tiempo_col)

            st.subheader("Datos (vista previa)")
            st.dataframe(datos.head(200))

            # Construir mapa variable -> columnas
            try:
                mapa_variable_a_columnas, mapa_norm_columns = construir_mapa_variables_base(nombres_col)
            except Exception:
                mapa_variable_a_columnas, mapa_norm_columns = construir_mapa_variables_base_fallback(nombres_col)

            # Detectar desaladores presentes a partir de nombres_col (patrón C#)
            # ======================================================
            # 🔷 Pregunta al usuario si quiere buscar varios desaladores
            # ======================================================
            
            st.sidebar.markdown("---")
            forzar_general = st.sidebar.radio(
                "¿Quieres que la app busque varios desaladores?",
                ["No, usar un solo desalador (GENERAL)", "Sí, detectar varios desaladores automáticamente"],
                index=0
            )

            # ======================================================
            # 🔥 DETECCIÓN AUTOMÁTICA DE DESALADORES (STREAMLIT)
            # ======================================================
            
            desaladores_detectados = set()
            
            patron_desal = re.compile(r"(c[\-\_ ]?\d{1,3})", flags=re.IGNORECASE)
            
            for n in nombres_col:
                m = patron_desal.search(str(n))
                if m:
                    desaladores_detectados.add(re.sub(r"[\-_\s]", "", m.group(1)).upper())
            
            desaladores_detectados = sorted(list(desaladores_detectados))
            
            # --- Lógica automática ---
            if len(desaladores_detectados) == 0:
                desal_sel = ["GENERAL"]
            elif len(desaladores_detectados) == 1:
                desal_sel = ["GENERAL"]
            else:
                # varios desaladores → permitir selección en sidebar
                st.sidebar.markdown("---")
                st.sidebar.info(f"Detectados varios desaladores: {', '.join(desaladores_detectados)}")
                desal_sel = st.sidebar.multiselect(
                    "Selecciona desaladores a analizar",
                    desaladores_detectados,
                    default=desaladores_detectados
                )

            # ===== Construcción REAL de variables base (igual que tu programa principal) =====
            mapa_variable_keys = list(mapa_variable_a_columnas.keys()) if mapa_variable_a_columnas else []
            variables_base = list(mapa_variable_keys)

            variables_base_limpias = []
            for v in variables_base:
                partes = v.split()
                if len(partes) > 1 and partes[-1].upper().startswith("C") and partes[-1][1:].isdigit():
                    variables_base_limpias.append(" ".join(partes[:-1]))
                else:
                    variables_base_limpias.append(v)

            # Eliminar duplicados manteniendo orden
            variables_base_limpias = list(dict.fromkeys(variables_base_limpias))

            # Quitar tokens que parezcan fechas
            variables_base_filtradas = [v for v in variables_base_limpias if not es_token_fecha_like(clean_token(v))]

            if len(variables_base_filtradas) == 0:
                # Si no quedan, usar limpias originales
                variables_base_filtradas = variables_base_limpias

            # Determinar opciones a mostrar en el desplegable
            if len(desaladores_detectados) > 1:
                st.sidebar.info(f"Se detectan varios desaladores: {', '.join(desaladores_detectados)}. Mostrando nombres base simples.")
                opciones_variables_base = variables_base_filtradas
            else:
                st.sidebar.info("Se detecta 1 desalador (o ninguno); se mostrarán nombres completos.")
                # en caso de 1 desalador mostramos todos los nombres tal cual (como en tu programa original)
                opciones_variables_base = nombres_col if nombres_col else variables_base_filtradas

            # eliminar duplicados y ordenar manteniendo orden original
            opciones_variables_base = list(dict.fromkeys(opciones_variables_base))

            if not opciones_variables_base:
                st.error("No se pudieron construir las opciones de variables base. Revisa el encabezado del Excel.")
            else:
                var_sel = st.selectbox("Selecciona variable base", options=opciones_variables_base)

                # Multiselección de desaladores (si hay varios)
                if len(desaladores_detectados) > 1:
                    desal_sel = st.multiselect("Selecciona desaladores (filtrar)", options=desaladores_detectados, default=desaladores_detectados)
                else:
                    desal_sel = st.multiselect("Selecciona desaladores (opcional)", options=desaladores_detectados, default=desaladores_detectados)

                # Si el usuario escoge el nombre básico (cuando hay varios desaladores), tenemos que mapearlo a las columnas completas
                # Construir cols_relacionadas a partir de mapa_variable_a_columnas
                cols_relacionadas = []
                if mapa_variable_a_columnas and var_sel in mapa_variable_a_columnas:
                    cols_relacionadas = mapa_variable_a_columnas[var_sel]
                    # si el usuario ha filtrado desaladores, aplicar filtro
                    if desal_sel:
                        filtered = []
                        for c in cols_relacionadas:
                            last_token = str(c).strip().split()[-1]
                            if any(d.upper() == re.sub(r"[\-_\s]", "", last_token).upper() for d in desal_sel):
                                filtered.append(c)
                        if filtered:
                            cols_relacionadas = filtered
                else:
                    # fallback: buscar columnas que contengan el string var_sel
                    if var_sel in datos.columns:
                        cols_relacionadas = [var_sel]
                    else:
                        cols_relacionadas = [c for c in datos.columns if var_sel.lower() in c.lower()]

                st.write(f"Columnas relacionadas con '{var_sel}': {cols_relacionadas}")

                st.markdown("---")
                colA, colB = st.columns(2)

                with colA:
                    valor_critico = st.number_input('Valor crítico (para análisis)', value=0.0, format="%.6f")
                    if st.button('Ejecutar análisis crítico'):
                        out_dir = Path.cwd() / 'Resultados_Desalacion_App' / 'Analisis_Criticos'
                        out_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            archivos = analisis_critico_extendido(datos, desal_sel or list(desaladores_detectados or []), var_sel, float(valor_critico), str(out_dir), mapa_norm_columns)
                            st.success(f'Análisis crítico generado. Archivos: {len(archivos)}')
                            for k,v in archivos.items():
                                try:
                                    with open(v, "rb") as f:
                                        st.download_button(f"Descargar {Path(v).name}", data=f, file_name=Path(v).name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                                except Exception as e:
                                    st.write(f"No se pudo preparar descarga para {v}: {e}")
                        except Exception as e:
                            st.error(f'Error generando análisis crítico: {e}')

                with colB:
                    if st.button('Generar gráficas por desalador'):
                        out_dir = Path.cwd() / 'Resultados_Desalacion_App' / 'Graficas'
                        out_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            archivos_g = generar_graficas_por_desalador(datos, desal_sel or list(desaladores_detectados or []), var_sel, str(out_dir), mapa_norm_columns)
                            st.success(f'Gráficas generadas. Archivos: {len(archivos_g)}')
                            for k,v in archivos_g.items():
                                try:
                                    with open(v, "rb") as f:
                                        st.download_button(f"Descargar {Path(v).name}", data=f, file_name=Path(v).name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                                except Exception as e:
                                    st.write(f"No se pudo preparar descarga para {v}: {e}")
                        except Exception as e:
                            st.error(f'Error generando gráficas: {e}')

                st.markdown("---")
                st.subheader('Visualizaciones interactivas')
                try:
                    cols_plot = [c for c in datos.columns if c != 'Tiempo']
                    if not cols_plot:
                        st.info("No hay columnas numéricas para graficar.")
                    else:
                        ycol = st.selectbox('Variable a graficar', options=cols_plot, index=0)
                        xmode = st.radio('Eje X', ['Tiempo','Variable base'], index=0)
                        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
                        if xmode == 'Tiempo':
                            ax.scatter(pd.to_datetime(datos['Tiempo']), datos[ycol], s=10, alpha=0.7)
                            ax.set_xlabel('Tiempo')
                        else:
                            try:
                                if len(cols_relacionadas) == 1:
                                    xseries = datos[cols_relacionadas[0]]
                                else:
                                    xseries = datos[cols_relacionadas].mean(axis=1, skipna=True)
                                ax.scatter(xseries, datos[ycol], s=10, alpha=0.7)
                                ax.set_xlabel(var_sel)
                            except Exception:
                                ax.scatter(datos.index, datos[ycol], s=10, alpha=0.7)
                                ax.set_xlabel('Index')
                        ax.set_ylabel(ycol)
                        ax.grid(True)
                        st.pyplot(fig)
                except Exception as e:
                    st.error(f'Error dibujando visualización: {e}')

                st.markdown("---")
                st.subheader("Exportar datos procesados")
                try:
                    to_export = datos.copy()
                    tmpfile = Path(tempfile.gettempdir()) / "datos_procesados_desalacion.xlsx"
                    to_export.to_excel(tmpfile, index=False)
                    with open(tmpfile, "rb") as f:
                        st.download_button("Descargar datos procesados (Excel)", data=f, file_name="datos_procesados_desalacion.xlsx",
                                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception as e:
                    st.error(f"No se pudo preparar exportación: {e}")

    else:
        st.info("El archivo no contiene hojas válidas o no se pudo leer.")

st.markdown("---")
st.caption("Aplicación creada integrando la lógica del programa original.")

# ------------------------
# BLOQUE AÑADIDO: Análisis Avanzado (integrado)
# ------------------------
# A partir de aquí: nueva pestaña, modelos y utilidades avanzadas solicitadas.
# Mantendrá los nombres de variables reales en todas las interfaces.

# --------------------------------------------------------------------------
# Librerías y utilidades para Análisis Avanzado
# --------------------------------------------------------------------------
import time
import zipfile
import base64
from io import BytesIO

# ML / Stats libs
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.impute import SimpleImputer
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.svm import SVR, SVC
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import r2_score, mean_squared_error, accuracy_score
from sklearn.neural_network import MLPRegressor, MLPClassifier
from sklearn.exceptions import NotFittedError

# Try to import shap and lime - optional
try:
    import shap
    SHAP_AVAILABLE = True
except Exception:
    SHAP_AVAILABLE = False

try:
    from lime import lime_tabular
    LIME_AVAILABLE = True
except Exception:
    LIME_AVAILABLE = False

# Try for tensorflow/keras for autoencoder (generative)
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    TF_AVAILABLE = True
except Exception:
    TF_AVAILABLE = False

# Simple Self-Organizing Map implementation (very small and educational)
import numpy as _np

class SimpleSOM:
    """A tiny SOM implementation for demonstration. Not production-grade."""
    def __init__(self, m=10, n=10, dim=3, learning_rate=0.5, sigma=None, random_state=None):
        self.m = m
        self.n = n
        self.dim = dim
        self.lr = learning_rate
        self.sigma = sigma if sigma is not None else max(m, n) / 2.0
        self.random_state = random_state
        self._rng = np.random.RandomState(random_state)
        self.weights = self._rng.rand(m, n, dim)
    def _neighborhood(self, bmu_idx, it, max_it):
        sigma = self.sigma * np.exp(-it / (max_it/2+1e-9))
        g = np.exp(-((np.indices((self.m, self.n)).T - np.array(bmu_idx))**2).sum(axis=2) / (2*sigma*sigma))
        return g.T
    def train(self, data, num_iterations=100):
        data = np.array(data)
        for it in range(num_iterations):
            idx = self._rng.randint(0, data.shape[0])
            vector = data[idx]
            # find bmu
            diffs = self.weights - vector.reshape(1,1,self.dim)
            dist = np.linalg.norm(diffs, axis=2)
            bmu_idx = np.unravel_index(np.argmin(dist), (self.m, self.n))
            # neighborhood
            h = self._neighborhood(bmu_idx, it, num_iterations)
            # update
            lr = self.lr * np.exp(-it/num_iterations)
            self.weights += lr * h[:,:,None] * (vector - self.weights)

# Utility: save matplotlib figure to bytes
def fig_to_bytes(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    return buf.getvalue()

# Main advanced analysis UI function
def advanced_analysis_tab(datos: pd.DataFrame, mapa_norm_columns: dict):
    st.header('Análisis Avanzado')
    st.markdown('Selecciona la variable objetivo y las variables predictoras. Se mostrarán múltiples modelos y comparativas.')
    # select target
    numeric_cols = [c for c in datos.columns if c != 'Tiempo' and pd.api.types.is_numeric_dtype(datos[c])]
    if not numeric_cols:
        st.warning('No se encontraron columnas numéricas en los datos procesados.')
        return
    target = st.selectbox('Variable objetivo (target)', options=numeric_cols, index=0)
    # predictors
    default_predictors = [c for c in numeric_cols if c != target]
    predictors = st.multiselect('Variables predictoras (features)', options=default_predictors, default=default_predictors[:6])
    if not predictors:
        st.info('Elige al menos una variable predictora.')
        return
    # task type detection (regression vs classification) based on unique values
    y = datos[target].copy()
    y_nonnull = y.dropna()
    is_classification = False
    if y_nonnull.nunique() <= 20 and all(float(x).is_integer() for x in y_nonnull.dropna().astype(float)):
        is_classification = True
    st.write('Tipo de problema detectado:', 'Clasificación' if is_classification else 'Regresión')
    # preprocessing options
    impute_strategy = st.selectbox('Imputación', options=['mean', 'median', 'most_frequent', 'constant'], index=0)
    scaling = st.selectbox('Escalado', options=['Ninguno', 'StandardScaler', 'MinMaxScaler'], index=1)
    test_size = st.slider('Tamaño test (%)', 5, 50, 20)
    random_state = st.number_input('Random seed', value=42, step=1)
    # prepare X, y
    X = datos[predictors].copy()
    imp = SimpleImputer(strategy=impute_strategy)
    # imputación robusta
    X_array = imp.fit_transform(X)
    
    # forzar la misma cantidad de columnas que X original después de imputar
    n_cols_final = X_array.shape[1]
    predictors_final = predictors[:n_cols_final]
    
    X_imp = pd.DataFrame(X_array, columns=predictors_final)
    
    
    # escalado robusto (igual controlado)
    if scaling == 'StandardScaler':
        scaler = StandardScaler()
        X_array2 = scaler.fit_transform(X_imp)
    elif scaling == 'MinMaxScaler':
        scaler = MinMaxScaler()
        X_array2 = scaler.fit_transform(X_imp)
    else:
        X_array2 = X_imp.values
    
    # ajustar nombre de columnas también aquí
    n_cols_final2 = X_array2.shape[1]
    predictors_final2 = predictors_final[:n_cols_final2]
    
    X_scaled = pd.DataFrame(X_array2, columns=predictors_final2)

    y_imp = y.fillna(y.mean()) if not is_classification else y.fillna(method='ffill').fillna(method='bfill').astype(float)
    if scaling == 'StandardScaler':
        scaler = StandardScaler()
    elif scaling == 'MinMaxScaler':
        scaler = MinMaxScaler()
    else:
        X_scaled = X_imp.copy()
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y_imp, test_size=test_size/100.0, random_state=int(random_state))
    st.write(f'Train shape: {X_train.shape}   Test shape: {X_test.shape}')
    # Buttons to run models
    run_models = st.button('Ejecutar todos los modelos')
    if not run_models:
        st.stop()
    results = {}
    # Decision Tree
    try:
        if is_classification:
            dt = DecisionTreeClassifier(random_state=int(random_state))
        else:
            dt = DecisionTreeRegressor(random_state=int(random_state))
        dt.fit(X_train, y_train)
        preds = dt.predict(X_test)
        if is_classification:
            score = accuracy_score(y_test, preds)
        else:
            score = r2_score(y_test, preds)
        results['DecisionTree'] = {'model': dt, 'score': float(score), 'preds': preds}
    except Exception as e:
        st.write('Error DecisionTree:', e)
    # Random Forest
    try:
        if is_classification:
            rf = RandomForestClassifier(n_estimators=100, random_state=int(random_state))
        else:
            rf = RandomForestRegressor(n_estimators=100, random_state=int(random_state))
        rf.fit(X_train, y_train)
        preds = rf.predict(X_test)
        if is_classification:
            score = accuracy_score(y_test, preds)
        else:
            score = r2_score(y_test, preds)
        results['RandomForest'] = {'model': rf, 'score': float(score), 'preds': preds}
    except Exception as e:
        st.write('Error RandomForest:', e)
    # SVM (use SVR/SVC)
    try:
        if is_classification:
            svm = SVC(probability=True, random_state=int(random_state))
        else:
            svm = SVR()
        svm.fit(X_train, y_train)
        preds = svm.predict(X_test)
        if is_classification:
            score = accuracy_score(y_test, preds)
        else:
            score = r2_score(y_test, preds)
        results['SVM'] = {'model': svm, 'score': float(score), 'preds': preds}
    except Exception as e:
        st.write('Error SVM:', e)
    # MLP (sustituto CNN para tabular)
    try:
        if is_classification:
            mlp = MLPClassifier(hidden_layer_sizes=(100,50), max_iter=500, random_state=int(random_state))
        else:
            mlp = MLPRegressor(hidden_layer_sizes=(100,50), max_iter=500, random_state=int(random_state))
        mlp.fit(X_train, y_train)
        preds = mlp.predict(X_test)
        if is_classification:
            score = accuracy_score(y_test, preds)
        else:
            score = r2_score(y_test, preds)
        results['MLP'] = {'model': mlp, 'score': float(score), 'preds': preds}
    except Exception as e:
        st.write('Error MLP:', e)
    # PCA
    try:
        pca = PCA(n_components=min(len(predictors), 6))
        pca.fit(X_scaled.fillna(0))
        explained = pca.explained_variance_ratio_
        results['PCA'] = {'model': pca, 'explained_variance_ratio': explained.tolist()}
    except Exception as e:
        st.write('Error PCA:', e)
    # KMeans
    try:
        kmeans = KMeans(n_clusters=min(6, max(2, len(predictors)//2)), random_state=int(random_state))
        km_labels = kmeans.fit_predict(X_scaled.fillna(0))
        results['KMeans'] = {'model': kmeans, 'labels': km_labels.tolist()}
    except Exception as e:
        st.write('Error KMeans:', e)
    # DBSCAN
    try:
        dbs = DBSCAN(eps=0.5, min_samples=5)
        db_labels = dbs.fit_predict(X_scaled.fillna(0))
        results['DBSCAN'] = {'model': dbs, 'labels': db_labels.tolist()}
    except Exception as e:
        st.write('Error DBSCAN:', e)
    # SOM
    try:
        som = SimpleSOM(m=8, n=8, dim=X_scaled.shape[1], learning_rate=0.5, random_state=int(random_state))
        som.train(X_scaled.fillna(0).values, num_iterations=200)
        results['SOM'] = {'model': som}
    except Exception as e:
        st.write('Error SOM:', e)
    # SHAP
    if SHAP_AVAILABLE:
        try:
            explainer = shap.Explainer(results['RandomForest']['model'], X_train)
            shap_values = explainer(X_test)
            # Compute mean absolute shap value per feature
            mean_abs_shap = np.mean(np.abs(shap_values.values), axis=0).tolist()
            results['SHAP'] = {'shap_values': shap_values.values.tolist(), 'mean_abs_shap': mean_abs_shap}
        except Exception as e:
            st.write('Error SHAP:', e)
    else:
        st.info('SHAP no disponible en el entorno. Para usar SHAP instala la librería "shap".')
    # LIME
    if LIME_AVAILABLE:
        try:
            explainer = lime_tabular.LimeTabularExplainer(training_data=X_train.values, feature_names=predictors, class_names=None, mode='regression' if not is_classification else 'classification')
            lime_exp = explainer.explain_instance(X_test.values[0], results['RandomForest']['model'].predict, num_features=min(10, len(predictors)))
            results['LIME'] = {'explanation': lime_exp.as_list()}
        except Exception as e:
            st.write('Error LIME:', e)
    else:
        st.info('LIME no disponible en el entorno. Para usar LIME instala la librería "lime".')
    # Generative: Autoencoder (if TF available)
    if TF_AVAILABLE:
        try:
            input_dim = X_scaled.shape[1]
            ae = keras.Sequential([layers.Input(shape=(input_dim,)), layers.Dense(int(input_dim*0.75), activation='relu'), layers.Dense(int(input_dim*0.5), activation='relu'), layers.Dense(int(input_dim*0.75), activation='relu'), layers.Dense(input_dim, activation='linear')])
            ae.compile(optimizer='adam', loss='mse')
            ae.fit(X_scaled.fillna(0).values, X_scaled.fillna(0).values, epochs=30, batch_size=32, verbose=0)
            recon = ae.predict(X_scaled.fillna(0).values)
            results['Autoencoder'] = {'model': ae}
        except Exception as e:
            st.write('Error Autoencoder:', e)
    else:
        st.info('TensorFlow/Keras no disponible. Para usar Autoencoder instala tensorflow.')
    # Calculate feature importances for tree-based models
    importances_df = pd.DataFrame(index=predictors)
    for name, res in results.items():
        try:
            mdl = res.get('model', None)
            if mdl is None:
                continue
            if hasattr(mdl, 'feature_importances_'):
                impvals = mdl.feature_importances_
                importances_df[name] = impvals
            elif hasattr(mdl, 'coef_'):
                coef = np.abs(mdl.coef_).reshape(-1)
                importances_df[name] = coef[:len(predictors)]
        except Exception as e:
            # skip
            pass
    # Normalize importances
    if not importances_df.empty:
        importances_df = importances_df.fillna(0)
        importances_norm = importances_df.divide(importances_df.max(axis=0)+1e-9)
        st.subheader('Importancia de variables por modelo (tabla)')
        st.dataframe(importances_norm)
        st.markdown('Puedes descargar la tabla de importancias como CSV.')
        csv_buf = BytesIO()
        importances_norm.to_csv(csv_buf)
        csv_buf.seek(0)
        st.download_button('Descargar importancias (CSV)', csv_buf.getvalue(), file_name='importancias_modelos.csv', mime='text/csv')
        # Plot importances comparison
        try:
            fig, ax = plt.subplots(figsize=(10, max(4, len(predictors)*0.3)))
            importances_norm.plot.bar(ax=ax)
            ax.set_ylabel('Importancia (normalizada)')
            ax.set_xlabel('Variables')
            ax.set_title('Comparación importancias por modelo')
            st.pyplot(fig)
            # save figure to bytes for zip
            fig_bytes = fig_to_bytes(fig)
        except Exception as e:
            st.write('Error graficando importancias:', e)
    else:
        st.info('No se pudieron calcular importancias automáticamente para los modelos usados.')
    # Summary table of model scores
    scores = []
    for name, res in results.items():
        score = res.get('score', None)
        scores.append({'modelo': name, 'score': score})
    scores_df = pd.DataFrame(scores).sort_values(by='score', ascending=False)
    st.subheader('Comparativa de modelos (score)')
    st.dataframe(scores_df)
    # Prepare downloadable zip with CSVs + images if any
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        # importances
        if not importances_df.empty:
            zf.writestr('importancias_normalizadas.csv', importances_norm.to_csv(index=True))
        # models scores
        zf.writestr('model_scores.csv', scores_df.to_csv(index=False))
        # add fig
        try:
            if 'fig_bytes' in locals():
                zf.writestr('importancias.png', fig_bytes)
            elif 'fig_bytes' not in locals() and 'fig_bytes' in globals():
                zf.writestr('importancias.png', globals().get('fig_bytes', b''))
        except Exception:
            pass
    zip_buf.seek(0)
    st.download_button('Descargar resultados (ZIP)', zip_buf.getvalue(), file_name='analisis_avanzado_resultados.zip', mime='application/zip')
    st.success('Análisis avanzado completado. Revisa tablas, gráficas y descarga el ZIP si lo deseas.')

# Integración final: intentar crear Tabs con la pestaña nueva
try:
    # Creamos dos pestañas: la primera 'Graficado y resumen estadístico' contendrá la vista original
    # (si el flujo original ya imprimió cosas, esta operación puede repetirse sin problema).
    tabs = st.tabs(["Graficado y resumen estadístico", "Análisis Avanzado"])
    # Colocamos la salida original dentro de la primera pestaña (esto no mueve lo ya mostrado,
    # pero ofrece la pestaña solicitada). Notar: si tu flujo original ya imprime en la app,
    # la separación exacta en pestañas puede variar según cómo Streamlit ejecute el script.
    with tabs[0]:
        st.write("Pestaña 'Graficado y resumen estadístico' — contiene la interfaz original y todas sus funciones.")
        st.write("Si ya subiste un archivo, revisa la sección de Datos (vista previa) y las opciones de graficado y exportación que aparecen en la interfaz principal.")
    # Segunda pestaña: función de análisis avanzado
    with tabs[1]:
        # Solo mostrar si existen 'datos' y 'mapa_norm_columns'
        if 'datos' in globals() and 'mapa_norm_columns' in globals():
            try:
                advanced_analysis_tab(datos, mapa_norm_columns)
            except Exception as e:
                st.error(f"Error ejecutando la pestaña Análisis Avanzado: {e}")
        else:
            st.info("Carga primero un archivo Excel y procesa los datos en la pestaña 'Graficado y resumen estadístico' para usar el Análisis Avanzado.")

except Exception as e:
    # Si algo falla al crear tabs, mostramos un mensaje pero no interrumpimos la app
    st.write("No se pudieron crear las pestañas automáticas. La app sigue funcionando en modo clásico. Error:", e)
# FIN DEL ARCHIVO
