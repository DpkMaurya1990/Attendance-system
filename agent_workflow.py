from datetime import datetime

import pandas as pd

# Define the required columns for regular and event attendance data, as well as allowed status values
REGULAR_REQUIRED_COLUMNS = {"Date", "Member Code", "Status"}
EVENT_REQUIRED_COLUMNS = {
    "Date",
    "Member Code",
    "Event Status",
    "From Time",
    "To Time",
}
ALLOWED_STATUS_VALUES = {"Present", "Absent"}

# Setting up the report columns for consistency in error reporting
REPORT_COLUMNS = [
    "Source File",
    "Row Number",
    "Date",
    "Member Code",
    "Member Name",
    "Issue Summary",
    "Suggested Fix",
    "Raw Values",
    "Severity",
]

# This function normalizes cell values by stripping whitespace and converting empty or "nan" values to None
def normalize_cell(value):
    if pd.isna(value):
        return None

    value_str = str(value).strip()
    if not value_str or value_str.lower() == "nan":
        return None

    return value_str

# This function standardizes the status values to ensure consistency in the attendance data
def normalize_status(value):
    normalized = normalize_cell(value)
    if normalized is None:
        return None
    return normalized.title()

# This function attempts to parse and standardize date values from the attendance data
def parse_attendance_date(value):
    normalized = normalize_cell(value)
    if normalized is None:
        return None

    supported_formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    )

    for fmt in supported_formats:
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue

    return None

    try:
        return pd.to_datetime(normalized).date().isoformat()
    except Exception:
        return None

# This function cleans and standardizes the uploaded DataFrame, ensuring consistent column names and adding a source row number for error tracking
def prepare_uploaded_dataframe(df):
    cleaned_df = df.copy()
    cleaned_df.columns = cleaned_df.columns.str.strip()
    cleaned_df = cleaned_df.dropna(how="all").reset_index(drop=True)

    for column in cleaned_df.columns:
        cleaned_df[column] = cleaned_df[column].apply(normalize_cell)

    cleaned_df["_source_row_number"] = cleaned_df.index + 2
    return cleaned_df

# This function attempts to parse and standardize time values from the event attendance data
def format_event_time(value):
    time_str = normalize_cell(value)

    if time_str is None:
        return None

    if ":" not in time_str:
        return None

    if " " in time_str and ":" in time_str:
        possible_time = time_str.split()[-1]
        if ":" in possible_time:
            time_str = possible_time

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

# This function creates a structured report row for any issues found during data validation
def create_report_row(source_file, row_number, row, issues, suggestions, severity):
    raw_values = {
        key: value
        for key, value in row.items()
        if key != "_source_row_number"
    }

    return {
        "Source File": source_file,
        "Row Number": row_number,
        "Date": normalize_cell(row.get("Date")),
        "Member Code": normalize_cell(row.get("Member Code")),
        "Member Name": normalize_cell(row.get("Member Name")),
        "Issue Summary": "; ".join(issues),
        "Suggested Fix": "; ".join(dict.fromkeys(suggestions)),
        "Raw Values": str(raw_values),
        "Severity": severity,
    }


def empty_report_df():
    return pd.DataFrame(columns=REPORT_COLUMNS)


def build_member_lookup(cursor):
    cursor.execute("SELECT id, member_code, name FROM employees")
    rows = cursor.fetchall()

    return {
        member_code: {"id": member_id, "name": member_name}
        for member_id, member_code, member_name in rows
        if member_code
    }


def load_existing_regular_keys(cursor):
    cursor.execute("SELECT emp_id, date FROM attendance")
    return {(row[0], str(row[1])) for row in cursor.fetchall()}


