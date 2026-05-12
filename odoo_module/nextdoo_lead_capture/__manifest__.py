# -*- coding: utf-8 -*-
{
    "name": "Nextdoo Lead Capture · Lead Magnets",
    "version": "19.0.1.0.0",
    "summary": "Endpoint /api/lead-magnet para capturar leads de calculadoras y recursos descargables.",
    "description": """
Captura unificada de leads para todas las landings de recursos Nextdoo
(calculadora ROI, calculadora costes, checklist migración, guías…).

* POST /api/lead-magnet — JSON-in, JSON-out, CORS abierto.
* Crea crm.lead con tags semánticos (ROI Calculator, Sector, fuente).
* Asigna automáticamente a Jeanlouis (CEO Nextdoo, UID 2).
* Crea mail.activity con deadline HOY tipo 'Llamada'.
* Notifica al CEO por email + bus channel en tiempo real.
* Marca prioridad alta (3 estrellas) si urgencia <= 3 meses.

Lead magnets soportados (campo `source`):
- roi-calculator
- cost-calculator
- migration-checklist
- retail-guide
- demo-request
- consultation-request
""",
    "author": "Nextdoo Cloud / Boomatik",
    "website": "https://www.nextdoo.cloud",
    "category": "Sales/CRM",
    "license": "LGPL-3",
    "depends": ["crm", "mail", "website"],
    "data": [
        "security/ir.model.access.csv",
        "data/crm_tag_data.xml",
        "data/mail_template_data.xml",
        "report/checklist_migracion_report.xml",
        "report/checklist_migracion_template.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
