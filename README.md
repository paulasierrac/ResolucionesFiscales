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

## Comparación con el bot original (Automation Anywhere)

El export original (`resolucionesFiscales.zip`) traía 1 orquestador
(`Main_ResolucionesFiscales`), 4 sub-bots (`HU00`–`HU03`) y 2 funciones globales
reutilizables (`WriteLog`, `DatabaseToExcel`). Se migró leyendo esos exports (JSON de
Automation Anywhere A360) paso a paso y replicando la lógica de negocio; abajo el
detalle de qué se tradujo tal cual y qué se decidió cambiar a propósito.

### Mapeo de lógica por HU

| AA | Python | Lógica preservada |
|----|--------|--------------------|
| `Main_ResolucionesFiscales` | [main.py](main.py) | Máquina de estados sobre `ControlHU` (cuál HU corre, reintentos de todo el flujo si falla). |
| `HU00_DespliegeAmbiente` | [HU/hu00_desplegar_ambiente.py](HU/hu00_desplegar_ambiente.py) | Upsert de 6 claves bootstrap en `Parametros`, carga completa de `Parametros` a memoria, validación de `RutaBase`, creación de subcarpetas, purga de logs por `MesesRepositorioLog`. |
| `HU01_CargarInsumos` | [HU/hu01_cargar_insumos.py](HU/hu01_cargar_insumos.py) | Hard-stops si falta la carpeta/archivo `Parametros.xlsx` (correos 1/2), soft-stop si falta `HomologacionPrefijo.xlsx` (correo 3), validación de hojas requeridas (correo 4), recarga de `Correos` y `HomologacionPrefijo` con limpieza de `Prefijo`. |
| `HU02_ProcesarPdfResoluciones` | [HU/hu02_procesar_pdf_resoluciones.py](HU/hu02_procesar_pdf_resoluciones.py) | Clasificación por número de hojas (2-4 válidas, correo 5 si no hay PDFs, correo 6 si hay inválidos), inserción en `TicketInsumo`, archivo de PDFs en carpeta fechada. |
| `HU03_GenerarReporteYNotificarCasos` | [HU/hu03_generar_reporte_notificar_casos.py](HU/hu03_generar_reporte_notificar_casos.py) | Depuración de registros incompletos (correo 7), homologación de `Prefijo` (correo 8 si no hay match), reporte diario (correo 9), consolidado, reporte mensual de vencimientos (correo 11) gatillado por `DiaReporteVencidos`. |
| `GlobalFunctions/ConfigFunctions/WriteLog` | `write_log()` en [Funciones/utils.py](Funciones/utils.py) | Mismo formato de línea (`timestamp \| Estado \| Mensaje \| CodigoRobot \| TaskName \| Maquina`), mismo nombre de archivo (`Log_<maquina>_<usuario>_<yyyyMMdd>.txt`), gateado por `ActivarLog`. |
| `GlobalFunctions/Excel/DatabaseToExcel` | `pandas.read_sql(...).to_excel(...)` inline en HU03 | Reemplaza la automatización COM de Excel (VBScript + `Excel.Application`) de AA — innecesaria en Python, `pandas`/`openpyxl` escriben `.xlsx` directo. |

### Tabla `Correos` — mapeo de `Num_Correo` (igual en ambos)

| Num_Correo | Caso |
|---|---|
| 0 | Pie/firma compartida, se agrega a todos los correos |
| 1 | No existe la carpeta `Parametros` |
| 2 | No existe el archivo `Parametros.xlsx` |
| 3 | No existe `HomologacionPrefijo.xlsx` (no detiene la ejecución) |
| 4 | Falta una hoja requerida en `Parametros.xlsx` |
| 5 | No hay PDFs para procesar |
| 6 | Hay PDFs con cantidad de hojas inválida |
| 7 | Registros de `TicketInsumo` con datos incompletos (se eliminan) |
| 8 | Hay `Prefijo` sin homologar en `HomologacionPrefijo` |
| 9 | Reporte diario generado |
| 10 | Inicio de ejecución del bot |
| 11 | Reporte de resoluciones que vencerán generado |

