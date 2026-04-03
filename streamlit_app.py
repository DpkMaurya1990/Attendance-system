import sys, os
import streamlit.components.v1 as components

# Add the parent directory (E:\attend) to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import date, datetime
import sqlite3
import pandas as pd
import psycopg2

TIME_OPTIONS = [
    datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").strftime("%I:%M %p")
    for hour in range(24)
    for minute in (0, 30)
]


def ensure_attendance_schema():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_member_id INTEGER"
    )
    cursor.execute(
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_member_name TEXT"
    )
    cursor.execute(
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_status TEXT"
    )
    cursor.execute(
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_from_time TEXT"
    )
    cursor.execute(
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_to_time TEXT"
    )

    conn.commit()
    conn.close()


# Add caching for employee list to optimize dropdown loading in Mark Attendance page
@st.cache_data
def get_employees():
    try:
        conn = get_db_connection()
        df = pd.read_sql("SELECT id, name, uid FROM employees", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame(columns=["id", "name", "uid"])


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
        port="6543",
        connect_timeout=10,
    )

def ensure_event_attendance_table():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_attendance (
                id SERIAL PRIMARY KEY,
                attendance_id INTEGER,
                event_member_id INTEGER NOT NULL,
                event_member_name TEXT NOT NULL,
                event_status TEXT NOT NULL,
                event_from_time TEXT,
                event_to_time TEXT,
                date DATE NOT NULL,
                marked_time TIMESTAMP NOT NULL
            )
            """
        )

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error creating event_attendance table: {e}")
        

st.set_page_config(page_title="Attendance System", layout="centered")
st.title("🧑‍💼 Attendance System 🚀 DEV")


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
            st.rerun()  # ✅ IMPORTANT

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

def mark_attendance_db(
    emp_id,
    emp_name,
    status,
    event_member_id,
    event_member_name,
    event_status,
    event_from_time,
    event_to_time,
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today_date = str(date.today())

        cursor.execute(
            """
            SELECT 1 FROM attendance
            WHERE emp_id = %s AND date = %s
            """,
            (emp_id, today_date),
        )

        if cursor.fetchone():
            conn.close()
            return "duplicate_employee"

        if event_member_id is not None:
            cursor.execute(
                """
                SELECT 1 FROM event_attendance
                WHERE event_member_id = %s AND date = %s
                """,
                (event_member_id, today_date),
            )

            if cursor.fetchone():
                conn.close()
                return "duplicate_event_member"

        cursor.execute(
            """
            INSERT INTO attendance
            (emp_id, status, marked_by, date, marked_time)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (emp_id, status, emp_name, today_date, current_timestamp),
        )

        attendance_id = cursor.fetchone()[0]

        if event_member_id is not None and event_member_name != "N/A":
            cursor.execute(
                """
                INSERT INTO event_attendance
                (
                    attendance_id,
                    event_member_id,
                    event_member_name,
                    event_status,
                    event_from_time,
                    event_to_time,
                    date,
                    marked_time
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    attendance_id,
                    event_member_id,
                    event_member_name,
                    event_status,
                    event_from_time,
                    event_to_time,
                    today_date,
                    current_timestamp,
                ),
            )

        conn.commit()
        conn.close()

        return "success"

    except Exception as e:
        return str(e)
    
    
def add_employee_db(name, department, doj, uid):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ✅ Duplicate check
        cursor.execute(
            "SELECT 1 FROM employees WHERE uid = %s", (uid,)
        )

        if cursor.fetchone():
            conn.close()
            return "duplicate"

        # ✅ Insert
        cursor.execute(
            """
            INSERT INTO employees (name, department, doj, uid)
            VALUES (%s, %s, %s, %s)
            """,
            (name, department, str(doj), uid),
        )

        conn.commit()
        conn.close()

        return "success"

    except Exception as e:
        return str(e)    

# ------------------- ADD EMPLOYEE PAGEs -------------------
if menu == "Add Employee":
    st.subheader("➕ Add New Member")
    st.markdown("Fields marked with * are required")

    # Name
    st.markdown("Name <span style='color:red'>*</span>", unsafe_allow_html=True)
    name = st.text_input("", key="name")

    # Department
    st.markdown("Department <span style='color:red'>*</span>", unsafe_allow_html=True)
    department = st.selectbox(
        "",
        [
            "Initiated Gents",
            "Initiated Ladies",
            "Gents",
            "Ladies",
            "Children",
            "Santsu",
            "Other",
        ],
        key="department",
    )

    if department == "Other":
        department = st.text_input("Enter Department", key="department_other")

    # Date of Joining
    st.markdown(
        "Date of Joining <span style='color:red'>*</span>", unsafe_allow_html=True
    )
    doj = st.date_input("", key="doj")

    # UID
    st.markdown("UID <span style='color:red'>*</span>", unsafe_allow_html=True)
    uid = st.text_input("", key="uid")

    
    if st.button("Add Employee", key="add_employee_btn_main"):
        if not name or not department or not doj or not uid:
            st.warning("Please fill all required fields.")

        else:
            result = add_employee_db(name, department, doj, uid)

            if result == "duplicate":
                st.error("UID already exists. Please use a unique UID.")

            elif result == "success":
                st.success("Employee added successfully!")
                st.cache_data.clear()

            else:
                st.error(f"Error: {result}")

    # added delete employee section in add employee page to avoid creating a separate page for it
    # 🗑️ Delete Employee Section
    st.divider()
    st.subheader("🗑️ Delete Employee")

    df_emp = get_employees()

    if df_emp.empty:
        st.info("No employees available to delete.")

    else:
        emp_options = {
    f"{row['name']} (UID: {row['uid']})": row["id"]
    for _, row in df_emp.iterrows()
    }
        
        
        selected_emp_del = st.selectbox(
            "Select Employee to Delete", list(emp_options.keys()), key="delete_emp"
        )

        confirm_delete = st.checkbox("Confirm delete", key="confirm_emp_delete")

        if st.button(
            "Delete Employee", key="delete_emp_btn", disabled=not confirm_delete
        ):
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
    f"{row['name']} (UID: {row['uid']})": row["id"]
    for _, row in df_emp.iterrows()
}
    
    
    # ✅ Dropdown

    selected_emp = st.selectbox("Select Employee", list(emp_options.keys()))
    emp_id = emp_options[selected_emp]
    emp_name = selected_emp.split(" (UID")[0]

    status = st.selectbox("Status", ["Present", "Absent"])

    event_member_options = ["N/A"] + list(emp_options.keys())

    selected_event_member = st.selectbox(
        "Event_member", event_member_options, key="event_member_select"
    )

    if selected_event_member == "N/A":
        event_member_id = None
        event_member_name = "N/A"
        event_status = "N/A"
        event_from_time = None
        event_to_time = None

        st.selectbox(
            "Event Status",
            ["N/A"],
            index=0,
            disabled=True,
            key="event_status_disabled",
        )

        col1, col2 = st.columns(2)
        with col1:
            st.text_input("From Time", value="N/A", disabled=True, key="event_from_na")
        with col2:
            st.text_input("To Time", value="N/A", disabled=True, key="event_to_na")

    else:
        event_member_id = emp_options[selected_event_member]
        event_member_name = selected_event_member.split(" (UID")[0]

        event_status = st.selectbox(
            "Event Status", ["Present", "Absent"], key="event_status"
        )

        event_from_time = None
        event_to_time = None

        if event_status == "Present":
            col1, col2 = st.columns(2)

            with col1:
                event_from_time = st.selectbox(
                    "From Time", TIME_OPTIONS, key="event_from_time"
                )

            with col2:
                event_to_time = st.selectbox(
                    "To Time", TIME_OPTIONS, index=8, key="event_to_time"
                )

            if TIME_OPTIONS.index(event_from_time) >= TIME_OPTIONS.index(event_to_time):
                st.error("To Time must be after From Time.")

    if emp_id > 0 and not emp_name:
        st.error("Employee not found!")

    is_valid_employee = emp_id > 0 and emp_name != ""
    is_valid_event_member = selected_event_member == "N/A" or (
        event_member_id is not None and event_member_name != ""
    )
    is_valid_event_time = selected_event_member == "N/A" or (
        event_status == "Absent"
        or (
            event_from_time is not None
            and event_to_time is not None
            and TIME_OPTIONS.index(event_from_time) < TIME_OPTIONS.index(event_to_time)
        )
    )

    st.text_input("Emp_Name", value=emp_name, disabled=True)
    st.text_input("Event Member Name", value=event_member_name, disabled=True)
    marked_by = emp_name

    if st.button(
        "Mark Attendance",
        key="mark_attendance_btn",
        disabled=not (is_valid_employee and is_valid_event_member and is_valid_event_time),
    ):
        result = mark_attendance_db(
            emp_id,
            emp_name,
            status,
            event_member_id,
            event_member_name,
            event_status,
            event_from_time,
            event_to_time,
        )

        if result == "duplicate_employee":
            st.warning(f"{emp_name} is already marked for today!")

        elif result == "duplicate_event_member":
            st.warning(f"{event_member_name} is already marked in Event_member for today!")

        elif result == "success":
            st.session_state.pop("chart_path", None)
            st.session_state.pop("chart_generated", None)
            st.success("Attendance marked successfully!")
            

        else:
            st.error(f"Error: {result}")

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

        regular_query = f"""
        SELECT * FROM attendance
        WHERE date(marked_time) BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY marked_time DESC
        LIMIT 500
        """
        df = pd.read_sql(regular_query, conn)
        df.rename(
            columns={
                "emp_id": "Employee ID",
                "marked_time": "Timestamp",
                "marked_by": "EName",
                "status": "Status",
            },
            inplace=True,
        )

        event_query = f"""
        SELECT * FROM event_attendance
        WHERE date(marked_time) BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY marked_time DESC
        LIMIT 500
        """
        event_df = pd.read_sql(event_query, conn)
        event_df.rename(
            columns={
                "event_member_id": "Event Member ID",
                "event_member_name": "Event Member",
                "event_status": "Event Status",
                "event_from_time": "Event From",
                "event_to_time": "Event To",
                "marked_time": "Timestamp",
            },
            inplace=True,
        )

        conn.close()

        records = df.to_dict(orient="records")
        event_records = event_df.to_dict(orient="records")

    except Exception as e:
        st.error(f"Error fetching attendance: {e}")
        records = []
        event_records = []

    if not records:
        st.session_state.pop("csv_path", None)

    # ✅ OUTSIDE try/except (IMPORTANT)
    if records:
        st.write("### Regular Attendance Records")
        st.dataframe(records)
    else:
        st.info("No regular attendance records found.")

    if event_records:
        st.write("### Event Attendance Records")
        st.dataframe(event_records)
    else:
        st.info("No event attendance records found.")

    df_display = pd.DataFrame(records)
    event_df_display = pd.DataFrame(event_records)

    # 🗑️ Delete Attendance Record
    st.subheader("🗑️ Delete Attendance Record")
    
    if not df_display.empty:

        record_options = {
            f"{row.get('EName', '')} | {row.get('Status', row.get('status', ''))} | {row.get('Timestamp', '')}": row[
                "id"
            ]
            for _, row in df_display.iterrows()
        }

        selected_record = st.selectbox(
            "Select record to delete", list(record_options.keys())
        )

        if st.session_state.pop("reset_confirm_att_delete", False):
            st.session_state["confirm_att_delete"] = False

        confirm_delete = st.checkbox("Confirm delete", key="confirm_att_delete")

        if st.button(
            "Delete Attendance", key="delete_att_btn", disabled=not confirm_delete
        ):
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

                st.session_state["reset_confirm_att_delete"] = True
                st.session_state.pop("chart_path", None)
                st.session_state.pop("chart_generated", None)

                # ✅ Then refresh
                st.rerun()

            except Exception as e:
                st.error(f"Error deleting attendance: {e}")

    st.subheader("Delete Event Member Record")

    event_record_options = {
        f"{row.get('Event Member', '')} | {row.get('Event Status', '')} | {row.get('Timestamp', '')}": row["id"]
        for _, row in event_df_display.iterrows()
    }

    if event_record_options:
        selected_event_record = st.selectbox(
            "Select event record to delete",
            list(event_record_options.keys()),
            key="delete_event_record",
        )

        if st.session_state.pop("reset_confirm_event_delete", False):
            st.session_state["confirm_event_delete"] = False

        confirm_event_delete = st.checkbox(
            "Confirm event delete", key="confirm_event_delete"
        )

        if st.button(
            "Delete Event Member",
            key="delete_event_btn",
            disabled=not confirm_event_delete,
        ):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                event_record_id = int(event_record_options[selected_event_record])

                cursor.execute(
                    "DELETE FROM event_attendance WHERE id = %s",
                    (event_record_id,),
                )

                conn.commit()
                conn.close()

                st.success("Event member record deleted successfully!")

                import time

                time.sleep(1)

                st.session_state["reset_confirm_event_delete"] = True
                st.rerun()

            except Exception as e:
                st.error(f"Error deleting event member record: {e}")
    else:
        st.info("No event member records available to delete.")
        
        from utils import generate_summary, plot_summary_chart
        
        
        # 📊 Summary
        normal_summary_df = generate_summary(records, "Status")
        st.write("### Regular Attendance Summary")
        st.dataframe(normal_summary_df)

        if not normal_summary_df.empty:
            normal_chart_path = plot_summary_chart(normal_summary_df)
            st.image(normal_chart_path)

        event_summary_df = generate_summary(records, "Event Status")
        st.write("### Event Attendance Summary")
        st.dataframe(event_summary_df)

        if not event_summary_df.empty:
            event_chart_path = plot_summary_chart(event_summary_df)
            st.image(event_chart_path)

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Download CSV Report",
            csv,
            file_name="attendance_report.csv",
            mime="text/csv",
        )

    st.divider()
    if st.button("🧾 See_Emp", key="see_emp_view"):
        handle_see_emp()

    # Close the modal when JS sends the event
# --- ALWAYS render modal (important) ---
show_employee_modal()
