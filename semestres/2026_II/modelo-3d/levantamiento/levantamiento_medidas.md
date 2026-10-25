# Levantamiento de medidas y estructura cinemática · XK-JS1-1

Entregable A (borrador para revisión). Fuentes: bocetos acotados y fotos etiquetadas tomadas el
20/10/2026 (carpeta `modelo brazo/medidas`), manual de fábrica `global/manuales/manual_xk-js1-1_en.pdf`
(secciones 1.1-1.3 y 2.4), Informe Lab 2 (II-2026) y `brazo_robotico_v2.glb`.

Las cotas de los bocetos están en **cm**; aquí se pasan a **mm**. Estado de cada dato:

- **leída**: escrita en el boceto.
- **estimada (foto)**: medida sobre la foto tomando como escala una cota leída. Error de ±10 %.
- **fabricante**: tomada del manual.
- **falta**: hay que medirla en la planta.

Las 20 fotos están en [`fotos/`](fotos): `levantamiento_f01.jpg` a `levantamiento_f20.jpg`. Los números
"f01" a "f20" que aparecen en este documento se refieren a ellas. Los bocetos son f01-f06; las fotos de la
planta con etiquetas, f07-f20.

> **Estado al 25/10/2026.** No se pudo volver a la planta. Por indicación del equipo, las cotas que figuran
> como "falta" se completaron con valores **SUPUESTO**, estimados de las fotos o deducidos del diseño (tabla
> de la sección 3). Los valores usados están en `web/js/cinematica.js`.

![Esquema cinemático](esquema_cinematico.svg)

## 1. Cómo funciona el mecanismo (deducido de las fotos)

1. La **base giratoria** está formada por el disco superior 11, la columna 7 y el bloque 2. El motor
   NEMA 17 va montado sobre el disco superior y gira con él. Según el manual, mueve la base mediante
   engranajes ("Z axis used gear drive"). El sensor inductivo está en el disco y da el origen de θ.
2. El **bloque 2** está atornillado a la columna 7, así que no se mueve respecto a la base. Por él
   pasan las guías inferiores y lleva la tuerca del husillo inferior.
3. El **bastidor** está formado por las placas 10 (trasera, con los motores) y 5 (delantera), las
   4 guías 16, los 2 husillos y los 2 motores NEMA 23. Cuando gira el husillo inferior, **todo el
   bastidor se desliza a través del bloque 2**. Esto es el **carro X**: un par prismático P1 entre la
   base y el bastidor.
4. El **bloque 1** lleva la tuerca del husillo superior y corre sobre las guías superiores. Su carrera
   es **relativa al bastidor**. Esto es el **carro Y**: un par prismático P2 entre el bastidor y el
   bloque 1. En la foto f08 se ve el bloque 1 desplazado respecto al bloque 2, lo que confirma que se
   mueven por separado.
5. El **brazo 9** está atornillado a la escuadra 8 y forman un balancín. Pivota en **A**, sobre la
   placa delantera 5 (probablemente en la horquilla 17). La **biela 12** une el vértice **B** de la
   escuadra 8 con el vértice **C** de la escuadra 6, que está fija sobre el bloque 1. El conjunto
   bastidor-bloque 1-biela 12-balancín es un **mecanismo biela-manivela invertido**: s_Y fija el ángulo
   φ del brazo.
6. La **varilla 13** y los dos **postes 14** (A'-A y E'-E) forman un **paralelogramo** con el brazo 9.
   Gracias a él la pinza 4 **mantiene la orientación** (queda horizontal) para cualquier φ.
7. Los finales de carrera están en dos barras: una en la placa 5 (fotos f14 y f15) y otra en la placa
   10 (foto f17). En cada barra, el de arriba toca el bloque 1 (límites del carro Y) y el de abajo el
   bloque 2 (límites del carro X). Son 4 en total, 2 por eje, como dice el manual.

**Consecuencia para la cinemática.** El carro X traslada todo el brazo en la dirección radial y no
cambia φ, porque el bloque 1 viaja con el bastidor. El carro Y cambia φ y con ello mueve la garra a lo
largo de un arco, cambiando a la vez r y z. Queda así:

$$ r = r_0 + s_X + L_9\cos\varphi(s_Y) + d_{g},\qquad z = z_A - L_9\sin\varphi(s_Y) - h_{g} $$

φ(s_Y) sale de cerrar el lazo vectorial A-B-C, que es de tipo biela-manivela. Esto coincide con el
manual: "X axis for front and back movement, the Y axis for up and down movement".

