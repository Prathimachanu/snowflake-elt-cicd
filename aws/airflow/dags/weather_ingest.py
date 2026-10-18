import json, os
from datetime import datetime, timedelta

import boto3
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.standard.operators.python import PythonOperator


def invoke_lambda():
    client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "eu-north-1"))
    resp = client.invoke(FunctionName="weather-ingest", InvocationType="RequestResponse")
    result = json.loads(resp["Payload"].read())
    print(result)
    if resp.get("FunctionError"):
        raise Exception(result)


with DAG(
    dag_id="weather_ingest",
    start_date=datetime(2026, 10, 1),
    schedule="@hourly",
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
) as dag:
    PythonOperator(task_id="invoke_lambda", python_callable=invoke_lambda)