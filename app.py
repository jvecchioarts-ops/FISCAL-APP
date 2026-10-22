import datetime
import io
import bs4
import pandas as pd
import requests
import sqlite3
import streamlit as st

st.set_page_config(
    page_title="Control Fiscal Venezuela - Gastos e Ingresos", layout="wide"
)

st.title("🇻🇪 Control Financiero Multibanco y Base de Datos - Venezuela")
st.write(
    "Tus registros se guardan automáticamente de forma permanente. Gestiona ISLR, IVA, IGTF y conciliaciones."
)


# --- CONFIGURACIÓN DE LA BASE DE DATOS SQLITE ---
def init_db():
  conn = sqlite3.connect("control_fiscal.db", check_same_thread=False)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            banco TEXT,
            tipo TEXT,
            concepto TEXT,
            categoria TEXT,
            tasa_bcv REAL,
            deducible_islr TEXT,
            divisa TEXT,
            monto_original REAL,
            monto_ves REAL,
            monto_usd REAL,
            iva_ves REAL,
            igtf_ves REAL,
            monto_deducible_ves REAL,
            factura_ref TEXT,
            control TEXT
        )
    """)
  conn.commit()
  return conn


conn = init_db()


@st.cache_data(ttl=600)
def obtener_tasa_bcv_automatica():
  """Obtiene la tasa oficial actual del BCV con múltiples respaldos."""
  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
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

  try:
    r = requests.get("https://ve.dolarapi.com/v1/dolares/oficial", timeout=5)
    if r.status_code == 200:
      return float(r.json()["promedio"])
  except Exception:
    pass

  try:
    r = requests.get(
        "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?monitor=bcv",
        timeout=5,
    )
    if r.status_code == 200:
      return float(r.json()["monitors"]["bcv"]["price"])
  except Exception:
    pass

  return 36.50


requests.packages.urllib3.disable_warnings()

# Barra lateral informativa de referencia actual
st.sidebar.header("⚙️ Configuración Fiscal")
st.sidebar.markdown(
    "🔗 [Consultar Tasa Oficial en el BCV](https://www.bcv.org.ve/)",
    unsafe_allow_html=True,
)

tasa_detectada = obtener_tasa_bcv_automatica()
st.sidebar.metric(
    label="Tasa BCV del Día (Referencia)", value=f"Bs. {tasa_detectada:,.2f}"
)

rif_usuario = st.sidebar.text_input("Tu RIF / Cédula:", value="J-12345678-9")
tipo_contribuyente = st.sidebar.selectbox(
    "Tipo de Contribuyente", ["Persona Natural", "Persona Jurídica"]
)
porcentaje_vehiculo = st.sidebar.slider(
    "🚗 % Deducible para Mantenimiento de Vehículo", 0, 100, 75
)

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
    "Otro / Cuenta Internacional",
]

# ---------------------------------------------------------
# PESTAÑA 1: REGISTRO DIARIO (GUARDADO EN SQLITE)
# ---------------------------------------------------------
with pestanas[0]:
  st.subheader("Registrar Nuevo Movimiento")

  with st.form("form_transaccion", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
      banco_seleccionado = st.selectbox(
          "🏦 Banco / Cuenta de Origen o Destino", BANCOS_VENEZUELA
      )
      tipo = st.selectbox("Tipo de Movimiento", ["Ingreso", "Gasto"])
      divisa = st.selectbox("Moneda de la Operación", ["USD", "VES"])
      monto = st.number_input(
          "Monto Total de la Operación", min_value=0.0, step=0.01
      )
      fecha = st.date_input("Fecha de la Transacción", datetime.date.today())

      tasa_operacion = st.number_input(
          "Tasa BCV aplicada a esta operación:",
          min_value=0.0,
          value=tasa_detectada,
          step=0.01,
          help=(
              "Ajusta este valor si la transacción corresponde a una fecha"
              " anterior con otra tasa oficial."
          ),
      )

      concepto = st.text_input(
          "Concepto / Descripción",
          placeholder="Ej: Mercado semanal, Factura de proveedor, Almuerzo",
      )

    with col2:
      categorias = [
          "🛒 Alimentos / Supermercado / Comida",
          "🏥 Gastos Médicos y Odontológicos",
          "Alquiler de Local / Oficina",
          "Servicios Públicos (Luz, Agua, Telecomunicaciones)",
          "Honorarios Profesionales",
          "Publicidad y Mercadeo",
          "Inventario / Materia Prima",
          "Mantenimiento y Reparaciones Generales",
          "🚗 Mantenimiento y Reparaciones de Vehículo",
          "Gastos Personales (No Deducibles)",
          "Préstamos / Financiamiento",
          "Otros Gastos / Ingresos Operativos",
      ]
      categoria = st.selectbox("Rubro / Categoría", categorias)

      if "Médicos" in categoria and tipo_contribuyente == "Persona Natural":
        es_deducible_base = True
      elif "Alimentos" in categoria or "Personales" in categoria:
        es_deducible_base = False
      else:
        es_deducible_base = True if tipo == "Gasto" else False

      es_deducible = st.checkbox(
          "¿Es gasto deducible para el ISLR?", value=es_deducible_base
      )
      nro_factura = st.text_input("Número de Factura / Referencia")
      nro_control = st.text_input("Número de Control (SENIAT)")

    col3, col4 = st.columns(2)
    with col3:
      aplica_iva = st.selectbox("Aplica IVA", ["Exento (0%)", "General (16%)"])
    with col4:
      aplica_igtf = st.checkbox(
          "¿Aplica IGTF (3% por pago en divisas/efectivo)?", value=False
      )

    submitted = st.form_submit_button("Guardar Movimiento")

    if submitted:
      monto_ves = monto if divisa == "VES" else monto * tasa_operacion
      monto_usd = monto / tasa_operacion if divisa == "VES" else monto

      iva_porcentaje = 0.16 if aplica_iva == "General (16%)" else 0.0
      base_imponible = monto_ves / (1 + iva_porcentaje)
      monto_iva = monto_ves - base_imponible
      igtf_monto = monto_ves * 0.03 if aplica_igtf else 0.0

      factor_deduccion = (
          (porcentaje_vehiculo / 100.0) if "Vehículo" in categoria else 1.0
      )
      monto_deducible_calculado = (
          (base_imponible if aplica_iva != "Exento (0%)" else monto_ves)
          * factor_deduccion
          if (es_deducible and tipo == "Gasto")
          else 0.0
      )

      # Inserción directa en la base de datos SQLite
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
              "Sí" if es_deducible else "No",
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
      st.success("¡Movimiento guardado permanentemente en la base de datos!")

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

    st.divider()
    col_edit, col_del = st.columns(2)

    with col_del:
      st.write("### 🗑️ Eliminar Registro")
      ids_disponibles = df_gestion["id"].tolist()
      if ids_disponibles:
        id_a_eliminar = st.selectbox(
            "Selecciona el ID a eliminar:", ids_disponibles
        )
        confirmar_borrado = st.checkbox(
            f"⚠️ Confirmar eliminación permanente del ID #{id_a_eliminar}"
        )

        if st.button("🔴 Eliminar Registro", type="primary"):
          if confirmar_borrado:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM transacciones WHERE id = ?", (id_a_eliminar,)
            )
            conn.commit()
            st.success(f"Registro #{id_a_eliminar} eliminado.")
            st.rerun()
          else:
            st.warning("Marca la casilla de confirmación.")

    with col_edit:
      st.write("### ✏️ Modificar Registro")
      if ids_disponibles:
        id_a_editar = st.selectbox(
            "Selecciona el ID a modificar:", ids_disponibles, key="edit_select"
        )
        reg_actual = df_gestion[df_gestion["id"] == id_a_editar].iloc[0]

        nuevo_banco = st.selectbox(
            "Nuevo Banco:",
            BANCOS_VENEZUELA,
            index=BANCOS_VENEZUELA.index(reg_actual["banco"])
            if reg_actual["banco"] in BANCOS_VENEZUELA
            else 0,
        )
        nuevo_concepto = st.text_input(
            "Nuevo Concepto:", value=reg_actual["concepto"]
        )
        nuevo_monto = st.number_input(
            "Nuevo Monto:",
            value=float(reg_actual["monto_original"]),
            min_value=0.0,
        )
        nueva_tasa = st.number_input(
            "Tasa BCV:", value=float(reg_actual["tasa_bcv"]), min_value=0.0
        )

        confirmar_edicion = st.checkbox(
            f"⚠️ Confirmar cambios sobre ID #{id_a_editar}"
        )

        if st.button("🟢 Guardar Cambios"):
          if confirmar_edicion:
            monto_ves_nuevo = (
                nuevo_monto
                if reg_actual["divisa"] == "VES"
                else nuevo_monto * nueva_tasa
            )
            monto_usd_nuevo = (
                nuevo_monto / nueva_tasa
                if reg_actual["divisa"] == "VES"
                else nuevo_monto
            )

            cursor = conn.cursor()
            cursor.execute(
                """
                            UPDATE transacciones 
                            SET banco=?, concepto=?, monto_original=?, tasa_bcv=?, monto_ves=?, monto_usd=?
                            WHERE id=?
                        """,
                (
                    nuevo_banco,
                    nuevo_concepto,
                    nuevo_monto,
                    nueva_tasa,
                    round(monto_ves_nuevo, 2),
                    round(monto_usd_nuevo, 2),
                    id_a_editar,
                ),
            )
            conn.commit()
            st.success(f"Registro #{id_a_editar} actualizado.")
            st.rerun()
          else:
            st.warning("Marca la casilla de confirmación.")

# ---------------------------------------------------------
# PESTAÑA 3: CONCILIACIÓN BANCARIA
# ---------------------------------------------------------
with pestanas[2]:
  st.subheader("Conciliación Bancaria por Banco Específico")

  banco_conciliar = st.selectbox(
      "Selecciona el Banco a Conciliar:", BANCOS_VENEZUELA
  )
  archivo_banco = st.file_uploader(
      f"Cargar Estado de Cuenta de {banco_conciliar} (.xlsx, .csv)",
      type=["xlsx", "csv"],
  )

  if archivo_banco is not None:
    try:
      df_banco = (
          pd.read_csv(archivo_banco)
          if archivo_banco.name.endswith(".csv")
          else pd.read_excel(archivo_banco)
      )
      st.write(f"Estado de cuenta cargado de **{banco_conciliar}**:")
      st.dataframe(df_banco.head(), use_container_width=True)

      df_mis_regs = pd.read_sql("SELECT * FROM transacciones", conn)
      if not df_mis_regs.empty:
        df_mis_regs_banco = df_mis_regs[df_mis_regs["banco"] == banco_conciliar]
        st.divider()
        st.write(
            f"Tus registros guardados en la BD para **{banco_conciliar}**:"
        )
        st.dataframe(df_mis_regs_banco, use_container_width=True)
    except Exception as e:
      st.error(f"Error al leer el archivo: {e}")

# ---------------------------------------------------------
# PESTAÑA 4: CIERRE Y REPORTES
# ---------------------------------------------------------
with pestanas[3]:
  st.subheader("Consolidado Fiscal y Cierre General")
  df = pd.read_sql("SELECT * FROM transacciones", conn)

  if not df.empty:
    total_ingresos = df[df["tipo"] == "Ingreso"]["monto_ves"].sum()
    total_gastos = df[df["tipo"] == "Gasto"]["monto_ves"].sum()
    total_iva = df["iva_ves"].sum()
    total_deducible = df["monto_deducible_ves"].sum()
    enriquecimiento_neto = total_ingresos - total_deducible

    islr_estimado = 0.0
    if enriquecimiento_neto > 0:
      islr_estimado = (
          enriquecimiento_neto * 0.15
          if tipo_contribuyente == "Persona Jurídica"
          else enriquecimiento_neto * 0.06
      )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Ingresos", f"Bs. {total_ingresos:,.2f}")
    m2.metric("Gastos Deducibles", f"Bs. {total_deducible:,.2f}")
    m3.metric("IVA Acumulado", f"Bs. {total_iva:,.2f}")
    m4.metric("ISLR Estimado", f"Bs. {islr_estimado:,.2f}")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df.to_excel(writer, index=False, sheet_name="Cierre_Fiscal")
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Descargar Reporte Completo en Excel (.xlsx)",
        data=excel_data,
        file_name=(
            f"cierre_fiscal_{datetime.date.today().strftime('%Y_%m')}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
  else:
    st.info("Registra al menos un movimiento para ver el consolidado fiscal.")
