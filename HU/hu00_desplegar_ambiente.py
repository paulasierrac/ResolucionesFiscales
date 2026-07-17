"""
================================================================================
HU00 - DespliegeAmbiente
Migracion del bot Automation Anywhere "HU00_DespliegeAmbiente" a Python.
Propiedad de Colsubsidio
================================================================================

Siembra las claves de arranque en [Parametros], carga la tabla completa a un
diccionario de configuracion, valida que la ruta base de red exista, crea las
subcarpetas requeridas y purga logs viejos.
"""

import os
import sys
import getpass
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Funciones.utils import write_log, enviar_correo, conectar_bd

TASK_NAME = "HU00_DespliegeAmbiente"


def _restar_meses(fecha: date, meses: int) -> date:
    """Resta 'meses' meses a 'fecha' (usada para calcular la fecha de corte de logs viejos)."""
    mes_total = fecha.month - 1 - meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, 28)
    return date(anio, mes, dia)


def desplegar_ambiente(config: dict) -> dict:
    """
    Equivalente a HU00_DespliegeAmbiente.

    Parametros:
      config : dict devuelto por obtener_config() (debe traer '_db', '_correo', 'Scheme').

    Retorna dict:
      { "Config": dict, "IdHU": str, "Excecution": bool, "SystemException": str }
    """
    config = dict(config)
    esquema = config.get("Scheme", "[ResolucionesFiscales]")
    tabla_parametros = "Parametros"
    config["TablaParametros"] = tabla_parametros

    try:
        # --- Paso 1: valores de arranque que no vienen de la BD sino del entorno ---
        # (equivalente a System:USERNAME / System:USERPROFILE / @Server / @Database en AA)
        config["Usuario"] = getpass.getuser()
        config["RutaLocal"] = os.environ.get("USERPROFILE", str(Path.home()))
        config["Server"] = config.get("_db", {}).get("server", "")
        config["DataBase"] = config.get("_db", {}).get("database", "")

        claves_bootstrap = ["TablaParametros", "Scheme", "Server", "DataBase", "Usuario", "RutaLocal"]

        conn = conectar_bd(config)
        cursor = conn.cursor()

        # --- Paso 2: upsert de las 6 claves de arranque en [Parametros] ---
        # Si la fila no existe se crea vacia y luego se actualiza (igual que el bot AA,
        # que primero valida existencia y despues hace el UPDATE del valor real).
        for clave in claves_bootstrap:
            valor = config.get(clave, "")
            cursor.execute(
                f"SELECT 1 FROM {esquema}.{tabla_parametros} WHERE Nombre = ?", (clave,)
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    f"INSERT INTO {esquema}.{tabla_parametros} (Nombre, Valor, Descripcion) "
                    f"VALUES (?, '', 'Variable global del proceso')",
                    (clave,),
                )
            cursor.execute(
                f"UPDATE {esquema}.{tabla_parametros} SET Valor = ? WHERE Nombre = ?",
                (valor, clave),
            )
        conn.commit()

        # --- Paso 3: cargar TODA la tabla [Parametros] al diccionario de configuracion ---
        # A partir de aqui 'config' tiene todas las variables del proceso (RutaBase, MailTo,
        # nombres de archivo/carpeta, etc.), no solo las 6 claves de arranque.
        cursor.execute(f"SELECT Nombre, Valor FROM {esquema}.{tabla_parametros}")
        for nombre, valor in cursor.fetchall():
            config[nombre] = valor
        conn.close()

        # --- Paso 4: validar que la ruta base de red exista (hard-stop silencioso) ---
        # Si no existe, se notifica por correo y se retorna Excecution=False sin lanzar
        # excepcion: es un "no ejecutable", no un error real (igual que el stopTask de AA).
        ruta_base = config.get("RutaBase", "")
        if not ruta_base or not os.path.isdir(ruta_base):
            enviar_correo(
                config,
                i_num_correo="RutaBaseFaltante",
                i_from_address=config.get("_correo", {}).get("usuario", ""),
                i_asunto_fallback="RPA_LISA: No existe la ruta base definida para el bot",
                i_contenido_fallback=(
                    f"No fue posible iniciar el bot porque la ruta base "
                    f"'{ruta_base}' no existe o no es accesible."
                ),
                i_incluir_pie=False,
            )
            write_log(
                "Error",
                f"HU00: No existe la ruta base [{ruta_base}]",
                TASK_NAME, config,
            )
            return {"Config": config, "IdHU": "1", "Excecution": False, "SystemException": ""}

        write_log("Info", "-----HU00: Comienza la HU00-----", TASK_NAME, config)

        # --- Paso 5: crear las subcarpetas requeridas por el proceso ---
        # CarpetasRutaRed es una lista separada por comas (ej. "Logs,Parametros,...").
        carpetas = [c.strip() for c in config.get("CarpetasRutaRed", "").split(",") if c.strip()]
        for carpeta in carpetas:
            ruta_carpeta = os.path.join(ruta_base, carpeta)
            if not os.path.isdir(ruta_carpeta):
                os.makedirs(ruta_carpeta, exist_ok=True)
        write_log("Info", "HU00: Se validaron carpetas del proceso", TASK_NAME, config)

        # --- Paso 6: purgar logs mas viejos que MesesRepositorioLog meses ---
        path_log = config.get("PathLog", "")
        meses_repositorio = int(config.get("MesesRepositorioLog", "12") or "12")
        if path_log and os.path.isdir(path_log):
            fecha_corte = _restar_meses(date.today(), meses_repositorio)
            write_log(
                "Info",
                f"HU00: Se eliminaran logs anteriores a [{fecha_corte.strftime('%m/%d/%y')}]",
                TASK_NAME, config,
            )
            for nombre_archivo in os.listdir(path_log):
                ruta_archivo = os.path.join(path_log, nombre_archivo)
                if os.path.isfile(ruta_archivo):
                    fecha_mod = date.fromtimestamp(os.path.getmtime(ruta_archivo))
                    if fecha_mod < fecha_corte:
                        os.remove(ruta_archivo)
        write_log("Info", "HU00: Se realizo limpieza de Logs", TASK_NAME, config)

        write_log("Info", "-----HU00: Finalizo HU00-----", TASK_NAME, config)
        return {"Config": config, "IdHU": "1", "Excecution": True, "SystemException": ""}

    except Exception as e:
        system_exception = f"Line: {sys.exc_info()[2].tb_lineno} - Error: {e}"
        write_log("Error", system_exception, TASK_NAME, config)
        return {"Config": config, "IdHU": "1", "Excecution": False, "SystemException": system_exception}
