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
- El final de homing de Y es **I0.3** (Y abajo) y no I0.4 como decía la tabla anterior. Comprobarlo
  accionando el final de carrera a mano y mirando el LED de la entrada.
- La base a 88500 pulsos no cabe con la reducción 5:1 supuesta (serían casi 18 vueltas). Hay que medir
  cuántos pulsos da una vuelta de la base.
- Un contador único para X e Y no sirve para un gemelo digital: el programa nuevo debe llevar un contador
  por eje (sumar los pulsos de cada tramo al eje cuyo relé está cerrado, con el signo de su DIR).
