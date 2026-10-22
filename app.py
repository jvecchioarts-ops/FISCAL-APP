import datetime
import io
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Control Fiscal Venezuela - Gastos e Ingresos", layout="wide"
)

st.title("🇻🇪 Control Financiero Multibanco y Conciliación - Venezuela")
st.write(
    "Registra transacciones por banco, gestiona ISLR/IVA/IGTF y realiza conciliaciones independientes."
)


@st.cache_data(ttl=3600)
def obtener_tasa_bcv_actual():
  try:
    url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?monitor=bcv"
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
      data = response.json()
      return float(data["monitors"]["bcv"]["price"])
  except Exception:
    pass
  return 36.50


# Sidebar Config
st.sidebar.header("⚙️ Configuración Fiscal")
st.sidebar.markdown(
    "🔗 [Consultar Tasa Oficial en el BCV](https://www.bcv.org.ve/)",
    unsafe_allow_html=True,
)

tasa_automatica = obtener_tasa_bcv_actual()
tasa_bcv = st.sidebar.number_input(
    "Tasa Oficial BCV (VES/USD):",
    min_value=0.0,
    value=tasa_automatica,
    step=0.01,
)

rif_usuario = st.sidebar.text_input("Tu RIF / Cédula:", value="J-12345678-9")
tipo_contribuyente = st.sidebar.selectbox(
    "Tipo de Contribuyente", ["Persona Natural", "Persona Jurídica"]
)
porcentaje_vehiculo = st.sidebar.slider(
    "🚗 % Deducible para Mantenimiento de Vehículo", 0, 100, 75
)

if "transacciones" not in st.session_state:
  st.session_state.transacciones = []

pestanas = st.tabs([
    "📝 Registro Diario",
    "✏️ Gestionar Registros",
    "🏦 Conciliación Bancaria",
    "📊 Cierre y Reportes",
])

