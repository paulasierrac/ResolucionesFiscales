# ResolucionesFiscales

Migración a Python del bot RPA `ResolucionesFiscales` (originalmente en Automation
Anywhere). El bot procesa PDFs de "Autorización de Numeración de Facturación" de la
DIAN que llegan a una carpeta de red, homologa cada resolución contra los centros/
direcciones de Colsubsidio, y genera reportes y notificaciones por correo.

## Estructura del proceso

El proceso original se divide en 3 "HU" (historias de usuario) más un orquestador,
coordinadas por la tabla `[ResolucionesFiscales].[ControlHU]` (cada fila indica si
esa HU está activa; solo una debe estarlo a la vez):

| HU | Módulo Python | Qué hace |
|----|----------------|----------|
| 00 | [HU/hu00_desplegar_ambiente.py](HU/hu00_desplegar_ambiente.py) | Siembra/carga `[Parametros]` a memoria, valida `RutaBase`, crea subcarpetas, purga logs viejos. Corre siempre antes de cualquier HU. |
| 01 | [HU/hu01_cargar_insumos.py](HU/hu01_cargar_insumos.py) | Recarga `[Correos]` (plantillas de notificación) y `[HomologacionPrefijo]` desde `Parametros.xlsx` / `HomologacionPrefijo.xlsx`. |
| 02 | [HU/hu02_procesar_pdf_resoluciones.py](HU/hu02_procesar_pdf_resoluciones.py) | Escanea PDFs en `RutaBase`, valida hojas (2-4 válidas), extrae los datos ([Funciones/pdf_resoluciones.py](Funciones/pdf_resoluciones.py)) e inserta en `[TicketInsumo]`, archiva los PDFs. |
| 03 | [HU/hu03_generar_reporte_notificar_casos.py](HU/hu03_generar_reporte_notificar_casos.py) | Depura datos incompletos, homologa `Prefijo`, genera reporte diario + consolidado + reporte mensual de vencimientos, notifica por correo. |

[main.py](main.py) es el orquestador: ejecuta **una pasada** (corre la HU
actualmente activa en `ControlHU`, con reintentos si falla, y actualiza el
puntero a la siguiente HU) y termina. A diferencia del bot original en
Automation Anywhere (que quedaba en un bucle infinito dentro de un mismo
proceso), aquí un Task Scheduler externo debe invocar `python main.py`
periódicamente para que el ciclo 01→02→03 avance.

## Instalación y ejecución

```
pip install -r requirements.txt
python main.py
```

Requiere Python 3.10+ y el [ODBC Driver 17 (o superior) para SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
instalado en el equipo.

## Configuración

- **Azure Key Vault** ([Config/Configuracion.py](Config/Configuracion.py)): trae
  las credenciales de SQL Server. Requiere en `.env`: `VAULT_URL`, `TENANT_ID`,
  `CLIENT_ID`, `CLIENT_SECRET`.
- **`RPA_DEBUG`** (`.env`): si es `True`, el proceso usa las credenciales de BD
  `Dev-*` del Vault (ambiente de **desarrollo**); si es `False`, usa `Prod-*`.
  Estos secretos son compartidos entre proyectos (`environment=dev`/`prod`).
- **`DB_SCHEMA`** (`.env`): debe ser `ResolucionesFiscales`.
- El resto de parámetros del proceso (rutas de red, nombres de archivo, destinatarios
  de correo, etc.) vive en la tabla `[Parametros]` y se carga en memoria en HU00 —
  no se edita en código.
- Envío de correo: `smtplib` vía `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`
  en `.env` (el bot original usaba Exchange/OAuth; se decidió no replicar eso).

## Base de datos

**Única fuente de verdad del esquema:** [ResolucionesFiscales_Completo.sql](ResolucionesFiscales_Completo.sql)
(DDL + seed del esquema `ResolucionesFiscales`: `Parametros`, `ControlHU`, `Correos`,
`HomologacionPrefijo`, `TicketInsumo`). Ejecutarlo contra la BD de dev/prod antes
de correr el proceso.

> Nota: el seed trae `TablaHomologacionPrefijos = '[HomologacionPrefijos]'` (plural),
> pero la tabla real es `HomologacionPrefijo` (singular). El código usa el nombre
> correcto de forma literal; vale la pena corregir el seed también.

## Extracción de PDF

[Funciones/pdf_resoluciones.py](Funciones/pdf_resoluciones.py) usa `pdfplumber`
para extraer el texto de cada página y ancla los campos por las etiquetas impresas
del formulario DIAN (form 1876) en vez de replicar coordenadas de píxel de
Automation Anywhere. Calibrado y validado contra los PDFs reales de ejemplo en
`RESOLUCIONES RPA\2026\06\10\`.

## Pendiente / por verificar

- Correr el pipeline completo contra la BD de desarrollo (no se pudo probar desde
  el entorno donde se hizo la migración por falta de acceso de red al servidor).
- Confirmar la estructura real de carpetas bajo `RutaBase` (la carpeta de ejemplo
  no tiene el segmento `Reportes` que definiría `CarpetaReportes`).
