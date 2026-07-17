"""
================================================================================
main.py - Orquestador ResolucionesFiscales
Migracion del bot Automation Anywhere "Main_ResolucionesFiscales" a Python.
Propiedad de Colsubsidio
================================================================================

Ejecuta UNA pasada: corre la HU actualmente activa en [ControlHU] (con
reintentos de todo el flujo si falla, igual que el bot original), actualiza
[ControlHU] a la siguiente HU, y termina. Para procesar las 3 HUs en
secuencia, un Task Scheduler externo debe invocar este script cada N minutos
(a diferencia del bot AA, que quedaba corriendo en un bucle infinito).
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Funciones.utils import write_log, enviar_correo, obtener_config, conectar_bd
from HU.hu00_desplegar_ambiente import desplegar_ambiente
from HU.hu01_cargar_insumos import cargar_insumos
from HU.hu02_procesar_pdf_resoluciones import procesar_pdfs
from HU.hu03_generar_reporte_notificar_casos import generar_reporte_notificar_casos

TASK_NAME = "Main_ResolucionesFiscales"
MAXIMO_REINTENTOS = 5

_EJECUTORES = {
    "1": cargar_insumos,
    "2": procesar_pdfs,
    "3": generar_reporte_notificar_casos,
}


def _enviar_correo_fatal(config: dict, system_exception: str) -> None:
    """Notifica cuando se agotan los MAXIMO_REINTENTOS sin exito (ultimo recurso)."""
    enviar_correo(
        config, i_num_correo="FatalError",
        i_from_address=config.get("_correo", {}).get("usuario", ""),
        i_asunto_fallback="RPA_LISA: Ejecución finalizada - Error inesperado",
        i_contenido_fallback=(
            f"El bot RPA_LISA (ResolucionesFiscales) agotó los {MAXIMO_REINTENTOS} "
            f"reintentos permitidos. Último error:\n{system_exception}"
        ),
    )


def ejecutar_una_pasada() -> None:
    config = obtener_config()
    reintentos = 0

    while reintentos < MAXIMO_REINTENTOS:
        # --- HU00 corre SIEMPRE primero: recarga Config y valida el ambiente ---
        resultado_ambiente = desplegar_ambiente(config)
        config = resultado_ambiente["Config"]

        # Si HU00 truena, se reintenta todo el flujo desde cero (igual que AA).
        if resultado_ambiente["SystemException"]:
            reintentos += 1
            write_log(
                "Error",
                f"Main: fallo HU00 (intento {reintentos}/{MAXIMO_REINTENTOS}): {resultado_ambiente['SystemException']}",
                TASK_NAME, config,
            )
            if reintentos >= MAXIMO_REINTENTOS:
                _enviar_correo_fatal(config, resultado_ambiente["SystemException"])
                return
            continue

        if not resultado_ambiente["Excecution"]:
            # Stop silencioso (ej. RutaBase no existe): no es error, no reintenta.
            return

        # --- Determinar cual HU esta activa en ControlHU (maquina de estados en BD) ---
        esquema = config.get("Scheme", "[ResolucionesFiscales]")
        conn = conectar_bd(config)
        cursor = conn.cursor()
        cursor.execute(f"SELECT TOP(1) HU FROM {esquema}.ControlHU WHERE Activa = 1 ORDER BY HU")
        fila = cursor.fetchone()
        conn.close()

        if fila is None:
            write_log("Warning", "Main: no hay ninguna HU activa en ControlHU", TASK_NAME, config)
            return

        hu_actual = str(fila[0])
        ejecutor = _EJECUTORES.get(hu_actual)
        if ejecutor is None:
            write_log("Error", f"Main: HU desconocida en ControlHU: {hu_actual}", TASK_NAME, config)
            return

        # --- Ejecutar la HU activa (HU01/02/03) ---
        resultado = ejecutor(config)
        config = resultado["Config"]

        # Si la HU truena, se reintenta todo el flujo desde HU00 (no solo esta HU).
        if resultado["SystemException"]:
            reintentos += 1
            write_log(
                "Error",
                f"Main: fallo HU{hu_actual} (intento {reintentos}/{MAXIMO_REINTENTOS}): {resultado['SystemException']}",
                TASK_NAME, config,
            )
            if reintentos >= MAXIMO_REINTENTOS:
                _enviar_correo_fatal(config, resultado["SystemException"])
                return
            continue

        # --- Exito: mover el puntero de ControlHU a la siguiente HU y terminar la pasada ---
        conn = conectar_bd(config)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {esquema}.ControlHU SET Activa = 0")
        cursor.execute(
            f"UPDATE {esquema}.ControlHU SET Activa = 1, Maquina = ?, FechaModificacion = GETDATE() WHERE HU = ?",
            (config.get("Usuario", ""), resultado["IdHU"]),
        )
        conn.commit()
        conn.close()

        write_log(
            "Info",
            f"Main: HU{hu_actual} finalizó correctamente, siguiente HU activa = {resultado['IdHU']}",
            TASK_NAME, config,
        )
        return


if __name__ == "__main__":
    ejecutar_una_pasada()
