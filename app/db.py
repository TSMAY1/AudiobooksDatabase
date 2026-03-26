import pyodbc
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

conn_str = (
    f"DRIVER={{{os.getenv('DB_DRIVER')}}};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"Trusted_Connection={os.getenv('DB_TRUSTED_CONNECTION')};"
)


def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-ACE2DSF\\SQLEXPRESS;"
        "DATABASE=Audiobooks;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def run_query(query, params=None):
    with get_connection() as conn:
        return pd.read_sql(query, conn, params=params)


def execute_non_query(sql, params=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()


def execute_procedure(proc_name, params):
    placeholders = ", ".join(["?"] * len(params))
    sql = f"EXEC {proc_name} {placeholders}"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()