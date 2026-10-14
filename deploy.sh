#!/usr/bin/env bash
set -euo pipefail

# Configuration Defaults
RESOURCE_GROUP="${RESOURCE_GROUP:-d-sdc-rg-ghcpsre}"
LOCATION="${LOCATION:-swedencentral}"
APP_NAME="${APP_NAME:-demoapp1}"
ACR_NAME="${ACR_NAME:-ghcpsreacr}"

echo "=== Azure Container Apps + Table Storage Demo Deployment ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "Location:       $LOCATION"
echo "App Name:       $APP_NAME"
echo "ACR Name:      $ACR_NAME"
echo ""

# 1. Create Resource Group
echo "--> 1. Ensuring Resource Group exists..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" -o table

# 2. Deploy Azure Container Registry or Build Container Image
echo "--> 2. Building container image via Azure Container Registry (or local docker)..."
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
    echo "Creating Azure Container Registry: $ACR_NAME"
    az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic -o table
fi

IMAGE_TAG="$ACR_NAME.azurecr.io/$APP_NAME:latest"
echo "Building and pushing container image: $IMAGE_TAG"
az acr build --registry "$ACR_NAME" --image "$APP_NAME:latest" .

# 3. Deploy Bicep template
echo "--> 3. Deploying Infrastructure via Bicep..."
DEPLOYMENT_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file infra/main.bicep \
    --parameters appName="$APP_NAME" acrName="$ACR_NAME" containerImage="$IMAGE_TAG" \
    --query "properties.outputs" \
    --output json)

APP_URL=$(echo "$DEPLOYMENT_OUTPUT" | grep -o '"containerAppUrl": *{[^}]*}' | grep -o '"value": *"[^"]*"' | cut -d'"' -f4 || echo "")

echo ""
echo "=========================================================="
echo " Deployment Complete!"
echo " Web GUI URL: $APP_URL"
echo "=========================================================="
