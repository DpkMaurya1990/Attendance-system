import sys, os
import base64
from pathlib import Path


# Add the parent directory (E:\attend) to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import date, datetime
import sqlite3
import pandas as pd
import psycopg2

from agent_workflow import (
    EVENT_REQUIRED_COLUMNS,
    REGULAR_REQUIRED_COLUMNS,
    format_event_time,
    prepare_agent_sync_payload,
    prepare_uploaded_dataframe,
)

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
        df = pd.read_sql("SELECT id, member_code, name, uid FROM employees", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame(columns=["id", "member_code", "name", "uid"])

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
    
def ensure_member_code_column():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS member_code TEXT"
        )

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error creating member_code column: {e}")
        
def generate_next_member_code(cursor):
    cursor.execute(
        """
        SELECT member_code
        FROM employees
        WHERE member_code IS NOT NULL
        AND member_code LIKE 'GM-%'
        ORDER BY member_code DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    if not row or not row[0]:
        return "GM-0001"

    last_code = row[0]
    last_number = int(last_code.split("-")[1])
    next_number = last_number + 1

    return f"GM-{next_number:04d}"

def backfill_member_codes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id
            FROM employees
            WHERE member_code IS NULL OR TRIM(member_code) = ''
            ORDER BY id ASC
            """
        )

        rows = cursor.fetchall()

        for row in rows:
            member_id = row[0]
            next_code = generate_next_member_code(cursor)

            cursor.execute(
                """
                UPDATE employees
                SET member_code = %s
                WHERE id = %s
                """,
                (next_code, member_id),
            )

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error backfilling member_code: {e}")
            

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
        
        
def ensure_performance_indexes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance (emp_id, date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance (date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_attendance_member_date ON event_attendance (event_member_id, date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_attendance_date ON event_attendance (date)"
        )

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error creating performance indexes: {e}")       
@st.cache_data        
def get_base64_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()    
    

st.set_page_config(page_title="Attendance System", layout="centered")

# Sidebar menu
menu = st.sidebar.radio(
    "Menu",
    ["Home", "Add Member", "Mark Attendance", "View Attendance", "Analytics", "Member List", "Sync Attendance"],
)

if menu != "Home":
    st.title("🧑‍💼 Attendance System 🚀 DEV")
    

# Reset modal when page changes
if "last_menu" not in st.session_state:
    st.session_state["last_menu"] = menu
if st.session_state["last_menu"] != menu:
    st.session_state["last_menu"] = menu


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
        
        ensure_member_code_column()

        # ✅ Duplicate check
        cursor.execute(
            "SELECT 1 FROM employees WHERE uid = %s", (uid,)
        )

        if cursor.fetchone():
            conn.close()
            return "duplicate"
        
        member_code = generate_next_member_code(cursor)
        
        # ✅ Insert
        cursor.execute(
            """
            INSERT INTO employees (name, department, doj, uid, member_code)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, department, str(doj), uid, member_code),
        )

        conn.commit()
        conn.close()

        return "success"

    except Exception as e:
        return str(e)    

#-------------------- Sync Regular Attendance -------------------
def sync_regular_attendance_csv(regular_df):
    inserted_count = 0
    duplicate_count = 0
    missing_member_count = 0
    invalid_status_count = 0
    error_rows = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for idx, row in regular_df.iterrows():
            member_code = str(row.get("Member Code", "")).strip()
            status = str(row.get("Status", "")).strip().title()
            attendance_date = str(row.get("Date", "")).strip()

            if status not in ["Present", "Absent"]:
                invalid_status_count += 1
                error_rows.append(
                    {
                        "Row Number": idx + 2,
                        "Member Code": member_code,
                        "Reason": "Invalid status",
                    }
                )
                continue

            cursor.execute(
                """
                SELECT id, name
                FROM employees
                WHERE member_code = %s
                """,
                (member_code,),
            )
            member_row = cursor.fetchone()

            if not member_row:
                missing_member_count += 1
                error_rows.append(
                    {
                        "Row Number": idx + 2,
                        "Member Code": member_code,
                        "Reason": "Member code not found",
                    }
                )
                continue

            member_id, member_name = member_row

            cursor.execute(
                """
                SELECT 1
                FROM attendance
                WHERE emp_id = %s AND date = %s
                """,
                (member_id, attendance_date),
            )

            if cursor.fetchone():
                duplicate_count += 1
                error_rows.append(
                    {
                        "Row Number": idx + 2,
                        "Member Code": member_code,
                        "Reason": "Duplicate regular attendance",
                    }
                )
                continue

            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT INTO attendance (emp_id, status, marked_by, date, marked_time)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (member_id, status, member_name, attendance_date, current_timestamp),
            )

            inserted_count += 1

        conn.commit()
        conn.close()

        return {
            "inserted": inserted_count,
            "duplicates": duplicate_count,
            "missing_members": missing_member_count,
            "invalid_status": invalid_status_count,
            "error_rows": error_rows,
        }

    except Exception as e:
        return {"error": str(e)}


#-------------------- Sync Event Attendance -------------------

def format_event_time(value):
    time_str = str(value).strip()

    if not time_str or time_str.lower() == "nan":
        return None

    # If datetime-like value comes from CSV, keep only time part
    if " " in time_str and ":" in time_str:
        possible_time = time_str.split()[-1]
        if ":" in possible_time:
            time_str = possible_time

    # Remove fractional seconds if present, e.g. 13:00:00.000000
    if "." in time_str:
        time_str = time_str.split(".")[0]

    supported_formats = (
        "%H:%M:%S",
        "%H:%M",
        "%I:%M %p",
        "%I:%M:%S %p",
    )

    for fmt in supported_formats:
        try:
            return datetime.strptime(time_str, fmt).strftime("%I:%M %p")
        except ValueError:
            continue

    return None


def sync_event_attendance_csv(event_df):
    inserted_count = 0
    duplicate_count = 0
    missing_member_count = 0
    invalid_status_count = 0
    invalid_time_count = 0
    error_rows = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for idx, row in event_df.iterrows():
            member_code = str(row.get("Member Code", "")).strip()
            event_status = str(row.get("Event Status", "")).strip().title()
            attendance_date = str(row.get("Date", "")).strip()

            if event_status not in ["Present", "Absent"]:
                invalid_status_count += 1
                error_rows.append(
                    {
                        "Row Number": idx + 2,
                        "Member Code": member_code,
                        "Reason": "Invalid event status",
                    }
                )
                continue

            cursor.execute(
                """
                SELECT id, name
                FROM employees
                WHERE member_code = %s
                """,
                (member_code,),
            )
            member_row = cursor.fetchone()

            if not member_row:
                missing_member_count += 1
                error_rows.append(
                    {
                        "Row Number": idx + 2,
                        "Member Code": member_code,
                        "Reason": "Member code not found",
                    }
                )
                continue

            member_id, member_name = member_row

            cursor.execute(
                """
                SELECT 1
                FROM event_attendance
                WHERE event_member_id = %s AND date = %s
                """,
                (member_id, attendance_date),
            )

            if cursor.fetchone():
                duplicate_count += 1
                error_rows.append(
                    {
                        "Row Number": idx + 2,
                        "Member Code": member_code,
                        "Reason": "Duplicate event attendance",
                    }
                )
                continue

            from_time = None
            to_time = None

            if event_status == "Present":
                from_time = format_event_time(row.get("From Time", ""))
                to_time = format_event_time(row.get("To Time", ""))

                if not from_time or not to_time:
                    invalid_time_count += 1
                    error_rows.append(
                        {
                            "Row Number": idx + 2,
                            "Member Code": member_code,
                            "Raw From Time": str(row.get("From Time", "")),
                            "Raw To Time": str(row.get("To Time", "")),
                            "Reason": "Invalid or missing event time",
                        }
                    )
                    continue

            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
                    None,
                    member_id,
                    member_name,
                    event_status,
                    from_time,
                    to_time,
                    attendance_date,
                    current_timestamp,
                ),
            )

            inserted_count += 1

        conn.commit()
        conn.close()

        return {
            "inserted": inserted_count,
            "duplicates": duplicate_count,
            "missing_members": missing_member_count,
            "invalid_status": invalid_status_count,
            "invalid_time": invalid_time_count,
            "error_rows": error_rows,
        }

    except Exception as e:
        return {"error": str(e)}

# ------------------- HOME PAGEs -------------------

if menu == "Home":
    image_path = Path("assets/gurudwara_bg.png")
    encoded_image = get_base64_image(image_path)

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(255,255,255,0.12), rgba(255,255,255,0.12)), url("data:image/png;base64,{encoded_image}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        .home-spacer {{
            min-height: 80vh;
        }}
        </style>

        <div class="home-spacer"></div>
        """,
        unsafe_allow_html=True,
    )

# ------------------- Add Employee PAGE -------------------

elif menu == "Add Member":
    st.subheader("➕ Add New Member")
    st.markdown("Fields marked with * are required")

    st.markdown("Name <span style='color:red'>*</span>", unsafe_allow_html=True)
    name = st.text_input("", key="name")

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

    st.markdown(
        "Date of Joining <span style='color:red'>*</span>", unsafe_allow_html=True
    )
    doj = st.date_input("", key="doj")

    st.markdown("UID <span style='color:red'>*</span>", unsafe_allow_html=True)
    uid = st.text_input("", key="uid")

    if st.button("Add Member", key="add_employee_btn_main"):
        if not name or not department or not doj or not uid:
            st.warning("Please fill all required fields.")
        else:
            result = add_employee_db(name, department, doj, uid)

            if result == "duplicate":
                st.error("UID already exists. Please use a unique UID.")
            elif result == "success":
                st.success("Member added successfully!")
                st.cache_data.clear()
            else:
                st.error(f"Error: {result}")
                
    
# ------------------- MARK ATTENDANCE PAGE -------------------
elif menu == "Mark Attendance":
    st.subheader("🕒 Mark Attendance")

    # ✅ Fetch employees for dropdown
    df_emp = get_employees()

    emp_options = {
        f"{row['member_code']} | {row['name']} (UID: {row['uid']})": row["id"]
        for _, row in df_emp.iterrows()
    }
    
    
    # ✅ Dropdown

    selected_emp = st.selectbox("Select Member", list(emp_options.keys()))
    emp_id = emp_options[selected_emp]
    emp_name = selected_emp.split(" | ", 1)[1].split(" (UID")[0]

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
        event_member_name = selected_event_member.split(" | ", 1)[1].split(" (UID")[0]

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
        st.error("Member not found!")

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
    

# ------------------- VIEW ATTENDANCE PAGE -------------------
elif menu == "View Attendance":
    st.subheader("📋 Attendance Records 🚀")

    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    start_date = st.date_input("Start Date", default_start)
    end_date = st.date_input("End Date", default_end)
    member_search = st.text_input("Search Member Name (Regular/Event)").strip()

    try:
        conn = get_db_connection()

        regular_query = f"""
        SELECT
            a.id,
            e.member_code AS "Member Code",
            a.marked_by AS "Member Name",
            a.status AS "Status",
            a.date,
            a.marked_time AS "Timestamp"
        FROM attendance a
        LEFT JOIN employees e ON a.emp_id = e.id
        WHERE a.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY a.marked_time DESC
        LIMIT 500
        """
        df = pd.read_sql(regular_query, conn)

        event_query = f"""
        SELECT
            ea.id,
            e.member_code AS "Member Code",
            ea.event_member_name AS "Member Name",
            ea.event_status AS "Event Status",
            ea.event_from_time AS "Event From",
            ea.event_to_time AS "Event To",
            ea.date,
            ea.marked_time AS "Timestamp"
        FROM event_attendance ea
        LEFT JOIN employees e ON ea.event_member_id = e.id
        WHERE ea.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY ea.marked_time DESC
        LIMIT 500
        """
        event_df = pd.read_sql(event_query, conn)

        conn.close()

        if member_search:
            df = df[
                df["Member Name"].str.contains(member_search, case=False, na=False)
            ]

        if member_search:
            event_df = event_df[
                event_df["Member Name"].str.contains(member_search, case=False, na=False)
            ]

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
        regular_display_df = pd.DataFrame(records).drop(columns=["id"], errors="ignore")
        st.dataframe(regular_display_df)
    else:
        st.info("No regular attendance records found.")

    if event_records:
        st.write("### Event Attendance Records")
        event_display_df = pd.DataFrame(event_records).drop(columns=["id"], errors="ignore")
        st.dataframe(event_display_df)
    else:
        st.info("No event attendance records found.")

    df_display = pd.DataFrame(records)
    event_df_display = pd.DataFrame(event_records)

    # 🗑️ Delete Attendance Record
    st.subheader("🗑️ Delete Attendance Record")
    
    if not df_display.empty:

        record_options = {
            f"{row.get('Member Code', '')} | {row.get('Member Name', row.get('EName', ''))} | {row.get('Status', row.get('status', ''))} | {row.get('Timestamp', '')}": row[
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
        f"{row.get('Member Code', '')} | {row.get('Member Name', row.get('Event Member', ''))} | {row.get('Event Status', '')} | {row.get('Timestamp', '')}": row["id"]
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
        
        
    st.divider()
    
    
# ------------------- Analytics PAGE -------------------    
    
elif menu == "Analytics":
    st.subheader("📊 Attendance Analytics")

    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    start_date = st.date_input("Analytics Start Date", default_start, key="analytics_start")
    end_date = st.date_input("Analytics End Date", default_end, key="analytics_end")

    try:
        conn = get_db_connection()

        regular_query = f"""
        SELECT
            a.id,
            e.uid AS "UID",
            a.marked_by AS "EName",
            a.status AS "Status",
            a.date,
            a.marked_time AS "Timestamp"
        FROM attendance a
        LEFT JOIN employees e ON a.emp_id = e.id
        WHERE a.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY a.marked_time DESC
        LIMIT 500
        """
        df = pd.read_sql(regular_query, conn)

        event_query = f"""
        SELECT
            ea.id,
            e.uid AS "UID",
            ea.event_member_name AS "Event Member",
            ea.event_status AS "Event Status",
            ea.event_from_time AS "Event From",
            ea.event_to_time AS "Event To",
            ea.date,
            ea.marked_time AS "Timestamp"
        FROM event_attendance ea
        LEFT JOIN employees e ON ea.event_member_id = e.id
        WHERE ea.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY ea.marked_time DESC
        LIMIT 500
        """
        event_df = pd.read_sql(event_query, conn)

        conn.close()

        records = df.to_dict(orient="records")
        event_records = event_df.to_dict(orient="records")

    except Exception as e:
        st.error(f"Error fetching analytics data: {e}")
        records = []
        event_records = []

    from utils import generate_summary, plot_summary_chart

    normal_summary_df = generate_summary(records, "Status")
    st.write("### Regular Attendance Summary")
    st.dataframe(normal_summary_df)

    if not normal_summary_df.empty:
        normal_chart_path = plot_summary_chart(
            normal_summary_df, "Status", "regular_attendance_chart.png"
        )
        st.image(normal_chart_path)

    event_summary_df = generate_summary(event_records, "Event Status")
    st.write("### Event Attendance Summary")
    st.dataframe(event_summary_df)

    if not event_summary_df.empty:
        event_chart_path = plot_summary_chart(
            event_summary_df, "Event Status", "event_attendance_chart.png"
        )
        st.image(event_chart_path)
        
        
        
# ------------------- Member List PAGE ------------------- 
elif menu == "Member List":
    st.subheader("📋 Member List")

    try:
        conn = get_db_connection()
        df_emp_list = pd.read_sql_query(
            "SELECT id, member_code, name, uid, department, doj FROM employees ORDER BY name ASC",
            conn,
        )
        conn.close()

        if df_emp_list.empty:
            st.info("No members found.")
        else:
            st.dataframe(df_emp_list, use_container_width=True)

            st.divider()
            st.subheader("🗑️ Delete Member")

            emp_options = {
                f"{row['member_code']} | {row['name']} (UID: {row['uid']})": row["id"]
                for _, row in df_emp_list.iterrows()
            }

            selected_emp_del = st.selectbox(
                "Select Member to Delete",
                list(emp_options.keys()),
                key="delete_emp_from_list",
            )

            if st.session_state.pop("reset_emp_delete_from_list", False):
                st.session_state["confirm_emp_delete_from_list"] = False

            confirm_delete = st.checkbox(
                "Confirm delete", key="confirm_emp_delete_from_list"
            )

            if st.button(
                "Delete Member",
                key="delete_emp_btn_from_list",
                disabled=not confirm_delete,
            ):
                emp_id_del = emp_options[selected_emp_del]

                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute("DELETE FROM employees WHERE id=%s", (emp_id_del,))
                    conn.commit()
                    conn.close()

                    st.success("Member deleted successfully!")
                    st.cache_data.clear()
                    st.session_state["reset_emp_delete_from_list"] = True
                    st.rerun()

                except Exception as e:
                    st.error(f"Error deleting Member: {e}")

    except Exception as e:
        st.error(f"Error fetching Member list: {e}")
        
        
        
# ------------------- Sync Attendance PAGE -------------------
elif menu == "Sync Attendance":
    st.subheader("Upload Attendance CSV Files")
    
    st.info("For CSV sync, use Date in YYYY-MM-DD format only. Example: 2026-04-06")
    
    st.caption(
        "Upload one or both attendance CSV files, review the cleaned output and sync report, then sync only the clean rows."
    )

    regular_csv = st.file_uploader(
        "Upload Regular Attendance CSV",
        type=["csv"],
        key="regular_attendance_csv",
    )

    event_csv = st.file_uploader(
        "Upload Event Attendance CSV",
        type=["csv"],
        key="event_attendance_csv",
    )

    required_regular_columns = REGULAR_REQUIRED_COLUMNS
    required_event_columns = EVENT_REQUIRED_COLUMNS
    
    if (
        "prepared_sync_payload" in st.session_state
        and regular_csv is None
        and event_csv is None
    ):
        st.session_state.pop("prepared_sync_payload", None)
        
    
    current_upload_signature = (
        regular_csv.name if regular_csv else None,
        regular_csv.size if regular_csv else None,
        event_csv.name if event_csv else None,
        event_csv.size if event_csv else None,
    )

    if st.session_state.get("agent_upload_signature") != current_upload_signature:
        st.session_state["agent_upload_signature"] = current_upload_signature
        st.session_state.pop("prepared_sync_payload", None)
        
        

    regular_preview_df = None
    event_preview_df = None
    regular_valid = False
    event_valid = False
    prepared_sync_payload = None
    can_prepare_regular_agent_file = False

    if regular_csv is not None:
        try:
            regular_preview_df = prepare_uploaded_dataframe(pd.read_csv(regular_csv))
            regular_preview_df.columns = regular_preview_df.columns.str.strip()
            st.write("### Regular Attendance Preview")
            st.dataframe(
                regular_preview_df.drop(columns=["_source_row_number"], errors="ignore"),
                use_container_width=True,
            )

            missing_regular_columns = required_regular_columns - set(regular_preview_df.columns)
            if missing_regular_columns:
                st.error(
                    f"Regular Attendance CSV is missing columns: {', '.join(sorted(missing_regular_columns))}"
                )
            else:
                regular_valid = True
                st.success("Regular Attendance CSV format looks valid.")

        except Exception as e:
            st.error(f"Error reading regular attendance CSV: {e}")
            
    
    if event_csv is not None:
        try:
            event_preview_df = prepare_uploaded_dataframe(pd.read_csv(event_csv))
            event_preview_df.columns = event_preview_df.columns.str.strip()
            st.write("### Event Attendance Preview")
            st.dataframe(
                event_preview_df.drop(columns=["_source_row_number"], errors="ignore"),
                use_container_width=True,
            )

            missing_event_columns = required_event_columns - set(event_preview_df.columns)
            if missing_event_columns:
                st.error(
                    f"Event Attendance CSV is missing columns: {', '.join(sorted(missing_event_columns))}"
                )
            else:
                event_valid = True
                st.success("Event Attendance CSV format looks valid.")

                event_validation_issues = []

                for idx, row in event_preview_df.iterrows():
                    event_status = str(row.get("Event Status", "")).strip().title()
                    from_time_raw = str(row.get("From Time", "")).strip()
                    to_time_raw = str(row.get("To Time", "")).strip()
                    member_code_raw = str(row.get("Member Code", "")).strip()

                    if not member_code_raw or member_code_raw.lower() == "nan":
                        event_validation_issues.append(
                            {
                                "Row Number": idx + 2,
                                "Member Code": member_code_raw,
                                "Reason": "Missing Member Code",
                            }
                        )

                    if event_status not in ["Present", "Absent"]:
                        event_validation_issues.append(
                            {
                                "Row Number": idx + 2,
                                "Member Code": member_code_raw,
                                "Reason": "Invalid Event Status",
                            }
                        )

                    if event_status == "Present":
                        if not from_time_raw or from_time_raw.lower() == "nan":
                            event_validation_issues.append(
                                {
                                    "Row Number": idx + 2,
                                    "Member Code": member_code_raw,
                                    "Reason": "Missing From Time",
                                }
                            )
                        elif ":" not in from_time_raw or format_event_time(from_time_raw) is None:
                            event_validation_issues.append(
                                {
                                    "Row Number": idx + 2,
                                    "Member Code": member_code_raw,
                                    "Reason": "Invalid From Time format",
                                }
                            )

                        if not to_time_raw or to_time_raw.lower() == "nan":
                            event_validation_issues.append(
                                {
                                    "Row Number": idx + 2,
                                    "Member Code": member_code_raw,
                                    "Reason": "Missing To Time",
                                }
                            )
                        elif ":" not in to_time_raw or format_event_time(to_time_raw) is None:
                            event_validation_issues.append(
                                {
                                    "Row Number": idx + 2,
                                    "Member Code": member_code_raw,
                                    "Reason": "Invalid To Time format",
                                }
                            )

                if event_validation_issues:
                    st.warning("Event Attendance CSV has row-level validation issues.")
                    st.dataframe(pd.DataFrame(event_validation_issues), use_container_width=True)
                else:
                    st.success("Event Attendance CSV row-level validation looks good.")

        except Exception as e:
            st.error(f"Error reading event attendance CSV: {e}")
            
            
    can_prepare_regular_agent_file = (
        regular_preview_df is not None or event_preview_df is not None
    )

    if st.button(
        "Review and Prepare Clean CSVs",
        key="prepare_clean_regular_csv_btn",
        disabled=not can_prepare_regular_agent_file,
    ):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            prepared_sync_payload = prepare_agent_sync_payload(
                regular_preview_df,
                event_preview_df,
                cursor,
            )

            conn.close()
            st.session_state["prepared_sync_payload"] = prepared_sync_payload

        except Exception as e:
            st.error(f"Could not prepare the uploaded CSV files: {e}")

    if "prepared_sync_payload" in st.session_state:
        prepared_sync_payload = st.session_state["prepared_sync_payload"]

    if prepared_sync_payload is not None:
        show_regular_sections = regular_preview_df is not None
        show_event_sections = event_preview_df is not None
        if show_regular_sections:
            st.write("### Regular Attendance Summary")

            regular_summary = prepared_sync_payload["regular_summary"]

            summary_df = pd.DataFrame(
                [
                    {
                        "Source File": "Regular_Attendance",
                        "Accepted Rows": regular_summary["accepted"],
                        "Warnings": regular_summary["warnings"],
                        "Rejected Rows": regular_summary["rejected"],
                    }
                ]
            )
            st.dataframe(summary_df, use_container_width=True)
        
        
        if show_event_sections:
            event_summary = prepared_sync_payload["event_summary"]

            event_summary_df = pd.DataFrame(
                [
                    {
                        "Source File": "Event_Attendance",
                        "Accepted Rows": event_summary["accepted"],
                        "Warnings": event_summary["warnings"],
                        "Rejected Rows": event_summary["rejected"],
                    }
                ]
            )
            st.write("### Event Attendance Summary")
            st.dataframe(event_summary_df, use_container_width=True)
        

        if show_regular_sections:
            st.write("### Ready to Sync: Regular Attendance")
            if prepared_sync_payload["regular_clean_df"].empty:
                st.info("No clean regular attendance rows are ready yet.")
            else:
                st.dataframe(
                    prepared_sync_payload["regular_clean_df"],
                    use_container_width=True,
                )

        if show_event_sections:
            st.write("### Ready to Sync: Event Attendance")
            if prepared_sync_payload["event_clean_df"].empty:
                st.info("No clean event attendance rows are ready yet.")
            else:
                st.dataframe(
                    prepared_sync_payload["event_clean_df"],
                    use_container_width=True,
                )


        report_title = "### Agent Sync Report"

        if show_regular_sections and not show_event_sections:
            report_title = "### Regular Attendance Agent Report"
        elif show_event_sections and not show_regular_sections:
            report_title = "### Event Attendance Agent Report"

        st.write(report_title)

        if prepared_sync_payload["report_df"].empty:
            st.success("No sync issues found in the prepared data.")
        else:
            st.dataframe(
                prepared_sync_payload["report_df"],
                use_container_width=True,
            )        
            
            

    if st.button(
        "Sync Attendance",
        key="sync_attendance_btn",
        disabled=not (
            prepared_sync_payload is not None
            and (
                not prepared_sync_payload["regular_clean_df"].empty
                or not prepared_sync_payload["event_clean_df"].empty
            )
        ),
    ):
        regular_result = None
        event_result = None

        if not prepared_sync_payload["regular_clean_df"].empty:
            regular_result = sync_regular_attendance_csv(
                prepared_sync_payload["regular_clean_df"]
            )

        if not prepared_sync_payload["event_clean_df"].empty:
            event_result = sync_event_attendance_csv(
                prepared_sync_payload["event_clean_df"]
            )

        if regular_result is not None:
            if "error" in regular_result:
                st.error(f"Regular Attendance sync failed: {regular_result['error']}")
            else:
                st.success("Regular attendance clean rows synced successfully.")
                st.write(f"Clean rows inserted: {regular_result['inserted']}")
                st.write(f"Duplicate rows skipped: {regular_result['duplicates']}")
                st.write(f"Rows skipped for missing member code: {regular_result['missing_members']}")
                st.write(f"Rows skipped for invalid status: {regular_result['invalid_status']}")

                if regular_result["error_rows"]:
                    st.write("### Regular Sync Details")
                    st.dataframe(
                        pd.DataFrame(regular_result["error_rows"]),
                        use_container_width=True,
                    )

        if event_result is not None:
            if "error" in event_result:
                st.error(f"Event Attendance sync failed: {event_result['error']}")
            else:
                st.success("Event attendance clean rows synced successfully.")
                st.write(f"Clean rows inserted: {event_result['inserted']}")
                st.write(f"Duplicate rows skipped: {event_result['duplicates']}")
                st.write(f"Rows skipped for missing member code: {event_result['missing_members']}")
                st.write(f"Rows skipped for invalid event status: {event_result['invalid_status']}")
                st.write(f"Rows skipped for invalid event time: {event_result['invalid_time']}")

                if event_result["error_rows"]:
                    st.write("### Event Sync Details")
                    st.dataframe(
                        pd.DataFrame(event_result["error_rows"]),
                        use_container_width=True,
                    )
