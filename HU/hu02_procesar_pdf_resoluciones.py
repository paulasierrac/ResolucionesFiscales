"""
================================================================================
HU02 - ProcesarPdfResoluciones
Migracion del bot Automation Anywhere "HU02_ProcesarPdfResoluciones" a Python.
Propiedad de Colsubsidio
================================================================================

Escanea RutaBase en busca de PDFs de Resolucion Fiscal DIAN, valida la cantidad
de hojas (validas: 2, 3 o 4; invalidas: 1 o mas de 4), extrae los datos de las
validas (Funciones/pdf_resoluciones.extraer_datos_pdf) e inserta en TicketInsumo,
archiva los PDFs procesados/invalidos y notifica por correo.

A diferencia del bot original (que insertaba las 11 filas candidatas por hoja y
luego borraba las vacias por SQL), aca solo se insertan las filas que si tienen
datos -- mismo resultado final, mecanismo mas simple.
"""

import os
import sys
import shutil
from datetime import date

_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Funciones.utils import write_log, enviar_correo, conectar_bd
from Funciones.pdf_resoluciones import contar_paginas, extraer_datos_pdf

TASK_NAME = "HU02_ProcesarPdfResoluciones"


def _mover_archivo(origen: str, destino_carpeta: str, nombre: str) -> None:
    """Copia + borra (equivalente a un 'mover' que funciona entre discos/unidades de red)."""
    os.makedirs(destino_carpeta, exist_ok=True)
    shutil.copyfile(origen, os.path.join(destino_carpeta, nombre))
    os.remove(origen)


