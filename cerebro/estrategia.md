# Estrategia

## Situación actual (21 de Abril 2026 — semana 17)

Maleu está en el **mes 2 de Q1 (Marzo-Mayo)**. Tadeo opera solo desde febrero 2026.

Marzo cerró por encima del objetivo: **$7.49M facturados** vs objetivo $5M. Abril hasta hoy va en **$4.13M con 73 pedidos entregados** (Home 61 / Clubes 7 / Pilar 3 / Red 4). El año acumulado va en **$15.36M con 275 entregas**.

> Nota: la estrategia Q1 está en revisión. Después del cierre de Marzo (muy por encima de objetivos) hay que rehacer el modelo de objetivos Abril/Mayo a partir de los datos reales del Panel. **No usar las metas viejas** (Marzo $5M / Abril $6M / Mayo $7M VD) como referencia hasta que se replanteen.

---

## Stack operativo actual

| Herramienta | Función |
|---|---|
| **WhatsApp Business + WATI** | Canal principal de ventas, atención y campañas. WATI es la única BBDD desde 13/04. |
| **Tienda online** (`maleupedidos.github.io`) | 3 zonas: Estancias / Pilar y Alrededores / Clubes |
| **Panel admin** (`panel.html`) | Pedidos, caja, stock, ventas — dashboard real-time desde el celular |
| **Búsqueda / Abastecimiento** (`busqueda.html`) | PWA para comprar a proveedores |
| **Ruta de entregas** (`ruta.html`) | PWA offline-first para delivery |
| **Portal Red** (`red.html`) | Login de vendedores + dashboard + nuevo pedido |
| **Google Apps Script** | Backend único de todas las webs |
| **Google Sheets "Maleu - Pedidos"** | Base de datos transaccional (21 hojas) |
| **N8N** | Solo Confirmación Pedido activa. Resto desactivado. |
| **Instagram / Facebook** | Captación y contenido |

**Excels discontinuados**: Excel MALEU 2026 ya no se usa para campañas. Excel Contactos Personal Tadeo tampoco. Todo migrado a WATI.

---

## Canales de venta

### 1. Venta Directa (principal)
100% WhatsApp. Familias y personas en Estancias del Pilar y zona Pilar.

| Sub-canal | Zona | Días entrega |
|---|---|---|
| **Home** | Estancias del Pilar + Los Alcanfores + Estancias del Río | Lun, Mié, Vie, Sáb 19-21hs · Dom 11-13hs |
| **Pilar** | Resto de Pilar | Mié y Vie a coordinar (envío $3.000, gratis +$25K) |

> Capital Federal **discontinuado** como zona pública (la hoja del Sheets queda como histórico). Quien vive en CABA ahora pide por "Pilar y Alrededores".

Producto estrella: la pizza. → Plan detallado: [[plan-ventas-q1-venta-directa]]

### 2. Maleu Clubes (principal)
Solución de tercer tiempo. Pizza finita pre-cocida a $7.000/unidad. Entrega en puerta del club.

**Estado actual (29/04/2026): 8 clientes activos en 4 clubes.**
- **Champagnat** — 5 clientes (Hockey línea A, B, C, D + PUB veteranos rugby)
- **Jesús María** — 1 cliente (todo el club de hockey, sumado el 29/04)
- **Atlético Pilar** — 1 cliente (Plantel Superior de hockey)
- **Los Pinos** — 1 cliente (Infantiles de hockey)
- **Posible**: Los Molinos plantel superior

→ Detalle completo y evolución: [[01-Ventas/clubes-clientes]]
→ Plan Q1: [[plan-ventas-q1-clubes]]

**Snapshot histórico:**
- 21/04/2026: 8 clubes contactados con actividad real o reciente — Champagnat, Los Molinos, Los Pinos, Deportiva Francesa, San Patricio, Atlético Pilar, St. Brendan's, Banco Nación.
- 29/04/2026: cambio de métrica (clientes ≠ clubes). St. Brendan's y Banco Nación ya no están interesados. Entra Jesús María.

