"""Administración desde la terminal del servidor.

  python -m server.admin crear-admin      # crea tu usuario administrador (te pide la contraseña)
  python -m server.admin invitar          # genera un código de invitación para un amigo
  python -m server.admin usuarios         # lista usuarios
"""
import getpass
import sys

from . import db


def main():
    db.init()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "crear-admin":
        user = input("Nombre de usuario: ").strip()
        pw = getpass.getpass("Contraseña (mín. 8 caracteres): ")
        if len(pw) < 8 or pw != getpass.getpass("Repite la contraseña: "):
            sys.exit("Las contraseñas no coinciden o son demasiado cortas.")
        db.create_user(user, pw, is_admin=True)
        print(f"Usuario administrador «{user}» creado, con una cartera ficticia de 10.000 €.")
    elif cmd == "invitar":
        with db.conn() as c:
            admin = c.execute("SELECT id FROM users WHERE is_admin = 1 ORDER BY id LIMIT 1").fetchone()
        if not admin:
            sys.exit("Primero crea el administrador: python -m server.admin crear-admin")
        print("Código de invitación:", db.new_invite(admin["id"]))
    elif cmd == "usuarios":
        with db.conn() as c:
            for u in c.execute("SELECT username, is_admin, datetime(created,'unixepoch') FROM users"):
                print(f"{u[0]:20} {'admin' if u[1] else '':6} {u[2]}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