def procesar_pdfs(config: dict) -> dict:
    """
    Equivalente a HU02_ProcesarPdfResoluciones.

    Retorna dict:
      { "Config": dict, "IdHU": str, "Excecution": bool, "SystemException": str }
    """
    config = dict(config)
    esquema = config.get("Scheme", "[ResolucionesFiscales]")
    from_address = config.get("_correo", {}).get("usuario", "")

    ruta_base = config.get("RutaBase", "")
    ruta_pdfs_invalidos = os.path.join(ruta_base, config.get("CarpetaPdfInvalido", "PDFsInvalidos"))

    try:
        # --- Paso 1: escanear RutaBase (solo el nivel superior, PDFs recien llegados) ---
        nombres_pdf = sorted(
            f for f in os.listdir(ruta_base) if f.lower().endswith(".pdf")
        ) if os.path.isdir(ruta_base) else []

        # --- Salida temprana: no hay nada que procesar (Num_Correo=5) ---
        if not nombres_pdf:
            enviar_correo(
                config, i_num_correo="5", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: No existen PDFs para procesar el día de hoy",
                i_contenido_fallback=(
                    "Se finalizó la ejecución sin procesar ninguna resolución fiscal, "
                    f"esto debido a que no existe ningún PDF en la ruta [{ruta_base}]."
                ),
            )
            write_log("Info", f"HU02: No existen archivos PDF para procesar en la ruta [{ruta_base}]", TASK_NAME, config)
            write_log("Info", "-----HU02: Finalizo HU02-----", TASK_NAME, config)
            return {"Config": config, "IdHU": "3", "Excecution": True, "SystemException": ""}

        # --- Paso 2: carpeta destino de los PDFs validos, con estructura RutaBase/Reportes/AAAA/MM/DD ---
        hoy = date.today()
        ruta_reportes = os.path.join(
            ruta_base, config.get("CarpetaReportes", "Reportes"),
            f"{hoy.year:04d}", f"{hoy.month:02d}", f"{hoy.day:02d}",
        )
        os.makedirs(ruta_reportes, exist_ok=True)
        write_log("Info", f"HU02: En la ruta [{ruta_reportes}] quedan los archivos procesados", TASK_NAME, config)

        # --- Paso 3: clasificar cada PDF por cantidad de hojas ---
        # Validas: 2, 3 o 4 hojas (formulario DIAN 1876 con 1 pagina de datos generales
        # + 1 pagina de tabla por cada hoja adicional). Invalidas: 1 hoja o mas de 4.
        validos, invalidos = [], []
        for nombre in nombres_pdf:
            ruta_pdf = os.path.join(ruta_base, nombre)
            try:
                paginas = contar_paginas(ruta_pdf)
            except Exception as e:
                write_log("Error", f"HU02: No se pudo abrir [{nombre}]: {e}", TASK_NAME, config)
                invalidos.append(nombre)
                continue
            (validos if 2 <= paginas <= 4 else invalidos).append(nombre)

        # --- Paso 4: notificar y archivar los PDFs invalidos (Num_Correo=6) ---
        if invalidos:
            os.makedirs(ruta_pdfs_invalidos, exist_ok=True)
            lista = ", ".join(invalidos)
            enviar_correo(
                config, i_num_correo="6", i_from_address=from_address,
                i_asunto_fallback="RPA_LISA: Existen PDFs con hojas diferentes a las esperadas",
                i_contenido_fallback=(
                    f"Los archivos [{lista}] de la ruta de red [{ruta_base}] NO cumplen con el "
                    f"número de hojas definidas para el bot y se encuentran en [{ruta_pdfs_invalidos}]."
                ),
            )
            write_log(
                "Business",
                f"HU02: Los archivos [{lista}] NO cumplen con el número de hojas definidas para el bot.",
                TASK_NAME, config,
            )
            for nombre in invalidos:
                _mover_archivo(os.path.join(ruta_base, nombre), ruta_pdfs_invalidos, nombre)

        # --- Paso 5: extraer datos e insertar en TicketInsumo (Estado='1' = recien insertado) ---
        # A diferencia de AA (que insertaba 11 filas candidatas por hoja y borraba las
        # vacias por SQL), aca extraer_datos_pdf() ya devuelve solo las filas con datos.
        if validos:
            conn = conectar_bd(config)
            cursor = conn.cursor()
            for nombre in validos:
                ruta_pdf = os.path.join(ruta_base, nombre)
                filas = extraer_datos_pdf(ruta_pdf)
                filas_utiles = [f for f in filas if "_sin_parsear" not in f]

                # PDF valido por cantidad de hojas pero sin ningun dato reconocible:
                # equivalente al caso "el bot no puede identificar" de HU03, pero aca
                # se deja visible en el log en vez de fallar en silencio.
                if not filas_utiles:
                    write_log(
                        "Warning",
                        f"HU02: El PDF [{nombre}] no produjo ninguna fila reconocible "
                        f"(estructura inesperada o formulario vacío).",
                        TASK_NAME, config,
                    )

                for fila in filas_utiles:
                    cursor.execute(
                        f"INSERT INTO {esquema}.TicketInsumo "
                        "(FechaInicio, FechaModificacion, FechaFin, Estado, Observacion, Centro, "
                        " CentroBeneficio, NombreBase, Resolucion, FechaInicioRes, FechaVencimientoRes, "
                        " Prefijo, NumInicial, NumFinal, Tipo, Direccion, Meses, TipoHomologacion, "
                        " DireccionHomologacion, NombrePdf) "
                        "VALUES (GETDATE(), GETDATE(), NULL, '1', '', '', '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?)",
                        (
                            fila.get("Resolucion", ""),
                            fila.get("FechaInicioRes") or None,
                            fila.get("FechaVencimientoRes") or None,
                            fila.get("Prefijo", ""),
                            fila.get("NumInicial", ""),
                            fila.get("NumFinal", ""),
                            fila.get("Tipo", ""),
                            fila.get("Direccion", ""),
                            fila.get("Meses", ""),
                            nombre,
                        ),
                    )
                conn.commit()
                _mover_archivo(ruta_pdf, ruta_reportes, nombre)

            # --- Paso 6: commit final -> Estado '1' (extraido) pasa a '2' (comprometido) ---
            # HU03 solo trabaja sobre filas en Estado='2'.
            cursor.execute(f"UPDATE {esquema}.TicketInsumo SET Estado = '2', FechaModificacion = GETDATE() WHERE Estado = '1'")
            conn.commit()
            conn.close()
            write_log("Info", f"HU02: Se procesaron {len(validos)} PDF(s) válido(s)", TASK_NAME, config)

        write_log("Info", "-----HU02: Finalizo HU02-----", TASK_NAME, config)
        return {"Config": config, "IdHU": "3", "Excecution": True, "SystemException": ""}

    except Exception as e:
        system_exception = f"Line: {sys.exc_info()[2].tb_lineno} - Error: {e}"
        write_log("Error", system_exception, TASK_NAME, config)
        return {"Config": config, "IdHU": "2", "Excecution": False, "SystemException": system_exception}
