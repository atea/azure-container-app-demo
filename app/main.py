import os
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ConfigDict

from app.storage import TableStorageService
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aca_demo")

app = FastAPI(
    title="Azure Table Storage Manager - Azure Container Apps Demo",
    description="Full-featured Web GUI and REST API for Azure Table Storage running on Azure Container Apps.",
    version="1.0.0",
)

# Mount static and templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir)

# Initialize Storage Service singleton
storage_service = TableStorageService()


# Models
class CreateTableRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=63, description="Alphanumeric table name")

class EntityPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    PartitionKey: str
    RowKey: str

class BatchDeleteRequest(BaseModel):
    items: List[Dict[str, str]]  # list of {"PartitionKey": "...", "RowKey": "..."}

class ConnectionUpdateRequest(BaseModel):
    connection_string: Optional[str] = None
    account_name: Optional[str] = None


# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": "1.0.0",
            "default_table": storage_service.default_table,
        },
    )


# ACA Probes
@app.get("/healthz", tags=["Health"])
async def liveness():
    """Liveness probe for Azure Container Apps"""
    return {"status": "healthy"}

@app.get("/ready", tags=["Health"])
async def readiness():
    """Readiness probe for Azure Container Apps"""
    status_info = storage_service.get_status()
    if status_info["connected"]:
        return {"status": "ready", "details": status_info}
    # Return 200 if running in-memory demo mode or degraded
    if status_info["mode"] == "in_memory":
        return {"status": "ready", "mode": "in_memory"}
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "details": status_info},
    )


# Status & Configuration API
@app.get("/api/status", tags=["System"])
async def get_system_status():
    return storage_service.get_status()

@app.post("/api/configure", tags=["System"])
async def update_connection(req: ConnectionUpdateRequest):
    global storage_service
    if req.connection_string is not None:
        os.environ["AZURE_TABLES_CONNECTION_STRING"] = req.connection_string
    if req.account_name is not None:
        os.environ["AZURE_STORAGE_ACCOUNT_NAME"] = req.account_name
    
    # Reinitialize
    storage_service = TableStorageService()
    return storage_service.get_status()


# Table Management
@app.get("/api/tables", tags=["Tables"])
async def list_tables():
    try:
        tables = storage_service.list_tables()
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tables", tags=["Tables"])
async def create_table(req: CreateTableRequest):
    try:
        storage_service.create_table(req.name)
        return {"message": f"Table '{req.name}' created successfully", "name": req.name}
    except ResourceExistsError:
        raise HTTPException(status_code=409, detail=f"Table '{req.name}' already exists.")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating table: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tables/{table_name}", tags=["Tables"])
async def delete_table(table_name: str):
    try:
        storage_service.delete_table(table_name)
        return {"message": f"Table '{table_name}' deleted successfully"}
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
    except Exception as e:
        logger.error(f"Error deleting table: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tables/{table_name}/seed", tags=["Tables"])
async def seed_table(table_name: str):
    try:
        count = storage_service.seed_sample_data(table_name)
        return {"message": f"Seeded {count} sample entities into '{table_name}'", "count": count}
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Entity CRUD
@app.get("/api/tables/{table_name}/entities", tags=["Entities"])
async def list_entities(
    table_name: str,
    partition_key: Optional[str] = Query(None, description="Optional PartitionKey filter"),
    filter_query: Optional[str] = Query(None, description="Optional OData filter query"),
    limit: int = Query(200, ge=1, le=1000, description="Max entities to return"),
):
    try:
        entities = storage_service.list_entities(
            table_name=table_name,
            filter_query=filter_query,
            partition_key=partition_key,
            limit=limit,
        )
        return {"table": table_name, "count": len(entities), "entities": entities}
    except Exception as e:
        logger.error(f"Error listing entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tables/{table_name}/entities/{partition_key}/{row_key}", tags=["Entities"])
async def get_entity(table_name: str, partition_key: str, row_key: str):
    try:
        entity = storage_service.get_entity(table_name, partition_key, row_key)
        return entity
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Entity not found")
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tables/{table_name}/entities", tags=["Entities"])
async def create_entity(table_name: str, payload: Dict[str, Any]):
    if "PartitionKey" not in payload or "RowKey" not in payload:
        raise HTTPException(status_code=400, detail="PartitionKey and RowKey are required.")
    
    try:
        created = storage_service.create_entity(table_name, payload)
        return {"message": "Entity created successfully", "entity": created}
    except ResourceExistsError:
        raise HTTPException(status_code=409, detail="An entity with this PartitionKey and RowKey already exists.")
    except Exception as e:
        logger.error(f"Error creating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/tables/{table_name}/entities/{partition_key}/{row_key}", tags=["Entities"])
async def update_entity(
    table_name: str,
    partition_key: str,
    row_key: str,
    payload: Dict[str, Any],
    mode: str = Query("MERGE", enum=["MERGE", "REPLACE"]),
):
    # Ensure PartitionKey and RowKey match URL
    payload["PartitionKey"] = partition_key
    payload["RowKey"] = row_key
    
    try:
        updated = storage_service.upsert_entity(table_name, payload, mode=mode)
        return {"message": "Entity updated successfully", "entity": updated}
    except Exception as e:
        logger.error(f"Error updating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tables/{table_name}/entities/{partition_key}/{row_key}", tags=["Entities"])
async def delete_entity(table_name: str, partition_key: str, row_key: str):
    try:
        storage_service.delete_entity(table_name, partition_key, row_key)
        return {"message": f"Entity [{partition_key}, {row_key}] deleted successfully"}
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Entity not found")
    except Exception as e:
        logger.error(f"Error deleting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tables/{table_name}/entities/batch-delete", tags=["Entities"])
async def batch_delete_entities(table_name: str, req: BatchDeleteRequest):
    deleted = 0
    errors = []
    for item in req.items:
        p_key = item.get("PartitionKey")
        r_key = item.get("RowKey")
        if not p_key or not r_key:
            continue
        try:
            storage_service.delete_entity(table_name, p_key, r_key)
            deleted += 1
        except Exception as e:
            errors.append(f"Failed to delete [{p_key}, {r_key}]: {str(e)}")

    return {"deleted": deleted, "errors": errors}
