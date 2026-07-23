"""
================================================================================
HU01 - CargarInsumos
Migracion del bot Automation Anywhere "HU01_CargarInsumos" a Python.
Propiedad de Colsubsidio
================================================================================

Recarga las tablas [Correos] y [HomologacionPrefijo] desde los archivos
Parametros.xlsx / HomologacionPrefijo.xlsx en la carpeta de red configurada.

Nota: el seed de [Parametros] trae 'TablaHomologacionPrefijos' = '[HomologacionPrefijos]'
(plural), que NO coincide con la tabla real 'HomologacionPrefijo' (singular) del DDL.
Por eso este modulo usa nombres de tabla literales en vez de leerlos de Config,
para no arrastrar ese error del seed. Ver tambien memoria de proyecto sobre RPA_DEBUG.
"""

import os
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Funciones.utils import write_log, enviar_correo, conectar_bd

TASK_NAME = "HU01_CargarInsumos"

TABLA_CORREOS = "Correos"
TABLA_HOMOLOGACION = "HomologacionPrefijo"


def _normalizar_num_correo(valor: str) -> str:
    """Si la celda de Excel quedo formateada como numero, pandas (con dtype=str)
    puede devolver '8.0' en vez de '8' -- se quita el '.0' para que despues
    coincida con el WHERE Num_Correo=? de enviar_correo()."""
    valor = (valor or "").strip()
    if valor.endswith(".0") and valor[:-2].isdigit():
        return valor[:-2]
    return valor


