# Calculadora ROI Odoo · Nextdoo

> Lead magnet de Nextdoo Cloud — Partner Odoo especialista en **retail y servicios** (Valencia, España).
> Calculadora ROI multi-paso con captura automática a CRM Odoo + actividad al comercial.

[![Odoo](https://img.shields.io/badge/Odoo-19-purple)](https://www.odoo.com) [![Lead Magnet](https://img.shields.io/badge/lead--magnet-gated-A855F7)]() [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Qué entrega

### Para el visitante
- Wizard de **4 pasos guiados** (empresa · situación actual · módulos · ajustes financieros).
- KPIs en vivo visibles desde el primer paso (ROI año 1, ahorro, payback).
- **Iconos oficiales Odoo** de cada módulo (servidos desde nextdoo.cloud).
- Selector de sector con **especialidad Nextdoo destacada** (★ Retail · ★ Servicios).
- Análisis detallado bloqueado tras registro: proyección 5 años, escenarios, VAN, TIR, sensibilidad, desglose por área, coste de inacción.

### Para Nextdoo (CRM)
- POST a `/api/lead-magnet` cuando el visitante envía sus datos.
- **`crm.lead`** creado con:
  - Tags semánticos: `ROI Calculator`, `Lead Magnet`, `Sector: Retail`…
  - Asignado a **Jeanlouis Rodes** (CEO) por defecto.
  - Prioridad alta (3 ★) si urgencia ≤ 3 meses.
  - Descripción completa con análisis financiero.
- **Actividad de llamada** con deadline **HOY**.
- **Email HTML** al asignado con paleta Nextdoo y botón directo al lead.
- Mensaje en chatter del lead para trazabilidad.

---

## Estructura del repo

```
nextdoo-roi-calculator/
├── index.html                      ← Calculadora (single-file, sin build)
├── odoo_module/
│   └── nextdoo_lead_capture/       ← Endpoint /api/lead-magnet
│       ├── __manifest__.py
│       ├── controllers/lead_magnet.py
│       ├── data/crm_tag_data.xml
│       ├── data/mail_template_data.xml
│       └── README.md
├── docs/
│   ├── BENCHMARKS.md               ← Fuentes Forrester, Nucleus, Aberdeen…
│   └── FORMULAS.md                 ← ROI, VAN, TIR, payback, sensibilidad
├── scripts/
│   └── deploy_to_odoo.py           ← Despliega como página Odoo
└── README.md
```

---

## Arranque rápido

### 1. Probar local (sin nada)
```bash
git clone https://github.com/supportboo/nextdoo-roi-calculator.git
cd nextdoo-roi-calculator
python -m http.server 8000          # → http://localhost:8000
```

> En modo local el POST a `/api/lead-magnet` fallará (CORS contra dominio inexistente). El formulario activa el **fallback automático**: guarda en `localStorage` y abre mailto al CEO. El detalle se desbloquea igualmente.

### 2. Configurar endpoint propio
```html
<script>window.NEXTDOO_LEAD_ENDPOINT = 'https://tu-dominio.com/api/lead-magnet';</script>
```

### 3. Producción · Nextdoo Cloud

#### 3.1 Desplegar la calculadora
```bash
cd scripts
export NEXTDOO_API_KEY="..."                # brain/API-KEYS.md
python deploy_to_odoo.py                    # iframe a GitHub Pages
# o
python deploy_to_odoo.py --inline           # mejor SEO
```

Crea `https://www.nextdoo.cloud/calculadora-roi-pro` y la indexa.

#### 3.2 Instalar el módulo de captura
```bash
# Copiar a custom addons
scp -r odoo_module/nextdoo_lead_capture user@vps:/opt/odoo/custom/

# En Odoo:
# Apps → Update Apps List → buscar "Nextdoo Lead Capture" → Install
```

#### 3.3 Verificar endpoint
```bash
curl -X POST https://www.nextdoo.cloud/api/lead-magnet \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email_from":"test@ex.com","partner_name":"ACME"}'
# → {"ok": true, "lead_id": ...}
```

---

## Personalización

### Paleta (si se reutiliza para otra marca)
Bloque `:root` (líneas 24–35 de `index.html`):
```css
--nd-primary:   #A855F7;
--nd-secondary: #EC4899;
--nd-bg:        #0A0A0A;
```

### Asignado / CEO
En `odoo_module/nextdoo_lead_capture/controllers/lead_magnet.py`:
```python
DEFAULT_ASSIGNEE_LOGIN = "jeanlouis"
```

### Sectores destacados
En `index.html` constante `SECTORS`, propiedad `spec: true` marca con badge "★ Especialidad":
```js
{ id:'retail',    name:'Retail · ecommerce',  spec:true,  coef:1.15, … },
{ id:'servicios', name:'Servicios profesionales', spec:true, coef:0.85, … },
```

### Otras landings de recursos
Replica el patrón: cualquier landing puede enviar el JSON a `/api/lead-magnet` con un `source` distinto y se etiqueta automáticamente:
```js
fetch('/api/lead-magnet', { method:'POST', headers:{'Content-Type':'application/json'},
  body: JSON.stringify({
    source: 'migration-checklist',    // se etiqueta como Migration Checklist + Lead Magnet
    name: '...', email_from: '...', partner_name: '...', urgency: '3m'
  })
});
```

Sources soportadas: `roi-calculator`, `cost-calculator`, `migration-checklist`, `retail-guide`, `demo-request`, `consultation-request`. Cualquier valor nuevo recibe tag `Lead Magnet` y se puede ampliar editando `SOURCE_TAGS` en el controller.

---

## Datos y benchmarks

| Métrica | Fuente | Año |
|---|---|---|
| ROI medio ERP | Nucleus Research | 2024 |
| Payback típico | Panorama Consulting | 2024 |
| Reducción inventario | Aberdeen Group | 2023 |
| Reducción coste admin | Deloitte | 2023 |
| Mejora DSO | PwC Working Capital | 2024 |
| Productividad usuario | IDC | 2023 |

Doc completa: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md). Fórmulas: [`docs/FORMULAS.md`](docs/FORMULAS.md).

---

## Iconos Odoo oficiales

Cada módulo usa su icono oficial Odoo:
```
https://www.nextdoo.cloud/{module_name}/static/description/icon.png
```

18 módulos cubiertos en `MODULES` (sale_management, crm, account_accountant, stock, purchase, mrp, website_sale, point_of_sale, website, project, hr, hr_timesheet, mass_mailing, helpdesk, sale_subscription, stock_barcode, sign, documents).

---

## Roadmap

- [x] v1.0 — Single-file con KPIs en vivo
- [x] v2.0 — Wizard real 4 pasos · iconos Odoo oficiales · lead gate · módulo CRM
- [ ] v2.1 — Export PDF business case (jsPDF)
- [ ] v2.2 — Estado en URL (compartir resultado por enlace)
- [ ] v2.3 — Comparativa contra SAP / Sage / MS Dynamics
- [ ] v2.4 — Versión inglés y francés
- [ ] v2.5 — Variante Boomatik (mismo motor, paleta `#875A7B / #FFD700`)

---

## Otras landings de recursos Nextdoo a integrar

El mismo módulo `nextdoo_lead_capture` ya soporta:
- `/calculadora-odoo` (cost calculator existente) — añadir POST con `source: 'cost-calculator'`
- `/checklist-migracion-odoo` — `source: 'migration-checklist'`
- `/guia-odoo-retail` — `source: 'retail-guide'`
- `/prueba-gratis` (trial) — `source: 'demo-request'`

Todas las landings de recursos tienen que ser lead magnet · cero descargas sin registro.

---

## Licencia

[MIT](LICENSE) © 2026 Nextdoo Cloud / Boomatik S.C.P.

---

**Hecho por** [Nextdoo](https://www.nextdoo.cloud) — Partner Odoo Ready Retail Valencia.
+34 622 891 192 · info@nextdoo.cloud