# This function processes the regular attendance DataFrame, validating each row against the member lookup and existing attendance records, and generates a clean DataFrame for valid entries along with a report DataFrame for any issues found
def prepare_regular_attendance_agent_data(df, member_lookup, existing_regular_keys):
    clean_rows = []
    report_rows = []
    seen_keys = set()

    for _, row in df.iterrows():
        row_number = int(row["_source_row_number"])
        issues = []
        suggestions = []

        #Normalize and validate key fields from the row
        member_code = normalize_cell(row.get("Member Code"))
        member_name = normalize_cell(row.get("Member Name"))
        status = normalize_status(row.get("Status"))
        attendance_date = parse_attendance_date(row.get("Date"))

        if normalize_cell(row.get("Date")) is None:
            issues.append("Missing Date")
            suggestions.append("Provide a valid Date value")
        elif attendance_date is None:
            issues.append("Invalid Date")
            suggestions.append("Use a valid Date format")

        if member_code is None:
            issues.append("Missing Member Code")
            suggestions.append("Provide a valid Member Code")
            member_record = None
        else:
            member_record = member_lookup.get(member_code)
            if member_record is None:
                issues.append("Unknown Member Code")
                suggestions.append("Use an existing Member Code")

        if status is None:
            issues.append("Missing Status")
            suggestions.append("Provide Status as Present or Absent")
        
        elif status not in ALLOWED_STATUS_VALUES:
            issues.append("Invalid Status")
            suggestions.append("Use only Present or Absent")
            
        # Validate Member Name against the member lookup if Member Code is valid
        if member_record and member_name and member_name != member_record["name"]:
            issues.append("Member Name does not match system record")
            suggestions.append("Review Member Name for this Member Code")

        if member_record and attendance_date:
            duplicate_key = (member_record["id"], attendance_date)

            if duplicate_key in seen_keys or duplicate_key in existing_regular_keys:
                issues.append("Duplicate regular attendance row")
                suggestions.append("Remove the duplicate regular attendance entry")
            else:
                seen_keys.add(duplicate_key)

        has_error = any(
            issue
            for issue in issues
            if issue != "Member Name does not match system record"
        )

        if issues:
            severity = "Error" if has_error else "Warning"
            report_rows.append(
                create_report_row(
                    "Regular_Attendance",
                    row_number,
                    row,
                    issues,
                    suggestions,
                    severity,
                )
            )

        if has_error:
            continue

        clean_rows.append(
            {
                "Date": attendance_date,
                "Member Code": member_code,
                "Member Name": member_record["name"] if member_record else member_name,
                "Status": status,
            }
        )

    return pd.DataFrame(clean_rows), pd.DataFrame(report_rows, columns=REPORT_COLUMNS)


def load_existing_event_keys(cursor):
    cursor.execute(
        """
        SELECT event_member_id, date, event_status, event_from_time, event_to_time
        FROM event_attendance
        """
    )
    return {
        (
            row[0],
            str(row[1]),
            normalize_cell(row[2]),
            normalize_cell(row[3]),
            normalize_cell(row[4]),
        )
        for row in cursor.fetchall()
    }


def prepare_event_attendance_agent_data(df, member_lookup, existing_event_keys):
    clean_rows = []
    report_rows = []
    seen_keys = set()

    for _, row in df.iterrows():
        row_number = int(row["_source_row_number"])
        issues = []
        suggestions = []

        member_code = normalize_cell(row.get("Member Code"))
        member_name = normalize_cell(row.get("Member Name"))
        event_status = normalize_status(row.get("Event Status"))
        attendance_date = parse_attendance_date(row.get("Date"))
        from_time_raw = normalize_cell(row.get("From Time"))
        to_time_raw = normalize_cell(row.get("To Time"))
        from_time = None
        to_time = None

        if normalize_cell(row.get("Date")) is None:
            issues.append("Missing Date")
            suggestions.append("Provide a valid Date value")
        elif attendance_date is None:
            issues.append("Invalid Date")
            suggestions.append("Use a valid Date format")

        if member_code is None:
            issues.append("Missing Member Code")
            suggestions.append("Provide a valid Member Code")
            member_record = None
        else:
            member_record = member_lookup.get(member_code)
            if member_record is None:
                issues.append("Unknown Member Code")
                suggestions.append("Use an existing Member Code")

        if event_status is None:
            issues.append("Missing Event Status")
            suggestions.append("Provide Event Status as Present or Absent")
        elif event_status not in ALLOWED_STATUS_VALUES:
            issues.append("Invalid Event Status")
            suggestions.append("Use only Present or Absent")

        if member_record and member_name and member_name != member_record["name"]:
            issues.append("Member Name does not match system record")
            suggestions.append("Review Member Name for this Member Code")

        if event_status == "Present":
            if from_time_raw is None:
                issues.append("Missing From Time for Present row")
                suggestions.append("Provide From Time for Present rows")
            else:
                from_time = format_event_time(from_time_raw)
                if from_time is None:
                    issues.append("Invalid From Time format")
                    suggestions.append("Use a valid From Time like 13:00 or 01:00 PM")

            if to_time_raw is None:
                issues.append("Missing To Time for Present row")
                suggestions.append("Provide To Time for Present rows")
            else:
                to_time = format_event_time(to_time_raw)
                if to_time is None:
                    issues.append("Invalid To Time format")
                    suggestions.append("Use a valid To Time like 13:00 or 01:00 PM")

        elif event_status == "Absent":
            if from_time_raw is not None or to_time_raw is not None:
                issues.append("Times provided for Absent event row; values will be cleared")
                suggestions.append("Leave From Time and To Time blank for Absent rows")
            from_time = None
            to_time = None

        if member_record and attendance_date and event_status in ALLOWED_STATUS_VALUES:
            duplicate_key = (
                member_record["id"],
                attendance_date,
                event_status,
                normalize_cell(from_time),
                normalize_cell(to_time),
            )

            if duplicate_key in seen_keys or duplicate_key in existing_event_keys:
                issues.append("Duplicate event attendance row")
                suggestions.append("Remove the duplicate event attendance entry")
            else:
                seen_keys.add(duplicate_key)

        has_error = any(
            issue
            for issue in issues
            if issue
            not in {
                "Member Name does not match system record",
                "Times provided for Absent event row; values will be cleared",
            }
        )

        if issues:
            severity = "Error" if has_error else "Warning"
            report_rows.append(
                create_report_row(
                    "Event_Attendance",
                    row_number,
                    row,
                    issues,
                    suggestions,
                    severity,
                )
            )

        if has_error:
            continue

        clean_rows.append(
            {
                "Date": attendance_date,
                "Member Code": member_code,
                "Member Name": member_record["name"] if member_record else member_name,
                "Event Status": event_status,
                "From Time": from_time,
                "To Time": to_time,
            }
        )

    return pd.DataFrame(clean_rows), pd.DataFrame(report_rows, columns=REPORT_COLUMNS)