# Lista de bancos soportados
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
# PESTAÑA 1: REGISTRO DIARIO (MULTIBANCO)
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
      concepto = st.text_input(
          "Concepto / Descripción",
          placeholder="Ej: Pago de proveedor, Transferencia recibida, Almuerzo",
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
      monto_ves = monto if divisa == "VES" else monto * tasa_bcv
      monto_usd = monto / tasa_bcv if divisa == "VES" else monto

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

      nueva_transaccion = {
          "ID": len(st.session_state.transacciones) + 1,
          "Fecha": fecha,
          "Banco": banco_seleccionado,
          "Tipo": tipo,
          "Concepto": concepto if concepto else "Sin concepto",
          "Categoría": categoria,
          "Deducible ISLR": "Sí" if es_deducible else "No",
          "Divisa": divisa,
          "Monto Original": monto,
          "Monto VES": round(monto_ves, 2),
          "Monto USD": round(monto_usd, 2),
          "IVA VES": round(monto_iva, 2),
          "IGTF VES": round(igtf_monto, 2),
          "Monto Deducible VES": round(monto_deducible_calculado, 2),
          "Factura / Ref": nro_factura,
          "Control": nro_control,
      }

      st.session_state.transacciones.append(nueva_transaccion)
      st.success("¡Movimiento registrado con éxito!")

# ---------------------------------------------------------
# PESTAÑA 2: GESTIONAR REGISTROS
# ---------------------------------------------------------
with pestanas[1]:
  st.subheader("Gestión y Edición de Registros")
  if not st.session_state.transacciones:
    st.info("No hay transacciones registradas.")
  else:
    df_gestion = pd.DataFrame(st.session_state.transacciones)

    # Filtro opcional por Banco
    banco_filtro = st.selectbox(
        "Filtrar lista por Banco:", ["Todos"] + BANCOS_VENEZUELA
    )
    if banco_filtro != "Todos":
      df_gestion = df_gestion[df_gestion["Banco"] == banco_filtro]

    st.dataframe(df_gestion, use_container_width=True)

    st.divider()
    col_edit, col_del = st.columns(2)

    with col_del:
      st.write("### 🗑️ Eliminar Registro")
      ids_disponibles = [t["ID"] for t in st.session_state.transacciones]
      id_a_eliminar = st.selectbox(
          "Selecciona el ID a eliminar:", ids_disponibles
      )
      confirmar_borrado = st.checkbox(
          f"⚠️ Confirmar eliminación permanente del ID #{id_a_eliminar}"
      )

      if st.button("🔴 Eliminar Registro", type="primary"):
        if confirmar_borrado:
          st.session_state.transacciones = [
              t
              for t in st.session_state.transacciones
              if t["ID"] != id_a_eliminar
          ]
          st.success(f"Registro #{id_a_eliminar} eliminado.")
          st.rerun()
        else:
          st.warning("Marca la casilla de confirmación.")

    with col_edit:
      st.write("### ✏️ Modificar Registro")
      id_a_editar = st.selectbox(
          "Selecciona el ID a modificar:", ids_disponibles, key="edit_select"
      )
      reg_actual = next(
          t
          for t in st.session_state.transacciones
          if t["ID"] == id_a_editar
      )

      nuevo_banco = st.selectbox(
          "Nuevo Banco:",
          BANCOS_VENEZUELA,
          index=BANCOS_VENEZUELA.index(reg_actual["Banco"])
          if reg_actual["Banco"] in BANCOS_VENEZUELA
          else 0,
      )
      nuevo_concepto = st.text_input(
          "Nuevo Concepto:", value=reg_actual["Concepto"]
      )
      nuevo_monto = st.number_input(
          "Nuevo Monto:",
          value=float(reg_actual["Monto Original"]),
          min_value=0.0,
      )

      confirmar_edicion = st.checkbox(
          f"⚠️ Confirmar cambios sobre ID #{id_a_editar}"
      )

      if st.button("🟢 Guardar Cambios"):
        if confirmar_edicion:
          reg_actual["Banco"] = nuevo_banco
          reg_actual["Concepto"] = nuevo_concepto
          reg_actual["Monto Original"] = nuevo_monto
          reg_actual["Monto VES"] = (
              nuevo_monto
              if reg_actual["Divisa"] == "VES"
              else nuevo_monto * tasa_bcv
          )
          reg_actual["Monto USD"] = (
              nuevo_monto / tasa_bcv
              if reg_actual["Divisa"] == "VES"
              else nuevo_monto
          )

          st.success(f"Registro #{id_a_editar} actualizado.")
          st.rerun()
        else:
          st.warning("Marca la casilla de confirmación.")

# ---------------------------------------------------------
# PESTAÑA 3: CONCILIACIÓN BANCARIA POR BANCO
# ---------------------------------------------------------
with pestanas[2]:
  st.subheader("Conciliación Bancaria por Banco Especifico")

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

      # Registros guardados para ese banco
      if st.session_state.transacciones:
        df_mis_regs = pd.DataFrame(st.session_state.transacciones)
        df_mis_regs_banco = df_mis_regs[df_mis_regs["Banco"] == banco_conciliar]

        st.divider()
        st.write(
            f"Tus registros internos guardados para **{banco_conciliar}**:"
        )
        st.dataframe(df_mis_regs_banco, use_container_width=True)
    except Exception as e:
      st.error(f"Error al leer el archivo: {e}")

# ---------------------------------------------------------
# PESTAÑA 4: CIERRE Y REPORTES
# ---------------------------------------------------------
with pestanas[3]:
  st.subheader("Consolidado Fiscal y Cierre General")

  if st.session_state.transacciones:
    df = pd.DataFrame(st.session_state.transacciones)

    total_ingresos = df[df["Tipo"] == "Ingreso"]["Monto VES"].sum()
    total_gastos = df[df["Tipo"] == "Gasto"]["Monto VES"].sum()
    total_iva = df["IVA VES"].sum()
    total_deducible = df["Monto Deducible VES"].sum()
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
