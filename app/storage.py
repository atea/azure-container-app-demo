import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError, HttpResponseError
from azure.data.tables import TableServiceClient, TableClient, UpdateMode
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("azure_tables")

AZURITE_TABLE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
)

class TableStorageService:
    """
    Unified manager for Azure Table Storage supporting:
    1. Connection string (Azure or Azurite emulator)
    2. Managed Identity / DefaultAzureCredential (Azure Container Apps)
    3. In-memory fallback if no credentials are configured (demo mode)
    """

    def __init__(self):
        conn = os.getenv("AZURE_TABLES_CONNECTION_STRING", "").strip()
        if conn.lower() in ["usedevelopmentstorage=true", "usedevelopmentstorage=true;"]:
            conn = AZURITE_TABLE_CONNECTION_STRING
        self.connection_string = conn
        self.account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
        self.endpoint_suffix = os.getenv("AZURE_STORAGE_ENDPOINT_SUFFIX", "core.windows.net").strip()
        self.default_table = os.getenv("TABLE_NAME", "demotable").strip()
        
        self.service_client: Optional[TableServiceClient] = None
        self.mode = "uninitialized"
        self.account_display = "Unknown"
        self._mock_tables: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        self._init_client()

    def _init_client(self):
        # 1. Connection string provided
        if self.connection_string:
            try:
                self.service_client = TableServiceClient.from_connection_string(self.connection_string)
                self.mode = "connection_string"
                if "UseDevelopmentStorage=true" in self.connection_string or "127.0.0.1" in self.connection_string or "azurite" in self.connection_string:
                    self.mode = "azurite"
                    self.account_display = "Azurite (Local Emulator)"
                else:
                    parts = dict(item.split("=", 1) for item in self.connection_string.split(";") if "=" in item)
                    self.account_display = parts.get("AccountName", "Azure Storage")
                logger.info(f"Initialized TableServiceClient with connection string ({self.account_display})")
                return
            except Exception as e:
                logger.error(f"Failed to initialize TableServiceClient from connection string: {e}")

        # 2. Managed Identity / Account Name provided
        if self.account_name:
            try:
                endpoint = f"https://{self.account_name}.table.{self.endpoint_suffix}"
                credential = DefaultAzureCredential()
                self.service_client = TableServiceClient(endpoint=endpoint, credential=credential)
                self.mode = "managed_identity"
                self.account_display = f"{self.account_name} (Managed Identity)"
                logger.info(f"Initialized TableServiceClient with Managed Identity for {endpoint}")
                return
            except Exception as e:
                logger.error(f"Failed to initialize TableServiceClient with Managed Identity: {e}")

        # 3. Fallback to Demo In-Memory mode
        self.mode = "in_memory"
        self.account_display = "Demo In-Memory Mode (No Azure Configured)"
        logger.warning("No Azure Table Storage credentials configured. Running in in-memory demo mode.")
        self._seed_mock_data()

    def _seed_mock_data(self):
        sample_table = self.default_table or "demotable"
        self._mock_tables[sample_table] = {}
        sample_items = self._get_sample_items()
        for item in sample_items:
            key = f"{item['PartitionKey']}_{item['RowKey']}"
            item_copy = dict(item)
            item_copy["Timestamp"] = datetime.now(timezone.utc).isoformat()
            self._mock_tables[sample_table][key] = item_copy

    def _get_sample_items(self) -> List[Dict[str, Any]]:
        return [
            {
                "PartitionKey": "Devices",
                "RowKey": "DEV-001",
                "Name": "Temperature Sensor Alpha",
                "Location": "Building A - Server Room",
                "Status": "Online",
                "BatteryPercent": 94,
                "LastTemperatureC": 21.5,
                "IsActive": True,
            },
            {
                "PartitionKey": "Devices",
                "RowKey": "DEV-002",
                "Name": "Humidity Monitor Beta",
                "Location": "Building B - Lab 3",
                "Status": "Warning",
                "BatteryPercent": 28,
                "LastTemperatureC": 24.8,
                "IsActive": True,
            },
            {
                "PartitionKey": "Products",
                "RowKey": "PRD-101",
                "Name": "Azure Container App Starter Kit",
                "Category": "Cloud Services",
                "Price": 149.99,
                "Stock": 50,
                "IsActive": True,
            },
            {
                "PartitionKey": "Products",
                "RowKey": "PRD-102",
                "Name": "Serverless Event Hub Connector",
                "Category": "Integration",
                "Price": 79.50,
                "Stock": 120,
                "IsActive": False,
            },
        ]

    def get_status(self) -> Dict[str, Any]:
        live_test = False
        message = ""
        try:
            if self.mode == "in_memory":
                live_test = True
                message = "Running in in-memory mode. All CRUD operations will be kept in memory."
            elif self.service_client:
                # Perform a lightweight call
                _ = list(self.service_client.list_tables(results_per_page=1))
                live_test = True
                message = f"Connected successfully to {self.account_display}"
        except Exception as e:
            message = f"Connection error: {str(e)}"
            live_test = False

        return {
            "mode": self.mode,
            "account_display": self.account_display,
            "connected": live_test,
            "default_table": self.default_table,
            "message": message,
        }

    # Table Operations
    def list_tables(self) -> List[str]:
        if self.mode == "in_memory":
            return sorted(list(self._mock_tables.keys()))
        
        tables = []
        for t in self.service_client.list_tables():
            tables.append(t.name)
        return sorted(tables)

    def create_table(self, table_name: str) -> bool:
        clean_name = table_name.strip()
        if not clean_name.isalnum():
            raise ValueError("Table name must be alphanumeric and between 3 and 63 characters.")

        if self.mode == "in_memory":
            if clean_name in self._mock_tables:
                raise ResourceExistsError("Table already exists")
            self._mock_tables[clean_name] = {}
            return True

        self.service_client.create_table(clean_name)
        return True

    def delete_table(self, table_name: str) -> bool:
        if self.mode == "in_memory":
            if table_name in self._mock_tables:
                del self._mock_tables[table_name]
                return True
            raise ResourceNotFoundError("Table not found")

        self.service_client.delete_table(table_name)
        return True

    def _get_table_client(self, table_name: str) -> TableClient:
        return self.service_client.get_table_client(table_name)

    # Entity Operations
    def list_entities(
        self,
        table_name: str,
        filter_query: Optional[str] = None,
        partition_key: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        if self.mode == "in_memory":
            if table_name not in self._mock_tables:
                self._mock_tables[table_name] = {}
            items = list(self._mock_tables[table_name].values())
            if partition_key:
                items = [i for i in items if i.get("PartitionKey") == partition_key]
            return items[:limit]

        table_client = self._get_table_client(table_name)
        
        query_filter = filter_query
        if partition_key and not query_filter:
            query_filter = f"PartitionKey eq '{partition_key}'"
            
        entities = []
        try:
            if query_filter:
                query_result = table_client.query_entities(query_filter=query_filter, results_per_page=limit)
            else:
                query_result = table_client.list_entities(results_per_page=limit)
                
            for entity in query_result:
                item = dict(entity)
                if "Timestamp" in item and hasattr(item["Timestamp"], "isoformat"):
                    item["Timestamp"] = item["Timestamp"].isoformat()
                entities.append(item)
                if len(entities) >= limit:
                    break
        except ResourceNotFoundError:
            # Auto-create if not found for convenience
            table_client.create_table()
            return []
            
        return entities

    def get_entity(self, table_name: str, partition_key: str, row_key: str) -> Dict[str, Any]:
        if self.mode == "in_memory":
            key = f"{partition_key}_{row_key}"
            if table_name in self._mock_tables and key in self._mock_tables[table_name]:
                return self._mock_tables[table_name][key]
            raise ResourceNotFoundError("Entity not found")

        table_client = self._get_table_client(table_name)
        entity = dict(table_client.get_entity(partition_key=partition_key, row_key=row_key))
        if "Timestamp" in entity and hasattr(entity["Timestamp"], "isoformat"):
            entity["Timestamp"] = entity["Timestamp"].isoformat()
        return entity

    def create_entity(self, table_name: str, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        if "PartitionKey" not in entity_data or "RowKey" not in entity_data:
            raise ValueError("Entity must contain PartitionKey and RowKey")

        p_key = str(entity_data["PartitionKey"]).strip()
        r_key = str(entity_data["RowKey"]).strip()
        entity_data["PartitionKey"] = p_key
        entity_data["RowKey"] = r_key

        if self.mode == "in_memory":
            if table_name not in self._mock_tables:
                self._mock_tables[table_name] = {}
            k = f"{p_key}_{r_key}"
            if k in self._mock_tables[table_name]:
                raise ResourceExistsError("Entity with this PartitionKey and RowKey already exists")
            payload = dict(entity_data)
            payload["Timestamp"] = datetime.now(timezone.utc).isoformat()
            self._mock_tables[table_name][k] = payload
            return payload

        table_client = self._get_table_client(table_name)
        try:
            table_client.create_entity(entity=entity_data)
        except ResourceNotFoundError:
            table_client.create_table()
            table_client.create_entity(entity=entity_data)
            
        return self.get_entity(table_name, p_key, r_key)

    def upsert_entity(self, table_name: str, entity_data: Dict[str, Any], mode: str = "MERGE") -> Dict[str, Any]:
        if "PartitionKey" not in entity_data or "RowKey" not in entity_data:
            raise ValueError("Entity must contain PartitionKey and RowKey")

        p_key = str(entity_data["PartitionKey"]).strip()
        r_key = str(entity_data["RowKey"]).strip()
        entity_data["PartitionKey"] = p_key
        entity_data["RowKey"] = r_key

        if self.mode == "in_memory":
            if table_name not in self._mock_tables:
                self._mock_tables[table_name] = {}
            k = f"{p_key}_{r_key}"
            if mode == "MERGE" and k in self._mock_tables[table_name]:
                self._mock_tables[table_name][k].update(entity_data)
            else:
                payload = dict(entity_data)
                payload["Timestamp"] = datetime.now(timezone.utc).isoformat()
                self._mock_tables[table_name][k] = payload
            return self._mock_tables[table_name][k]

        table_client = self._get_table_client(table_name)
        update_mode = UpdateMode.MERGE if mode == "MERGE" else UpdateMode.REPLACE
        table_client.upsert_entity(entity=entity_data, mode=update_mode)
        return self.get_entity(table_name, p_key, r_key)

    def delete_entity(self, table_name: str, partition_key: str, row_key: str) -> bool:
        if self.mode == "in_memory":
            k = f"{partition_key}_{row_key}"
            if table_name in self._mock_tables and k in self._mock_tables[table_name]:
                del self._mock_tables[table_name][k]
                return True
            raise ResourceNotFoundError("Entity not found")

        table_client = self._get_table_client(table_name)
        table_client.delete_entity(partition_key=partition_key, row_key=row_key)
        return True

    def seed_sample_data(self, table_name: str) -> int:
        samples = self._get_sample_items()
        count = 0
        for item in samples:
            try:
                self.upsert_entity(table_name, item, mode="REPLACE")
                count += 1
            except Exception as e:
                logger.error(f"Error seeding sample item {item.get('RowKey')}: {e}")
        return count
