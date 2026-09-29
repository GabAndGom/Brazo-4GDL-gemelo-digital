cd ~/brazo

cat << 'EOF' > README.md
<div align="center">

# 🦾 BRAZO ROBÓTICO DIDÁCTICO 4 GDL (XK-JS1-1)
### Proyecto Integrador de Ingeniería Electrónica — UMSA
**Gestión Académica II/2026**

[![GitHub Repo](https://img.shields.io/badge/GitHub-Brazo--4GDL-181717?style=for-the-badge&logo=github)](https://github.com/GabAndGom/Brazo-de-4-grados-de-libertad)
[![PLC](https://img.shields.io/badge/PLC-Siemens%20S7--200%20CPU%20224-00646E?style=for-the-badge&logo=siemens)](https://github.com/GabAndGom/Brazo-de-4-grados-de-libertad)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20(3FN)-336791?style=for-the-badge&logo=postgresql)](https://github.com/GabAndGom/Brazo-de-4-grados-de-libertad)
[![Normas](https://img.shields.io/badge/Normas-ISA--S5.1%20%7C%20IEC%2060617-darkred?style=for-the-badge)](https://github.com/GabAndGom/Brazo-de-4-grados-de-libertad)

<p align="center">
  <b>Sistemas de Control II (ETN-902)</b> • <b>Aplicación de Técnicas de Control (ETN-1034)</b> • <b>Bases de Datos (ETN-1000)</b>
</p>

[📌 Descripción](#-1-visión-general-del-sistema) • [🏗️ Arquitectura](#️-2-arquitectura-tecnológica) • [📂 Directorios](#-3-estructura-modular-del-repositorio) • [🔄 Flujo Git](#-4-flujo-de-trabajo-concurrente) • [👥 Equipo](#-5-equipo-y-créditos)

---

</div>

## 📌 1. Visión General del Sistema

El robot didáctico **XK-JS1-1** es una estación manipuladora de 4 grados de libertad diseñada para el entrenamiento en automatización industrial. El sistema opera mediante una **estrategia de lazo abierto con supervisión discreta** (ausencia de retroalimentación analógica continua por falta de encoders).

```mermaid
flowchart LR
    subgraph SENS [Instrumentación de Límite]
        S1[Microinterruptores X/Y<br>V-156-1C25]
        S2[Inductivo Z<br>LJ12A3-4-Z/BX]
    end

    subgraph CTRL [Capa de Control - PLC S7-200]
        PLC[CPU 224 AC/DC/RLY o DC/DC/DC]
        MAP[Librerías MAP_SERV<br>Pulsos PTO / Q0.0, Q0.1]
    end

    subgraph ACT [Etapa de Potencia y Movimiento]
        D1[Drivers Leadshine<br>DM542 / 2M530]
        M1[Motores Paso a Paso<br>NEMA 23 y NEMA 17]
        G[Efector Final<br>Garra / Solenoide 24V]
    end

    subgraph DATA [Supervisión y Persistencia]
        DB[(PostgreSQL 3FN<br>Telemetría de Ejes)]
        HMI[Panel HMI / ERP<br>Supervisión de Ciclos]
    end

    SENS -->|Entradas I0.0 - I0.3| PLC
    PLC --> MAP
    MAP -->|Tren de Pulsos + DIR| D1
    D1 --> M1
    PLC -->|Salida K3| G
    PLC -.->|Com. Industrial| DB
    DB <--> HMI
