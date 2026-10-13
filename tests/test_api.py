import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Azure Table Storage Explorer" in response.text

def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "mode" in data
    assert "connected" in data

def test_table_lifecycle():
    # 1. Create table
    tbl_name = "testtablelifecycle"
    res = client.post("/api/tables", json={"name": tbl_name})
    assert res.status_code == 200
    
    # 2. List tables
    res = client.get("/api/tables")
    assert res.status_code == 200
    assert tbl_name in res.json()["tables"]

    # 3. Duplicate create should fail
    res = client.post("/api/tables", json={"name": tbl_name})
    assert res.status_code == 409

    # 4. Delete table
    res = client.delete(f"/api/tables/{tbl_name}")
    assert res.status_code == 200

    # 5. Verify deleted
    res = client.get("/api/tables")
    assert tbl_name not in res.json()["tables"]

def test_entity_crud():
    tbl_name = "crudtable"
    client.post("/api/tables", json={"name": tbl_name})

    # 1. Seed
    seed_res = client.post(f"/api/tables/{tbl_name}/seed")
    assert seed_res.status_code == 200
    assert seed_res.json()["count"] > 0

    # 2. List entities
    list_res = client.get(f"/api/tables/{tbl_name}/entities")
    assert list_res.status_code == 200
    entities = list_res.json()["entities"]
    assert len(entities) > 0

    # 3. Create single entity
    new_entity = {
        "PartitionKey": "NorthRegion",
        "RowKey": "ITEM-999",
        "ProductName": "Azure Container Apps Pro",
        "Price": 299.95,
        "IsActive": True
    }
    create_res = client.post(f"/api/tables/{tbl_name}/entities", json=new_entity)
    assert create_res.status_code == 200
    assert create_res.json()["entity"]["ProductName"] == "Azure Container Apps Pro"

    # 4. Get single entity
    get_res = client.get(f"/api/tables/{tbl_name}/entities/NorthRegion/ITEM-999")
    assert get_res.status_code == 200
    assert get_res.json()["Price"] == 299.95

    # 5. Update entity
    update_payload = {
        "PartitionKey": "NorthRegion",
        "RowKey": "ITEM-999",
        "Price": 349.00,
        "Status": "Updated"
    }
    put_res = client.put(f"/api/tables/{tbl_name}/entities/NorthRegion/ITEM-999?mode=MERGE", json=update_payload)
    assert put_res.status_code == 200
    assert put_res.json()["entity"]["Price"] == 349.00
    assert put_res.json()["entity"]["ProductName"] == "Azure Container Apps Pro"

    # 6. Delete entity
    del_res = client.delete(f"/api/tables/{tbl_name}/entities/NorthRegion/ITEM-999")
    assert del_res.status_code == 200

    # 7. Verify deletion
    verify_del = client.get(f"/api/tables/{tbl_name}/entities/NorthRegion/ITEM-999")
    assert verify_del.status_code == 404

    # 8. Batch delete
    batch_res = client.post(
        f"/api/tables/{tbl_name}/entities/batch-delete",
        json={"items": [{"PartitionKey": "Devices", "RowKey": "DEV-001"}]}
    )
    assert batch_res.status_code == 200
    assert batch_res.json()["deleted"] >= 1

    # 9. Query with filters
    filter_res = client.get(f"/api/tables/{tbl_name}/entities?partition_key=Products")
    assert filter_res.status_code == 200
    for item in filter_res.json()["entities"]:
        assert item["PartitionKey"] == "Products"

    # Cleanup table
    client.delete(f"/api/tables/{tbl_name}")

def test_configure_endpoint():
    res = client.post("/api/configure", json={"connection_string": "UseDevelopmentStorage=true;"})
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "azurite"

    # Reset back to in-memory for other tests
    res = client.post("/api/configure", json={"connection_string": ""})
    assert res.status_code == 200
    assert res.json()["mode"] == "in_memory"

def test_not_found_handling():
    res = client.get("/api/tables/nonexistenttable/entities/PK/RK")
    assert res.status_code == 404

    res = client.delete("/api/tables/nonexistenttable")
    assert res.status_code == 404

