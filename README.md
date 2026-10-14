# Azure Container Apps - Azure Table Storage Demo & Web GUI

[![Azure Container Apps](https://img.shields.io/badge/Azure-Container%20Apps-0078D4?logo=microsoftazure&logoColor=white)](https://learn.microsoft.com/azure/container-apps/)
[![Azure Table Storage](https://img.shields.io/badge/Azure-Table%20Storage-0089D6?logo=microsoftazure&logoColor=white)](https://learn.microsoft.com/azure/storage/tables/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://docker.com)

A production-ready demo application designed for **Azure Container Apps (ACA)** featuring a modern, responsive Web GUI and REST API for CRUD operations against **Azure Table Storage**.

---

## Architecture Overview

```
                      +-------------------------------------------------------+
                      |                 Azure Container Apps                  |
                      |                                                       |
[User Web Browser] ---> [ HTTPS Ingress : 8000 ]                              |
                      |         |                                             |
                      |    +----+----------------------------------------+    |
                      |    | FastAPI Container (Python 3.11)             |    |
                      |    |   • Web GUI (Tailwind CSS + Alpine.js)      |    |
                      |    |   • REST API + OpenAPI (/docs)              |    |
                      |    |   • Health Probes (/healthz, /ready)        |    |
                      |    +----+----------------------------------------+    |
                      |         |                                             |
                      +---------|---------------------------------------------+
                                | Managed Identity (RBAC)
                                | Storage Table Data Contributor
                                v
               +---------------------------------+
               |       Azure Table Storage       |
               | (or Azurite Emulator for local) |
               +---------------------------------+
```

### Key Highlights
- **Zero-Config Demo Mode**: Starts instantly in in-memory mode if no Azure credentials are configured, pre-loaded with sample IoT & Product data.
- **Multiple Authentication Modes**:
  1. **Azure Managed Identity** (`DefaultAzureCredential`) — Recommended for ACA with RBAC (`Storage Table Data Contributor`).
  2. **Connection String** — Direct connection to cloud storage or Azurite.
  3. **Azurite Local Emulator** — Full local development stack via Docker Compose.
- **Production ACA Features**:
  - Unprivileged container (`appuser`, non-root).
  - External Ingress configuration on port 8000.
  - Native Liveness (`/healthz`) and Readiness (`/ready`) probes.
  - Infrastructure as Code (Bicep) with Log Analytics integration.
- **Web GUI Features**:
  - Table management: Create, select, switch, and delete tables.
  - Dynamic column discovery: Automatically parses and renders custom attributes across entities.
  - Visual Entity Builder: Form-based key-value input with type detection (String, Number, Boolean, DateTime).
  - Raw JSON Editor: Toggle between form builder and raw JSON for bulk or complex payloads.
  - OData Query Filtering: Search by `PartitionKey` or custom OData expressions (e.g. `Price gt 50 and IsActive eq true`).
  - Single & Bulk Deletions: Multi-row selection with batch deletion.
  - Seed Sample Data: One-click population of mock IoT sensors and product catalog items.

---

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI endpoints, ACA health probes, OpenAPI docs
│   ├── storage.py           # Azure Table Storage client wrapper & fallback mock
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js        # Reactive client-side Alpine.js logic
│   └── templates/
│       └── index.html       # Single-page Web GUI (Tailwind CSS + Lucide Icons)
├── infra/
│   └── main.bicep           # Azure Bicep template (ACA, Storage Account, RBAC, CAE)
├── tests/
│   └── test_api.py          # Pytest integration tests (Health, Table, Entity CRUD)
├── Dockerfile               # Production multi-stage / slim container
├── docker-compose.yml       # Local dev with Azurite Table Storage emulator
├── requirements.txt         # Application dependencies
├── .env.example             # Configuration reference
├── deploy.sh                # Automated Azure CLI deployment script
└── README.md
```

---

## Quickstart

### 1. Run with Docker Compose (App + Azurite Emulator)

This is the fastest way to run locally with a real table storage backend:

```bash
docker compose up --build
```

Open your browser to:
- **Web GUI**: [http://localhost:8000](http://localhost:8000)
- **API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Liveness Probe**: [http://localhost:8000/healthz](http://localhost:8000/healthz)
- **Readiness Probe**: [http://localhost:8000/ready](http://localhost:8000/ready)

---

### 2. Run Locally with Python

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Configure environment variables in .env
# If omitted, app runs in in-memory demo mode!
cp .env.example .env

# 4. Start the server
uvicorn app.main:app --reload --port 8000
```

---

### 3. Run Automated Tests

```bash
source .venv/bin/activate
pip install pytest httpx
PYTHONPATH=. pytest -v
```

---

## Deploy to Azure Container Apps

### Automated Deployment via Script

Ensure you are logged into Azure CLI (`az login`):

```bash
chmod +x deploy.sh
./deploy.sh
```

### Manual Deployment via Azure CLI & Bicep

```bash
# 1. Set variables
RG="rg-aca-table-demo"
LOCATION="westeurope"
APP="table-explorer"

# 2. Create Resource Group
az group create --name "$RG" --location "$LOCATION"

# 3. Build & push image to Azure Container Registry
ACR="acr${APP}demo"
az acr create --resource-group "$RG" --name "$ACR" --sku Basic
az acr build --registry "$ACR" --image "$APP:latest" .

# 4. Deploy Bicep template
az deployment group create \
  --resource-group "$RG" \
  --template-file infra/main.bicep \
  --parameters appName="$APP" acrName="$ACR" containerImage="$ACR.azurecr.io/$APP:latest"
```

---

## Environment Variables

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name when using Managed Identity | `mystorageaccount` |
| `AZURE_STORAGE_ENDPOINT_SUFFIX` | Storage endpoint suffix | `core.windows.net` |
| `AZURE_TABLES_CONNECTION_STRING` | Full connection string or `UseDevelopmentStorage=true` | *(optional)* |
| `TABLE_NAME` | Initial/default table name | `demotable` |
| `PORT` | Container HTTP port | `8000` |

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Web GUI Single-Page App |
| `GET` | `/healthz` | Container Apps Liveness Probe |
| `GET` | `/ready` | Container Apps Readiness Probe |
| `GET` | `/api/status` | Current storage mode and connection status |
| `POST` | `/api/configure` | Dynamic connection update |
| `GET` | `/api/tables` | List all tables in storage account |
| `POST` | `/api/tables` | Create a new table |
| `DELETE` | `/api/tables/{table_name}` | Delete a table |
| `POST` | `/api/tables/{table_name}/seed` | Seed mock records into table |
| `GET` | `/api/tables/{table_name}/entities` | Query entities (with filter & limit) |
| `GET` | `/api/tables/{table_name}/entities/{pk}/{rk}` | Get single entity |
| `POST` | `/api/tables/{table_name}/entities` | Insert new entity |
| `PUT` | `/api/tables/{table_name}/entities/{pk}/{rk}` | Update/upsert entity (`MERGE` or `REPLACE`) |
| `DELETE` | `/api/tables/{table_name}/entities/{pk}/{rk}` | Delete single entity |
| `POST` | `/api/tables/{table_name}/entities/batch-delete` | Batch delete selected entities |
