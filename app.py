import datetime
import io
import os
import bs4
import pandas as pd
import requests
import sqlite3
import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="FISCAL APP - Gestión Financiera Local",
    page_icon="logo.jpg",
    layout="wide",
)

DB_NAME = "control_fiscal.db"


# --- INICIALIZACIÓN DE BASE DE DATOS LOCAL ---
def init_db():
  conn = sqlite3.connect(DB_NAME, check_same_thread=False)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT, banco TEXT, tipo TEXT, concepto TEXT, categoria TEXT,
            tasa_bcv REAL, deducible_islr TEXT, divisa TEXT, monto_original REAL,
            monto_ves REAL, monto_usd REAL, iva_ves REAL, igtf_ves REAL,
            monto_deducible_ves REAL, factura_ref TEXT, control TEXT
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion_licencia (
            id INTEGER PRIMARY KEY,
            licencia_key TEXT,
            activa INTEGER
        )
    """)
  cursor.execute(
      "INSERT OR IGNORE INTO configuracion_licencia (id, licencia_key, activa)"
      " VALUES (1, '', 0)"
  )
  conn.commit()
  return conn


conn = init_db()


# --- FUNCIONES DE SEGURIDAD Y LICENCIAMIENTO LOCAL ---
def verificar_licencia():
  cursor = conn.cursor()
  cursor.execute(
      "SELECT licencia_key, activa FROM configuracion_licencia WHERE id = 1"
  )
  res = cursor.fetchone()
  if res and res[1] == 1:
    return True, res[0]
  return False, ""


def activar_licencia_local(clave_ingresada):
  CLAVE_MAESTRA = "FISCAL-PRO-2026"
  if (
      clave_ingresada.strip().upper() == CLAVE_MAESTRA
      or clave_ingresada.endswith("-FISCAL2026")
  ):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE configuracion_licencia SET licencia_key = ?, activa = 1 WHERE"
        " id = 1",
        (clave_ingresada,),
    )
    conn.commit()
    return True
  return False


# --- CONTROL DE ACTIVACIÓN DE LA APP ---
licencia_valida, clave_actual = verificar_licencia()

if not licencia_valida:
  st.warning("🔒 **APLICACIÓN NO ACTIVADA**")
  st.info("Por favor, ingresa tu Clave de Licencia Local para activar FISCAL APP.")

  col_lic1, col_lic2 = st.columns([3, 1])
  with col_lic1:
    clave_input = st.text_input(
        "Clave de Producto / Licencia:", type="password"
    )
  with col_lic2:
    st.write(" ")
    st.write(" ")
    if st.button("Activar Licencia", type="primary"):
      if activar_licencia_local(clave_input):
        st.success("¡Licencia activada con éxito!")
        st.rerun()
      else:
        st.error("Clave de licencia inválida.")

  st.divider()
  st.caption(
      "Para adquirir una licencia o soporte técnico, contacta con el autor del"
      " software."
  )
  st.stop()


# --- CABECERA PRINCIPAL ---
col_logo, col_titulo = st.columns([1, 4])
with col_logo:
  try:
    st.image("logo.jpg", width=130)
  except Exception:
    st.title("🇻🇪")

with col_titulo:
  st.title("FISCAL APP")
  st.subheader('"Gestión Financiera y Control Fiscal Local"')

st.divider()


@st.cache_data(ttl=600)
def obtener_tasa_bcv_automatica():
  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    response = requests.get(
        "https://www.bcv.org.ve/", headers=headers, timeout=6, verify=False
    )
    if response.status_code == 200:
      soup = bs4.BeautifulSoup(response.text, "html.parser")
      div_dolar = soup.find("div", id="dolar")
      if div_dolar:
        texto_tasa = div_dolar.find("strong").text.strip()
        tasa_limpia = (
            texto_tasa.replace(".", "").replace(",", ".").strip()
        )
        return float(tasa_limpia)
  except Exception:
    pass
  return 36.50


requests.packages.urllib3.disable_warnings()

# --- BARRA LATERAL CON MÓDULO DE RESPALDOS (BACKUP) ---
st.sidebar.image("logo.jpg", use_container_width=True)
st.sidebar.header("⚙️ Configuración y Respaldos")

tasa_detectada = obtener_tasa_bcv_automatica()
tasa_bcv = st.sidebar.number_input(
    "Tasa BCV (Bs. / USD):",
    min_value=0.0,
    value=float(tasa_detectada),
    step=0.01,
    format="%.2f",
)

rif_usuario = st.sidebar.text_input("Tu RIF / Cédula:", value="J-12345678-9")
tipo_contribuyente = st.sidebar.selectbox(
    "Tipo de Contribuyente", ["Persona Natural", "Persona Jurídica"]
)

st.sidebar.divider()
st.sidebar.subheader("💾 Respaldos de Datos (Backup)")

if os.path.exists(DB_NAME):
  with open(DB_NAME, "rb") as db_file:
    st.sidebar.download_button(
        label="📦 Exportar Copia de Seguridad (.db)",
        data=db_file.read(),
        file_name=(
            f"backup_fiscal_{datetime.date.today().strftime('%Y_%m_%d')}.db"
        ),
        mime="application/x-sqlite3",
    )

archivo_backup = st.sidebar.file_uploader(
    "Restaurar Base de Datos (.db)", type=["db"]
)
if archivo_backup is not None:
  if st.sidebar.button("⚠️ Confirmar Restauración"):
    with open(DB_NAME, "wb") as f:
      f.write(archivo_backup.getbuffer())
    st.sidebar.success("¡Base de datos restaurada correctamente!")
    st.rerun()

pestanas = st.tabs([
    "📝 Registro Diario",
    "✏️ Gestionar Registros",
    "🏦 Conciliación Bancaria",
    "📊 Cierre y Reportes",
])

BANCOS_VENEZUELA = [
    "Banco de Venezuela (BDV)",
    "Banesco Banco Universal",
    "Banco Mercantil",
    "BBVA Provincial",
    "Banco Nacional de Crédito (BNC)",
    "Bancamiga",
    "Banplus",
    "Efectivo / Divisas en Mano",
]

# ---------------------------------------------------------
# PESTAÑA 1: REGISTRO DIARIO
# ---------------------------------------------------------
with pestanas[0]:
  st.subheader("Registrar Nuevo Movimiento")

  c_tipo, c_cat = st.columns(2)
  with c_tipo:
    tipo = st.selectbox("Tipo de Movimiento", ["Ingreso", "Gasto"])

  categorias = [
      "🛒 Alimentos / Supermercado / Comida",
      "🏥 Gastos Médicos y Odontológicos",
      "🏢 Alquiler de Local / Oficina",
      "💡 Servicios Públicos (Luz, Agua, Telecomunicaciones)",
      "👨‍💼 Honorarios Profesionales",
      "📣 Publicidad y Mercadeo",
      "📦 Inventario / Materia Prima",
      "🛠️ Mantenimiento y Reparaciones Generales",
      "🚗 Mantenimiento y Reparaciones de Vehículo",
      "👤 Gastos Personales (No Deducibles)",
      "🏦 Préstamos / Financiamiento",
      "📊 Otros Gastos / Ingresos Operativos",
  ]

  with c_cat:
    categoria = st.selectbox("Rubro / Categoría", categorias)

  cat_lower = categoria.lower()

  if tipo == "Ingreso":
    status_deducible = "No Aplica (Es un Ingreso)"
    es_deducible_bool = False
  else:
    if any(
        kw in cat_lower
        for kw in ["alimento", "comida", "personal", "préstamo", "prestamo"]
    ):
      status_deducible = "No Deducible (Gasto Personal o no vinculado)"
      es_deducible_bool = False
    elif any(kw in cat_lower for kw in ["médic", "medic", "odontol"]):
      if tipo_contribuyente == "Persona Natural":
        status_deducible = "Deducible (Vía Desgravamen de Salud)"
        es_deducible_bool = True
      else:
        status_deducible = (
            "No Deducible (Gasto médico personal para PJ no vinculado)"
        )
        es_deducible_bool = False
    else:
      status_deducible = "Deducible (Gasto Necesario - Art. 27 LISLR)"
      es_deducible_bool = True

  if es_deducible_bool:
    st.success(f"✅ **Criterio ISLR:** {status_deducible}")
  else:
    st.info(f"⚖️ **Criterio ISLR:** {status_deducible}")

  with st.form("form_transaccion", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
      # Selección de banco con opción personalizada integrada
      banco_opcion = st.selectbox(
          "🏦 Banco / Cuenta", BANCOS_VENEZUELA + ["Otro (Especificar)"]
      )
      if banco_opcion == "Otro (Especificar)":
        banco_seleccionado = st.text_input(
            "Escriba el nombre del Banco / Entidad:"
        )
        if not banco_seleccionado:
          banco_seleccionado = "Banco Personalizado"
      else:
        banco_seleccionado = banco_opcion

      divisa = st.selectbox("Moneda", ["USD", "VES"])
      monto = st.number_input(
          "Monto Total", min_value=0.0, step=0.01
      )
      fecha = st.date_input("Fecha", datetime.date.today())

    with col2:
      tasa_operacion = st.number_input(
          "Tasa BCV Operación:", min_value=0.0, value=tasa_bcv, step=0.01
      )
      concepto = st.text_input("Concepto / Descripción")
      nro_factura = st.text_input("N° Factura / Ref")
      nro_control = st.text_input("N° Control (SENIAT)")

    col3, col4 = st.columns(2)
    with col3:
      aplica_iva = st.selectbox("Aplica IVA", ["Exento (0%)", "General (16%)"])
    with col4:
      aplica_igtf = st.checkbox("¿Aplica IGTF (3%)?", value=False)

    submitted = st.form_submit_button("Guardar Movimiento")

    if submitted:
      monto_ves = monto if divisa == "VES" else monto * tasa_operacion
      monto_usd = monto / tasa_operacion if divisa == "VES" else monto
      iva_porcentaje = 0.16 if aplica_iva == "General (16%)" else 0.0
      base_imponible = monto_ves / (1 + iva_porcentaje)
      monto_iva = monto_ves - base_imponible
      igtf_monto = monto_ves * 0.03 if aplica_igtf else 0.0

      factor_deduccion = 0.75 if "vehículo" in cat_lower else 1.0
      monto_deducible_calculado = (
          (base_imponible if aplica_iva != "Exento (0%)" else monto_ves)
          * factor_deduccion
          if (es_deducible_bool and tipo == "Gasto")
          else 0.0
      )

      cursor = conn.cursor()
      cursor.execute(
          """
                INSERT INTO transacciones (fecha, banco, tipo, concepto, categoria, tasa_bcv, deducible_islr, divisa, monto_original, monto_ves, monto_usd, iva_ves, igtf_ves, monto_deducible_ves, factura_ref, control)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              str(fecha),
              banco_seleccionado,
              tipo,
              concepto if concepto else "Sin concepto",
              categoria,
              tasa_operacion,
              "Sí" if es_deducible_bool else "No",
              divisa,
              monto,
              round(monto_ves, 2),
              round(monto_usd, 2),
              round(monto_iva, 2),
              round(igtf_monto, 2),
              round(monto_deducible_calculado, 2),
              nro_factura,
              nro_control,
          ),
      )
      conn.commit()
      st.success("¡Movimiento registrado con éxito!")

