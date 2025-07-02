from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
from botocore.exceptions import ClientError
import io
import os

app = FastAPI()

# Initialize DuckDB in-memory database
con = duckdb.connect(database=':memory:', read_only=False)

# Initialize MinIO client (placeholders for now)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000") # Replace with actual MinIO service endpoint
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"

s3_client = boto3.client(
    's3',
    endpoint_url=f"http://{MINIO_ENDPOINT}",
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4')
)

# Models for DuckDB operations
class Table(BaseModel):
    name: str
    schema: Dict[str, str] # e.g., {"col1": "INTEGER", "col2": "VARCHAR"}

class TableData(BaseModel):
    rows: List[Dict[str, Any]]

class Query(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"Hello": "World"}

# DuckDB table operations
@app.post("/tables")
def create_table(table: Table):
    try:
        columns_sql = ", ".join([f"{col_name} {col_type}" for col_name, col_type in table.schema.items()])
        create_table_sql = f"CREATE TABLE {table.name} ({columns_sql})"
        con.execute(create_table_sql)
        return {"message": f"Table '{table.name}' created successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating table: {e}")

@app.put("/tables/{table_name}")
def append_to_table(table_name: str, data: TableData):
    try:
        # Convert list of dicts to PyArrow Table, then to Pandas DataFrame for append
        table = pa.Table.from_pylist(data.rows)
        df = table.to_pandas()
        con.append(table_name, df)
        return {"message": f"Data appended to table '{table_name}' successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error appending data: {e}")

@app.delete("/tables/{table_name}")
def delete_table(table_name: str):
    try:
        con.execute(f"DROP TABLE {table_name}")
        return {"message": f"Table '{table_name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting table: {e}")

@app.get("/tables/{table_name}")
def get_table(table_name: str):
    try:
        # Get table schema using DuckDB's information_schema
        schema_query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'"
        schema_result = con.execute(schema_query).fetch_arrow_table()
        schema = {row["column_name"]: row["data_type"] for row in schema_result.to_pylist()}
        return {"name": table_name, "schema": schema}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or error retrieving schema: {e}")

@app.post("/tables/{table_name}/query")
def query_table(table_name: str, query: Query):
    try:
        result_arrow_table = con.execute(query.query).fetch_arrow_table()
        return {"result": result_arrow_table.to_pylist()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error executing query: {e}")

# MinIO dataset operations
@app.post("/datasets/{bucket_name}")
def create_bucket(bucket_name: str):
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        return {"message": f"Bucket '{bucket_name}' created successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error creating bucket: {e}")

@app.put("/datasets/{bucket_name}/{object_name}")
def upload_object(bucket_name: str, object_name: str, file: UploadFile = File(...)):
    try:
        s3_client.upload_fileobj(file.file, bucket_name, object_name)
        return {"message": f"Object '{object_name}' uploaded to bucket '{bucket_name}' successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error uploading object: {e}")

@app.get("/datasets/{bucket_name}/{object_name}")
def download_object(bucket_name: str, object_name: str):
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=object_name)
        return Response(content=response['Body'].read(), media_type=response['ContentType'])
    except ClientError as e:
        raise HTTPException(status_code=404, detail=f"Error downloading object: {e}")

@app.delete("/datasets/{bucket_name}/{object_name}")
def delete_object(bucket_name: str, object_name: str):
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        return {"message": f"Object '{object_name}' from bucket '{bucket_name}' deleted successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error deleting object: {e}")

@app.get("/datasets/{bucket_name}")
def list_objects(bucket_name: str):
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        objects = [obj['Key'] for obj in response.get('Contents', [])]
        return {"bucket": bucket_name, "objects": objects}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=f"Error listing objects in bucket: {e}")
