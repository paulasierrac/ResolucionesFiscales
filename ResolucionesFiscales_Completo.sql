-- Crear esquema
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'ResolucionesFiscales')
BEGIN
    EXEC('CREATE SCHEMA ResolucionesFiscales');
END
GO

-- Tablas
CREATE TABLE ResolucionesFiscales.Parametros(
    ID INT IDENTITY(1,1) NOT NULL,
    Nombre VARCHAR(MAX) NULL,
    Valor VARCHAR(MAX) NULL,
    Descripcion VARCHAR(MAX) NOT NULL
);
GO

CREATE TABLE ResolucionesFiscales.ControlHU(
    HU INT NULL,
    NombreHU VARCHAR(MAX) NULL,
    Activa BIT NULL,
    Maquina VARCHAR(MAX) NULL,
    FechaModificacion DATETIME NOT NULL
);
GO

CREATE TABLE ResolucionesFiscales.Correos(
    Num_Correo VARCHAR(MAX) NULL,
    HU VARCHAR(MAX) NULL,
    Actividad VARCHAR(MAX) NULL,
    Caso VARCHAR(MAX) NULL,
    Para VARCHAR(MAX) NULL,
    Asunto VARCHAR(MAX) NULL,
    Contenido VARCHAR(MAX) NULL,
    ArchivoAdjunto VARCHAR(MAX) NOT NULL
);
GO

CREATE TABLE ResolucionesFiscales.HomologacionPrefijo(
    ID INT IDENTITY(1,1) NOT NULL,
    Prefijo VARCHAR(MAX) NULL,
    Centro VARCHAR(MAX) NULL,
    CentroBeneficio VARCHAR(MAX) NULL,
    NombreEnBase VARCHAR(MAX) NULL,
    Tipo VARCHAR(MAX) NULL,
    Direccion VARCHAR(MAX) NULL,
    FechaModificacion DATE NOT NULL
);
GO

CREATE TABLE ResolucionesFiscales.TicketInsumo(
    IdTicket INT IDENTITY(1,1) NOT NULL,
    FechaInicio DATETIME NOT NULL,
    FechaModificacion DATETIME NULL,
    FechaFin DATETIME NULL,
    Estado INT NULL,
    Observacion VARCHAR(200) NULL,
    Centro VARCHAR(200) NULL,
    CentroBeneficio VARCHAR(200) NULL,
    NombreBase VARCHAR(200) NULL,
    Resolucion VARCHAR(MAX) NULL,
    FechaInicioRes VARCHAR(MAX) NULL,
    FechaVencimientoRes VARCHAR(MAX) NULL,
    Prefijo VARCHAR(MAX) NULL,
    NumInicial VARCHAR(MAX) NULL,
    NumFinal VARCHAR(MAX) NULL,
    Tipo VARCHAR(MAX) NULL,
    Direccion VARCHAR(MAX) NULL,
    Meses VARCHAR(MAX) NULL,
    TipoHomologacion VARCHAR(MAX) NULL,
    DireccionHomologacion VARCHAR(MAX) NULL,
    NombrePdf VARCHAR(MAX) NOT NULL
);
GO