# ---------------------------------------------------------
# PESTAÑA 2: GESTIONAR REGISTROS
# ---------------------------------------------------------
with pestanas[1]:
  st.subheader("Gestión y Edición de Registros")
  df_gestion = pd.read_sql("SELECT * FROM transacciones", conn)

  if df_gestion.empty:
    st.info("No hay transacciones registradas.")
  else:
    banco_filtro = st.selectbox(
        "Filtrar lista por Banco:", ["Todos"] + BANCOS_VENEZUELA
    )
    if banco_filtro != "Todos":
      df_gestion = df_gestion[df_gestion["banco"] == banco_filtro]

    st.dataframe(df_gestion, use_container_width=True)

# ---------------------------------------------------------
# PESTAÑA 3: CONCILIACIÓN BANCARIA
# ---------------------------------------------------------
with pestanas[2]:
  st.subheader("Conciliación Bancaria Local")
  st.caption(
      "Los archivos procesados permanecen en la memoria local de tu equipo."
  )

# ---------------------------------------------------------
# PESTAÑA 4: CIERRE Y REPORTES
# ---------------------------------------------------------
with pestanas[3]:
  st.subheader("Consolidado Fiscal y Cierre General")
  df = pd.read_sql("SELECT * FROM transacciones", conn)

  if not df.empty:
    total_ingresos = df[df["tipo"] == "Ingreso"]["monto_ves"].sum()
    total_gastos = df[df["tipo"] == "Gasto"]["monto_ves"].sum()
    total_deducible = df["monto_deducible_ves"].sum()
    enriquecimiento_neto = total_ingresos - total_deducible

    m1, m2 = st.columns(2)
    m1.metric("Total Ingresos", f"Bs. {total_ingresos:,.2f}")
    m2.metric("Gastos Deducibles", f"Bs. {total_deducible:,.2f}")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df.to_excel(writer, index=False, sheet_name="Cierre_Fiscal")
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Exportar Reporte en Excel (.xlsx)",
        data=excel_data,
        file_name=(
            f"cierre_fiscal_{datetime.date.today().strftime('%Y_%m')}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
