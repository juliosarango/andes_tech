# Consultas preparadas para la demo en vivo
## AWS GenAI Day Ecuador 2026 — AndesTech MCP Demo

> **Tip general:** antes de cada consulta, muestra la terminal con el MCP Server corriendo.
> El logging `🔧 Claude invocó →` aparece en tiempo real — es el gancho visual de la demo.

---

## Nivel 1 — Una herramienta, resultado inmediato

*Objetivo: mostrar que Claude sabe cuándo y cómo llamar a una herramienta.*

---

### 1.1 Stock de un producto específico

```
¿Cuántas unidades tenemos del Monitor LG 27 pulgadas?
```

**Herramienta que invoca Claude:** `buscar_producto("Monitor LG 27")`

**Qué verás en el log:**
```
🔧 Claude invocó → buscar_producto(query='Monitor LG 27')
```

**Respuesta esperada:** Claude confirma que hay 6 unidades del Monitor LG 27 Full HD IPS a $279.99, stock OK.

**Punto de charla:** *"Claude no adivinó el dato — llamó a una herramienta real que consultó nuestra base de datos en EC2."*

---

### 1.2 Alerta de inventario

```
¿Qué productos necesitan reabastecimiento urgente?
```

**Herramienta:** `productos_stock_bajo()`

**Qué verás en el log:**
```
🔧 Claude invocó → productos_stock_bajo()
```

**Respuesta esperada:** Lista de 5 productos con déficit, el más crítico el Cargador USB-C Anker (stock 2, mínimo 8, déficit 6).

**Punto de charla:** *"Ningún prompt engineering especial. La descripción de la herramienta es lo que le dice a Claude cuándo usarla."*

---

## Nivel 2 — Filtrado y parámetros

*Objetivo: Claude elige parámetros correctos según el contexto de la pregunta.*

---

### 2.1 Agenda de seguimientos de la semana

```
¿Qué leads del CRM necesitan seguimiento esta semana?
```

**Herramienta:** `leads_por_seguir(dias=7)`

**Qué verás en el log:**
```
🔧 Claude invocó → leads_por_seguir(dias=7)
```

**Respuesta esperada:** 5 leads con seguimiento entre el 9 y el 16 de mayo 2026, valor total en juego ~$60,700.

**Punto de charla:** *"Claude calculó solo las fechas — hoy + 7 días. No le di las fechas, le di la intención."*

---

### 2.2 Pipeline filtrado por estado

```
Muéstrame solo los leads que están actualmente en negociación
```

**Herramienta:** `listar_leads(estado="en_negociacion")`

**Qué verás en el log:**
```
🔧 Claude invocó → listar_leads(estado='en_negociacion')
```

**Respuesta esperada:** 4 leads en negociación con valor total de pipeline ~$62,000.

---

### 2.3 Ventas recientes del negocio

```
Dame las últimas 8 ventas registradas
```

**Herramienta:** `ventas_recientes(limite=8)`

**Qué verás en el log:**
```
🔧 Claude invocó → ventas_recientes(limite=8)
```

**Respuesta esperada:** Lista de las 8 ventas más recientes (mayo 2026), con estado ✅/⏳/❌.

---

## Nivel 3 — Encadenamiento de herramientas

*Objetivo: una sola pregunta hace que Claude llame a 2-3 herramientas en secuencia.*

---

### 3.1 Perfil completo de una cliente

```
Busca a la cliente María Fernanda López y dame su historial completo de compras
```

**Herramientas en secuencia:**
1. `listar_clientes(busqueda="María Fernanda")`  → obtiene ID 1
2. `historial_cliente(cliente_id=1)` → obtiene historial completo

**Qué verás en el log:**
```
🔧 Claude invocó → listar_clientes(busqueda='María Fernanda')
🔧 Claude invocó → historial_cliente(cliente_id=1)
```

**Respuesta esperada:** Perfil de María Fernanda López de Constructora Andina S.A. (Quito), 4 pedidos, monto total $3,449.92, incluyendo una laptop pendiente.

**Punto de charla:** *"Dos llamadas a herramientas distintas, encadenadas automáticamente. Yo solo hice una pregunta."*

---

### 3.2 Alerta + borrador de email al proveedor

```
¿Cuál es el producto con mayor déficit de stock?
Redacta un email profesional al proveedor solicitando reabastecimiento urgente.
```

**Herramienta:** `productos_stock_bajo()` → Claude elige el de mayor déficit → redacta el email

**Qué verás en el log:**
```
🔧 Claude invocó → productos_stock_bajo()
```

**Respuesta esperada:** Claude identifica el Cargador USB-C Anker (déficit 6) y el Mouse Rapoo (déficit 6), y redacta un email a "Anker Distribuidora Ecuador" solicitando 20 unidades con urgencia.

