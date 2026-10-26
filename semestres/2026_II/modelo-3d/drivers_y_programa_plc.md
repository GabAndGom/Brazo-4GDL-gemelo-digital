# Drivers y programa actual del PLC (26/10/2026)

## Drivers de los motores (foto del tablero)

Los dos drivers de arriba son **JMC 2M542-N** (carros X e Y; el de arriba lleva la etiqueta K1 y el del medio
K2 y Q0.4). El de abajo (base, DIP rojo) es de otro modelo, sin etiqueta visible: hay que leer su placa.

Los tres tienen los DIP en la misma posición (ON hacia abajo):

| SW1 | SW2 | SW3 | SW4 | SW5 | SW6 | SW7 | SW8 |
|---|---|---|---|---|---|---|---|
| OFF | OFF | ON | OFF | ON | ON | ON | OFF |

Con la tabla del fabricante (manual JMC de la serie 2DM542/2M542, 1 = ON):

| Función | DIP | Valor |
|---|---|---|
| Corriente de trabajo | SW1-SW3 = OFF OFF ON | 2.37 A pico (1.69 A RMS) |
| Corriente en reposo | SW4 = OFF | la mitad de la de trabajo |
| Micropasos | SW5-SW8 = ON ON ON OFF | **1000 pulsos/rev** |

Para el driver de la base se asume la misma tabla (SUPUESTO) hasta confirmar el modelo.

Con un husillo de 5 mm/rev (SUPUESTO) queda 0.005 mm/pulso: los 170 mm de cada carro son 34000 pulsos.

### Sugerencias para mejorar la dinámica

1. **Corriente:** poner SW1-SW3 según la placa del motor (corriente RMS del driver ≈ corriente nominal por fase).
   Si el NEMA 23 es de 2.8 A, por ejemplo, 2.84 A pico (ON ON OFF) o 3.31 A pico (OFF ON OFF), vigilando la temperatura.
2. **SW4 en el driver del carro Y:** el husillo de bolas es reversible y el peso del brazo empuja el carro Y.
   Con SW4 = ON el motor retiene con toda la corriente (calienta más). Probar si el brazo se cae al quedar quieto.
3. **Micropasos:** X e Y deben tener siempre el mismo valor porque comparten el tren de pulsos Q0.1. 1000
   pulsos/rev es un buen compromiso: a 20 kHz (máximo del PTO) son 100 mm/s. Más micropasos suavizan
   pero bajan la velocidad máxima.
4. **Rampas en el PLC:** el programa arranca en 6000 pulsos/s (6 vueltas/s sin rampa), muy alto para un
   motor paso a paso con carga: puede perder pasos. Propuesta: arranque 1000-1500 pulsos/s, máximo
   10000-15000 pulsos/s y rampa de 0.5-1 s en `Q0_x_CTRL`.
5. **Fuente:** los drivers admiten 24-50 V y hoy se alimentan con 24 V. Con 36-48 V el par a alta velocidad
   mejora mucho (si la fuente y el motor lo permiten).

## Programa del PLC (Laboratorio 4, `principal.awl`)

Se encontró en `ETN/1-2026/ETN 902/Laboratorio 4/` (carpeta compartida con la VM). No se sabe si es el
que está cargado hoy en el PLC: hay que confirmarlo subiendo el programa desde Micro/WIN.

- `Q0_0_CTRL` (base) y `Q0_1_CTRL` (X/Y) con arranque 6000 pulsos/s, máximo 10000 y rampa 0.5 s.
  Los dos finales de carrera de la librería están en I1.6 (sin usar).
- I0.5 selecciona manual (SBR0) o automático (SBR8).
- **Manual:** I1.0/I1.1 mueven la base (DIR Q0.2) a 3000 pulsos/s. I1.2/I1.3 mueven X (K1 = Q0.5, DIR Q0.3)
  e I1.4/I1.5 mueven Y (K2 = Q0.6, DIR Q0.4) a 6000 pulsos/s. I0.7 abre o cierra la garra (Q0.7).
- **Origen (SBR7):** cierra K1 y K2 con Q0.3 = Q0.4 = 1 y mueve X e Y a la vez hasta I0.1 (X) e I0.3 (Y),
  pone a cero el contador de Q0.1 y luego el de la base cuando I0.0 está activo.
- **Automático:** secuencia fija de `MoveAbsolute` (base a 15000 y 88500 pulsos, Q0.1 a 20000, 30000,
  40000 y 60000) con K1/K2 cambiando entre tramos. El contador de Q0.1 es único: VD220 suma los pulsos
  de X y de Y, y el programa copia VD220 en VD230 (X) o VD240 (Y) según el relé activo.

### Lo que cambia en el gemelo digital

- El homing simulado sigue al programa: X e Y juntos, luego la base.
- El final de homing de Y es **I0.3** (Y abajo) y no I0.4 como decía la tabla anterior (confirmado en la
  planta el 26/10/2026, ver abajo).
- La base a 88500 pulsos no cabe con la reducción 5:1 supuesta (serían casi 18 vueltas). Hay que medir
  cuántos pulsos da una vuelta de la base.
- Un contador único para X e Y no sirve para un gemelo digital: el programa nuevo debe llevar un contador
  por eje (sumar los pulsos de cada tramo al eje cuyo relé está cerrado, con el signo de su DIR).