### 3. Maleu Red (secundario)
Vendedores independientes. 17% comisión. **1 vendedor activo: Marcos Bottcher** (Garín, El Lucero / Los Tacos). En Abril: 4 pedidos / $331.200.

### 4. Catering (pasivo)
Eventos y reuniones. No se promociona, se toma si cae.

### 5. B2B (pasivo)
Restaurantes, mini markets. Sin foco.

---

## Tono de comunicación
- Directo, cálido, resolutivo
- Nunca usar "congelado/congelados" → siempre **"listos para cocinar"**
- Frase ancla: **"Rico y listo en minutos."**
- → Personalidad completa: [[identidad-marca]]

---

## Palancas de crecimiento

### Canal Venta Directa

**Palanca 1 — Visibilidad dentro del barrio**
El 80% de Estancias todavía no sabe que Maleu existe. Presencia física (flyers), reactivación de base dormida, presencia en redes locales.

**Palanca 2 — Activación de la base dormida**
Reactivar a quien compró una sola vez cuesta menos que conseguir clientes nuevos. Mensaje personalizado por WhatsApp, sin descuento, solo presencia.

**Palanca 3 — Boca a boca estructurado**
Programa de referidos. Los recurrentes son promotores activos.

**Palanca 4 — Contenido en redes con foco local**
Instagram + WhatsApp Status. Mínimo 3 posteos/semana. Status todos los días de entrega.

**Palanca 5 — Ticket promedio**
Hoy ~$49.727 (acumulado año). El catálogo permite combos naturales. Sugerir en el momento de la compra.

### Canal Clubes

**Palanca 1 — Profundidad dentro del club**
Antes de buscar clubes nuevos, agotar el potencial del actual. Cada categoría es un cliente.

**Palanca 2 — Volumen de contactos semanales**
Meta: **5 clubes nuevos por semana** de forma consistente.

**Palanca 3 — Boca a boca entre encargados**
Activar explícitamente referidos cruzados entre clubes.

**Palanca 4 — Expansión de deportes**
Rugby y hockey son la base. Fútbol, básquet, vóley para explorar.

---

## Cuello de botella actual

**Visibilidad y consistencia.** El producto y la operación funcionan. Falta consistencia semana a semana.

- VD: la sem 15 hizo 34 pedidos Home; la 16 bajó a 24. Mucho rebote.
- Clubes: el crecimiento depende de cuántos clubes se contactan por semana.

---

## Foco esta semana (semana 17)

→ Ver [[prioridades-semana]]
**Meta: 50 pedidos entregados sumando Home + Pilar + Clubes** entre el 21 y 27 de abril.

---

## Riesgos principales

| Riesgo | Canal | Acción |
|---|---|---|
| Tadeo no da abasto | Ambos | Definir límite de pedidos/día. Planificar con anticipación. |
| Base dormida no reactiva | VD | Ofrecer motivo concreto, no descuento. |
| Clubes no responden | Clubes | Seguimiento a los 7 días. |
| Producto sin stock | Ambos | Buffer mínimo de los 3 productos más vendidos. Hoy: empanadas CaC y JyQ críticos. |
| Margen ajustado Clubes | Clubes | Mantener precio hasta consolidar. Revisar aumento desde Mayo. |
| Competencia (Frizata, otros) | VD | Diferenciarse por cercanía, confianza y experiencia local. |

---

## Métricas de seguimiento semanal

**Cada domingo registrar (desde el Panel):**

| Métrica | Canal |
|---|---|
| Pedidos de la semana (Home + Pilar + Clubes) | VD + Clubes |
| Facturación de la semana | Todos |
| Ticket promedio | VD |
| Clientes únicos | VD |
| Pedidos por día de entrega | Home |
| Clubes contactados / cerrados | Clubes |
| Stock crítico al cierre | Ops |

---

*Documento vivo — actualizar al cierre de cada mes. Última actualización: 21 de Abril 2026.*
