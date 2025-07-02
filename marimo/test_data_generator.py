import marimo as mo
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pyarrow as pa
import pyarrow.parquet as pq
import io
import requests

def generate_instrument_data(instrument_name, start_time, num_minutes):
    data = []
    current_time = start_time
    for i in range(num_minutes):
        # Simulate price movements
        if i == 0:
            open_price = 100.0
        else:
            open_price = data[-1]["close"]

        high_price = open_price + np.random.uniform(0, 1)
        low_price = open_price - np.random.uniform(0, 1)
        close_price = open_price + np.random.uniform(-0.5, 0.5)

        data.append({
            "instrumentname": instrument_name,
            "id": i + 1,
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "open": round(open_price, 2),
            "close": round(close_price, 2),
            "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S")
        })
        current_time += timedelta(minutes=1)
    return pd.DataFrame(data)

# --- Marimo UI Elements ---

num_instruments = mo.ui.slider(1, 10, value=2, label="Number of Instruments")
num_days = mo.ui.slider(1, 7, value=1, label="Number of Days (1440 rows/day)")

mo.md(f"""
# DuckLake Test Data Generator

Generate time-series data for multiple instruments.

Number of Instruments: {num_instruments}
Number of Days: {num_days}
""")

@mo.action
def generate_data():
    all_data = pd.DataFrame()
    start_time = datetime(2025, 1, 1, 9, 0, 0) # Start from Jan 1, 2025, 09:00:00
    total_minutes = num_days.value * 1440 # 1440 minutes in a day

    for i in range(num_instruments.value):
        instrument_name = f"INSTRUMENT_{i+1}"
        df = generate_instrument_data(instrument_name, start_time, total_minutes)
        all_data = pd.concat([all_data, df], ignore_index=True)
    
    mo.output.clear()
    mo.md(f"""
### Generated Data Preview ({len(all_data)} rows)

{all_data.head()}

""")
    return all_data

# Display a button to trigger data generation
mo.ui.button(label="Generate Data", on_click=generate_data)

# Add a button to save data to Parquet
@mo.action
def save_data_to_parquet(data: pd.DataFrame):
    if data is not None:
        file_path = "generated_data.parquet"
        table = pa.Table.from_pandas(data)
        pq.write_table(table, file_path)
        mo.md(f"Data saved to `{file_path}`")

mo.ui.button(label="Save Data to Parquet", on_click=lambda: save_data_to_parquet(generate_data()))

# Add a button to upload data to MinIO via backend API
@mo.action
def upload_data_to_minio(data: pd.DataFrame, bucket_name: str, object_name: str):
    if data is not None:
        # Convert DataFrame to Parquet in-memory
        table = pa.Table.from_pandas(data)
        buffer = io.BytesIO()
        pq.write_table(table, buffer)
        parquet_bytes = buffer.getvalue()

        # Make a POST request to the backend API
        backend_url = "http://localhost:8000"
        upload_url = f"{backend_url}/datasets/{bucket_name}/{object_name}"

        try:
            files = {'file': (object_name, parquet_bytes, 'application/octet-stream')}
            response = requests.put(upload_url, files=files)
            response.raise_for_status() # Raise an exception for HTTP errors
            mo.md(f"Data uploaded to MinIO bucket `{bucket_name}` as `{object_name}` successfully!")
        except requests.exceptions.RequestException as e:
            mo.md(f"Error uploading data to MinIO: {e}")

minio_bucket_name = mo.ui.text(value="ducklake-data", label="MinIO Bucket Name")
minio_object_name = mo.ui.text(value="instrument_data.parquet", label="MinIO Object Name")

mo.ui.button(label="Upload Data to MinIO", on_click=lambda: upload_data_to_minio(generate_data(), minio_bucket_name.value, minio_object_name.value))
