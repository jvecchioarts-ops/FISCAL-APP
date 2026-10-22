import datetime
import io
import bs4
import pandas as pd
import requests
import sqlite3
import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA E ÍCONO EN PESTAÑA ---
st.set_page_config(
    page_title="FISCAL APP - Gestiona tus Finanzas Fácilmente",
    page_icon="logo.jpg",
    layout="wide",
)


# --- BASE DE DATOS Y ESTADO DE BLOQUEO ---
def init_db():
  conn = sqlite3.connect("control_fiscal.db", check_same_thread=False)
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
        CREATE TABLE IF NOT EXISTS estado_demo (
            id INTEGER PRIMARY KEY,
            bloqueado INTEGER
        )
    """)
  cursor.execute(
      "INSERT OR IGNORE INTO estado_demo (id, bloqueado) VALUES (1, 0)"
  )
  conn.commit()
  return conn


conn = init_db()


def esta_bloqueada():
  cursor = conn.cursor()
  cursor.execute("SELECT bloqueado FROM estado_demo WHERE id = 1")
  res = cursor.fetchone()
  return res[0] == 1 if res else False


def bloquear_app():
  cursor = conn.cursor()
  cursor.execute("UPDATE estado_demo SET bloqueado = 1 WHERE id = 1")
  conn.commit()


# --- SI LA APP ESTÁ BLOQUEADA ---
if esta_bloqueada():
  st.error("🔒 **EL PERIODO DE PRUEBA HA FINALIZADO**")
  st.info(
      "Esta versión de prueba ha completado su ciclo tras el cierre y exportación"
      " del ejercicio."
  )
  st.markdown("""
    ### 🚀 Gracias por probar FISCAL APP
    * **Gestión Financiera y Control Fiscal en Venezuela**
    
    Para reactivar la aplicación, solicitar licencias multiusuario o personalizar la plataforma para tu empresa, ponte en contacto con el desarrollador.
    """)
  st.stop()

# --- CABECERA PRINCIPAL CON LOGO Y TÍTULO ---
col_logo, col_titulo = st.columns([1, 4])

with col_logo:
  try:
    st.image("logo.jpg", width=130)
  except Exception:
    st.title("🇻🇪")

with col_titulo:
  st.title("FISCAL APP")
  st.subheader('"Gestiona tus Finanzas Fácilmente"')

st.caption(
    "Control financiero multibanco, gestión de ISLR/IVA/IGTF y conciliación"
    " bancaria bajo normativas SENIAT."
)
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

  try:
    r = requests.get("https://ve.dolarapi.com/v1/dolares/oficial", timeout=5)
    if r.status_code == 200:
      return float(r.json()["promedio"])
  except Exception:
    pass

  return 36.50


requests.packages.urllib3.disable_warnings()

# --- BARRA LATERAL (CONFIGURACIÓN FISCAL Y TASA EDITABLE) ---
st.sidebar.image("logo.jpg", use_container_width=True)
st.sidebar.header("⚙️ Configuración Fiscal")

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
porcentaje_vehiculo = st.sidebar.slider(
    "🚗 % Deducible Vehículo", 0, 100, 75
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
# PESTAÑA 1: REGISTRO DIARIO
# ---------------------------------------------------------
with pestanas[0]:
  st.subheader("Registrar Nuevo Movimiento")

  # CAMPOS DE SELECCIÓN DINÁMICA (FUERA DEL FORMULARIO PARA REACCIÓN EN TIEMPO REAL)
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

  # --- EVALUACIÓN AUTOMÁTICA EN TIEMPO REAL ---
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

  # MOSTRAR EL VEREDICTO DE FORMA CLARA Y DESTACADA
  if es_deducible_bool:
    st.success(f"✅ **Criterio ISLR:** {status_deducible}")
  else:
    st.info(f"⚖️ **Criterio ISLR:** {status_deducible}")

  # FORMULARIO PARA INGRESAR VALORES Y GUARDAR
  with st.form("form_transaccion", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
      banco_seleccionado = st.selectbox(
          "🏦 Banco / Cuenta", BANCOS_VENEZUELA
      )
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

      factor_deduccion = (
          (porcentaje_vehiculo / 100.0) if "vehículo" in cat_lower else 1.0
      )
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

# ---------------------------------------------------------
# PESTAÑA 3: CONCILIACIÓN BANCARIA
# ---------------------------------------------------------
with pestanas[2]:
  st.subheader("Conciliación Bancaria")
  banco_conciliar = st.selectbox(
      "Selecciona el Banco:", BANCOS_VENEZUELA
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
# PESTAÑA 4: CIERRE, REPORTES Y BLOQUEO AUTOMÁTICO
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

    st.divider()
    st.warning(
        "⚠️ **Atención:** Al hacer clic en descargar, la versión de evaluación"
        " se dará por completada y se bloqueará."
    )

    btn_descargar = st.download_button(
        label="📥 Descargar Reporte Completo en Excel (.xlsx)",
        data=excel_data,
        file_name=(
            f"cierre_fiscal_{datetime.date.today().strftime('%Y_%m')}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )

    if btn_descargar:
      bloquear_app()
      st.success("Reporte generado. La aplicación de prueba se ha bloqueado.")
      st.rerun()

  else:
    st.info("Registra al menos un movimiento para ver el consolidado fiscal.")