-- 1. insert_parametros.sql
INSERT INTO ResolucionesFiscales.Parametros
(
    Nombre,
    Valor,
    Descripcion
)
VALUES
('RutaRed', '\\192.168.50.169\Division Mercadeo Social\Informes Financieros\Finanzas Supermercados\RESOLUCIONES RPA', 'Variable global del proceso'),
('RutaRedLogs', '\\192.168.50.169\Division Mercadeo Social\Informes Financieros\Finanzas Supermercados\RESOLUCIONES RPA\Logs\', 'Variable global del proceso'),
('Scheme', '[ResolucionesFiscales]', 'Variable global del proceso'),
('PathLog', '\\192.168.50.169\Division Mercadeo Social\Informes Financieros\Finanzas Supermercados\RESOLUCIONES RPA\Logs\', 'Variable global del proceso'),
('TablaParametros', '[Parametros]', 'Variable global del proceso'),
('CarpetaParametros', 'Parametros', 'Variable HU01'),
('NombreArchivoParametros', 'Parametros.xlsx', 'Nombre del Excel Parametros'),
('HojasDeParametros', 'Correos', 'Variable HU01, Nombre Paginas Excel Parametros'),
('CarpetasRutaRed', 'Logs', 'Nombre de carpetas indispensables para el proceso'),
('MesesRepositorioLog', '12', 'Variable HU0, me indica la cantidad de meses que se conservaran de los LOGS'),
('Server', '192.168.50.57', 'Variable global del proceso'),
('DataBase', 'RPA', 'Variable global del proceso'),
('Usuario', 'CGRPA052', 'Variable global del proceso'),
('RutaLocal', 'C:\Users\CGRPA052', 'Variable global del proceso'),
('RutaBase', '\\192.168.50.169\Division Mercadeo Social\Informes Financieros\Finanzas Supermercados\RESOLUCIONES RPA', 'Ruta base suministrada por el negocio, allí se depositan los PDFs y se genera la estructura de carpetas para los reportes'),
('CarpetaReportes', 'Reportes', 'Nombre de carpeta donde se genera la estructura de carpetas para depositar los archivos generados'),
('CarpetaConsolidado', 'Consolidado', 'Nombre de carpeta donde se genera el consolidado diario'),
('CarpetaValidarPdf', 'ValidarPDF', 'Nombre de carpeta donde lee la cantidad de hojas de cada PDF'),
('NombreArchivoReporteResoluciones', 'ReporteResolucionesFiscales', 'Nombre del archivo donde se dejaran todos los registros procesados de Resoluciones Fiscales'),
('NombreArchivoConsolidadoResoluciones', 'ConsolidadoResolucionesFiscales', 'Nombre del archivo donde se deja el consolidado de las resoluciones procesadas'),
('TablaCorreos', '[Correos]', 'Nombre de la tabla [Correos]'),
('TablaParametros', '[Parametros]', 'Nombre de la tabla [Parametros]'),
('TablaTicketInsumo', '[TicketInsumo]', 'Nombre de la tabla [TicketInsumo]'),
('Scheme', '[ResolucionesFiscales]', 'Variable global, schema del proceso'),
('MailTo', 'carlbejrod@colsubsidio.com;cgghurpm@colsubsidio.com', 'Variable global, correo de notificaciones del proceso'),
('CarpetaPdfInvalido', 'PDFsInvalidos', 'Nombre de carpeta donde se depositan los PDFs que no cumplieron la estructura definida'),
('NombreArchivoHomologacionPrefijo', 'HomologacionPrefijo.xlsx', 'Nombre del Excel HomologacionPrefijo.xlsx'),
('TablaHomologacionPrefijos', '[HomologacionPrefijos]', 'Nombre de la tabla [HomologacionPrefijos]'),
('PalabraClaveResElectronica', 'ELECTRONICA,ELECTRÓNICA', 'Variable HU2, lista de dos palabras que indican cuáles son Resoluciones Electrónicas'),
('DiaReporteVencidos', '10', 'Variable HU3, corresponde al día del mes en que se generará el reporte con las resoluciones que se vencerán'),
('NombreArchivoResolucionesQueVenceran', 'ResolucionesQueVenceran', 'Variable HU3, nombre del archivo donde se dejan las resoluciones que se vencerán el próximo mes'),
('CarpetaReporteResolucionesQueVenceran', 'ReporteResolucionesQueVenceran', 'Nombre de carpeta donde se dejan los archivos con las resoluciones próximas a vencer'),
('CodigoRobot', 'RPA_LISA', 'Nombramiento del bot para registrar en el LOG'),
('ActivarLog', 'True', 'Boolean que indica si se realiza la ejecución del Write Log'),
('StatusDelCargue', 'No se a cargado a BD', 'Variable HU03. Me indica si el insumo Jobs ya se descargó a BD o no'),
('StatusDelCargue', 'No se a cargado a BD', 'Variable HU03. Me indica si el insumo Jobs ya se descargó a BD o no');

-- 2. insert_controlhu.sql
INSERT INTO ResolucionesFiscales.ControlHU
(
    HU,
    NombreHU,
    Activa,
    Maquina,
    FechaModificacion
)
VALUES
(1, 'CargarInsumos', 0, 'CGGRPARPM', '2023-11-21 20:02:39.203'),
(2, 'ProcesarPdfsResoluciones', 0, 'CGRPA052', '2026-07-13 20:01:36.970'),
(3, 'GenerarReporteYNotificarCasos', 0, 'CGRPA052', '2026-07-13 20:01:44.427');

-- 3. insert_correos.sql
INSERT INTO ResolucionesFiscales.Correos (Num_Correo, HU, Actividad, Caso, Para, Asunto, Contenido, ArchivoAdjunto)
VALUES
('0','1, 2, 3','','Para insertar el final del correo cuando es necesario incluir una variables en el contenido del correo ','No aplica','No aplica','Atentamente,
 
RPA_LISA','No aplica'),
('1','1','','No existe la carpeta Parametros','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: No existe la carpeta Parametros','Buen día, 
 
No fue posible realizar la ejecución del BOT, esto debido a que no se tiene acceso a la carpeta Parametros, la cual es indispensable para la ejecución correcta del BOT.
 
 La ruta consultada por el bot es la siguiente:','No aplica'),
('2','1','','No existe el archivo Parametros.xlsx','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: No existe el archivo Parametros.xlsx','Buen día, 
 
No fue posible realizar la ejecución del BOT, esto debido a que no se encuentra el archivo Parametros.xlsx. Por favor validar la existencia de este archivo el cual es indispensable para que en la próxima ejecución se pueda realizar correctamente el proceso. 
 
 El archivo esperado por el bot debe encontrarse en la siguiente ruta de red:','No aplica'),
('3','1','','No existe el archivo HomologacionPrefijos.xlsx','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: No existe el archivo HomologacionPrefijos.xlsx','Buen día, 
 
No fue posible realizar la ejecución del BOT, esto debido a que no se encuentra el archivo HomologacionPrefijos.xlsx. Por favor validar la existencia de este archivo el cual es indispensable para que en la próxima ejecución se pueda realizar correctamente el proceso. 
 
 El archivo esperado por el bot debe encontrarse en la siguiente ruta de red:','No aplica'),
('4','1','','No existe la hoja Correos','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: No existe la hoja Correos en el archivo Parametros','Buen día, 
 
No fue posible realizar la ejecución del BOT, esto debido a que no se encontro la Hoja Correos del insumo Parametros.xlsx . Por favor validar la existencia de esta hoja, esto con el fin de que las notificaciones realizadas por el bot cumplan con los parametros establecidos en ese archivo.
 
Atentamente,
 
RPA_LISA','No aplica'),
('5','2','','No existen PDFs para procesar ','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: No existen PDFs para procesar el día de hoy','Buen día, 
 
Se finalizó la ejecución sin procesar ninguna resolución fiscal, esto debido a que no existe ningun PDF en la ruta definida para el BOT.

Atentamente,
 
RPA_LISA','No aplica'),
('6','2','','Los PDFs presentan una cantidad de hojas diferentes a las esperadas (igual a 1 o mayor a 4)','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: Existen PDFs con hojas diferentes a las esperadas','Buen día, 
 
Se identificaron PDFs que no cumplen con el número de hojas definidas para el bot. Los archivos que no cumplen esta condición son los siguientes:','No aplica'),
('7','3','','El archivo procesado contiene información que el bot no puede identificar','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: Existen PDFs que contienen información que el bot no puede identificar','Buen día, 
 
Se presentaron inconsistencias en el procesamiento de algunos PDFs de resoluciones fiscales, esto se debe a que el archivo trae algún campo nuevo o el archivo PDF presenta alguna diferencia al PDF definido para el BOT. Cabe resaltar que la información de estas resoluciones se eliminara de la Base de datos despues de haber recibido esta notificación.
 
Los PDFs  que presentaron esta inconsistencia con los siguientes:','No aplica'),
('8','3','','En algun PDF existe un registro con un Prefijo que no se encuentra en la tabla [HomlogacionPrefijo]','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com','RPA_LISA: Existen registros que tienen un prefijo nuevo','Buen día, 
 
Durante el procesamiento de las resoluciones se identificaron Prefijos que no tienen homologación en la tabla [HomologacionPrefijos] cargada a partir del archivo con el mismo nombre.
 
Los prefijos que no se encontraron en la tabla [HomologacionPrefijos] son los siguientes:','No aplica'),
('9','3','','Se notifica el archivo de ReporteResolucionesFiscales generado a partir de los archivos procesados en cada ejecución','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com; dianjimm@colsubsidio.com','RPA_LISA: Se genero el archivo ReporteResolucionesFiscales.xlsx','Buen día, 

Se completo de forma exitosa el procesamiento de los PDFs de ResolucionesFiscales, el archivo con las Resoluciones procesadas se encuentra n la ruta de red:','Si aplica (archivo ReporteResolucioneFiscales.xlsx)'),
('10','1','','Comienza el bot','carlbejrod@colsubsidio.com;cgghurpm@colsubsidio.com;Resoluciones_fiscales_med@colsubsidio.com;johamunb@colsubsidio.com','RPA_LISA: Se da comienzo a la ejecución del bot','Buen día, 
 
Se informa que se dara comienzo a la ejecución del bot RPA_LISA para el día de hoy.
 
 
Atentamente,
 
RPA_LISA','No aplica'),
('11','3','','Se notifican las resoluciones que venceran el proximo mes','Resoluciones_fiscales_med@colsubsidio.com; johamunb@colsubsidio.com; dianjimm@colsubsidio.com','RPA_LISA: Se genero reporte con las resoluciones que se venceran','Buen día, 
 
En el archivo adjunto se encuentran las resoluciones que se encuentran proximas a vencer.
 
 
Atentamente,
 
RPA_LISA','Si aplica (ArchivoResolucionesQueVenceran.xlsx)'),
('12','3','','Fin del bot ','Jamebarrub@colsubsidio.com','','','');

-- 4. insert_homologacionprefijo.sql
INSERT INTO ResolucionesFiscales.HomologacionPrefijo
(Prefijo, Centro, CentroBeneficio, NombreEnBase, Tipo, Direccion, FechaModificacion)
VALUES
('3634','D006','MINIM QUIROGA','Drog. Quiroga','Electrónica - Cont','CR 23 31 C 00 S','2026-07-13'),
('3635','D006','MINIM QUIROGA','DROG QUIROGA','Electrónica','CR 23 C 31 B 79 S','2026-07-13'),
('1508','D013','TIENDA 20 DE JULIO','Drog. 20 de Julio','Electrónica','CL 27 S 5 74','2026-07-13'),
('1515','D013','TIENDA 20 DE JULIO','TIENDA 20 DE JULIO','Electrónica - NCR','CL 27 S 5 74','2026-07-13'),
('1517','D013','TIENDA 20 DE JULIO','TIENDA 20 DE JULIO','Electrónica - NCR','CL 27 S 5 74','2026-07-13'),
('1524','D013','TIENDA 20 DE JULIO','Drog. 20 de Julio','Electrónica - Cont','CL 27 S 5 74','2026-07-13'),
('2007','D015','Drog. Capilla','DROG LA CAPLL','Electrónica','CR 13 49 55','2026-07-13'),
('2011','D015','Drog. Capilla','DROG LA CAPLL','Electrónica - NCR','CR 13 49 55','2026-07-13'),
('2012','D015','Drog. Capilla','DROG LA CAPLL','Electrónica - NCR','CR 13 49 55','2026-07-13'),
('2014','D015','Drog. Capilla','DROG. CAPILLA ','Electrónica - Cont','CR 13 49 55','2026-07-13');

-- 5. insert_ticketinsumo.sql
INSERT INTO ResolucionesFiscales.TicketInsumo
(FechaInicio,FechaModificacion,FechaFin,Estado,Observacion,Centro,CentroBeneficio,NombreBase,Resolucion,FechaInicioRes,FechaVencimientoRes,Prefijo,NumInicial,NumFinal,Tipo,Direccion,Meses,TipoHomologacion,DireccionHomologacion,NombrePdf)
VALUES
('2022-11-23 20:07:33.900','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D032','Droguería Santa Isabel','Supermercado Santa Isabel','18764039794487','2022-11-18','2024-05-18','1015','24593','1000000','FACTURA ELECTRÓNICA DE VENTA','SUPERMERCADO SANTA ISABEL CL 1 C   27   08','18','Electroníca','CL 1 C 27 08','18764039794487 Superm Sta Isabel.pdf'),
('2022-11-23 20:08:10.993','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D008','Drog. Alhambra','DROG ALHAMBRA','18764039799083','2022-11-18','2024-05-18','1604','30899','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA COLSUBSIDIO ALHAMBRA AV 116   45   93','18','Electroníca','AV 116 45 93','18764039799083 Drog Alhambra.pdf'),
('2022-11-23 20:12:13.100','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D379','Drog Vida Centro Profesional','DROGUERIA VIDA CENTRO PROFESIONAL - CALI','18764039825771','2022-11-18','2024-05-18','AU04','8853','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA VIDA CENTRO PROFESIONAL  CALI CL 5 D   38 A   35 LC 116','18','Electroníca','CL 5 D 38 A 35 LC 116','18764039825771 Drog vida centro profesional.pdf'),
('2022-11-23 20:12:21.680','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D069','Droguería Cajica','Supermercado Cajica','18764039873214','2022-11-21','2024-05-21','B512','49498','1000000','FACTURA ELECTRÓNICA DE VENTA','CENTRO DE SERVICIOS CAJICA CR 5   2    85 SUR','18','Electroníca','CR 5 2 85 SUR','18764039873214 Supermercado Cajica.pdf'),
('2022-11-23 20:12:29.110','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D080','Drog. Tunal','DROG TUNAL','18764039873593','2022-11-21','2024-05-21','B803','19619','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA CENTRO COMERCIAL CIUDAD TUNAL CC CIUDAD TUNAL LC 2120','18','Electroníca','CC CIUDAD TUNAL LC 2120','18764039873593 DROG TUNAL.pdf'),
('2022-11-23 20:16:13.450','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D539','DROGUERÍA CC MAYORCA','DROGUERÍA CC MAYORCA','18764039885791','2022-11-21','2024-05-21','ID02','11543','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA CENTRO COMERCIAL MAYORCA  - SABANETA CL 51 SUR   48   57 LC 3013','18','Electroníca','CALLE 51 SUR N° 48 - 57, SABANETA LOCAL 3013','18764039885791 Drog CC Mayorca.pdf'),
('2022-11-23 20:16:21.603','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D414','Drog Av Circunvalar - Pereira','DROGUERIA AV CIRCUNVALAR- PEREIRA','18764039886055','2022-11-21','2024-05-21','CG05','39126','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA AV CIRCUNVALAR   PEREIRA CR 13   11   26','18','Electroníca','CR 13 11 26','18764039886055  DROGUERIA AV CIRCUNVALAR- PEREIRA.pdf'),
('2022-11-23 20:16:30.943','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D537','SF Chicalá','SF Chicalá','18764039886173','2022-11-21','2024-05-21','IE03','215323','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA SF CHICALA  - BOGOTA CR 82 B   53 B   06 SUR','18','Electroníca','Cra.82BN°53B-06Sur','18764039886173 SF Chicala.pdf'),
('2022-11-23 20:16:40.543','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D416','Drogueria cc jardin plaza ','Drogueria cc jardin plaza ','18764039887458','2022-11-21','2024-05-21','CI04','7322','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA CENTRO CIAL JARDIN PLAZA  CALI CR 98   16   200 LC 77 CC JARDIN PLAZA','18','Electroníca','CR 98 16 200 LC 77 CC JARDIN PLAZA','18764039887458 Drogueria cc jardin plaza.pdf'),
('2022-11-23 20:16:47.927','2022-11-23 20:39:53.863','2022-11-23 20:39:53.863',3,'','D417','Drog CC Palmetto - Cali','DROGUERIA PALMETO CALI','18764039889479','2022-11-21','2024-05-21','CJ04','12332','1000000','FACTURA ELECTRÓNICA DE VENTA','DROGUERIA CENTRO CIAL PALMETTO   CALI CL 9 CR 50 LC 109 CC PALMETTO','18','Electroníca','CL 9 CR 50 LC 109 CC PALMETTO','18764039889479 DROGUERIA PALMETO CALI.pdf');