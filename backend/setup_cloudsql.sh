#!/bin/bash
# Script de configuración de Cloud SQL PostgreSQL

PROJECT_ID="cerebro-backend-484020"
INSTANCE_NAME="finanzas-db"
DB_NAME="finanzas"
DB_USER="finanzas_user"
REGION="southamerica-east1"

echo "🔧 Configurando Cloud SQL PostgreSQL..."
echo "======================================"

# 1. Esperar a que la instancia esté lista
echo "⏳ Esperando a que la instancia esté lista..."
gcloud sql operations list --instance=$INSTANCE_NAME --project=$PROJECT_ID --limit=1

# 2. Crear base de datos
echo "📊 Creando base de datos '$DB_NAME'..."
gcloud sql databases create $DB_NAME \
    --instance=$INSTANCE_NAME \
    --project=$PROJECT_ID

# 3. Establecer contraseña para usuario postgres (temporal)
echo "🔐 Configurando contraseña para usuario postgres..."
gcloud sql users set-password postgres \
    --instance=$INSTANCE_NAME \
    --password="TempPass123!" \
    --project=$PROJECT_ID

# 4. Crear usuario de aplicación
echo "👤 Creando usuario de aplicación..."
gcloud sql users create $DB_USER \
    --instance=$INSTANCE_NAME \
    --password="FinanzasApp2026!" \
    --project=$PROJECT_ID

# 5. Obtener información de conexión
echo ""
echo "✅ Configuración completada!"
echo "======================================"
echo "📋 Información de conexión:"
echo ""

CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --project=$PROJECT_ID --format="value(connectionName)")
IP_ADDRESS=$(gcloud sql instances describe $INSTANCE_NAME --project=$PROJECT_ID --format="value(ipAddresses[0].ipAddress)")

echo "🔌 Connection Name: $CONNECTION_NAME"
echo "🌐 IP Address: $IP_ADDRESS"
echo "📦 Database: $DB_NAME"
echo "👤 User: $DB_USER"
echo "🔑 Password: FinanzasApp2026!"
echo ""
echo "📝 DATABASE_URL para .env:"
echo "postgresql://$DB_USER:FinanzasApp2026!@/$DB_NAME?host=/cloudsql/$CONNECTION_NAME"
echo ""
echo "🔧 Para Cloud Run, usa:"
echo "gcloud run services update cerebro-backend-v2 \\"
echo "  --add-cloudsql-instances $CONNECTION_NAME \\"
echo "  --region=$REGION \\"
echo "  --project=$PROJECT_ID"
