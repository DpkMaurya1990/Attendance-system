import sys, os
import streamlit.components.v1 as components
# Add the parent directory (E:\attend) to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import date, datetime
import sqlite3
import pandas as pd
import psycopg2

#Add caching for employee list to optimize dropdown loading in Mark Attendance page
@st.cache_data
def get_employees():
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, name FROM employees", conn)
    conn.close()
    return df

# ---------- CUSTOM MODAL HELPERS ----------
def close_employee_modal():
    st.session_state["show_modal"] = False

def render_employee_modal(employees):
    """Displays a centered popup overlay with employee table inside and working close button."""
    import pandas as pd
    import json
    import streamlit.components.v1 as components

    # Convert to DataFrame if list/dict
    df = pd.DataFrame(employees)
    table_html = df.to_html(index=False, classes="employee-table")

    modal_html = f"""
    <html>
    <head>
    <style>
    .modal-overlay {{
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background-color: rgba(0,0,0,0.55);
        display: flex; align-items: center; justify-content: center;
        z-index: 9999;
    }}
    .modal-content {{
        background-color: #ffffff;
        width: 75%;
        max-height: 80%;
        overflow-y: auto;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        padding: 25px;
        position: relative;
        animation: fadeIn 0.25s ease-in-out;
    }}
    .modal-close {{
        position: absolute;
        top: 10px;
        right: 15px;
        background: #f44336;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        cursor: pointer;
        font-size: 0.9rem;
    }}
    .employee-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }}
    .employee-table th, .employee-table td {{
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }}
    .employee-table th {{
        background-color: #4CAF50;
        color: white;
    }}
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: scale(0.9); }}
        to {{ opacity: 1; transform: scale(1); }}
    }}
    </style>
    </head>
    <body>
    <div class="modal-overlay" id="employee-modal">
      <div class="modal-content">
        <button class="modal-close" onclick="document.getElementById('employee-modal').remove()">✖</button>
        <h3>📋 Employee List</h3>
        <p>List of Employees (Emp_ID | Name | Manual_ID)</p>
        {table_html}
      </div>
    </div>

    <script>
    function closeModal() {{
        const modal = document.getElementById("employee-modal");
        if (modal) {{
            modal.remove();
        }}
    }}
    
    // Notify Streamlit backend to update state
    
    </script>
    </body>
    </html>
    """

    components.html(modal_html, height=700, scrolling=True)




# Backend API base URL
API_URL = "http://127.0.0.1:8000"

def get_db_connection():
    return psycopg2.connect(
        host="aws-1-ap-northeast-1.pooler.supabase.com",
        database="postgres",
        user="postgres.rejmmghqbhtgmeedlmea",
        password="Alliswell@0605",
        port="6543"
    )

st.set_page_config(page_title="Attendance System", layout="centered")
st.title("🧑‍💼 Attendance System")

# Sidebar menu
menu = st.sidebar.radio("Menu", ["Add Employee", "Mark Attendance", "View Attendance"])

# Reset modal when page changes
if "last_menu" not in st.session_state:
    st.session_state["last_menu"] = menu

if st.session_state["last_menu"] != menu:
    st.session_state["show_modal"] = False
    st.session_state["last_menu"] = menu
    

# --- Global state for modal ---
if "show_modal" not in st.session_state:
    st.session_state["show_modal"] = False
if "employees" not in st.session_state:
    st.session_state["employees"] = []

# --- Common See_Emp button (works in all pages) ---
def handle_see_emp():
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM employees", conn)
        conn.close()

        if not df.empty:
            st.session_state["employees"] = df.to_dict(orient="records")
            st.session_state["show_modal"] = True
            st.rerun()   # ✅ IMPORTANT

        else:
            st.info("No employees found.")

    except Exception as e:
        st.error(f"Error fetching employees: {e}")

# --- Modal display (custom HTML/CSS modal) ---
def show_employee_modal():
    if st.session_state.get("show_modal", False):
        employees = st.session_state.get("employees", [])

        if employees:
            if st.button("❌ Close Employee List", key="close_modal_btn"):
                st.session_state["show_modal"] = False
                st.session_state["employees"] = []
                st.rerun()

            render_employee_modal(employees)
           


