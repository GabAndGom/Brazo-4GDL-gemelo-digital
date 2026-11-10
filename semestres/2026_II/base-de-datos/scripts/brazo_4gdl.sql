-- =====================================================================
-- Base de datos de telemetría del brazo XK-JS1-1 (4 GDL) - II/2026
-- PostgreSQL 13 o superior.
--
-- Parte del modelo E-R preliminar del equipo (modelo/modelo_er_preliminar.png)
-- y lo lleva a tercera forma normal (3FN):
--   * 1FN: sin grupos repetidos (los destinos de una orden van en orden_parametro,
--          una fila por eje; la posición X, Y, Z no va en una sola celda).
--   * 2FN: cada tabla tiene clave primaria simple o, si es compuesta, todos los
--          atributos dependen de la clave completa.
--   * 3FN: sin dependencias transitivas (la duración de un ciclo no se guarda:
--          se calcula en la vista v_ciclo; la unidad y el rango de una medida
--          viven en variable, no en cada muestra).
-- Los tags siguen la propuesta ISA-5.1 del manual técnico (lazos 100 a 104).
--
-- Uso:
--   createdb brazo4gdl
--   psql -d brazo4gdl -f brazo_4gdl.sql
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------- catálogos
CREATE TABLE sistema (
    id          SMALLSERIAL PRIMARY KEY,
    nombre      VARCHAR(60)  NOT NULL UNIQUE,
    tipo        VARCHAR(40)  NOT NULL,
    plc         VARCHAR(60)  NOT NULL
);

CREATE TABLE eje (
    id              SMALLSERIAL PRIMARY KEY,
    sistema_id      SMALLINT     NOT NULL REFERENCES sistema(id),
    codigo          CHAR(1)      NOT NULL,              -- Z (base), X, Y, G (garra)
    nombre          VARCHAR(40)  NOT NULL,
    tipo_mov        VARCHAR(12)  NOT NULL CHECK (tipo_mov IN ('rotacional', 'lineal', 'binario')),
    unidad          VARCHAR(8)   NOT NULL,
    pulsos_unidad   NUMERIC(10,4),                      -- NULL para la garra
    lazo_isa        SMALLINT     NOT NULL,
    UNIQUE (sistema_id, codigo)
);

CREATE TABLE punto_io (                                 -- señales del PLC (entidad PUNT_I/O)
    id              SMALLSERIAL PRIMARY KEY,
    sistema_id      SMALLINT     NOT NULL REFERENCES sistema(id),
    eje_id          SMALLINT     REFERENCES eje(id),    -- NULL: señal general del panel
    direccion       VARCHAR(8)   NOT NULL,              -- I0.1, Q0.5 ...
    tag_isa         VARCHAR(16)  NOT NULL UNIQUE,
    tipo_senal      VARCHAR(4)   NOT NULL CHECK (tipo_senal IN ('DI', 'DO', 'PTO')),
    descripcion     VARCHAR(120) NOT NULL,
    UNIQUE (sistema_id, direccion)
);

CREATE TABLE variable (                                 -- magnitudes continuas (entidad VARIABLE_PROCESO)
    id              SMALLSERIAL PRIMARY KEY,
    eje_id          SMALLINT     NOT NULL REFERENCES eje(id),
    tag_isa         VARCHAR(16)  NOT NULL UNIQUE,
    clase           CHAR(2)      NOT NULL CHECK (clase IN ('PV', 'MV', 'DV')),
    nombre          VARCHAR(80)  NOT NULL,
    unidad          VARCHAR(8)   NOT NULL,
    rango_min       DOUBLE PRECISION NOT NULL,
    rango_max       DOUBLE PRECISION NOT NULL,
    CHECK (rango_min < rango_max)
);

CREATE TABLE programa_plc (
    id              SMALLSERIAL PRIMARY KEY,
    nombre          VARCHAR(40)  NOT NULL UNIQUE,
    perfil_app      VARCHAR(12)  NOT NULL UNIQUE,       -- gemelo, cargado, monitor
    firma           VARCHAR(40),
    descripcion     VARCHAR(160)
);

CREATE TABLE alarma (                                   -- catálogo (entidad ALERTA)
    id              SMALLSERIAL PRIMARY KEY,
    codigo          VARCHAR(24)  NOT NULL UNIQUE,
    severidad       SMALLINT     NOT NULL CHECK (severidad BETWEEN 1 AND 3),   -- 1 aviso, 2 falla, 3 crítica
    descripcion     VARCHAR(160) NOT NULL
);

-- ---------------------------------------------------------------- usuarios
CREATE TABLE rol (
    id      SMALLSERIAL PRIMARY KEY,
    nombre  VARCHAR(16) NOT NULL UNIQUE
);

