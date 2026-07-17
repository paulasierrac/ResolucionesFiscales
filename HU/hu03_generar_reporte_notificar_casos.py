"""
================================================================================
HU03 - GenerarReporteYNotificarCasos
Migracion del bot Automation Anywhere "HU03_GenerarReporteYNotificarCasos" a Python.
Propiedad de Colsubsidio
================================================================================

Depura registros con datos incompletos, homologa Prefijo contra
[HomologacionPrefijo], genera el reporte diario + el consolidado, y (solo el
dia configurado en DiaReporteVencidos) el reporte de resoluciones que
venceran el mes siguiente. Notifica cada paso por correo (tabla [Correos]).
"""

import os
import sys
from datetime import date

import pandas as pd

_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Funciones.utils import write_log, enviar_correo, conectar_bd

TASK_NAME = "HU03_GenerarReporteYNotificarCasos"

_COLUMNAS_REPORTE = (
    "Centro, CentroBeneficio, NombreBase, Resolucion, FechaInicioRes, FechaVencimientoRes, "
    "Prefijo, NumInicial, NumFinal, Tipo, TipoHomologacion, Direccion, DireccionHomologacion, "
    "Meses, FechaInicio AS FechaDeProcesamiento"
)


def _sumar_meses(fecha: date, meses: int) -> date:
    """Suma 'meses' meses a 'fecha' (usada para calcular el mes objetivo del reporte de vencimientos)."""
    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, 28)
    return date(anio, mes, dia)


def _ultimo_dia_mes(anio: int, mes: int) -> date:
    """Retorna la fecha del ultimo dia calendario del mes dado."""
    if mes == 12:
        return date(anio, 12, 31)
    primero_siguiente = date(anio, mes + 1, 1)
    from datetime import timedelta
    return primero_siguiente - timedelta(days=1)