### Grados de libertad (Grübler-Kutzbach, plano r-z)

| # | Eslabón | Piezas |
|---|---|---|
| 1 | Base giratoria (fijo en el plano) | 11 sup., 7, 2, NEMA 17 |
| 2 | Bastidor (carro X) | 5, 10, 16 ×4, husillos ×2, 3 ×2, NEMA 23 ×2, 17 |
| 3 | Carro Y | 1, 6 |
| 4 | Biela | 12 |
| 5 | Balancín | 9, 8 |
| 6 | Varilla del paralelogramo | 13 |
| 7 | Pinza | 4, 15, 18 (?), poste 14 de la pinza |

| Par | Entre | Tipo |
|---|---|---|
| P1 | 1-2 | prismático (s_X) |
| P2 | 2-3 | prismático (s_Y) |
| C | 3-4 | revoluta |
| B | 4-5 | revoluta |
| A | 5-2 | revoluta |
| E | 5-7 | revoluta |
| A' | 2-6 (poste 14) | revoluta |
| E' | 6-7 (poste 14) | revoluta |

$$ M = 3(n-1) - 2j_1 - j_2 = 3(7-1) - 2\cdot 8 - 0 = 2 $$

Sumando el giro de la base (R1) y la garra ON/OFF quedan **4 GDL**. El paralelogramo no añade
movilidad, solo fija la orientación de la pinza. La garra es un grado de libertad de actuación: no
cambia la posición del TCP.

## 2. Tabla de piezas

Ejes de la pieza: **L** a lo largo de las guías, **W** transversal horizontal, **H** vertical.

| Nº | Nombre | Nodo GLB v2 | Cotas (mm) | Estado | Padre | Unión con el padre |
|---|---|---|---|---|---|---|
| 11 | Discos de base (inferior fijo, superior giratorio) | Base | Ø165 × 15 c/u; agujero central Ø42; separación entre discos ~36 ("A = 3,6 cm") | leída (la separación, por confirmar) | mesa / disco inf. | superior: **revoluta θ** (eje vertical) |
| 7 | Columna en H con ranuras | Base | H 120 × W 100 × L 71; nervios 23 / 15 / 10 | leída (lectura del boceto a confirmar: lo rotulé 7, se ve como "9") | disco 11 sup. | fija |
| 2 | Bloque fijo del husillo X | Base | L 100 × W 130 × H 40; bujes Ø28 (LM16UU), tuerca Ø50, separación 10 | leída | columna 7 | fija |
| — | Motor base NEMA 17 + reductor | Base | 42 × 42 × 48 | fabricante | disco 11 sup. | fija (mueve θ) |
| 10 | Placa trasera del bastidor | CarroHorizontal | 110.3 × 120.6 × 13.1; 6 agujeros: 2 niveles a ~44 entre ejes | leída | bastidor | fija |
| 5 | Placa delantera del bastidor | CarroHorizontal | igual que 10 ("es igual que la 5") | leída | bastidor | fija |
| 16 | Guías lineales ×4 | CarroHorizontal | Ø16 × 300 | leída | placas 5-10 | fija |
| — | Husillos de bolas ×2 | CarroHorizontal | Ø ~21 (boceto: "2,1 cm"), **paso: falta** | leída / **falta** | placas 5-10 | fija (gira) |
| 3 | Adaptadores de motor NEMA 23 ×2 | CarroHorizontal | 57 × 57 × 50 | leída | placa 10 | fija |
| — | Motores NEMA 23 ×2 (arriba Y, abajo X) | CarroHorizontal | 57 × 57 × ~76 | fabricante / estimada | adaptador 3 | fija |
| — | Bastidor completo (carro X) | CarroHorizontal | L total ≈ 300 + 2×13 + motores | estimada | bloque 2 | **prismática s_X** (eje L) |
| 1 | Bloque del carro Y | CarroElevacion | L 100 × W 130 × H 50; bujes Ø28, tuerca Ø50 | leída | bastidor | **prismática s_Y** (eje L) |
| 6 | Escuadra triangular sobre el bloque 1 | CarroElevacion | H 110, base 49, punta 24, espesor 11, fondo 46; ranura | leída | bloque 1 | fija; pivote **C** en la punta |
| 12 | Biela ranurada | BielaTrasera | largo total 240, ancho 24, espesor 11.1; ranura ~160 | leída; distancia entre pivotes C-B = 240 (cota del boceto f05) | escuadra 6 | revoluta C (pasiva) |
| 8 | Escuadra triangular del balancín | BrazoSoporte | igual que 6 (110 × 49 × 24 × 11) | leída | brazo 9 | fija; pivote **B** en la punta |
| 17 | Horquilla en U | BrazoSoporte / CarroHorizontal | 55.4 × 49.7 × 25.4; alas 9.7; 14.3 | leída; **ubicación: falta** (¿pivote A en la placa 5?) | placa 5 | fija |
| 9 | Brazo principal ranurado | BrazoSoporte | ancho 46, ranura 20, extremo 25, espesor 10; **largo A-E: falta** (est. ≈ 300, igual a la varilla 13 por el paralelogramo) | leída / **falta** | bastidor (A) | revoluta A (pasiva, φ) |
| 13 | Varilla del paralelogramo | BielaSuperior | Ø11 × 300 | leída; **distancia entre pivotes A'-E': falta** | poste 14 | revoluta A' (pasiva) |
| 14 | Postes ×2 (A-A' y E-E') | BielaSuperior / pinza | 46 × 10 × 4.4 | leída; **distancia entre centros: falta** | placa 5 / pinza | fija |
| 4 | Cuerpo de la pinza (solenoide) | pinza | L 80 × 55 × 55 | leída | brazo 9 (E) | revoluta E (orientación fija) |
| 15 | Mordazas | pinza | 150 × 80 × 30 (puntas 15 × 10) | leída (cota de 150 a confirmar) | cuerpo 4 | **garra ON/OFF** (prismática o pivote) |
| 18 | Soporte con 3 agujeros | pinza (?) | 28.3 × 30 × 13.9 | leída; **ubicación: falta** | ? | fija |

