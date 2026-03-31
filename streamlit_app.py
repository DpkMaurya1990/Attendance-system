# ------------------- ADD EMPLOYEE PAGE -------------------
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
        # ✅ Validation (designation removed)
        if not name or not department or not doj or not manual_id:
            st.warning("Please fill all required fields.")

        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # ✅ Duplicate check
                cursor.execute(
                    "SELECT 1 FROM employees WHERE manual_id = %s", (manual_id,)
                )
                existing = cursor.fetchone()

                if existing:
                    st.error("Manual ID already exists. Please use a unique ID.")

                else:
                    cursor.execute(
                        """
                        INSERT INTO employees 
                        (name, department, doj, shift_start, shift_end, manual_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            name,
                            department,
                            str(doj),
                            shift_start,
                            shift_end,
                            manual_id,
                        ),
                    )

                    conn.commit()
                    conn.close()
                    st.success("Employee added successfully!")

                    # ✅ refresh cache
                    st.cache_data.clear()

            except Exception as e:
                st.error(f"Error adding employee: {e}")