# ------------------- ADD EMPLOYEE PAGE -------------------
if menu == "Add Employee":
    st.subheader("➕ Add New Employee")
    st.markdown("Fields marked with * are required")
    # Name
    st.markdown("Name <span style='color:red'>*</span>", unsafe_allow_html=True)
    name = st.text_input("", key="name")

    # Department
    st.markdown("Department <span style='color:red'>*</span>", unsafe_allow_html=True)
    department = st.selectbox(
        "",
        ["Initiated Gents", "Initiated Ladies", "Gents", "Ladies", "Children", "Santsu", "Other"],
        key="department"
    )
    
    if department == "Other":
        department = st.text_input("Enter Department", key="department_other")

    # Designation
    st.markdown("Designation <span style='color:red'>*</span>", unsafe_allow_html=True)
    designation = st.selectbox(
    "",
    [
        "IT",
        "Branch Sec",
        "Ass Branch Sec",
        "Youth Sec",
        "Youth Teas",
        "Mahila 1",
        "Mahila 2",
        "Mahila 3",
        "Office Bearer",
        "Other"
    ],
    key="designation"
    )
    
    if designation == "Other":
        designation = st.text_input("Enter Designation", key="designation_other")


    # Date of Joining
    st.markdown("Date of Joining <span style='color:red'>*</span>", unsafe_allow_html=True)
    doj = st.date_input("", key="doj")
    
    # Manual ID
    st.markdown("Manual ID <span style='color:red'>*</span>", unsafe_allow_html=True)
    manual_id = st.text_input("", key="manual_id")
    
    # Shift Start (optional)
    st.markdown("Shift Start")
    shift_start = st.text_input("", value="09:00", key="shift_start")

    # Shift End (optional)
    st.markdown("Shift End")
    shift_end = st.text_input("", value="18:00", key="shift_end")

    if st.button("Add Employee", key="add_employee_btn_main"):
        # ✅ Validation
        if not name or not department or not designation or not doj or not manual_id:
            st.warning("Please fill all fields (except Shift timings).")
            
        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
            # ✅ Duplicate check
                cursor.execute("SELECT 1 FROM employees WHERE manual_id = %s", (manual_id,))
                existing = cursor.fetchone()

                if existing:
                    st.error("Manual ID already exists. Please use a unique ID.")

                cursor.execute("""
                    INSERT INTO employees 
                    (name, department, designation, doj, shift_start, shift_end, manual_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (name, department, designation, str(doj), shift_start, shift_end, manual_id))

                conn.commit()
                conn.close()
                st.success("Employee added successfully!")
                # ✅ refresh cache
                st.cache_data.clear()

            except Exception as e:
                st.error(f"Error adding employee: {e}")
                
#added delete employee section in add employee page to avoid creating a separate page for it            
# 🗑️ Delete Employee Section
    st.divider()
    st.subheader("🗑️ Delete Employee")

    df_emp = get_employees()

    if df_emp.empty:
        st.info("No employees available to delete.")

    else:
        emp_options = {
            f"{row['name']} (ID: {row['id']})": row['id']
            for _, row in df_emp.iterrows()
        }

        selected_emp_del = st.selectbox(
            "Select Employee to Delete",
            list(emp_options.keys()),
            key="delete_emp"
        )

        confirm_delete = st.checkbox("Confirm delete", key="confirm_emp_delete")

        if st.button("Delete Employee", key="delete_emp_btn", disabled=not confirm_delete):
            emp_id_del = emp_options[selected_emp_del]

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute("DELETE FROM employees WHERE id=%s", (emp_id_del,))
                conn.commit()
                conn.close()

                st.success("Employee deleted successfully!")

                # ✅ Refresh cache + UI
                st.cache_data.clear()
                st.rerun()

            except Exception as e:
                st.error(f"Error deleting employee: {e}")

# ------------------- MARK ATTENDANCE PAGE -------------------
elif menu == "Mark Attendance":
    st.subheader("🕒 Mark Attendance")
    
    # ✅ Fetch employees for dropdown
    df_emp = get_employees()

    emp_options = {
        f"{row['name']} (ID: {row['id']})": row['id']
        for _, row in df_emp.iterrows()
    }
    # ✅ Dropdown
    
    selected_emp = st.selectbox("Select Employee", list(emp_options.keys()))
    emp_id = emp_options[selected_emp]
    emp_name = selected_emp.split(" (ID")[0]
    
    status = st.selectbox("Status", ["Present", "Absent"])

        
    # ✅ Check if employee ID exists
    if emp_id > 0 and not emp_name:
        st.error("Employee not found!")
        
    is_valid_employee = emp_id > 0 and emp_name != ""    

    #Replace Emp_Name field with a disabled text input showing the name of the selected employee
    st.text_input("Emp_Name", value=emp_name, disabled=True)
    marked_by = emp_name

    if st.button("Mark Attendance", key="mark_attendance_btn", disabled=not is_valid_employee):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO attendance 
                (emp_id, status, marked_by, date, marked_time)
                VALUES (%s, %s, %s, %s, %s)
            """, (emp_id, status, marked_by, str(date.today()), current_timestamp))

            conn.commit()
            conn.close()

            st.success("Attendance marked successfully!")

        except Exception as e:
            st.error(f"Error marking attendance: {e}")

    st.divider()
    if st.button("🧾 See_Emp", key="see_emp_mark"):
        handle_see_emp()
        
        
        