def generar_reporte_notificar_casos(config: dict) -> dict:
    """
    Equivalente a HU03_GenerarReporteYNotificarCasos.

    Retorna dict:
      { "Config": dict, "IdHU": str, "Excecution": bool, "SystemException": str }
    """
    config = dict(config)
    esquema = config.get("Scheme", "[ResolucionesFiscales]")
    from_address = config.get("_correo", {}).get("usuario", "")
    ruta_base = config.get("RutaBase", "")
    hoy = date.today()

    try:
        ruta_reportes = os.path.join(
            ruta_base, config.get("CarpetaReportes", "Reportes"),
            f"{hoy.year:04d}", f"{hoy.month:02d}", f"{hoy.day:02d}",
        )
        os.makedirs(ruta_reportes, exist_ok=True)

        conn = conectar_bd(config)
        cursor = conn.cursor()

        # --- 1. Depurar registros con datos incompletos (Num_Correo=7) ---
        # Chequeo defensivo: HU02 ya deberia insertar solo filas completas, pero se
        # conserva la validacion por si algun PDF produjo datos parciales.
        # Se notifica y se eliminan (no se reintenta su extraccion).
        cursor.execute(
            f"SELECT NombrePdf FROM {esquema}.TicketInsumo WHERE Estado = '2' AND "
            "(FechaInicioRes IS NULL OR FechaVencimientoRes IS NULL OR "
            " CONVERT(varchar, FechaInicioRes, 23) = '1900-01-01' OR "
            " CONVERT(varchar, FechaVencimientoRes, 23) = '1900-01-01' OR "
            " Prefijo IS NULL OR Prefijo = '')"
        )
        pdfs_invalidos = [r[0] for r in cursor.fetchall()]
        if pdfs_invalidos:
            lista = ", ".join(pdfs_invalidos)
            enviar_correo(
                config, i_num_correo="7", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: Existen PDFs que contienen información que el bot no puede identificar",
                i_contenido_fallback=(
                    "Se presentaron inconsistencias en el procesamiento de algunos PDFs de "
                    f"resoluciones fiscales: {lista}. Esta información se eliminará de la base de datos."
                ),
            )
            cursor.execute(
                f"DELETE FROM {esquema}.TicketInsumo WHERE Estado = '2' AND "
                "(FechaInicioRes IS NULL OR FechaVencimientoRes IS NULL OR "
                " CONVERT(varchar, FechaInicioRes, 23) = '1900-01-01' OR "
                " CONVERT(varchar, FechaVencimientoRes, 23) = '1900-01-01' OR "
                " Prefijo IS NULL OR Prefijo = '')"
            )
            conn.commit()
            write_log("Business", f"HU03: Se eliminaron registros inconsistentes de: {lista}", TASK_NAME, config)

        # --- 2. Homologar Prefijo contra HomologacionPrefijo ---
        # Rellena Centro/CentroBeneficio/NombreBase/TipoHomologacion/DireccionHomologacion
        # por cada Prefijo que coincida; los que no tienen match quedan con esos campos
        # vacios y se notifican (Num_Correo=8) pero SIN eliminarse (siguen en el reporte).
        cursor.execute(
            f"UPDATE t1 SET t1.Centro = t2.Centro, t1.CentroBeneficio = t2.CentroBeneficio, "
            "t1.NombreBase = t2.NombreEnBase, t1.TipoHomologacion = t2.Tipo, "
            "t1.DireccionHomologacion = t2.Direccion "
            f"FROM {esquema}.TicketInsumo t1 INNER JOIN {esquema}.HomologacionPrefijo t2 "
            "ON t1.Prefijo = t2.Prefijo "
            "WHERE t1.Estado = '2' AND (t1.TipoHomologacion IS NULL OR t1.TipoHomologacion = '')"
        )
        conn.commit()

        cursor.execute(
            f"SELECT DISTINCT Prefijo FROM {esquema}.TicketInsumo "
            "WHERE Estado = '2' AND (TipoHomologacion IS NULL OR TipoHomologacion = '')"
        )
        prefijos_nuevos = [r[0] for r in cursor.fetchall()]
        if prefijos_nuevos:
            enviar_correo(
                config, i_num_correo="8", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: Existen registros que tienen un prefijo nuevo",
                i_contenido_fallback=(
                    "Se identificaron Prefijos que no tienen homologación en la tabla "
                    f"[HomologacionPrefijo]: {', '.join(prefijos_nuevos)}"
                ),
            )
            write_log("Business", f"HU03: Prefijos sin homologar: {prefijos_nuevos}", TASK_NAME, config)

        # --- 3. Reporte diario (Estado = '2') ---
        # Si hay filas pendientes: exportar a Excel, detectar resoluciones "electronicas"
        # (Tipo contiene alguna de las PalabraClaveResElectronica), notificar con el
        # reporte adjunto (Num_Correo=9), y promover esas filas a Estado='3' (cerradas).
        cursor.execute(f"SELECT COUNT(*) FROM {esquema}.TicketInsumo WHERE Estado = '2'")
        hay_pendientes = cursor.fetchone()[0] > 0

        if hay_pendientes:
            df_reporte = pd.read_sql(
                f"SELECT {_COLUMNAS_REPORTE} FROM {esquema}.TicketInsumo WHERE Estado = '2'", conn
            )
            nombre_reporte = f"{config.get('NombreArchivoReporteResoluciones', 'ReporteResolucionesFiscales')}_{hoy.isoformat()}.xlsx"
            ruta_reporte = os.path.join(ruta_reportes, nombre_reporte)
            df_reporte.to_excel(ruta_reporte, index=False)

            palabras = [p.strip() for p in config.get("PalabraClaveResElectronica", "").split(",") if p.strip()]
            resoluciones_electronicas = []
            if palabras:
                condiciones = " OR ".join("Tipo LIKE ?" for _ in palabras)
                cursor.execute(
                    f"SELECT DISTINCT Resolucion FROM {esquema}.TicketInsumo WHERE Estado = '2' AND ({condiciones})",
                    tuple(f"%{p}%" for p in palabras),
                )
                resoluciones_electronicas = [r[0] for r in cursor.fetchall()]

            cuerpo_extra = f"Ruta del reporte: {ruta_reporte}"
            if resoluciones_electronicas:
                cuerpo_extra += "\nResoluciones electrónicas identificadas: " + ", ".join(resoluciones_electronicas)

            enviar_correo(
                config, i_num_correo="9", i_from_address=from_address,
                i_sufijo_contenido=cuerpo_extra,
                i_asunto_fallback="RPA_LISA: Se generó el archivo ReporteResolucionesFiscales.xlsx",
                i_contenido_fallback=(
                    "Se completó de forma exitosa el procesamiento de los PDFs de ResolucionesFiscales, "
                    "el archivo con las resoluciones procesadas se encuentra en la ruta de red:"
                ),
                i_attachment=[ruta_reporte],
            )
            write_log("Info", f"HU03: Reporte diario generado en [{ruta_reporte}]", TASK_NAME, config)

            cursor.execute(
                f"UPDATE {esquema}.TicketInsumo SET Estado = '3', FechaModificacion = GETDATE(), "
                "FechaFin = GETDATE() WHERE Estado = '2'"
            )
            conn.commit()

        # --- 4. Consolidado (Estado = '3', historico completo) ---
        # Se corre siempre (haya o no reporte diario nuevo), sobrescribiendo el mismo
        # archivo cada vez con TODO el historico de resoluciones ya cerradas.
        ruta_consolidado_carpeta = os.path.join(ruta_base, config.get("CarpetaReportes", "Reportes"), config.get("CarpetaConsolidado", "Consolidado"))
        os.makedirs(ruta_consolidado_carpeta, exist_ok=True)
        ruta_consolidado = os.path.join(
            ruta_consolidado_carpeta, config.get("NombreArchivoConsolidadoResoluciones", "ConsolidadoResolucionesFiscales") + ".xlsx"
        )
        df_consolidado = pd.read_sql(
            f"SELECT {_COLUMNAS_REPORTE} FROM {esquema}.TicketInsumo WHERE Estado = '3' ORDER BY FechaInicio DESC", conn
        )
        df_consolidado.to_excel(ruta_consolidado, index=False)
        write_log("Info", f"HU03: Consolidado actualizado en [{ruta_consolidado}]", TASK_NAME, config)

        # --- 5. Reporte mensual de resoluciones que venceran (solo el dia configurado) ---
        # Se gatilla unicamente cuando hoy.day == DiaReporteVencidos (ej. dia 10 de cada
        # mes). Ventana de fechas = TODO el mes siguiente al actual (mes_objetivo).
        # Incluye tanto Estado='2' (aun no reportadas) como Estado='3' (ya reportadas).
        dia_reporte_vencidos = str(config.get("DiaReporteVencidos", "")).strip()
        if dia_reporte_vencidos and f"{hoy.day:02d}" == dia_reporte_vencidos.zfill(2):
            mes_objetivo = _sumar_meses(hoy, 1)
            rango_inicial = date(mes_objetivo.year, mes_objetivo.month, 1)
            rango_final = _ultimo_dia_mes(mes_objetivo.year, mes_objetivo.month)

            ruta_venceran_carpeta = os.path.join(ruta_base, config.get("CarpetaReporteResolucionesQueVenceran", "ReporteResolucionesQueVenceran"))
            os.makedirs(ruta_venceran_carpeta, exist_ok=True)
            nombre_venceran = f"{config.get('NombreArchivoResolucionesQueVenceran', 'ResolucionesQueVenceran')}{mes_objetivo.strftime('%Y-%m')}.xlsx"
            ruta_venceran = os.path.join(ruta_venceran_carpeta, nombre_venceran)

            df_venceran = pd.read_sql(
                f"SELECT {_COLUMNAS_REPORTE} FROM {esquema}.TicketInsumo "
                "WHERE (Estado = '3' OR Estado = '2') AND FechaVencimientoRes BETWEEN ? AND ? "
                "ORDER BY FechaInicio DESC",
                conn, params=(rango_inicial, rango_final),
            )
            if not df_venceran.empty:
                df_venceran.to_excel(ruta_venceran, index=False)
                enviar_correo(
                    config, i_num_correo="11", i_from_address=from_address,
                    i_asunto_fallback="RPA_LISA: Se generó reporte con las resoluciones que se vencerán",
                    i_contenido_fallback=f"En el archivo adjunto se encuentran las resoluciones próximas a vencer: {ruta_venceran}",
                    i_attachment=[ruta_venceran],
                )
                write_log("Info", f"HU03: Reporte de vencimientos generado en [{ruta_venceran}]", TASK_NAME, config)
            else:
                write_log("Info", "HU03: No hay resoluciones que venzan el próximo mes", TASK_NAME, config)

        conn.close()
        write_log("Info", "HU03: ejecución completada exitosamente", TASK_NAME, config)
        write_log("Info", "-----HU03: Finalizo HU03-----", TASK_NAME, config)
        return {"Config": config, "IdHU": "1", "Excecution": True, "SystemException": ""}

    except Exception as e:
        system_exception = f"Line: {sys.exc_info()[2].tb_lineno} - Error: {e}"
        write_log("Error", system_exception, TASK_NAME, config)
        return {"Config": config, "IdHU": "3", "Excecution": False, "SystemException": system_exception}
