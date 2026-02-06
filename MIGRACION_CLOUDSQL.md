# MIGRACIÓN A CLOUD SQL POSTGRESQL

## 📋 Estado Actual
- **Proyecto:** cerebro-backend-484020
- **Instancia:** finanzas-db (creándose...)
- **Región:** southamerica-east1
- **Tier:** db-f1-micro
- **Costo estimado:** $10-12 USD/mes

## ✅ Pasos Completados

### 1. Habilitación de API
```bash
✅ gcloud services enable sqladmin.googleapis.com
```

### 2. Creación de Instancia
```bash
⏳ gcloud sql instances create finanzas-db
   Status: CREANDO (5-10 minutos)
```

## 📝 Próximos Pasos (Automáticos)

### 3. Configuración de Base de Datos
Una vez creada la instancia, ejecutar:
```bash
# Crear base de datos
gcloud sql databases create finanzas --instance=finanzas-db

# Configurar usuario
gcloud sql users create finanzas_user \
  --instance=finanzas-db \
  --password="FinanzasApp2026!"
```

### 4. Conectar Cloud Run con Cloud SQL
```bash
gcloud run services update cerebro-backend-v2 \
  --add-cloudsql-instances cerebro-backend-484020:southamerica-east1:finanzas-db \
  --set-env-vars DATABASE_URL="postgresql://finanzas_user:FinanzasApp2026!@/finanzas?host=/cloudsql/cerebro-backend-484020:southamerica-east1:finanzas-db" \
  --region=southamerica-east1
```

### 5. Inicializar Datos
La aplicación auto-inicializará:
- Tablas (users, expenses, budgets, categories, etc.)
- Presupuesto mensual default
- Categorías default

## 🎯 Beneficios Post-Migración

✅ **Datos persistentes** - No se borran al reiniciar
✅ **Mejor rendimiento** - PostgreSQL es más rápido que Sheets
✅ **Escalable** - Puede crecer con tu app
✅ **Profesional** - Base de datos real en producción

## 💰 Costos Mensuales

| Item | Costo |
|------|-------|
| Instancia db-f1-micro | ~$7.50 USD |
| Almacenamiento 10GB SSD | ~$1.70 USD |
| Backups automáticos | ~$1.00 USD |
| **TOTAL** | **~$10-12 USD/mes** |

## 🔧 Comandos de Gestión Útiles

```bash
# Ver estado de instancia
gcloud sql instances describe finanzas-db

# Ver logs
gcloud sql operations list --instance=finanzas-db

# Conectar vía proxy (desarrollo local)
cloud_sql_proxy -instances=cerebro-backend-484020:southamerica-east1:finanzas-db=tcp:5432

# Backup manual
gcloud sql backups create --instance=finanzas-db

# Ver backups
gcloud sql backups list --instance=finanzas-db
```

## 📅 Timeline

- **23:47** - Inicio creación instancia
- **~00:00** - Instancia lista (estimado)
- **00:05** - Configuración completa
- **00:10** - Aplicación desplegada con PostgreSQL
