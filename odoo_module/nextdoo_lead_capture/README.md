# Nextdoo Lead Capture · Módulo Odoo 19

Endpoint unificado `/api/lead-magnet` para capturar leads de TODAS las landings de recursos Nextdoo (calculadora ROI, calculadora costes, checklist migración, guías, formularios demo).

## Qué hace

Cuando una landing dispara `POST /api/lead-magnet` con JSON:

1. Crea un **`crm.lead`** etiquetado con tags semánticos (`ROI Calculator`, `Lead Magnet`, `Sector: Retail`, etc).
2. Asigna automáticamente al CEO **Jeanlouis** (login `jeanlouis`).
3. Programa una **`mail.activity`** tipo *Llamada* con `date_deadline = HOY`.
4. Marca **prioridad alta** si urgencia ≤ 3 meses (3 estrellas).
5. Envía **email HTML** al asignado con paleta Nextdoo y botón directo al lead.
6. Postea en el chatter del lead el análisis completo (visible en el CRM).
7. Devuelve `{ok:true, lead_id}` al frontend para desbloquear el contenido gated.

## Instalación

```bash
# 1. Copiar a custom addons de la instancia Odoo
cp -r odoo_module/nextdoo_lead_capture /opt/odoo/custom/

# 2. Actualizar apps en Odoo
# Settings → Apps → Update Apps List
# Buscar "Nextdoo Lead Capture" → Install

# 3. Verificar endpoint disponible
curl -X OPTIONS https://www.nextdoo.cloud/api/lead-magnet -H "Origin: https://supportboo.github.io"
# Debe responder 204 con cabeceras CORS
```

## Test manual

```bash
curl -X POST https://www.nextdoo.cloud/api/lead-magnet \
  -H "Content-Type: application/json" \
  -H "Origin: https://supportboo.github.io" \
  -d '{
    "name": "Marc Herrero",
    "partner_name": "ACME Retail SL",
    "email_from": "marc@acme.com",
    "phone": "+34600000000",
    "function": "Director",
    "source": "roi-calculator",
    "urgency": "3m",
    "tags": ["Sector: Retail"],
    "analysis": {
      "facturacion": 2000000,
      "roi_anio1": 0.87,
      "payback_meses": 14
    }
  }'
```

Respuesta esperada:
```json
{"ok": true, "lead_id": 1234, "source": "roi-calculator"}
```

## Fuentes (source) soportadas

| Source value | Tags base aplicadas |
|---|---|
| `roi-calculator` | ROI Calculator, Lead Magnet |
| `cost-calculator` | Cost Calculator, Lead Magnet |
| `migration-checklist` | Migration Checklist, Lead Magnet |
| `retail-guide` | Retail Guide, Lead Magnet |
| `demo-request` | Demo Request |
| `consultation-request` | Consultation Request |

Cualquier `source` no listado recibe tag `Lead Magnet` por defecto.

## Configurar otro asignado

Editar `controllers/lead_magnet.py` línea 20:

```python
DEFAULT_ASSIGNEE_LOGIN = "jeanlouis"   # cambia aquí
```

## CORS · dominios permitidos

`controllers/lead_magnet.py` constante `CORS_ALLOWED_ORIGINS`. Por defecto acepta:

- `https://www.nextdoo.cloud`
- `https://supportboo.github.io`
- `https://www.boomatik.com`
- `http://localhost:*` (dev)

## Mapeo de campos JSON → Odoo

| JSON in | `crm.lead` field |
|---|---|
| `name` o `nombre` | `contact_name` |
| `partner_name` o `empresa` | `partner_name` |
| `email_from` o `email` | `email_from` |
| `phone` o `telefono` | `phone` |
| `function` o `cargo` | `function` |
| `description` | `description` (autogenerado si falta) |
| `tags[]` | `tag_ids` (upsert en `crm.tag`) |
| `urgency` 3m/6m/12m/explorar | `priority` 3/2/1/0 |

## Roadmap

- [x] v1.0 · ROI Calculator
- [ ] v1.1 · Hook para integrar también a calculadora-odoo (cost calc actual)
- [ ] v1.2 · Webhook a Slack/Telegram del CEO en paralelo
- [ ] v1.3 · Anti-spam (rate limit por IP + honeypot)
- [ ] v1.4 · A/B test de mail templates

## Licencia

LGPL-3
