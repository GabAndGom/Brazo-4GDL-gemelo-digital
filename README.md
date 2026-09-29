# Brazo Robótico de 4 Grados de Libertad (4 GDL)
### Proyecto Integrador de Ingeniería Electrónica — UMSA
**Asignaturas Concurrentes:** Sistemas de Control II (ETN-902), Aplicación de Técnicas de Control (ETN-1034) y Bases de Datos (ETN-1000).

Este repositorio centraliza la documentación técnica, modelado P&ID/eléctrico, lógica en Ladder (PLC Siemens S7-200 CPU 224), scripts de base de datos relacional (PostgreSQL en 3FN), interfaces de supervisión (HMI) y protocolos de pruebas de la planta XK-JS1-1.

---

## Estructura Modular del Repositorio

- `01_Documentacion_de_la_Planta/`: Fichas técnicas de hardware y manuales del fabricante.
- `02_Modelado_de_la_Planta/`: Diagramas eléctricos normalizados (IEC), P&ID (ANSI/ISA-S5.1) y mapeo de variables.
- `03_Control_y_Supervision/`: Programas STEP 7-Micro/WIN (Ladder), tabla de símbolos y prototipos HMI.
- `04_Base_de_Datos/`: Scripts DDL en PostgreSQL (3FN), diagramas Entidad-Relación y triggers.
- `05_Pruebas/`: Protocolos de validación unitaria e integral.
- `06_Evidencias/`: Registros de mediciones y evidencias operativas.
- `07_Informe/`: Informes técnicos compilados y guías de trabajo colaborativo.

---

## Flujo de Trabajo con Git
1. Toda nueva tarea se desarrolla en una rama auxiliar: `feature/nombre-tarea`.
2. Para integrar cambios a `main`, se realiza un **Pull Request (PR)** con revisión cruzada.
3. Para la guía detallada de comandos, revisar el documento compilado en:
   `07_Informe/Guias_y_Plantillas/Guia_Git_GitHub_Brazo4GDL.pdf`
