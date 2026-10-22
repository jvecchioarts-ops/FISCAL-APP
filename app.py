import datetime
import io
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Control Fiscal Venezuela - Gastos e Ingresos", layout="wide"
)

st.title("🇻🇪 Control Financiero y Conciliación Bancaria - Venezuela")
st.write(
    "Registra tus movimientos, calcula IVA/IGTF, estima tu ISLR, realiza la conciliación con tu estado de cuenta y exporta tu cierre mensual."
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


# Panel Lateral de Configuración Fiscal
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

# Pestañas principales de la aplicación
pestanas = st.tabs(
    ["📝 Registro Diario", "🏦 Conciliación Bancaria", "📊 Cierre y Reportes"]
)

with pestanas[0]:
  st.subheader("Registrar Nuevo Movimiento")

  with st.form("form_transaccion"):
    col1, col2 = st.columns(2)

    with col1:
      tipo = st.selectbox("Tipo de Movimiento", ["Ingreso", "Gasto"])
      divisa = st.selectbox("Moneda de la Operación", ["USD", "VES"])
      monto = st.number_input(
          "Monto Total de la Operación", min_value=0.0, step=0.01
      )
      fecha = st.date_input("Fecha de la Transacción", datetime.date.today())

    with col2:
      categorias = [
          "Alquiler de Local / Oficina",
          "Servicios Públicos (Luz, Agua, Telecomunicaciones)",
          "Honorarios Profesionales",
          "Publicidad y Mercadeo",
          "Inventario / Materia Prima",
          "Mantenimiento y Reparaciones Generales",
          "🚗 Mantenimiento y Reparaciones de Vehículo",
          "Gastos Personales (No Deducibles)",
          "Otros Gastos Operativos",
      ]
      categoria = st.selectbox("Rubro / Categoría", categorias)

      es_deducible_base = False if "Personales" in categoria else True
      es_deducible = st.checkbox(
          "¿Es gasto deducible para el ISLR?", value=es_deducible_base
      )

      nro_factura = st.text_input("Número de Factura")
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
          if es_deducible
          else 0.0
      )

      nueva_transaccion = {
          "Fecha": fecha,
          "Tipo": tipo,
          "Categoría": categoria,
          "Deducible ISLR": "Sí" if es_deducible else "No",
          "Divisa": divisa,
          "Monto Original": monto,
          "Monto VES": round(monto_ves, 2),
          "Monto USD": round(monto_usd, 2),
          "IVA VES": round(monto_iva, 2),
          "IGTF VES": round(igtf_monto, 2),
          "Monto Deducible VES": round(monto_deducible_calculado, 2),
          "Factura": nro_factura,
          "Control": nro_control,
      }

      st.session_state.transacciones.append(nueva_transaccion)
      st.success("¡Movimiento registrado con éxito!")

  if st.session_state.transacciones:
    st.divider()
    st.subheader("Movimientos Registrados Recientemente")
    df_temp = pd.DataFrame(st.session_state.transacciones)
    st.dataframe(df_temp, use_container_width=True)

with pestanas[1]:
  st.subheader("Conciliación Bancaria Mensual")
  st.write(
      "Sube el archivo de tu estado de cuenta (formato Excel o CSV que descargues de tu banco en Venezuela) para compararlo con tus registros."
  )

  archivo_banco = st.file_uploader(
      "Cargar Estado de Cuenta Bancario (.xlsx, .csv)", type=["xlsx", "csv"]
  )

  if archivo_banco is not None:
    try:
      if archivo_banco.name.endswith(".csv"):
        df_banco = pd.read_csv(archivo_banco)
      else:
        df_banco = pd.read_excel(archivo_banco)

      st.write("Vista previa del estado de cuenta bancario cargado:")
      st.dataframe(df_banco.head(), use_container_width=True)

      if st.session_state.transacciones:
        st.info(
            "💡 Consejo de conciliación: Verifica que los montos totales y referencias de tus registros coincidan con los débitos/créditos de este archivo bancario."
        )
      else:
        st.warning(
            "No hay transacciones guardadas aún en la pestaña de Registro Diario para conciliar."
        )
    except Exception as e:
      st.error(f"Error al leer el archivo bancario: {e}")

with pestanas[2]:
  st.subheader("Consolidado, Estimación Fiscal y Cierre")

  if st.session_state.transacciones:
    df = pd.DataFrame(st.session_state.transacciones)

    total_ingresos = df[df["Tipo"] == "Ingreso"]["Monto VES"].sum()
    total_gastos = df[df["Tipo"] == "Gasto"]["Monto VES"].sum()
    total_iva = df["IVA VES"].sum()
    total_igtf = df["IGTF VES"].sum()
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
        label="📥 Descargar Reporte de Cierre en Excel (.xlsx)",
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