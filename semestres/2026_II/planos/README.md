# Planos del brazo XK-JS1-1 · versión 2.0 (Kaizen, laboratorio 2)

| Archivo | Contenido |
|---|---|
| `pid/brazo_pid_historico.dwg` | P&ID histórico (sin cambios) |
| `pid/brazo_pid_v2.dwg` / `.dxf` / `.pdf` | P&ID v2.0 · ISA-5.1-2009 · plano P&ID-B4G-01 |
| `electrico/brazo_electrico_historico.dwg` | Plano eléctrico histórico (sin cambios) |
| `electrico/brazo_electrico_v2.dwg` / `.dxf` / `.pdf` | Esquema eléctrico v2.0 · IEC 60617 / 60204-1 · plano E-B4G-01, hoja 1 (potencia) y hoja 2 (mando PLC) |
| `generar_planos_v2.py` | Genera los DXF y PDF (Python 3; matplotlib solo para el PDF) |

En el DWG eléctrico las dos hojas están lado a lado en el espacio modelo (la hoja 2 empieza en x = 450 mm).

## Regenerar

```bash
python3 generar_planos_v2.py
ODAFileConverter entrada/ salida/ ACAD2018 DWG 0 1 "*.dxf"
```

## Correcciones frente al plano histórico

- Entradas verificadas con el PLC en marcha: I0.0 inductivo de la base; I0.1 a I0.4 finales (X atrás/adelante, Y abajo/arriba).
- Tren de pulsos de X e Y compartido: Q0.1 pasa por K1 (Q0.5) al driver X y por K2 (Q0.6) al driver Y.
- Dirección: Q0.2 base, Q0.3 X (0 = adelante), Q0.4 Y (0 = arriba), conectadas a DIR+.
- Garra: Q0.7, bobina de K3, contacto de K3 al solenoide.
- Tags ISA-5.1 en los lazos 100 a 104 (los mismos de la base de datos), enlace PPI al gemelo digital y tabla de E/S.

## Por verificar en el tablero (marcado en los planos)

- Comunes 1M y 2M: se dibujaron a +24 V porque el sensor de la base es NPN (SUPUESTO).
- Nivel de PUL/DIR: entradas optoacopladas de 5 V alimentadas con 24 V del PLC (resistencia en serie o riel de 5 V, SUPUESTO).
- Tabla DIP del driver 2M530 de la base y numeración del zócalo de los relés MY2N-J.
- Correspondencia LS1–LS4 del plano histórico con S11–S14 (por orden, SUPUESTO).