def cargar_insumos(config: dict) -> dict:
    """
    Equivalente a HU01_CargarInsumos.

    Parametros:
      config : dict ya enriquecido por desplegar_ambiente() (HU00).

    Retorna dict:
      { "Config": dict, "IdHU": str, "Excecution": bool, "SystemException": str }
    """
    config = dict(config)
    esquema = config.get("Scheme", "[ResolucionesFiscales]")
    from_address = config.get("_correo", {}).get("usuario", "")

    ruta_base = config.get("RutaBase", "")
    ruta_carpeta_parametros = os.path.join(ruta_base, config.get("CarpetaParametros", "Parametros"))
    ruta_parametros_xlsx = os.path.join(ruta_carpeta_parametros, config.get("NombreArchivoParametros", "Parametros.xlsx"))
    ruta_homologacion_xlsx = os.path.join(
        ruta_carpeta_parametros, config.get("NombreArchivoHomologacionPrefijo", "HomologacionPrefijo.xlsx")
    )

    try:
        # --- Hard-stop 1: no existe la carpeta Parametros (Num_Correo=1) ---
        if not os.path.isdir(ruta_carpeta_parametros):
            enviar_correo(
                config, i_num_correo="1", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: No existe la carpeta Parametros",
                i_contenido_fallback=(
                    "No fue posible realizar la ejecución del BOT, esto debido a que no se tiene "
                    "acceso a la carpeta Parametros, la cual es indispensable para la ejecución "
                    f"correcta del BOT.\nLa ruta consultada por el bot es: {ruta_carpeta_parametros}"
                ),
            )
            write_log("Error", f"HU01: No existe la carpeta [{ruta_carpeta_parametros}]", TASK_NAME, config)
            return {"Config": config, "IdHU": "1", "Excecution": False, "SystemException": ""}

        # --- Hard-stop 2: no existe el archivo Parametros.xlsx (Num_Correo=2) ---
        if not os.path.isfile(ruta_parametros_xlsx):
            enviar_correo(
                config, i_num_correo="2", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: No existe el archivo Parametros.xlsx",
                i_contenido_fallback=(
                    "No fue posible realizar la ejecución del BOT, esto debido a que no se encuentra "
                    f"el archivo Parametros.xlsx en la ruta: {ruta_parametros_xlsx}"
                ),
            )
            write_log("Error", f"HU01: No existe el archivo [{ruta_parametros_xlsx}]", TASK_NAME, config)
            return {"Config": config, "IdHU": "1", "Excecution": False, "SystemException": ""}

        # --- Soft-stop: no existe HomologacionPrefijo.xlsx (Num_Correo=3) ---
        # No detiene la ejecucion: solo se omite la recarga de esa tabla y se sigue
        # con lo que ya haya en BD de una corrida anterior.
        existe_homologacion = os.path.isfile(ruta_homologacion_xlsx)
        if not existe_homologacion:
            enviar_correo(
                config, i_num_correo="3", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: No existe el archivo HomologacionPrefijos.xlsx",
                i_contenido_fallback=(
                    "No fue posible cargar HomologacionPrefijo.xlsx, esto debido a que no se encuentra "
                    f"el archivo en la ruta: {ruta_homologacion_xlsx}"
                ),
            )
            write_log(
                "Warning",
                f"HU01: No existe [{ruta_homologacion_xlsx}], se continuará con la información ya cargada a BD",
                TASK_NAME, config,
            )

        # --- Validar que las hojas requeridas (ej. "Correos") existan en el Excel (Num_Correo=4) ---
        # Nota: si faltan hojas, IdHU queda en "2" (no "1"): la siguiente corrida salta
        # directo a HU02 usando los datos ya cargados, en vez de reintentar HU01.
        hojas_requeridas = [h.strip() for h in config.get("HojasDeParametros", "Correos").split(",") if h.strip()]
        xl = pd.ExcelFile(ruta_parametros_xlsx)
        faltantes = [h for h in hojas_requeridas if h not in xl.sheet_names]
        if faltantes:
            enviar_correo(
                config, i_num_correo="4", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: No existe la hoja Correos en el archivo Parametros",
                i_contenido_fallback=(
                    f"No se encontraron las siguientes hojas en Parametros.xlsx: {', '.join(faltantes)}"
                ),
            )
            write_log("Error", f"HU01: Faltan hojas en Parametros.xlsx: {faltantes}", TASK_NAME, config)
            return {"Config": config, "IdHU": "2", "Excecution": False, "SystemException": ""}

        conn = conectar_bd(config)
        cursor = conn.cursor()

        # --- Recargar [Correos]: se trunca (DELETE) e inserta todo de nuevo desde la hoja "Correos" ---
        # 'Actividad' no viene en el Excel, siempre se inserta vacia (igual que el bot original).
        df_correos = pd.read_excel(xl, sheet_name="Correos", dtype=str).fillna("")
        cursor.execute(f"DELETE FROM {esquema}.{TABLA_CORREOS}")
        for _, fila in df_correos.iterrows():
            cursor.execute(
                f"INSERT INTO {esquema}.{TABLA_CORREOS} "
                "(Num_Correo, HU, Actividad, Caso, Para, Asunto, Contenido, ArchivoAdjunto) "
                "VALUES (?, ?, '', ?, ?, ?, ?, ?)",
                (
                    _normalizar_num_correo(fila.get("Num_Correo", "")), fila.get("HU", ""), fila.get("Caso", ""),
                    fila.get("Para", ""), fila.get("Asunto", ""), fila.get("Contenido", ""),
                    fila.get("ArchivoAdjunto", ""),
                ),
            )
        conn.commit()
        write_log("Info", f"HU01: Se recargo la tabla Correos ({len(df_correos)} filas)", TASK_NAME, config)

        # --- Notificacion de inicio de ejecucion (Num_Correo=10) ---
        # Se envia DESPUES de recargar [Correos] (no antes, como en el bot original)
        # para usar siempre los destinatarios frescos del Excel, no los que hubiera
        # en la tabla de una corrida anterior (evita notificar a la lista vieja).
        enviar_correo(
            config, i_num_correo="10", i_from_address=from_address,
            i_asunto_fallback="RPA_LISA: Se da comienzo a la ejecución del bot",
            i_contenido_fallback="Se informa que se dara comienzo a la ejecución del bot RPA_LISA para el día de hoy.",
        )

        # --- Recargar [HomologacionPrefijo] solo si el archivo existia ---
        # Se trunca (TRUNCATE) e inserta desde Sheet1, y se limpia el Prefijo
        # (quitar espacios/guiones) para que despues homologue bien contra el Prefijo
        # extraido de los PDFs en HU03.
        if existe_homologacion:
            df_homolog = pd.read_excel(ruta_homologacion_xlsx, sheet_name=0, dtype=str).fillna("")
            cursor.execute(f"TRUNCATE TABLE {esquema}.{TABLA_HOMOLOGACION}")
            for _, fila in df_homolog.iterrows():
                valores = tuple(fila.iloc[0:6])
                cursor.execute(
                    f"INSERT INTO {esquema}.{TABLA_HOMOLOGACION} "
                    "(Prefijo, Centro, CentroBeneficio, NombreEnBase, Tipo, Direccion, FechaModificacion) "
                    "VALUES (?, ?, ?, ?, ?, ?, GETDATE())",
                    valores,
                )
            cursor.execute(
                f"UPDATE {esquema}.{TABLA_HOMOLOGACION} SET Prefijo = REPLACE(REPLACE(Prefijo,' ',''),'-','')"
            )
            conn.commit()
            write_log("Info", f"HU01: Se recargo la tabla HomologacionPrefijo ({len(df_homolog)} filas)", TASK_NAME, config)

        conn.close()
        write_log("Info", "-----HU01: Finalizo HU01-----", TASK_NAME, config)
        return {"Config": config, "IdHU": "2", "Excecution": True, "SystemException": ""}

    except Exception as e:
        system_exception = f"Line: {sys.exc_info()[2].tb_lineno} - Error: {e}"
        write_log("Error", system_exception, TASK_NAME, config)
        return {"Config": config, "IdHU": "1", "Excecution": False, "SystemException": system_exception}
