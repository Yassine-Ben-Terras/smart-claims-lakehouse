# Azure setup (ADLS Gen2, Event Hubs, Azure SQL)

One-time infrastructure steps. The notebooks read and write through Unity Catalog volumes (`/Volumes/...`), so nothing in the code points at a storage URL.

## 1. ADLS Gen2 storage

1. Create a storage account with **hierarchical namespace enabled**.
2. Create containers, for example `landing` (raw files) and `catalog` (managed tables).
3. Create an **Access Connector for Azure Databricks** (a managed identity) and give it **Storage Blob Data Contributor** on the storage account.
4. If the storage firewall is enabled:
   - serverless compute: create a network connectivity configuration with private endpoint rules for the storage account;
   - classic compute: use VNet injection and allow the subnets.

## 2. Unity Catalog objects

Run in a SQL warehouse or notebook (replace the placeholders):

```sql
CREATE STORAGE CREDENTIAL IF NOT EXISTS smart_claims_cred
  WITH (AZURE_MANAGED_IDENTITY = (ACCESS_CONNECTOR_ID = '<access-connector-resource-id>'));

CREATE EXTERNAL LOCATION IF NOT EXISTS smart_claims_landing
  URL 'abfss://landing@<storage-account>.dfs.core.windows.net/'
  WITH (STORAGE CREDENTIAL smart_claims_cred);

CREATE EXTERNAL LOCATION IF NOT EXISTS smart_claims_catalog
  URL 'abfss://catalog@<storage-account>.dfs.core.windows.net/'
  WITH (STORAGE CREDENTIAL smart_claims_cred);

CREATE CATALOG IF NOT EXISTS smart_claims_dev
  MANAGED LOCATION 'abfss://catalog@<storage-account>.dfs.core.windows.net/smart_claims_dev';

CREATE SCHEMA IF NOT EXISTS smart_claims_dev.`00_landing`;
CREATE SCHEMA IF NOT EXISTS smart_claims_dev.`01_bronze`;
CREATE SCHEMA IF NOT EXISTS smart_claims_dev.`02_silver`;
CREATE SCHEMA IF NOT EXISTS smart_claims_dev.`03_gold`;

CREATE EXTERNAL VOLUME IF NOT EXISTS smart_claims_dev.`00_landing`.claims
  LOCATION 'abfss://landing@<storage-account>.dfs.core.windows.net/claims';
CREATE EXTERNAL VOLUME IF NOT EXISTS smart_claims_dev.`00_landing`.training_imgs
  LOCATION 'abfss://landing@<storage-account>.dfs.core.windows.net/training_imgs';
```

Keep the volume and schema names as above: the notebooks hardcode them.

## 3. Azure Event Hubs (streaming source)

1. Create an Event Hubs namespace on the **Standard tier or above** (Basic has no Kafka endpoint) and an event hub for telematics.
2. Create a shared access policy with **Listen** rights and copy its connection string.
3. Store it in a secret scope:
   ```bash
   databricks secrets create-scope <secret-scope>
   databricks secrets put-secret <secret-scope> <eventhubs-connection-string-key>
   ```
4. Fill in `EH_NAMESPACE`, `EH_NAME`, `SECRET_SCOPE` and `SECRET_KEY` in `src/ingestion/streaming/eventhubs_parsed.py`.
5. Messages must be JSON objects with `chassis_no`, `latitude`, `longitude`, `event_timestamp` and `speed`.

## 4. Azure SQL / SQL Server (Lakeflow Connect source)

1. Run `src/ingestion/lakeflow_connect/db_setup.sql` against the source database. It uses `sys.sp_cdc_enable_db`.
2. Allow Databricks to reach the server (firewall rule or private endpoint).
3. Create a Unity Catalog **connection** to the server and use its name for `sqlserver_connection_name` in `databricks.yml`.
4. Run the DDL support objects script linked in `db_setup.sql`.
5. Check the Databricks docs for the SQL Server connector to confirm your Azure SQL flavor is supported (Database, Managed Instance or a VM).

## 5. Auto Loader notes

- Directory listing mode (the default) works unchanged on ADLS Gen2.
- For file notification mode, prefer **file events** on the external location. The alternative needs Event Grid and storage queue permissions.
- The `cleanSource` archive path must be in the same storage account and writable by the access connector.
