import sqlite3
import pandas as pd

conn = sqlite3.connect("employees.db")

employees = pd.read_sql("SELECT * FROM employees", conn)
attendance = pd.read_sql("SELECT * FROM attendance", conn)

employees.to_csv("employees.csv", index=False)
attendance.to_csv("attendance.csv", index=False)

conn.close()

print("✅ Export done")