CREATE TABLE usuario (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(32)  NOT NULL UNIQUE,
    rol_id      SMALLINT     NOT NULL REFERENCES rol(id),
    clave_hash  VARCHAR(200) NOT NULL,                   -- PBKDF2, igual que usuarios.json de la app
    creado_en   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE sesion (                                    -- registro de ingresos (logs)
    id          BIGSERIAL PRIMARY KEY,
    usuario_id  INTEGER      REFERENCES usuario(id),     -- NULL: usuario inexistente
    nombre_usado VARCHAR(32) NOT NULL,
    ip          INET         NOT NULL,
    instante    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    exito       BOOLEAN      NOT NULL,
    fin         TIMESTAMPTZ
);

-- ---------------------------------------------------------------- operación
CREATE TABLE ciclo_operacion (                           -- cada vez que se elige un modo en la app
    id          BIGSERIAL PRIMARY KEY,
    sistema_id  SMALLINT     NOT NULL REFERENCES sistema(id),
    programa_id SMALLINT     REFERENCES programa_plc(id),
    modo        VARCHAR(12)  NOT NULL CHECK (modo IN ('simulacion', 'local', 'red')),
    inicio      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fin         TIMESTAMPTZ,
    CHECK (fin IS NULL OR fin >= inicio)
);

CREATE TABLE muestra (                                   -- telemetría de variables continuas
    id          BIGSERIAL PRIMARY KEY,
    ciclo_id    BIGINT           NOT NULL REFERENCES ciclo_operacion(id),
    variable_id SMALLINT         NOT NULL REFERENCES variable(id),
    instante    TIMESTAMPTZ      NOT NULL,
    valor       DOUBLE PRECISION NOT NULL
);
CREATE INDEX muestra_variable_instante ON muestra (variable_id, instante);

CREATE TABLE estado_io (                                 -- cambios de las señales digitales
    id          BIGSERIAL PRIMARY KEY,
    ciclo_id    BIGINT      NOT NULL REFERENCES ciclo_operacion(id),
    punto_id    SMALLINT    NOT NULL REFERENCES punto_io(id),
    instante    TIMESTAMPTZ NOT NULL,
    valor       BOOLEAN     NOT NULL
);
CREATE INDEX estado_io_punto_instante ON estado_io (punto_id, instante);

CREATE TABLE orden (                                     -- acción de control (entidad ACCION_CONT)
    id          BIGSERIAL PRIMARY KEY,
    ciclo_id    BIGINT       NOT NULL REFERENCES ciclo_operacion(id),
    usuario_id  INTEGER      REFERENCES usuario(id),     -- NULL: PC del laboratorio (local)
    instante    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    tipo        VARCHAR(16)  NOT NULL CHECK (tipo IN ('homing', 'mover', 'garra', 'detener', 'velocidad',
                                                       'iniciar', 'emergencia', 'rearmar', 'mando')),
    aceptada    BOOLEAN      NOT NULL,
    motivo      VARCHAR(200)                             -- motivo del rechazo
);

CREATE TABLE orden_parametro (                           -- destinos de una orden, uno por eje (1FN)
    orden_id    BIGINT           NOT NULL REFERENCES orden(id) ON DELETE CASCADE,
    eje_id      SMALLINT         NOT NULL REFERENCES eje(id),
    valor       DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (orden_id, eje_id)
);

CREATE TABLE evento_alarma (
    id          BIGSERIAL PRIMARY KEY,
    alarma_id   SMALLINT     NOT NULL REFERENCES alarma(id),
    ciclo_id    BIGINT       NOT NULL REFERENCES ciclo_operacion(id),
    instante    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    activa      BOOLEAN      NOT NULL,
    detalle     VARCHAR(200)
);

-- ---------------------------------------------------------------- reglas
-- Trigger: una muestra fuera del rango de su variable no entra (pide la guía de laboratorio 1).
CREATE FUNCTION validar_muestra() RETURNS trigger AS $$
DECLARE
    r variable%ROWTYPE;
BEGIN
    SELECT * INTO r FROM variable WHERE id = NEW.variable_id;
    IF NEW.valor < r.rango_min OR NEW.valor > r.rango_max THEN
        RAISE EXCEPTION 'muestra fuera de rango para % (%): % no está en [%, %]',
            r.tag_isa, r.unidad, NEW.valor, r.rango_min, r.rango_max;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER muestra_en_rango BEFORE INSERT OR UPDATE ON muestra
    FOR EACH ROW EXECUTE FUNCTION validar_muestra();

-- Vista: duración de cada ciclo (se calcula, no se guarda: 3FN)
CREATE VIEW v_ciclo AS
SELECT c.id, c.modo, p.nombre AS programa, c.inicio, c.fin,
       COALESCE(c.fin, now()) - c.inicio AS duracion
FROM ciclo_operacion c LEFT JOIN programa_plc p ON p.id = c.programa_id;

-- Vista: última posición conocida de cada eje
CREATE VIEW v_ultima_posicion AS
SELECT DISTINCT ON (m.variable_id) v.tag_isa, v.nombre, v.unidad, m.valor, m.instante
FROM muestra m JOIN variable v ON v.id = m.variable_id
WHERE v.clase = 'PV'
ORDER BY m.variable_id, m.instante DESC;

-- ---------------------------------------------------------------- datos de la planta
INSERT INTO sistema (nombre, tipo, plc) VALUES
    ('Brazo XK-JS1-1', 'brazo robótico 4 GDL', 'Siemens S7-200 CPU 224 CN');

INSERT INTO eje (sistema_id, codigo, nombre, tipo_mov, unidad, pulsos_unidad, lazo_isa) VALUES
    (1, 'Z', 'base (theta)', 'rotacional', 'deg', 190.3, 101),
    (1, 'X', 'carro X (alcance)', 'lineal', 'mm', 200, 102),
    (1, 'Y', 'carro Y (altura)', 'lineal', 'mm', 200, 103),
    (1, 'G', 'garra', 'binario', '-', NULL, 104);

INSERT INTO punto_io (sistema_id, eje_id, direccion, tag_isa, tipo_senal, descripcion) VALUES
    (1, 1,    'I0.0', 'ZS-101',   'DI',  'sensor inductivo de la base (theta = 0)'),
    (1, 2,    'I0.1', 'ZSL-102',  'DI',  'final de carrera X atrás (origen)'),
    (1, 2,    'I0.2', 'ZSH-102',  'DI',  'final de carrera X adelante'),
    (1, 3,    'I0.3', 'ZSL-103',  'DI',  'final de carrera Y abajo (origen)'),
    (1, 3,    'I0.4', 'ZSH-103',  'DI',  'final de carrera Y arriba'),
    (1, NULL, 'I0.5', 'HS-100',   'DI',  'selector manual / automático'),
    (1, NULL, 'I0.6', 'HS-100P',  'DI',  'pulsador de paro'),
    (1, 4,    'I0.7', 'HS-104',   'DI',  'garra / inicio'),
    (1, 1,    'I1.0', 'HS-101A',  'DI',  'jog base +'),
    (1, 1,    'I1.1', 'HS-101B',  'DI',  'jog base -'),
    (1, 2,    'I1.2', 'HS-102A',  'DI',  'jog X adelante'),
    (1, 2,    'I1.3', 'HS-102B',  'DI',  'jog X atrás'),
    (1, 3,    'I1.4', 'HS-103A',  'DI',  'jog Y arriba'),
    (1, 3,    'I1.5', 'HS-103B',  'DI',  'jog Y abajo'),
    (1, 1,    'Q0.0', 'ZY-101',   'PTO', 'tren de pulsos de la base (PTO0)'),
    (1, NULL, 'Q0.1', 'ZY-100',   'PTO', 'tren de pulsos compartido X/Y (PTO1)'),
    (1, 1,    'Q0.2', 'ZY-101D',  'DO',  'dirección base (1 = hacia el inductivo)'),
    (1, 2,    'Q0.3', 'ZY-102D',  'DO',  'dirección X (0 = adelante)'),
    (1, 3,    'Q0.4', 'ZY-103D',  'DO',  'dirección Y (0 = arriba)'),
    (1, 2,    'Q0.5', 'ZY-102K',  'DO',  'relé K1: Q0.1 al driver X'),
    (1, 3,    'Q0.6', 'ZY-103K',  'DO',  'relé K2: Q0.1 al driver Y'),
    (1, 4,    'Q0.7', 'XY-104',   'DO',  'relé K3 del solenoide de la garra (1 = cerrada)');

INSERT INTO variable (eje_id, tag_isa, clase, nombre, unidad, rango_min, rango_max) VALUES
    (1, 'ZI-101',  'PV', 'posición de la base', 'deg', -263, 263),
    (2, 'ZI-102',  'PV', 'posición del carro X', 'mm', 0, 170),
    (3, 'ZI-103',  'PV', 'posición del carro Y', 'mm', 0, 170),
    (1, 'SY-101',  'MV', 'frecuencia del tren de la base', 'Hz', 0, 20000),
    (2, 'SY-100',  'MV', 'frecuencia del tren X/Y', 'Hz', 0, 20000);

INSERT INTO programa_plc (nombre, perfil_app, firma, descripcion) VALUES
    ('brazo_gemelo', 'gemelo', 'VB1141 = 16#47', 'posición contada en el PLC, órdenes por VB1100-VB1119'),
    ('brazo_secuencias_original_v1', 'cargado', 'VD340 = 30000, VD344 = 25000', 'homing y 2 secuencias fijas'),
    ('otro', 'monitor', NULL, 'programa no reconocido: solo lectura');

INSERT INTO alarma (codigo, severidad, descripcion) VALUES
    ('comunicacion', 2, 'se perdió la comunicación PPI con el PLC'),
    ('watchdog', 3, 'el PLC detuvo un movimiento porque la PC dejó de dar señales de vida'),
    ('paro', 2, 'paro por pulsador, selector u orden de la PC'),
    ('fuera_de_rango', 1, 'destino fuera del recorrido'),
    ('sin_homing', 1, 'orden de movimiento sin referencia'),
    ('ocupado', 1, 'orden con un movimiento en curso'),
    ('falla_homing', 3, 'homing sin sensor o con tiempo excedido'),
    ('posicion_incierta', 2, 'tramo interrumpido: hace falta un nuevo homing');

INSERT INTO rol (nombre) VALUES ('observador'), ('operador');

COMMIT;
