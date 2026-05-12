"""
deploy_to_odoo.py — Embebe landings del repo como páginas Odoo en Nextdoo Cloud.

Crea o actualiza páginas en website 1 (Nextdoo) usando un iframe a la versión
GitHub Pages — los pushes al repo se reflejan en producción sin re-deploy.

Páginas soportadas:
    roi          → /calculadora-roi-pro      (index.html)
    checklist    → /checklist-migracion-odoo (checklist/index.html)

Variables de entorno:
    NEXTDOO_API_KEY   API key del usuario Odoo (admin o equivalente)

Uso:
    export NEXTDOO_API_KEY="..."
    python deploy_to_odoo.py                    # deploy roi (compat retro)
    python deploy_to_odoo.py --page roi
    python deploy_to_odoo.py --page checklist
    python deploy_to_odoo.py --page roi --inline   # inline QWeb (mejor SEO)
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
GH_PAGES_BASE = "https://supportboo.github.io/nextdoo-roi-calculator"

# Registry de páginas a desplegar.
PAGES = {
    "roi": {
        "url": "/calculadora-roi-pro",
        "name": "Calculadora ROI Odoo Pro",
        "template_key": "website.calculadora_roi_pro",
        "iframe_src": f"{GH_PAGES_BASE}/",
        "html_relpath": "index.html",
        "meta": {
            "website_meta_title": "Calculadora ROI Odoo — Nextdoo",
            "website_meta_description": (
                "Calcula en 2 minutos cuánto ahorrarás migrando a Odoo. "
                "Análisis personalizado por Jeanlouis (CEO Nextdoo) en 24 h."
            ),
            "website_meta_keywords": "calculadora ROI Odoo, ahorro ERP, payback Odoo, VAN TIR ERP, Odoo partner Valencia retail",
        },
    },
    "checklist": {
        "url": "/checklist-migracion-odoo",
        "name": "Checklist Migración Odoo · 42 puntos",
        "template_key": "website.checklist_migracion_odoo",
        "iframe_src": f"{GH_PAGES_BASE}/checklist/",
        "html_relpath": "checklist/index.html",
        "meta": {
            "website_meta_title": "Checklist Migración Odoo · 42 puntos · Nextdoo",
            "website_meta_description": (
                "Descarga gratis la guía con los 42 puntos críticos para migrar "
                "a Odoo sin sustos. Método Nextdoo. PDF al instante en tu email."
            ),
            "website_meta_keywords": "checklist migracion odoo, guia odoo, migrar odoo, 42 puntos odoo, Nextdoo partner",
        },
    },
}


def connect(api_key: str):
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, api_key, {})
    if not uid:
        raise SystemExit("Autenticación fallida. Revisa NEXTDOO_API_KEY.")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models


def build_iframe_arch(page_cfg: dict, iframe_src: str | None = None) -> str:
    src = html.escape(iframe_src or page_cfg["iframe_src"], quote=True)
    return f"""<t name="{page_cfg['name']}" t-name="{page_cfg['template_key']}">
    <t t-call="website.layout">
        <div id="wrap">
            <section class="s_text_block" style="padding:0;background:#0A0A0A">
                <iframe src="{src}"
                        style="width:100%;border:0;display:block;min-height:100vh"
                        loading="lazy"
                        referrerpolicy="no-referrer-when-downgrade"
                        title="{html.escape(page_cfg['name'], quote=True)}">
                </iframe>
            </section>
        </div>
    </t>
</t>"""


def extract_style_and_body(html_path: Path) -> tuple[str, str]:
    raw = html_path.read_text(encoding="utf-8")
    style_match = re.search(r"<style[^>]*>(.*?)</style>", raw, re.DOTALL)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL)
    if not body_match:
        raise SystemExit(f"No se encontró <body> en {html_path}")
    style = style_match.group(1) if style_match else ""
    body = body_match.group(1)
    return style, body


def build_inline_arch(page_cfg: dict, html_path: Path) -> str:
    style, body = extract_style_and_body(html_path)
    # Escape XML conflicts: parser Odoo es XML estricto.
    body = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+);)", "&amp;", body)
    style = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+);)", "&amp;", style)
    return f"""<t name="{page_cfg['name']}" t-name="{page_cfg['template_key']}">
    <t t-call="website.layout">
        <div id="wrap">
            <style>{style}</style>
            {body}
        </div>
    </t>