**Punto de charla:** *"El dato viene de la BD, la redacción viene del modelo. Ningún humano escribió ese email."*

---

### 3.3 Detalle de un lead con seguimiento hoy

```
Dame todos los detalles del lead de Hotel Quito Imperial, incluyendo sus notas internas
```

**Herramientas:**
1. `listar_leads(estado="en_negociacion")` → identifica lead ID 1
2. `detalle_lead(lead_id=1)` → ficha completa con notas

**Qué verás en el log:**
```
🔧 Claude invocó → listar_leads(estado='en_negociacion')
🔧 Claude invocó → detalle_lead(lead_id=1)
```

**Respuesta esperada:** Ficha de Carlos Mendoza Villacís, Hotel Quito Imperial, $12,500, seguimiento el 12 de mayo, nota: *"Interesado en financiamiento a 12 meses"*.

---

## Nivel 4 — Razonamiento sobre datos

*Objetivo: Claude analiza, compara y saca conclusiones propias a partir de múltiples herramientas.*

---

### 4.1 Comparativa de ventas mes a mes

```
Compara las ventas de abril versus marzo por categoría.
¿Qué categoría creció más y cuál cayó?
```

**Herramientas en paralelo/secuencia:**
1. `ventas_por_categoria("2026-03-01", "2026-03-31")`
2. `ventas_por_categoria("2026-04-01", "2026-04-30")`

**Qué verás en el log:**
```
🔧 Claude invocó → ventas_por_categoria(fecha_inicio='2026-03-01', fecha_fin='2026-03-31')
🔧 Claude invocó → ventas_por_categoria(fecha_inicio='2026-04-01', fecha_fin='2026-04-30')
```

**Respuesta esperada:** Tabla comparativa. Laptops domina ambos meses (>60%). Claude identifica qué categorías crecieron o cayeron y por qué cantidad.

**Punto de charla:** *"Dos consultas a la BD, una sola respuesta analítica. Esto antes requería un analista y un dashboard."*

---

### 4.2 Priorización del pipeline de ventas

```
De todos los leads en negociación, ¿cuál tiene el mayor valor?
¿Cuándo es su seguimiento y qué dicen las notas?
Dame una recomendación de qué hacer antes de esa reunión.
```

**Herramientas:**
1. `listar_leads(estado="en_negociacion")` → identifica el de mayor valor (StartupHub Guayaquil, $18,500)
2. `detalle_lead(lead_id=5)` → notas completas

**Qué verás en el log:**
```
🔧 Claude invocó → listar_leads(estado='en_negociacion')
🔧 Claude invocó → detalle_lead(lead_id=5)
```

**Respuesta esperada:** Claude identifica a StartupHub Guayaquil ($18,500, seguimiento 16 mayo), lee las notas (*"quieren demo de productos"*) y sugiere: preparar demostración de los 3 modelos de laptops más vendidos, llevar accesorios de coworking, confirmar disponibilidad de stock con `productos_stock_bajo`.

---

### 4.3 Consulta multi-dominio (el gran cierre de demo)

```
Tengo una reunión mañana con un cliente importante.
¿Qué leads tengo agendados esta semana, cuánto vale el pipeline,
y qué productos debería llevar para mostrar dado que tienen stock disponible?
```

**Herramientas (Claude decide el orden):**
1. `leads_por_seguir(dias=7)` → leads de la semana
2. `consultar_inventario()` o `productos_stock_bajo()` → stock disponible

**Qué verás en el log:**
```
🔧 Claude invocó → leads_por_seguir(dias=7)
🔧 Claude invocó → productos_stock_bajo()
🔧 Claude invocó → consultar_inventario(categoria='Laptops')
```

**Respuesta esperada:** Claude entrega un briefing ejecutivo: 5 reuniones esta semana con $60,700 en juego, lista de productos con buen stock para llevar a demo, y alerta de que las Laptops Dell y Lenovo no deberían prometerse (stock bajo).

**Punto de charla:** *"Esto es lo que MCP habilita — Claude coordinando información de múltiples sistemas en tiempo real para darte inteligencia accionable. No es un chatbot. Es un agente de negocio."*

---

## Checklist pre-demo (día de la charla)

```bash
# 1. Verificar que ambos servicios están corriendo
curl http://localhost:8080/health

# 2. Hacer una consulta de prueba rápida en Claude Desktop
#    "¿Cuántos productos tenemos en inventario?"

# 3. Tener dos terminales visibles en pantalla:
#    Terminal 1: logs del MCP Server (journalctl -u andestech-mcp -f)
#    Terminal 2: Claude Desktop

# 4. Resetear la BD si hiciste pruebas que modificaron datos
#    python setup_db.py --reset
```
