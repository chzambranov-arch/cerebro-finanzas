# HITO: LÚCIO, MIGUEL Y FARO - El Tridente de Inteligencia Financiera
Fecha: 2026-02-08

## Resumen del Hito (TEAM CEREBRO LISTO)
Se ha implementado una arquitectura de multi-agentes que revoluciona el procesamiento de datos financieros en Cerebro. Ya no es una sola IA intentando hacer todo; ahora es un equipo especializado coordinado por Lúcio.

## El Equipo de Inteligencia
1.  **LÚCIO (El Orquestador):**
    *   Es el rostro del sistema y el único que interactúa con el usuario.
    *   Coordina a Miguel y Faro en segundo plano.
    *   Filtra la información técnica para presentarla de forma ejecutiva y amigable.
    *   Gestiona la navegación dinámica por carpetas (secciones) y pide aclaraciones si hay ambigüedad.

2.  **MIGUEL (El Especialista de Campo):**
    *   **OCR de Precisión:** Lee boletas físicamente, extrayendo ítems, precios y totales sin inventar datos.
    *   **Matemática de División:** Especialista en dividir cuentas entre múltiples personas (ej: "yo, nico y mamá"). Calcula las partes exactas y genera las deudas (ME DEBEN) automáticamente.
    *   **Inmune a la Charla:** Es un agente puramente técnico que entrega JSON estructurado.

3.  **FARO (El Científico de Datos):**
    *   **Análisis de Patrones:** Detecta tendencias de gasto y comportamientos financieros.
    *   **Matemática Financiera:** Calcula resúmenes, promedios y proyecciones a fin de mes.
    *   **Cazador de Ahorros:** Identifica áreas de optimización para ayudar al usuario a gastar mejor.

## Avances Técnicos Clave
- **Arquitectura Multi-Agente:** Separación total de responsabilidades (OCR/Math vs. Analytics vs. UI).
- **Modo Estricto de JSON:** Implementación de `response_mime_type: "application/json"` para evitar que código técnico se filtre en el chat.
- **Lógica de División 2.0:** Soporte para divisiones dinámicas por N personas con creación automática de compromisos `LOAN`.
- **Filtro de Carpetas Inteligente:** El sistema detecta si una categoría existe en múltiples secciones y obliga a Lúcio a preguntar antes de registrar, manteniendo el presupuesto ordenado.
- **Normalización de Datos:** Limpieza automática de montos (remoción de "$" y puntos) y conceptos antes de llegar a la base de datos o Google Sheets.

---
**Estado Actual:** 🔥 SISTEMA DE AGENTES COORDINADOS OPERATIVO
**Próximo Paso:** Refinamiento de predicciones de Faro y entrenamiento de Miguel en boletas complejas.
