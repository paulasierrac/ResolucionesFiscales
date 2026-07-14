"""
================================================================================
Extraccion de datos del PDF "Autorizacion Numeracion de Facturacion" (DIAN, form 1876)
Propiedad de Colsubsidio
================================================================================

Reemplaza la extraccion por coordenadas de pixel de Automation Anywhere por una
extraccion de texto + regex: el formulario DIAN es fijo y pdfplumber devuelve el
texto de cada pagina ya agrupado por bloque (etiqueta, valor), lo que permite
anclar cada campo por las etiquetas impresas ("29. Establecimiento", "30. Modalidad...")
en vez de coordenadas fisicas fragiles.

Pagina 1: numero de formulario (-> Resolucion) y fecha de formalizacion (-> FechaInicioRes).
Pagina 2..N: tabla de hasta 11 filas por pagina (Establecimiento/Modalidad/Prefijo/
Desde/Hasta/Vigencia/Tipo solicitud); solo las filas con datos se reportan.

Mapeo de columnas confirmado contra el bot original (HU02_ProcesarPdfResoluciones):
  DB Tipo      <- PDF Modalidad
  DB Direccion <- PDF Establecimiento
  DB Meses     <- PDF Vigencia
"""

import re
from datetime import date

import pdfplumber

_RE_NUM_FORMULARIO = re.compile(r"formulario\s+(\d+)")
_RE_FECHA_FORMALIZACION = re.compile(r"Fecha formalizaci\S*\s+([\d\s\-/:]+)")
_RE_FILA_DATOS = re.compile(
    r"^(?P<modalidad>.+?)\s+(?P<cod1>\d+)\s+(?P<prefijo>\S+)\s+"
    r"(?P<desde>[\d,]+)\s+(?P<hasta>[\d,]+)\s+(?P<vigencia>\d+)\s+"
    r"(?P<tipo_solicitud>.+?)\s+(?P<cod2>\d+)$"
)


def contar_paginas(ruta_pdf: str) -> int:
    with pdfplumber.open(ruta_pdf) as pdf:
        return len(pdf.pages)


def _sumar_meses(fecha: date, meses: int) -> date:
    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, 28)
    return date(anio, mes, dia)


def _extraer_pagina1(texto: str) -> dict:
    m_form = _RE_NUM_FORMULARIO.search(texto or "")
    m_fecha = _RE_FECHA_FORMALIZACION.search(texto or "")
    num_formulario = m_form.group(1) if m_form else ""
    fecha_raw = m_fecha.group(1).strip() if m_fecha else ""
    fecha_sin_espacios = fecha_raw.replace(" ", "")
    fecha_inicio = fecha_sin_espacios.split("/")[0] if fecha_sin_espacios else ""
    return {"Resolucion": num_formulario, "FechaInicioRes": fecha_inicio}


def _limpiar_prefijo(prefijo: str) -> str:
    prefijo = prefijo.strip().replace(" ", "").replace("-", "")
    if prefijo and prefijo[0] == "0":
        prefijo = "*" + prefijo
    return prefijo


def _extraer_filas_tabla(texto: str) -> list:
    """Parsea una pagina de tabla (29. Establecimiento / 30. Modalidad...) y
    retorna solo las filas de las 11 que si tienen datos."""
    bloques = re.split(r"\n(?=29\. Establecimiento)", texto or "")
    filas = []
    for bloque in bloques:
        lineas = [l for l in bloque.splitlines() if l.strip()]
        if not lineas or not lineas[0].startswith("29. Establecimiento"):
            continue

        establecimiento = None
        fila_datos = None
        for linea in lineas[1:]:
            if re.match(r"^\d+$", linea.strip()) or linea.startswith("30. Modalidad"):
                continue
            if establecimiento is None:
                establecimiento = linea.strip()
                continue
            fila_datos = linea.strip()
            break

        if not (establecimiento and fila_datos):
            continue

        m = _RE_FILA_DATOS.match(fila_datos)
        if not m:
            # Formato inesperado: se reporta igual para que HU02 lo trate como
            # PDF no identificable (equivalente al caso "el bot no puede identificar").
            filas.append({"_sin_parsear": fila_datos, "Direccion": establecimiento})
            continue

        d = m.groupdict()
        filas.append({
            "Direccion": establecimiento,
            "Tipo": d["modalidad"].strip(),
            "Prefijo": _limpiar_prefijo(d["prefijo"]),
            "NumInicial": d["desde"].replace(",", ""),
            "NumFinal": d["hasta"].replace(",", ""),
            "Meses": d["vigencia"],
        })
    return filas


def extraer_datos_pdf(ruta_pdf: str) -> list:
    """
    Extrae los datos de un PDF de Resolucion Fiscal DIAN.

    Retorna una lista de dicts (uno por fila con datos en las tablas de la
    pagina 2 en adelante), cada uno con las claves:
    Resolucion, FechaInicioRes, FechaVencimientoRes, Prefijo, NumInicial,
    NumFinal, Tipo, Direccion, Meses.

    Lista vacia => PDF sin datos reconocibles (equivalente a que AA borre
    todas las filas candidatas por venir vacias).
    """
    with pdfplumber.open(ruta_pdf) as pdf:
        datos_pagina1 = _extraer_pagina1(pdf.pages[0].extract_text())
        filas = []
        for page in pdf.pages[1:]:
            filas.extend(_extraer_filas_tabla(page.extract_text()))

    resultado = []
    for fila in filas:
        if "_sin_parsear" in fila:
            resultado.append({**datos_pagina1, **fila})
            continue

        fecha_vencimiento = ""
        if datos_pagina1["FechaInicioRes"] and fila["Meses"].isdigit():
            try:
                fecha_ini = date.fromisoformat(datos_pagina1["FechaInicioRes"])
                fecha_vencimiento = _sumar_meses(fecha_ini, int(fila["Meses"])).isoformat()
            except ValueError:
                fecha_vencimiento = ""

        resultado.append({
            **datos_pagina1,
            "FechaVencimientoRes": fecha_vencimiento,
            **fila,
        })
    return resultado