## Programa "BRAZO MIGUEL ROBADO" (escritorio de la VM)

Exportado a AWL desde Micro/WIN el 26/10/2026 (copia en `ETN 1034/respaldo_vm/`). "PROGRAMA MIGUEL AJUSTADO"
tiene la misma lógica; solo cambian los títulos. Proyecto para CPU 224 CN REL 02.01. Bloque de sistema:
puerto 0 en dirección PPI **7**, 19.2 kbit/s (la CPU 224 tiene un solo puerto).

No usa MAP_SERV: maneja el PTO directamente en modo de un segmento (`SMB67`/`SMB77 = 16#85`, base de tiempo
en µs) con cantidad de pulsos fija, **sin rampa**. Las posiciones no se cuentan: VD210/VD220 solo se ponen a cero.

| Señal | Uso en el programa |
|---|---|
| I0.5 | selector: 0 manual, 1 automático |
| I0.6 (flanco), I1.0 en automático, V1000.2 | paro: corta los dos PTO y reinicia |
| I0.7 | manual: abre o cierra la garra; automático: arranca la secuencia siguiente |
| I1.0 / I1.1 | base con Q0.2 = 0 / 1 (paquetes de 100 pulsos a 4 kHz mientras se pulsa) |
| I1.2 / I1.3 | carro X con Q0.3 = 0 (hasta I0.2) / Q0.3 = 1 (hasta I0.1); necesita K2 abierto |
| I1.4 / I1.5 | carro Y con Q0.4 = 0 (hasta I0.4) / Q0.4 = 1 (hasta I0.3); necesita K1 abierto |
| Q0.5 / Q0.6 | relés K1 (X) y K2 (Y); en manual nunca los dos a la vez |
| Q0.7 | garra: 1 = cerrada (se pone a 1 al tomar la pieza) |

Velocidades: 4 kHz en X/Y y en la base (ciclo de 250 µs); homing de la base a 2.5 kHz (400 µs).
Con 1000 pulsos/rev y 5 mm/rev: 20 mm/s en los carros.

**Homing (SBR_HOMING), secuencial:** Y con Q0.4 = 1 hasta I0.3 → X con Q0.3 = 1 hasta I0.1 → abre la garra →
base con Q0.2 = 1 hasta I0.0 → V1001.1 = listo.

**Secuencia 1 (primer I0.7 o V1000.0):** Y +12000 pulsos (Q0.4 = 0, sube) → base 17000 (Q0.2 = 0) →
X +14000 (Q0.3 = 0, adelante) → garra abierta.

**Secuencia 2 (segundo I0.7 o V1000.1):** cierra la garra → Y +5000 → X −8000 → base 18000 (Q0.2 = 0) →
Y −14000 → abre la garra → Y +14000 → base 10000 (Q0.2 = 1) → X +8000 → Y −5000 → garra abierta.

**Interfaz remota ya incluida** (pensada para otra estación por NETR/NETW o un HMI):

| Dirección | Sentido | Significado |
|---|---|---|
| V1000.0 | PC → PLC | ejecutar secuencia 1 |
| V1000.1 | PC → PLC | ejecutar secuencia 2 |
| V1000.2 | PC → PLC | paro |
| V1001.0 / .1 | PLC → PC | homing en curso / listo |
| V1001.2 / .3 | PLC → PC | secuencia 1 en curso / terminada |
| V1001.4 / .5 | PLC → PC | secuencia 2 en curso / terminada |
| VD1004 / VD1008 | PLC → PC | posición base / X-Y (hoy siempre 0) |

Como el puerto queda en PPI, una PC puede leer y escribir esta memoria V con el protocolo PPI (dirección 7,
19.2 kbit/s) **sin cambiar el programa**: es la forma más segura de conectar primero la página web
(botones de secuencia 1, 2 y paro, y estado leído de VB1001). Para mover a posiciones arbitrarias hace falta
un programa nuevo con rampas y un contador por eje.

## Prueba de comunicación con el PLC (26/10/2026)

Desde Linux, por el cable USB (CH340, `/dev/ttyUSB0`) y con un cliente PPI propio de **solo lectura**:
el PLC responde en la **dirección PPI 6** (no en la 7 del proyecto de Miguel), a 19.2 kbit/s, 8E1, con la PC
como dirección 0. Leer entradas, salidas y VB1000-VB1011 toma unos 145 ms (≈ 7 lecturas por segundo).
Estado leído: PLC en RUN, valores del PTO iguales a los del jog de la base de Miguel y M0.0 = 1, lo que
indica que está cargado "BRAZO MIGUEL ROBADO" (falta confirmarlo subiendo el programa).

Con un monitor de cambios se accionó a mano cada sensor y se confirmó el cableado:

| Entrada | Sensor |
|---|---|
| I0.0 | inductivo de la base (θ = 0) |
| I0.1 | final del carro X atrás (homing) |
| I0.2 | final del carro X adelante |
| I0.3 | final del carro Y abajo (homing) |
| I0.4 | final del carro Y arriba |

También se vieron los jog del panel: I1.1 da pulsos en la base (PTO0) con Q0.2 = 1, e I1.2 cierra K1 (Q0.5)
y da pulsos en Q0.1 con Q0.3 = 0, con lo que el carro X se separa del final trasero (Q0.3 = 0 es hacia adelante).