</t>"""


def upsert_view(models, uid, api_key: str, page_cfg: dict, arch: str) -> int:
    existing = models.execute_kw(
        ODOO_DB, uid, api_key,
        "ir.ui.view", "search",
        [[("key", "=", page_cfg["template_key"])]],
    )
    vals = {
        "name": page_cfg["name"],
        "key": page_cfg["template_key"],
        "type": "qweb",
        "arch_db": arch,
        "active": True,
    }
    if existing:
        models.execute_kw(ODOO_DB, uid, api_key, "ir.ui.view", "write", [existing, vals])
        return existing[0]
    return models.execute_kw(ODOO_DB, uid, api_key, "ir.ui.view", "create", [vals])


def upsert_page(models, uid, api_key: str, page_cfg: dict, view_id: int) -> int:
    existing = models.execute_kw(
        ODOO_DB, uid, api_key,
        "website.page", "search",
        [[("url", "=", page_cfg["url"]), ("website_id", "=", WEBSITE_ID)]],
    )
    vals = {
        "url": page_cfg["url"],
        "name": page_cfg["name"],
        "view_id": view_id,
        "website_id": WEBSITE_ID,
        "is_published": True,
        "website_indexed": True,
    }
    if existing:
        models.execute_kw(ODOO_DB, uid, api_key, "website.page", "write", [existing, vals])
        return existing[0]
    return models.execute_kw(ODOO_DB, uid, api_key, "website.page", "create", [vals])


def set_meta(models, uid, api_key: str, page_cfg: dict, page_id: int):
    models.execute_kw(
        ODOO_DB, uid, api_key,
        "website.page", "write",
        [[page_id], page_cfg["meta"]],
        {"context": {"lang": "es_ES"}},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--page", choices=list(PAGES.keys()), default="roi",
        help="Página a desplegar (default: roi)",
    )
    parser.add_argument("--inline", action="store_true", help="Inline HTML completo (sin iframe)")
    parser.add_argument("--url", default=None, help="URL del iframe (sobrescribe default)")
    parser.add_argument(
        "--all", action="store_true",
        help="Desplegar todas las páginas configuradas",
    )
    args = parser.parse_args()

    api_key = os.environ.get("NEXTDOO_API_KEY")
    if not api_key:
        sys.exit("Falta variable de entorno NEXTDOO_API_KEY")

    uid, models = connect(api_key)
    print(f"Autenticado uid={uid} en {ODOO_URL}")

    pages_to_deploy = list(PAGES.keys()) if args.all else [args.page]

    for page_key in pages_to_deploy:
        page_cfg = PAGES[page_key]
        print(f"\n>> Deploy {page_key} → {page_cfg['url']}")

        if args.inline:
            html_path = Path(__file__).resolve().parent.parent / page_cfg["html_relpath"]
            if not html_path.exists():
                print(f"  ! No existe {html_path} — skip")
                continue
            arch = build_inline_arch(page_cfg, html_path)
            print(f"  Modo: inline ({html_path.stat().st_size//1024} KB)")
        else:
            arch = build_iframe_arch(page_cfg, args.url)
            print(f"  Modo: iframe → {args.url or page_cfg['iframe_src']}")

        view_id = upsert_view(models, uid, api_key, page_cfg, arch)
        print(f"  Vista: id={view_id} key={page_cfg['template_key']}")

        page_id = upsert_page(models, uid, api_key, page_cfg, view_id)
        print(f"  Página: id={page_id} url={page_cfg['url']}")

        set_meta(models, uid, api_key, page_cfg, page_id)
        print(f"  SEO meta actualizado (es_ES)")
        print(f"  → Público en: {ODOO_URL}{page_cfg['url']}")


if __name__ == "__main__":
    main()