## 3. Datos cinemáticos que faltan

Sin estos datos no se puede cerrar φ(s_Y). Son las cotas **entre centros de pasadores**, que son las
que importan para la cinemática.

| Símbolo | Qué medir | Valor usado (25/10/2026) |
|---|---|---|
| A | Posición del pivote del brazo respecto a la placa 5: Δu hacia adelante y Δh respecto al eje del husillo inferior | SUPUESTO: Δu = 43, Δh = 14 (h_A = 205 sobre la mesa) |
| C | Posición del pivote superior de la escuadra 6 respecto a la cara delantera del bloque 1: Δu y altura | SUPUESTO: centro del bloque (Δu = −50), 10 mm bajo la punta de la escuadra 6 (h_C = 361) |
| L12 | Distancia entre centros C-B de la biela 12 | **240** (boceto f05: "24"; en la foto se estima ≈ 237) |
| a, β | Distancia A-B y ángulo entre A-B y el brazo A-E | estimada (f13): a = 130, β = 50° |
| L9 | Distancia entre centros A-E del brazo 9 | estimada: 300 (igual a la varilla 13 por el paralelogramo) |
| L13, L14 | Distancias entre centros de la varilla 13 (A'-E') y de los postes 14 | 300 / 46 |
| d_g, h_g | Desde el pivote E hasta el centro de las mordazas (TCP), en horizontal y en vertical | SUPUESTO: 130 / 27.5 |
| z_base | Altura del eje del husillo inferior sobre la mesa | 15 + 21 (SUPUESTO) + 15 + 120 + 20 = 191 |
| r_base | Distancia horizontal del eje θ a la cara delantera del bloque 2 | 50 (bloque centrado en el eje: SUPUESTO) |
| s_X, s_Y | Carrera útil entre finales de carrera (mm) y posición del cero | SUPUESTO: 0-170 cada uno (300 − 2·13 − 100 − 2·2). El cero de cada eje es su final trasero (X) o superior (Y). El manual dice "X 200 mm, Y 440 mm"; el modelo da ~375 mm de recorrido vertical de la garra |
| p | Paso del husillo (mm/rev). El boceto f02 dice "1,37 — 5ap" (sin interpretar) | SUPUESTO: 5 mm/rev (SFU1605). Medir con 10 vueltas |
| μ | Micropasos de los drivers (DIP SW4-SW7 del 2M542) | SUPUESTO: 1600 pulsos/rev (SW4-SW7 = 0 0 1 1); no hubo acceso a los drivers |
| i_θ | Reducción del engranaje de la base y rango de giro útil | SUPUESTO: 5:1 y ±175° (manual: 360°) |

La búsqueda en internet (25/10/2026) no encontró datos publicados del XK-JS1-1 (paso del husillo ni
reducción de la base); solo descripciones genéricas de equipos didácticos con husillos de bolas y engranajes.
