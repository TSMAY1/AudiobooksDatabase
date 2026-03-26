import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-ACE2DSF\SQLEXPRESS;"
    "DATABASE=Audiobooks;"
    "Trusted_Connection=yes;"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
cursor.execute("SELECT DB_NAME();")
row = cursor.fetchone()
print("Connected to:", row[0])

conn.close()