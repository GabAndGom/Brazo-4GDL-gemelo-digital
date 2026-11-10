"""Prueba de conexión con el PLC, SOLO LECTURA: no escribe nada ni mueve el brazo.

Lista los puertos serie, busca el PLC en cada uno (dirección y velocidad), dice qué programa
tiene cargado y muestra las entradas y salidas. Sirve para comprobar el cable USB-PPI o un
convertidor USB-RS485 antes de abrir la app.

    py probar_plc.py              # prueba todos los puertos
    py probar_plc.py COM4         # solo ese puerto
"""
import struct
import sys
import time

import serie
from ppi import ClientePPI, ErrorPPI, buscar_plc


def main():
    lista = serie.puertos()
    print('Puertos serie encontrados:')
    if not lista:
        print('  ninguno. Revise que el cable esté enchufado y que Windows tenga su driver')
        print('  (Administrador de dispositivos > Puertos (COM y LPT)).')
    for p, d in lista:
        print(f'  {p:8} {d}')
    candidatos = sys.argv[1:] or [p for p, _ in lista]
    for puerto in candidatos:
        print(f'\nBuscando el PLC en {puerto} (puede tardar hasta un minuto)...')
        t = time.time()
        r = buscar_plc(puerto, direcciones=[2, 6, 7], baudios=(9600, 19200)) or \
            buscar_plc(puerto, direcciones=[d for d in range(1, 32) if d not in (2, 6, 7)])
        if not r:
            print(f'  no responde ningún PLC ({time.time() - t:.0f} s).')
            continue
        direccion, baudios = r
        print(f'  PLC encontrado: dirección PPI {direccion}, {baudios} baudios')
        c = ClientePPI(puerto, plc=direccion, baudios=baudios)
        try:
            c.abrir()
            programa = 'otro programa (solo monitor)'
            try:
                if c.leer('V', 1141, 1)[0] == 0x47:
                    programa = 'brazo_gemelo (programa del gemelo digital)'
                elif struct.unpack('>ii', c.leer('V', 340, 8)) == (30000, 25000):
                    programa = 'programa anterior de secuencias'
            except ErrorPPI:
                pass
            print(f'  programa cargado: {programa}')
            t = time.time()
            ib0, ib1, qb0 = (x[0] for x in c.leer_varios([('I', 0, 1), ('I', 1, 1), ('Q', 0, 1)]))
            print(f'  una lectura tarda {1000 * (time.time() - t):.0f} ms')
            bits = lambda b, n: ' '.join(f'{n}.{i}={(b >> i) & 1}' for i in range(8))
            print('  entradas  ' + bits(ib0, 'I0'))
            print('            ' + bits(ib1, 'I1'))
            print('  salidas   ' + bits(qb0, 'Q0'))
            print('\n  Conexión correcta. Ya puede abrir la app.')
        except (ErrorPPI, OSError) as ex:
            print(f'  error al leer: {ex}')
        finally:
            c.cerrar()
        return
    print('\nNo se encontró el PLC. Revise: PLC encendido y en RUN, cable en el puerto 0, que Micro/WIN'
          ' u otro programa no tenga abierto el puerto, y el driver del cable.')


if __name__ == '__main__':
    main()