# ------------------- VIEW ATTENDANCE PAGE -------------------
elif menu == "View Attendance":
    st.subheader("📋 Attendance Records 🚀")

    
    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    start_date = st.date_input("Start Date", default_start)
    end_date = st.date_input("End Date", default_end)
    
    
    try:
        conn = get_db_connection()
        query = f"""
        SELECT * FROM attendance
        WHERE date(marked_time) BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY marked_time DESC
        LIMIT 500
        """
        df = pd.read_sql(query, conn)
        df.rename(columns={
            "emp_id": "Employee ID",
            "marked_time": "Timestamp",
            "marked_by": "EName",
            "status": "status"
        }, inplace=True)
        conn.close()

        records = df.to_dict(orient="records")
        
       

    except Exception as e:
        st.error(f"Error fetching attendance: {e}")
        records = []

    
    if not records:
        st.session_state.pop("csv_path", None)

    # ✅ OUTSIDE try/except (IMPORTANT)
    if records:
        st.dataframe(records)

        # 🗑️ Delete Attendance Record
        st.subheader("🗑️ Delete Attendance Record")

        df_display = pd.DataFrame(records)

        if not df_display.empty:

            record_options = {
                f"{row.get('EName', '')} | {row.get('Status', row.get('status', ''))} | {row.get('Timestamp', '')}": row["id"]
                for _, row in df_display.iterrows()
            }

            selected_record = st.selectbox(
                "Select record to delete",
                list(record_options.keys())
            )

            confirm_delete = st.checkbox("Confirm delete", key="confirm_att_delete")

            if st.button("Delete Attendance", key="delete_att_btn", disabled=not confirm_delete):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    record_id = int(record_options[selected_record])

                    cursor.execute("DELETE FROM attendance WHERE id=%s", (record_id,))
                    conn.commit()
                    conn.close()

                    # ✅ Show message FIRST
                    st.success("Attendance deleted successfully!")

                    # ✅ Small delay (important)
                    import time
                    time.sleep(1)

                    # ✅ Then refresh
                    st.rerun()

                except Exception as e:
                    st.error(f"Error deleting attendance: {e}")
                
            
        from utils import generate_summary, plot_summary_chart

        # 📊 Summary
        summary_df = generate_summary(records)
        st.write("### 📊 Summary Report")
        st.dataframe(summary_df)

        
        # 📥 CSV Download (filtered data)
        csv = df.to_csv(index=False).encode('utf-8')

        st.download_button(
            "⬇️ Download CSV Report",
            csv,
            file_name="attendance_report.csv",
            mime="text/csv"
        )

        # 📈 Chart
        if "chart_generated" not in st.session_state:
            chart_path = plot_summary_chart(summary_df)
            st.session_state["chart_path"] = chart_path
            st.session_state["chart_generated"] = True

        st.image(st.session_state["chart_path"])

    else:
        st.info("No attendance records found.")

    st.divider()
    if st.button("🧾 See_Emp", key="see_emp_view"):
        handle_see_emp()
               
    # Close the modal when JS sends the event
# --- ALWAYS render modal (important) ---
show_employee_modal()

