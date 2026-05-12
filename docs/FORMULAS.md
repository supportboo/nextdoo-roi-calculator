# Fórmulas financieras — Calculadora ROI Odoo Nextdoo

Todas las fórmulas implementadas en `index.html` (función `calculate()`).
Notación: `t` = año (1..5), `n` = horizonte de análisis (años).

## 1. Ahorro anual bruto

```
ahorro_bruto(t) = Σ (coste_area_i × % ahorro_i × coef_sector × adopcion(t))
                 para cada área activada i
```

`coste_area_i` se estima como `% facturacion_area_i × facturacion_anual`.

Distribución típica del coste operativo por área (sobre facturación):

| Área | % facturación |
|---|---|
| Finanzas | 1.5 % |
| Ventas + CRM | 3.0 % |
| Inventario / Almacén | 4.0 % |
| Compras | 2.0 % |
| Producción | 8.0 % (solo manufactura) |
| Ecommerce | 2.5 % |
| RR. HH. | 1.8 % |
| Reporting / BI | 0.4 % |

## 2. Inversión y coste recurrente

```
inversion_total = horas_consultor × 75 € + licencias_año_1
coste_recurrente(t) = licencias_anuales + mantenimiento + soporte
```

Si el usuario no indica, defaults:
- Pack Starter: 2 990 €
- Pack Business: 5 990 €
- Pack Enterprise: 9 990 €
- Licencias Odoo Enterprise: 31,10 € / usuario / mes (precio público 2026)

## 3. Cash flow neto anual

```
cash_flow(t) = ahorro_bruto(t) − coste_recurrente(t)
cash_flow(0) = −inversion_total
```

## 4. ROI año 1

```
ROI_año_1 = (ahorro_bruto(1) − coste_recurrente(1)) / inversion_total × 100
```

## 5. ROI acumulado N años

```
ROI_acumulado(N) = Σ cash_flow(t) desde t=1..N / inversion_total × 100
```

## 6. Payback (sin descontar)

```
Encontrar T tal que Σ cash_flow(t) desde t=1..T ≥ inversion_total
payback_meses = (T − 1) × 12 + (gap / cash_flow(T)) × 12
```

## 7. Payback descontado

Igual que (6) pero usando `cash_flow(t) / (1+WACC)^t`.

## 8. VAN (Net Present Value)

```
VAN = −inversion_total + Σ cash_flow(t) / (1+WACC)^t   para t=1..n
```

## 9. TIR (Internal Rate of Return)

Tasa `r` que cumple `VAN(r) = 0`. Se resuelve numéricamente por bisección entre 0 % y 200 %.

## 10. Curva de adopción

Por defecto: 60 / 85 / 95 / 95 / 95 (%) años 1..5. Editable.

## 11. Coste de inacción a 7 años

```
coste_inaccion = (mantenimiento_actual × 7) + (ahorro_potencial_anual × 5) × factor_oportunidad
```

`factor_oportunidad = 0.70` (asumimos que solo el 70 % del ahorro se realiza si se posterga, por intereses, fricción, deuda técnica).

## 12. Análisis de escenarios

Tres curvas paralelas con multiplicadores de adopción:

| Escenario | Multiplicador | Notas |
|---|---|---|
| Conservador | 0.80 | Asume resistencia interna alta |
| Base | 1.00 | Caso esperado |
| Optimista | 1.15 | Adopción acelerada + ahorros secundarios |

## 13. Sensibilidad VAN

Matriz 5×5 que varía WACC (filas: 4 %, 6 %, 8 %, 10 %, 12 %) y crecimiento anual (cols: 0 %, 3 %, 5 %, 7 %, 10 %). El crecimiento amplifica `ahorro_bruto(t) × (1+g)^(t−1)`.

## 14. TCO 7 años (comparativa)

```
TCO_actual_7y   = (lic_actual + mantenim + horas_TI) × 7
TCO_odoo_7y     = inversion + Σ coste_recurrente(t) desde t=1..7
ahorro_TCO      = TCO_actual_7y − TCO_odoo_7y
```

## 15. Fiabilidad del análisis (reliability score)

Score 0–100 que mide cuántos inputs críticos se han rellenado:

```
reliability = (inputs_provistos / inputs_totales) × 100
```

Si reliability < 70 % se muestra warning "estimación orientativa".

---

## Implementación en JS

Ver función `calculate()` en `index.html` (~ líneas 600–900).
Tests rápidos en `scripts/test_formulas.html` (caso golden: empresa 5 M € retail con pack Business → ROI año 1 ≈ 95 %, payback ≈ 14 m).
