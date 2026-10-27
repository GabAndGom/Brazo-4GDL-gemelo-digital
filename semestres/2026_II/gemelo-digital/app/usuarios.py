#!/usr/bin/env python3
"""Administra los usuarios de la app del gemelo (las contraseñas se piden sin mostrarlas).

    python3 usuarios.py agregar ana --rol operador
    python3 usuarios.py agregar visita --rol observador
    python3 usuarios.py clave ana            # cambiar la contraseña
    python3 usuarios.py rol visita operador  # cambiar el rol
    python3 usuarios.py quitar visita
    python3 usuarios.py listar

Roles: observador (solo ve el brazo) y operador (lo manda y puede dar paro).
Los cambios valen en la siguiente petición de cada sesión, sin reiniciar la app.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acceso  # noqa: E402


def pedir_clave():
    c1 = getpass.getpass('Contraseña (mínimo 8 caracteres): ')
    c2 = getpass.getpass('Repítala: ')
    if c1 != c2:
        raise SystemExit('Las contraseñas no coinciden.')
    return c1


def main():
    ap = argparse.ArgumentParser(description='Usuarios de la app del gemelo digital')
    sub = ap.add_subparsers(dest='accion', required=True)
    a = sub.add_parser('agregar'); a.add_argument('nombre'); a.add_argument('--rol', choices=acceso.ROLES, required=True)
    c = sub.add_parser('clave'); c.add_argument('nombre')
    r = sub.add_parser('rol'); r.add_argument('nombre'); r.add_argument('nuevo', choices=acceso.ROLES)
    q = sub.add_parser('quitar'); q.add_argument('nombre')
    sub.add_parser('listar')
    args = ap.parse_args()

    u = acceso.cargar()
    try:
        if args.accion == 'agregar':
            if args.nombre in u:
                raise SystemExit(f'El usuario {args.nombre} ya existe (use "clave" o "rol").')
            acceso.poner_clave(u, args.nombre, pedir_clave(), args.rol)
        elif args.accion == 'clave':
            if args.nombre not in u:
                raise SystemExit(f'No existe el usuario {args.nombre}.')
            acceso.poner_clave(u, args.nombre, pedir_clave(), u[args.nombre]['rol'])
        elif args.accion == 'rol':
            if args.nombre not in u:
                raise SystemExit(f'No existe el usuario {args.nombre}.')
            u[args.nombre]['rol'] = args.nuevo
        elif args.accion == 'quitar':
            if u.pop(args.nombre, None) is None:
                raise SystemExit(f'No existe el usuario {args.nombre}.')
        elif args.accion == 'listar':
            if not u:
                print('No hay usuarios. Cree uno con: python3 usuarios.py agregar NOMBRE --rol operador')
            for nombre, d in sorted(u.items()):
                print(f'{nombre:20s} {d["rol"]}')
            return
    except ValueError as e:
        raise SystemExit(str(e))
    acceso.guardar(u)
    print('Listo.')


if __name__ == '__main__':
    main()
