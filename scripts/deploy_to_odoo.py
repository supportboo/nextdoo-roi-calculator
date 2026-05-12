"""
deploy_to_odoo.py — Embebe index.html como página Odoo en Nextdoo Cloud.

Crea o actualiza la página /calculadora-roi-pro en website 1 (Nextdoo).
Mantiene el layout original Nextdoo (navbar + footer) y embebe la calculadora
en el div#wrap usando un iframe (más seguro contra el parser XML de Odoo).

Requisitos:
    pip install requests

Variables de entorno:
    NEXTDOO_API_KEY   API key del usuario Odoo (admin o equivalente)

Uso:
    export NEXTDOO_API_KEY="..."
    python deploy_to_odoo.py                          # iframe a GitHub Pages
    python deploy_to_odoo.py --inline                 # inline HTML completo
    python deploy_to_odoo.py --url https://mi.cdn/   # iframe a otra URL
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import xmlrpc.client
from pathlib import Path

ODOO_URL = "https://www.nextdoo.cloud"
ODOO_DB = "nextdoo-sh-nextdoo-main-27318398"
ODOO_USER = "jeanlouis"
WEBSITE_ID = 1
PAGE_URL = "/calculadora-roi-pro"
PAGE_NAME = "Calculadora ROI Odoo Pro"
TEMPLATE_KEY = "website.calculadora_roi_pro"
IFRAME_DEFAULT = "https://supportboo.github.io/nextdoo-roi-calculator/"


def connect(api_key: str):
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, api_key, {})
    if not uid:
        raise SystemExit("Autenticación fallida. Revisa NEXTDOO_API_KEY.")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models


def build_iframe_arch(iframe_src: str) -> str:
    src = html.escape(iframe_src, quote=True)
    return f"""<t name="{PAGE_NAME}" t-name="{TEMPLATE_KEY}">
    <t t-call="website.layout">
        <div id="wrap">
            <section class="s_text_block" style="padding:0;background:#0A0A0A">
                <iframe src="{src}"
                        style="width:100%;border:0;display:block;min-height:100vh"
                        loading="lazy"
                        referrerpolicy="no-referrer-when-downgrade"
                        title="Calculadora ROI Odoo Nextdoo">
                </iframe>
            </section>
        </div>
    </t>
</t>"""


def extract_style_and_body(html_path: Path) -> tuple[str, str]:
    """Extrae <style> del <head> y contenido entre <body>...</body>."""
    raw = html_path.read_text(encoding="utf-8")
    style_match = re.search(r"<style[^>]*>(.*?)</style>", raw, re.DOTALL)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL)
    if not body_match:
        raise SystemExit("No se encontró <body> en index.html")
    style = style_match.group(1) if style_match else ""
    body = body_match.group(1)
    return style, body


def build_inline_arch(html_path: Path) -> str:
    style, body = extract_style_and_body(html_path)
    # Escape XML conflicts: parser Odoo es XML estricto.
    # Las entidades comunes ya están bien; solo cuidamos ampersands sueltos.
    body = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+);)", "&amp;", body)
    style = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+);)", "&amp;", style)
    return f"""<t name="{PAGE_NAME}" t-name="{TEMPLATE_KEY}">
    <t t-call="website.layout">
        <div id="wrap">
            <style>{style}</style>
            {body}
        </div>
    </t>
</t>"""


def upsert_view(models, uid, api_key: str, arch: str) -> int:
    """Crea o actualiza la vista QWeb con la `key` indicada."""
    existing = models.execute_kw(
        ODOO_DB, uid, api_key,
        "ir.ui.view", "search",
        [[("key", "=", TEMPLATE_KEY)]],
    )
    vals = {
        "name": PAGE_NAME,
        "key": TEMPLATE_KEY,
        "type": "qweb",
        "arch_db": arch,
        "active": True,
    }
    if existing:
        models.execute_kw(ODOO_DB, uid, api_key, "ir.ui.view", "write", [existing, vals])
        return existing[0]
    view_id = models.execute_kw(ODOO_DB, uid, api_key, "ir.ui.view", "create", [vals])
    return view_id


def upsert_page(models, uid, api_key: str, view_id: int) -> int:
    """Crea o actualiza la website.page apuntando a esa vista."""
    existing = models.execute_kw(
        ODOO_DB, uid, api_key,
        "website.page", "search",
        [[("url", "=", PAGE_URL), ("website_id", "=", WEBSITE_ID)]],
    )
    vals = {
        "url": PAGE_URL,
        "name": PAGE_NAME,
        "view_id": view_id,
        "website_id": WEBSITE_ID,
        "is_published": True,
        "website_indexed": True,
    }
    if existing:
        models.execute_kw(ODOO_DB, uid, api_key, "website.page", "write", [existing, vals])
        return existing[0]
    return models.execute_kw(ODOO_DB, uid, api_key, "website.page", "create", [vals])


def set_meta(models, uid, api_key: str, page_id: int):
    """Mete SEO tags por idioma. En Odoo 19 son translatables."""
    seo_es = {
        "website_meta_title": "Calculadora ROI Odoo — Nextdoo",
        "website_meta_description": (
            "Calcula en 2 minutos cuánto ahorrarás migrando a Odoo. ROI, payback, "
            "VAN y TIR con datos reales de Forrester, Aberdeen y Nucleus Research."
        ),
        "website_meta_keywords": "calculadora ROI Odoo, ahorro ERP, payback Odoo, VAN TIR ERP, Odoo partner Valencia",
    }
    models.execute_kw(
        ODOO_DB, uid, api_key,
        "website.page", "write",
        [[page_id], seo_es],
        {"context": {"lang": "es_ES"}},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inline", action="store_true", help="Inline HTML completo (sin iframe)")
    parser.add_argument("--url", default=IFRAME_DEFAULT, help="URL del iframe (si no --inline)")
    args = parser.parse_args()

    api_key = os.environ.get("NEXTDOO_API_KEY")
    if not api_key:
        sys.exit("Falta variable de entorno NEXTDOO_API_KEY")

    uid, models = connect(api_key)
    print(f"Autenticado uid={uid} en {ODOO_URL}")

    if args.inline:
        html_path = Path(__file__).resolve().parent.parent / "index.html"
        if not html_path.exists():
            sys.exit(f"No existe {html_path}")
        arch = build_inline_arch(html_path)
        print(f"Modo: inline ({html_path.stat().st_size//1024} KB)")
    else:
        arch = build_iframe_arch(args.url)
        print(f"Modo: iframe → {args.url}")

    view_id = upsert_view(models, uid, api_key, arch)
    print(f"Vista: id={view_id} key={TEMPLATE_KEY}")

    page_id = upsert_page(models, uid, api_key, view_id)
    print(f"Página: id={page_id} url={PAGE_URL}")

    set_meta(models, uid, api_key, page_id)
    print("SEO meta actualizado (es_ES)")

    print(f"\nPúblico en: {ODOO_URL}{PAGE_URL}")


if __name__ == "__main__":
    main()
