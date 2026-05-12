# Calculadora ROI Odoo · Nextdoo

> Calculadora interactiva de retorno de inversión para empresas que evalúan migrar a Odoo.
> Inspirada en [roierp.com](https://roierp.com), reescrita con datos reales y estilo Nextdoo.

[![Odoo](https://img.shields.io/badge/Odoo-19-purple)](https://www.odoo.com) [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE) [![Status](https://img.shields.io/badge/status-production--ready-success)]()

---

## Qué hace

Devuelve, en menos de 2 minutos y sin email obligatorio, los KPIs financieros de migrar a Odoo:

- **ROI año 1** y ROI acumulado 5 años.
- **Ahorro anual** por área funcional (finanzas, ventas, inventario, producción…).
- **Payback** simple y descontado.
- **VAN** y **TIR** a 5 años con WACC ajustable.
- **TCO** comparado a 7 años (sistema actual vs Odoo).
- **Análisis de sensibilidad** (matriz WACC × crecimiento).
- **Escenarios** conservador / base / optimista.
- **Coste de inacción** mensual y a 7 años.
- **Captura de lead** con resumen al equipo Nextdoo.

Todos los cálculos están documentados y son auditables. Fuentes en [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md), fórmulas en [`docs/FORMULAS.md`](docs/FORMULAS.md).

---

## Estructura del repo

```
nextdoo-roi-calculator/
├── index.html              ← Calculadora completa (single-file, sin build step)
├── docs/
│   ├── BENCHMARKS.md       ← Fuentes (Forrester, Nucleus, Aberdeen…) y coeficientes
│   └── FORMULAS.md         ← Fórmulas ROI, VAN, TIR, payback, sensibilidad
├── scripts/
│   └── deploy_to_odoo.py   ← Embed en Odoo Nextdoo via XML-RPC
├── assets/                 ← Logos y recursos opcionales
├── LICENSE                 ← MIT
└── README.md
```

---

## Uso rápido

### 1. Abrir local (sin servidor)

```bash
git clone https://github.com/supportboo/nextdoo-roi-calculator.git
cd nextdoo-roi-calculator
# Doble click en index.html
```

Funciona offline. Tailwind se carga desde CDN; cae al sistema de fuentes si no hay red.

### 2. Servir como página estática

Cualquier hosting de archivos estáticos funciona:

```bash
python -m http.server 8000
# → http://localhost:8000
```

Compatible con: GitHub Pages, Cloudflare Pages, Vercel, Netlify, Hostinger, IONOS, Odoo Website.

### 3. Embeber en Odoo (Nextdoo o cualquier instancia)

Dos opciones:

**A. Vista QWeb dedicada** (recomendado para SEO):
```bash
cd scripts
export NEXTDOO_API_KEY="tu_api_key"
python deploy_to_odoo.py
# → Crea/actualiza la página /calculadora-roi-pro en nextdoo.cloud
```

**B. Iframe en página existente**:
```html
<iframe src="https://www.nextdoo.cloud/calculator/" width="100%" height="2200" frameborder="0"></iframe>
```

---

## Configuración

### Endpoint de lead (formulario final)

Por defecto el formulario hace `POST` a `https://www.nextdoo.cloud/website/form/crm.lead`. Si quieres otro endpoint, define antes de `<script>`:

```html
<script>window.NEXTDOO_LEAD_ENDPOINT = 'https://mi-crm.com/leads';</script>
```

Como fallback (si la petición CORS falla en producción standalone) abre el cliente de email con el resumen prerellenado al destinatario `jeanlouis@nextdoo.cloud`.

### Datos por defecto

Editables sin tocar JS — modifica los `<select>` y `<input>` en `index.html`. Pre-selección de módulos por sector está en la constante `DEFAULT_MODS` del script.

### Personalizar branding

Toda la paleta vive en `:root` (líneas 24-35 del CSS):

```css
--nd-primary: #A855F7;   /* violeta principal */
--nd-secondary: #EC4899; /* rosa secundario */
--nd-bg: #0A0A0A;        /* fondo dark */
```

Cambia esos 3 valores y la calculadora se adapta a otra marca (Boomatik usaría `#875A7B / #FFD700`).

---

## Datos y benchmarks

Cada porcentaje de ahorro que aparece en la calculadora está respaldado por estudios públicos del sector ERP:

| Métrica | Fuente | Año |
|---|---|---|
| ROI medio ERP | Nucleus Research | 2024 |
| Payback típico | Panorama Consulting | 2024 |
| Reducción inventario | Aberdeen Group | 2023 |
| Reducción coste admin | Deloitte | 2023 |
| Mejora DSO | PwC Working Capital Survey | 2024 |
| Productividad usuario | IDC | 2023 |

Tabla completa en [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

---

## Iconografía Odoo

Cada módulo Odoo se representa con su SVG propio y color corporativo del módulo:

- **Ventas** `#714B67` · **CRM** `#C8385A` · **Contabilidad** `#0E6537`
- **Inventario** `#017E84` · **Compras** `#8E44AD` · **Fabricación** `#7C3AED`
- **Ecommerce** `#ED7D31` · **TPV** `#5B8FB9` · **Website** `#017E84`
- **Proyectos** `#3B82F6` · **RR. HH.** `#F59E0B` · **Marketing** `#EC4899`
- **Helpdesk** `#10B981` · **Barcode** `#71717A` · **Firma** `#A855F7`

Los iconos SVG están inline en el `<defs>` al inicio de `index.html` (id `ic-*`).

---

## Roadmap

- [x] v1.0 — Calculadora single-file con benchmarks reales
- [x] v1.0 — Captura de lead con resumen
- [x] v1.0 — Iconos oficiales Odoo
- [x] v1.0 — Charts SVG nativos (break-even, radar, sensibilidad)
- [ ] v1.1 — Export PDF business case (jsPDF)
- [ ] v1.1 — Compartir resultado por enlace (estado en URL)
- [ ] v1.2 — Comparativa contra SAP / Sage / Microsoft Dynamics
- [ ] v1.2 — Versión en/fr/pt
- [ ] v1.3 — Integración Calendly para reserva directa

---

## Despliegue actual

| Entorno | URL | Estado |
|---|---|---|
| Producción Nextdoo | https://www.nextdoo.cloud/calculadora-roi-pro | Pendiente deploy |
| GitHub Pages | https://supportboo.github.io/nextdoo-roi-calculator/ | Opcional |
| Local | `file:///.../index.html` | Funciona ✓ |

---

## Contribuir

Pull requests bienvenidos. Para cambios grandes abre primero un issue.

Para ajustar fórmulas o coeficientes: edita el bloque `MODULES`, `AREA_PCT` y `SECTOR_COEF` al inicio del `<script>` de `index.html`.

---

## Licencia

[MIT](LICENSE) © 2026 Nextdoo Cloud / Boomatik S.C.P.

---

**Hecho por** [Nextdoo](https://www.nextdoo.cloud) — Partner Odoo Ready en Valencia.
Mantenido junto a [Boomatik](https://www.boomatik.com), ecosistema de agentes IA para Odoo Partners.