### Diferencias deliberadas frente al bot original

- **Extracción de PDF**: AA usaba `extractField` por coordenadas de píxel fijas (AREA).
  El Python port usa `pdfplumber` + regex ancladas a las etiquetas impresas del
  formulario DIAN (`29. Establecimiento`, `30. Modalidad`, etc.) — más robusto, no
  depende de calibrar coordenadas por resolución/render. Ver [Funciones/pdf_resoluciones.py](Funciones/pdf_resoluciones.py).
- **Inserción en `TicketInsumo`**: AA insertaba las 11 filas candidatas de cada hoja y
  después borraba por SQL las que quedaban vacías. El port solo inserta las filas que
  ya vienen con datos — mismo resultado final, sin el paso intermedio.
- **Envío de correo**: AA usaba Exchange Web Services con OAuth (Azure AD
  client-credentials). El port usa `smtplib` con las credenciales SMTP de `.env`/Vault
  (decisión tomada con el negocio, ver commits de esta migración).
- **Orden de HU01**: en AA, el correo de "inicio de ejecución" (`Num_Correo=10`) se
  envía *antes* de recargar `Correos`. En el port se invirtió — se envía *después* de
  la recarga — porque si no, en cada corrida usa los destinatarios que hubiera *antes*
  de esa recarga (en dev, mandaba a las direcciones reales del seed en vez de a las de
  prueba). Ver commit de este fix.
- **Modelo de ejecución**: AA corría en un bucle infinito dentro de un mismo proceso,
  ciclando `HU00→1→2→3→1...` sin parar salvo error. El port ejecuta **una pasada por
  invocación** (procesa la HU activa y termina); un Task Scheduler externo debe
  invocarlo periódicamente. Decisión tomada con el negocio para simplificar la
  operación en Windows.
- **`TablaHomologacionPrefijos`**: el seed de `Parametros` trae `[HomologacionPrefijos]`
  (plural), que no coincide con la tabla real `HomologacionPrefijo` (singular) — bug
  del seed original. El port usa el nombre de tabla correcto de forma literal en vez
  de leerlo de `Parametros`, para no heredar el error.

## Instalación y ejecución

```
pip install -r requirements.txt
python main.py
```

Requiere Python 3.10+ y el [ODBC Driver 17 (o superior) para SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
instalado en el equipo.

> `.env` está en `.gitignore` (contiene secretos) y por lo tanto **no viaja con
> `git pull`**. Cada máquina/VM donde se ejecute el proceso necesita su propio
> `.env` creado manualmente (mismas claves que en desarrollo: `VAULT_URL`,
> `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`, `DB_SCHEMA`, `RPA_DEBUG`, `SMTP_*`).

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

## Estado actual

Probado de punta a punta contra la BD de **desarrollo** (`RPA_DEBUG=True`):

- ✅ HU00 (desplegar ambiente): bootstrap de `Parametros`, validación de carpetas, purga de logs.
- ✅ HU01 (cargar insumos): recarga `Correos` (13 filas) y `HomologacionPrefijo` (4076 filas) desde Excel.
- ✅ HU03 (reporte/notificación): genera el consolidado y notifica por correo.
- ⏳ HU02 (procesar PDFs) — falta confirmar en la BD de desarrollo con PDFs reales.

## Pendiente / por verificar

- Correr HU02 contra la BD de desarrollo con PDFs reales y confirmar los datos extraídos en `TicketInsumo`.
- Confirmar que ningún correo de prueba llegue a destinatarios reales de negocio: los
  primeros envíos de una corrida usan lo que ya esté en `[Correos]` en ese momento —
  si la BD de dev nunca se ha recargado desde el `Parametros.xlsx` de pruebas, esos
  primeros correos pueden usar destinatarios viejos/reales del seed.
