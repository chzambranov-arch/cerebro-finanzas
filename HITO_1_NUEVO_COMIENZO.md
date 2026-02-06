# Hito 1: Nuevo Comienzo - Proyecto Finanzas

**Fecha:** 4 de Febrero, 2026
**Estado:** Funcional / MVP Estable

## Resumen
Este hito marca el "nuevo comienzo" del sistema de finanzas personales. La aplicación ha sido migrada y estructurada para funcionar con una arquitectura Backend (FastAPI) + Frontend (Vanilla JS/PWA) desacoplada pero servida integradamente.

## Funcionalidades Actuales
1.  **Dashboard de Finanzas**: Visualización de saldo disponible, presupuesto mensual y gastos por categoría.
2.  **Registro de Gastos**: Posibilidad de agregar gastos con monto, concepto, sección, categoría y medio de pago.
3.  **Integración con Google Sheets**: Todos los movimientos se sincronizan en tiempo real con la planilla de cálculo principal.
4.  **Gestor de Compromisos (Deudas/Préstamos)**: Nueva funcionalidad para rastrear dinero prestado o debido, con estados (Pendiente/Pagado) y sincronización.
5.  **Autenticación**: Sistema de login básico funcional.
6.  **Despliegue Local**: Ejecución mediante Uvicorn en puerto 8000.

## Estructura Técnica
- **Backend**: Python / FastAPI
- **Frontend**: HTML5 / CSS3 / Vanilla JS (sin frameworks pesados)
- **Base de Datos**: SQLite (Local) + Google Sheets (Espejo en Nube)
- **PWA**: Preparado con manifest.json y sw.js para instalación en dispositivos.

## Próximos Pasos
- Completar la optimización de la PWA.
- Refinar la interfaz de usuario de "Compromisos".
- Validar despliegue en nube (Cloud Run / Railway).