def build_summary(clean_df, report_df, source_file):
    subset = (
        report_df[report_df["Source File"] == source_file]
        if not report_df.empty
        else pd.DataFrame(columns=REPORT_COLUMNS)
    )

    if subset.empty:
        warning_count = 0
        error_count = 0
    else:
        warning_count = int((subset["Severity"] == "Warning").sum())
        error_count = int((subset["Severity"] == "Error").sum())

    return {
        "accepted": int(len(clean_df)),
        "warnings": warning_count,
        "rejected": error_count,
    }
    

def prepare_agent_sync_payload(regular_df, event_df, cursor):
    prepared_regular_df = (
        prepare_uploaded_dataframe(regular_df)
        if regular_df is not None
        else pd.DataFrame(columns=list(REGULAR_REQUIRED_COLUMNS))
    )
    prepared_event_df = (
        prepare_uploaded_dataframe(event_df)
        if event_df is not None
        else pd.DataFrame(columns=list(EVENT_REQUIRED_COLUMNS))
    )
    

    regular_missing_columns = (
        sorted(REGULAR_REQUIRED_COLUMNS - set(prepared_regular_df.columns))
        if regular_df is not None
        else []
    )
    event_missing_columns = (
        sorted(EVENT_REQUIRED_COLUMNS - set(prepared_event_df.columns))
        if event_df is not None
        else []
    )

    member_lookup = build_member_lookup(cursor)
    existing_regular_keys = load_existing_regular_keys(cursor)
    existing_event_keys = load_existing_event_keys(cursor)

    regular_clean_df = pd.DataFrame()
    event_clean_df = pd.DataFrame()
    report_frames = []

    if regular_missing_columns:
        report_frames.append(
            pd.DataFrame(
                [
                    {
                        "Source File": "Regular_Attendance",
                        "Row Number": "",
                        "Date": "",
                        "Member Code": "",
                        "Member Name": "",
                        "Issue Summary": f"Missing required columns: {', '.join(regular_missing_columns)}",
                        "Suggested Fix": "Upload a CSV with all required columns present",
                        "Raw Values": "",
                        "Severity": "Error",
                    }
                ],
                columns=REPORT_COLUMNS,
            )
        )
    else:
        regular_clean_df, regular_report_df = prepare_regular_attendance_agent_data(
            prepared_regular_df,
            member_lookup,
            existing_regular_keys,
        )
        if not regular_report_df.empty:
            report_frames.append(regular_report_df)

    if event_missing_columns:
        report_frames.append(
            pd.DataFrame(
                [
                    {
                        "Source File": "Event_Attendance",
                        "Row Number": "",
                        "Date": "",
                        "Member Code": "",
                        "Member Name": "",
                        "Issue Summary": f"Missing required columns: {', '.join(event_missing_columns)}",
                        "Suggested Fix": "Upload a CSV with all required columns present",
                        "Raw Values": "",
                        "Severity": "Error",
                    }
                ],
                columns=REPORT_COLUMNS,
            )
        )
    else:
        event_clean_df, event_report_df = prepare_event_attendance_agent_data(
            prepared_event_df,
            member_lookup,
            existing_event_keys,
        )
        if not event_report_df.empty:
            report_frames.append(event_report_df)

    combined_report_df = (
        pd.concat(report_frames, ignore_index=True)
        if report_frames
        else empty_report_df()
    )

    return {
        "regular_clean_df": regular_clean_df,
        "event_clean_df": event_clean_df,
        "report_df": combined_report_df,
        "regular_missing_columns": regular_missing_columns,
        "event_missing_columns": event_missing_columns,
        "regular_summary": build_summary(
            regular_clean_df,
            combined_report_df,
            "Regular_Attendance",
        ),
        "event_summary": build_summary(
            event_clean_df,
            combined_report_df,
            "Event_Attendance",
        ),
    }