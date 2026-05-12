"""
install_module.py — Instala/actualiza el módulo nextdoo_lead_capture
en la instancia Nextdoo Cloud vía XML-RPC.

1. Actualiza la lista de apps (necesario tras git push a odoo.sh).
2. Busca el módulo por technical name.
3. Lo instala si está en estado uninstalled, o lo upgrada si ya está instalado.
4. Verifica el endpoint /api/lead-magnet con un OPTIONS request.

Uso:
    export NEXTDOO_API_KEY="..."
    python install_module.py
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request
import xmlrpc.client

ODOO_URL = "https://www.nextdoo.cloud"
ODOO_DB = "nextdoo-sh-nextdoo-main-27318398"
ODOO_USER = "jeanlouis"
MODULE_NAME = "nextdoo_lead_capture"


def connect(api_key):
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, api_key, {})
    if not uid:
        raise SystemExit("Auth fallido")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models


def find_module(models, uid, api_key):
    ids = models.execute_kw(
        ODOO_DB, uid, api_key,
        "ir.module.module", "search",
        [[("name", "=", MODULE_NAME)]],
    )
    if not ids:
        return None
    rec = models.execute_kw(
        ODOO_DB, uid, api_key,
        "ir.module.module", "read",
        [ids, ["name", "state", "shortdesc", "summary"]],
    )
    return rec[0] if rec else None


def update_apps_list(models, uid, api_key):
    print("→ Actualizando lista de apps…")
    models.execute_kw(
        ODOO_DB, uid, api_key,
        "ir.module.module", "update_list", [],
    )
    print("  OK")


def install_or_upgrade(models, uid, api_key, module):
    state = module["state"]
    print(f"→ Módulo encontrado: {module['name']} (estado: {state})")

    if state == "uninstalled":
        print("  Instalando…")
        models.execute_kw(
            ODOO_DB, uid, api_key,
            "ir.module.module", "button_immediate_install", [[module["id"]]],
        )
        print("  ✓ Instalado")
    elif state == "installed":
        print("  Ya instalado · upgrading para aplicar cambios nuevos…")
        models.execute_kw(
            ODOO_DB, uid, api_key,
            "ir.module.module", "button_immediate_upgrade", [[module["id"]]],
        )
        print("  ✓ Upgrade aplicado")
    elif state in ("to install", "to upgrade"):
        print(f"  Estado intermedio ({state}), esperando…")
    else:
        print(f"  Estado inesperado: {state}")


def verify_endpoint():
    print("\n→ Verificando endpoint /api/lead-magnet…")
    try:
        req = urllib.request.Request(
            f"{ODOO_URL}/api/lead-magnet",
            method="OPTIONS",
            headers={"Origin": "https://supportboo.github.io"},
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            print(f"  OPTIONS → {res.status}")
            cors = res.headers.get("Access-Control-Allow-Origin")
            print(f"  CORS: {cors}")
            return res.status == 204
    except Exception as e:
        print(f"  ✗ Endpoint no responde aún: {e}")
        return False


def wait_for_module(models, uid, api_key, max_retries=12):
    """Espera a que el módulo aparezca tras un git push reciente."""
    for i in range(max_retries):
        update_apps_list(models, uid, api_key)
        mod = find_module(models, uid, api_key)
        if mod:
            return mod
        wait = 20
        print(f"  Módulo no detectado aún. Esperando {wait}s (intento {i+1}/{max_retries})…")
        time.sleep(wait)
    return None


def main():
    api_key = os.environ.get("NEXTDOO_API_KEY")
    if not api_key:
        sys.exit("Falta NEXTDOO_API_KEY")

    uid, models = connect(api_key)
    print(f"Conectado uid={uid} a {ODOO_URL}")

    mod = wait_for_module(models, uid, api_key)
    if not mod:
        sys.exit(f"\n✗ Módulo {MODULE_NAME} no encontrado tras varios intentos. "
                 "Posiblemente odoo.sh aún no ha terminado de deployar.")

    install_or_upgrade(models, uid, api_key, mod)

    # Pequeña espera para que las rutas se registren
    time.sleep(8)
    ok = verify_endpoint()
    print()
    if ok:
        print(f"✓ Listo. Endpoint /api/lead-magnet operativo en {ODOO_URL}")
    else:
        print("⚠ Módulo instalado pero endpoint aún no responde. "
              "Espera 1-2 min más y prueba un POST de test.")


if __name__ == "__main__":
    main()
