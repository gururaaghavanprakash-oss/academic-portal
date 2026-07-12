import streamlit as st
import json
import os
import re
import random
from datetime import datetime, timedelta

# --- CUSTOM UI STYLING ---
hide_st_style = """
            <style>
            footer {visibility: hidden;}
            .viewerBadge_container {visibility: hidden;}
            .viewerBadge_link {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- DATABASE SETUP ---
FILES = ['credentials.json', 'questions.json', 'scores.json', 'institutions.json', 'deletion_requests.json', 'tests.json', 'students.json']
for file in FILES:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            if file in ['questions.json', 'deletion_requests.json']:
                json.dump([], f)
            else:
                json.dump({}, f)

# --- HELPER FUNCTIONS ---
def load_data(filename):
    try:
        if os.path.getsize(filename) == 0: return [] if filename in ['questions.json', 'deletion_requests.json'] else {}
        with open(filename, 'r') as f: return json.load(f)
    except Exception:
        return [] if filename in ['questions.json', 'deletion_requests.json'] else {}

def save_data(filename, data):
    with open(filename, 'w') as f: json.dump(data, f, indent=4)

def process_expired_deletions():
    insts = load_data('institutions.json')
    creds = load_data('credentials.json')
    qs = load_data('questions.json')
    scores = load_data('scores.json')
    tests_db = load_data('tests.json')
    students = load_data('students.json')
    changed = False
    
    now = datetime.now()
    keys_to_delete = []
    
    for k, v in insts.items():
        if isinstance(v, dict) and v.get("status") == "scheduled_for_deletion" and "deletion_date" in v:
            try:
                if now >= datetime.strptime(v["deletion_date"], "%Y-%m-%d %H:%M:%S"):
                    keys_to_delete.append(k)
            except Exception: pass
    
    for k in keys_to_delete:
        changed = True
        del insts[k]
        creds = {p: data for p, data in creds.items() if not (isinstance(data, dict) and data.get("institution") == k)}
        qs = [q for q in qs if isinstance(q, dict) and q.get("institution") != k]
        scores = {s: data for s, data in scores.items() if isinstance(data, dict) and data.get("institution") != k}
        tests_db = {t: data for t, data in tests_db.items() if not t.startswith(f"{k}_")}
        students = {s: data for s, data in students.items() if not (isinstance(data, dict) and data.get("institution") == k)}
        
    if changed:
        save_data('institutions.json', insts); save_data('credentials.json', creds)
        save_data('questions.json', qs); save_data('scores.json', scores)
        save_data('tests.json', tests_db); save_data('students.json', students)

# --- SESSION STATE INITIALIZATION ---
keys_to_init = {
    'logged_in': False, 'role': None, 'username': "", 'institution': "", 'inst_type': "College",
    'test_submitted': False, 'student_score': 0, 'test_total': 0, 
    'student_name': "", 'student_group': "", 'student_subgroup': "",
    'prof_dept': None, 'prof_subject': None, 'prof_test': None,
    'student_view_subject': None, 'student_view_test': None,  # NEW STUDENT NAV STATES
    'active_test_key': None, 'test_start_time': None, 'shuffled_qs': [], 'current_q': 0, 
    's_answers': {}, 'q_times': {}, 'last_time': None
}
for key, val in keys_to_init.items():
    if key not in st.session_state: st.session_state[key] = val

process_expired_deletions()

def clear_test_state():
    st.session_state.update({'active_test_key': None, 'test_start_time': None, 'shuffled_qs': [], 'current_q': 0, 's_answers': {}, 'q_times': {}, 'last_time': None})

# --- MAIN APP UI ---
st.title("⚙️ Academic Testing Portal")

if not st.session_state.logged_in:
    st.subheader("Welcome. Please select your portal:")
    portal = st.radio("Login as:", ["Student", "Professor/Teacher", "Admin"])

    if portal == "Professor/Teacher":
        st.info("Enter your assigned ID and passcode to log in.")
        prof_id = st.text_input("Staff ID (Username)")
        passcode = st.text_input("Passcode", type="password")
        if st.button("Staff Login"):
            creds = load_data('credentials.json')
            if prof_id in creds and isinstance(creds[prof_id], dict) and creds[prof_id].get("passcode") == passcode:
                inst_id = creds[prof_id].get("institution", "")
                insts = load_data('institutions.json')
                i_type = insts.get(inst_id, {}).get("inst_type", "College") if insts else "College"
                
                st.session_state.update({'logged_in': True, 'role': 'Professor', 'username': prof_id, 
                                         'institution': inst_id, 'inst_type': i_type, 'prof_dept': None, 'prof_subject': None, 'prof_test': None})
                st.rerun()
            else: st.error("Invalid credentials.")

    elif portal == "Student":
        insts = load_data('institutions.json')
        approved = [k for k, v in insts.items() if isinstance(v, dict) and v.get("status") == "approved"]
        if not approved: st.warning("No institutions active.")
        else:
            student_inst = st.selectbox("Select Institution", approved)
            student_user = st.text_input("Student Username / Roll No.")
            student_pass = st.text_input("Password", type="password")
            if st.button("Student Login"):
                if student_user and student_pass:
                    students = load_data('students.json')
                    s_key = f"{student_inst}_{student_user}"
                    if s_key in students and students[s_key].get("password") == student_pass:
                        s_data = students[s_key]
                        
                        if s_data.get("status", "active") == "graduated":
                            st.error("Access Denied: Your account is marked as Graduated/Alumni.")
                        else:
                            i_type = insts.get(student_inst, {}).get("inst_type", "College")
                            st.session_state.update({
                                'logged_in': True, 'role': 'Student', 'username': student_user,
                                'student_name': s_data.get("name", ""), 'institution': student_inst,
                                'student_group': s_data.get("group", ""), 'student_subgroup': s_data.get("subgroup", ""),
                                'inst_type': i_type, 'student_view_subject': None, 'student_view_test': None
                            })
                            st.rerun()
                    else: st.error("Invalid Username or Password.")
                else: st.warning("Please enter your credentials.")
                
    elif portal == "Admin":
        admin_id = st.text_input("Admin ID")
        admin_pass = st.text_input("Passcode", type="password")
        if st.button("Admin Login"):
            if admin_id == "ADMIN" and admin_pass == "ATP2026":
                st.session_state.update({'logged_in': True, 'role': 'SuperAdmin', 'username': 'Platform Admin'})
                st.rerun()
            else:
                insts = load_data('institutions.json')
                if admin_id in insts and isinstance(insts[admin_id], dict) and insts[admin_id].get("password") == admin_pass and insts[admin_id].get("status") in ["approved", "scheduled_for_deletion"]:
                    i_type = insts[admin_id].get("inst_type", "College")
                    st.session_state.update({'logged_in': True, 'role': 'Admin', 'username': admin_id, 'institution': admin_id, 'inst_type': i_type})
                    st.rerun()
                else: st.error("Access Denied.")

    st.markdown("---")
    with st.expander("Register a School/College/University"):
        with st.form("inst_reg_form", clear_on_submit=True):
            inst_type = st.selectbox("Institution Type", ["School", "College", "University"])
            inst_name = st.text_input("Full Institute Name")
            contact_name = st.text_input("Your Name (Admin Contact)")
            inst_email = st.text_input("Email Address")
            inst_phone = st.text_input("Phone Number")
            inst_pass = st.text_input("Set Institution Admin Password", type="password")
            if st.form_submit_button("Submit Registration Request"):
                if inst_name and contact_name and inst_email and inst_pass:
                    generated_id = re.sub(r'[^A-Z0-9]', '_', inst_name.upper())
                    insts = load_data('institutions.json')
                    if generated_id in insts: st.error(f"An institution similar to {generated_id} is already registered.")
                    else:
                        insts[generated_id] = {"inst_type": inst_type, "institute_name": inst_name, "contact": contact_name, "email": inst_email, "phone": inst_phone, "password": inst_pass, "status": "pending"}
                        save_data('institutions.json', insts)
                        st.success(f"✅ Registration Submitted! Please save your Admin ID: **{generated_id}**")
                else: st.warning("Please fill in all required fields.")

# --- DASHBOARDS ---
if st.session_state.logged_in:
    col_a, col_b = st.columns([4, 1])
    with col_a: st.success(f"User: {st.session_state.username} | Role: {st.session_state.role} | Inst: {st.session_state.institution}")
    with col_b: 
        if st.button("Log Out"):
            for key in keys_to_init.keys(): st.session_state[key] = None if key not in ['logged_in', 'test_submitted'] else False
            st.rerun()
            
    st.markdown("---")
    
    # === SUPER ADMIN ===
    if st.session_state.role == "SuperAdmin":
        st.header("👑 Platform Administrator Dashboard")
        sa_tab1, sa_tab2, sa_tab3 = st.tabs(["Pending Registrations", "Manage Active Institutions", "Institution Deletion Requests"])
        insts = load_data('institutions.json')
        
        with sa_tab1:
            pending = {k: v for k, v in insts.items() if isinstance(v, dict) and v.get("status") == "pending"}
            if not pending: st.info("No pending registrations.")
            else:
                for k, v in pending.items():
                    with st.expander(f"🏫 {v.get('institute_name', 'Unknown')} (ID: {k}) - {v.get('inst_type', 'College')}"):
                        st.write(f"**Contact Name:** {v.get('contact', 'N/A')}")
                        st.write(f"**Email Address:** {v.get('email', 'N/A')}")
                        st.write(f"**Phone Number:** {v.get('phone', 'N/A')}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Approve", key=f"app_{k}"): insts[k]["status"] = "approved"; save_data('institutions.json', insts); st.rerun()
                        with col2:
                            if st.button("Reject & Delete", key=f"rej_{k}"): del insts[k]; save_data('institutions.json', insts); st.rerun()
                                
        with sa_tab2:
            approved = {k: v for k, v in insts.items() if isinstance(v, dict) and v.get("status") in ["approved", "scheduled_for_deletion"]}
            if not approved: st.info("No approved institutions yet.")
            else:
                for k, v in approved.items():
                    with st.expander(f"🏫 {v.get('institute_name', 'Unknown')} (Admin ID: {k}) - {v.get('inst_type', 'College')}"):
                        st.write(f"**Contact Name:** {v.get('contact', 'N/A')}")
                        st.write(f"**Email Address:** {v.get('email', 'N/A')}")
                        st.write(f"**Phone Number:** {v.get('phone', 'N/A')}")
                        if v.get("status") == "scheduled_for_deletion": st.error(f"⚠️ *Pending Auto-Delete on {v.get('deletion_date')}*")
                        if st.button("Force Remove", key=f"force_del_{k}"): del insts[k]; save_data('institutions.json', insts); st.rerun()
                            
        with sa_tab3:
            reqs = load_data('deletion_requests.json')
            if not isinstance(reqs, list): reqs = []
            admin_reqs = [r for r in reqs if isinstance(r, dict) and r.get('role') == "Admin"]
            if not admin_reqs: st.info("No institution deletion requests pending.")
            else:
                for r in admin_reqs:
                    if st.button(f"Approve Request for {r.get('username')}", key=f"wipe_{r.get('username')}"):
                        if r.get('username') in insts:
                            insts[r['username']]["status"] = "scheduled_for_deletion"
                            insts[r['username']]["deletion_date"] = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
                            save_data('institutions.json', insts)
                        if r in reqs: reqs.remove(r); save_data('deletion_requests.json', reqs)
                        st.rerun()

    # === INSTITUTION ADMIN ===
    elif st.session_state.role == "Admin":
        insts = load_data('institutions.json')
        my_inst = insts.get(st.session_state.institution, {})
        is_school = (st.session_state.inst_type == "School")
        
        lbl_prof = "Teacher" if is_school else "Professor"
        lbl_grp = "Class" if is_school else "Department"
        lbl_sub = "Section" if is_school else "Year"
        
        if my_inst.get("status") == "scheduled_for_deletion":
            st.error("🚨 ACCOUNT SCHEDULED FOR DELETION 🚨")
            if st.button("Cancel Deletion Request & Recover Account", type="primary"):
                insts[st.session_state.institution]["status"] = "approved"
                if "deletion_date" in insts[st.session_state.institution]: del insts[st.session_state.institution]["deletion_date"]
                save_data('institutions.json', insts); st.rerun()
        else:
            st.header(f"🛡️ {st.session_state.institution} Admin Dashboard")
            admin_tab1, admin_tab2, admin_tab3, admin_tab4, admin_tab5, admin_tab6 = st.tabs([f"Manage {lbl_prof}s", f"Add {lbl_prof}", "Add Students", "Manage Students", "Graduated Batches", "Settings"])
            
            with admin_tab1:
                creds = load_data('credentials.json')
                inst_profs = {p: data for p, data in creds.items() if isinstance(data, dict) and data.get("institution") == st.session_state.institution}
                if not inst_profs: st.info(f"You haven't registered any {lbl_prof}s yet.")
                else:
                    for prof, data in inst_profs.items():
                        with st.expander(f"👨‍🏫 {prof}"):
                            upd_depts = st.text_input(f"{lbl_grp}es", value=", ".join(data.get('departments', [])), key=f"upd_dept_{prof}")
                            upd_subs = st.text_input("Subjects", value=", ".join(data.get('subjects', [])), key=f"upd_sub_{prof}")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Update Details", key=f"btn_upd_{prof}", type="primary"):
                                    creds[prof]["departments"] = [d.strip() for d in upd_depts.split(",") if d.strip()]
                                    creds[prof]["subjects"] = [s.strip() for s in upd_subs.split(",") if s.strip()]
                                    save_data('credentials.json', creds); st.rerun()
                            with col2:
                                if st.button("Remove Account", key=f"del_prof_{prof}"):
                                    del creds[prof]; save_data('credentials.json', creds)
                                    qs = load_data('questions.json')
                                    save_data('questions.json', [q for q in qs if not (isinstance(q, dict) and q.get("professor") == prof and q.get("institution") == st.session_state.institution)])
                                    st.rerun()
                                
            with admin_tab2:
                with st.form("create_prof_form", clear_on_submit=True):
                    new_prof_id = st.text_input(f"New {lbl_prof} ID (Username)")
                    new_prof_pass = st.text_input("Assign Passcode", type="password")
                    st.info(f"Separate multiple entries with commas (e.g. {'10, 11' if is_school else 'CS, Mechanical'})")
                    new_depts = st.text_input(f"Assigned {lbl_grp}es")
                    new_subs = st.text_input("Assigned Subjects")
                    if st.form_submit_button("Create Account"):
                        if new_prof_id and new_prof_pass and new_depts and new_subs:
                            creds = load_data('credentials.json')
                            if new_prof_id in creds: st.warning("This ID exists.")
                            else:
                                creds[new_prof_id] = {
                                    "passcode": new_prof_pass, "institution": st.session_state.institution,
                                    "departments": [d.strip() for d in new_depts.split(",") if d.strip()],
                                    "subjects": [s.strip() for s in new_subs.split(",") if s.strip()]
                                }
                                save_data('credentials.json', creds); st.success(f"✅ {lbl_prof} added!")
                        else: st.warning("Please fill out all fields.")
            
            with admin_tab3:
                students = load_data('students.json')
                with st.form("create_student_form", clear_on_submit=True):
                    st.subheader("Register New Student")
                    s_user = st.text_input("Student Username / Roll No.")
                    s_name = st.text_input("Full Name")
                    s_pass = st.text_input("Assign Password", type="password")
                    st.info(f"Make sure the {lbl_grp} exactly matches what {lbl_prof}s use.")
                    s_grp = st.text_input(f"Assigned {lbl_grp}")
                    s_subgrp = st.text_input(f"{lbl_sub} (Optional)" if is_school else f"{lbl_sub} (e.g., 1st Year)")
                    s_batch = st.text_input("Batch (e.g., 2022-2026)")
                    if st.form_submit_button("Register Student"):
                        if s_user and s_name and s_pass and s_grp and s_subgrp and s_batch:
                            s_key = f"{st.session_state.institution}_{s_user}"
                            if s_key in students: st.warning("Username already exists.")
                            else:
                                students[s_key] = {"username": s_user, "name": s_name, "password": s_pass, "institution": st.session_state.institution, "group": s_grp.strip(), "subgroup": s_subgrp.strip(), "batch": s_batch.strip(), "status": "active"}
                                save_data('students.json', students); st.success("✅ Student Registered!")
                        else: st.warning("Please fill out all required fields.")

            with admin_tab4:
                students = load_data('students.json')
                inst_students = {k: v for k, v in students.items() if isinstance(v, dict) and v.get("institution") == st.session_state.institution}
                active_students = {k: v for k, v in inst_students.items() if v.get("status", "active") == "active"}
                
                st.subheader("Manage Active Students")
                if not active_students: st.info("No active students found.")
                else:
                    depts = sorted(list(set([v.get("group") for v in active_students.values()])))
                    sel_dept = st.selectbox(f"1. Select {lbl_grp}:", depts)
                    dept_students = {k: v for k, v in active_students.items() if v.get("group") == sel_dept}
                    years = sorted(list(set([v.get("subgroup") for v in dept_students.values()])))
                    sel_year = st.selectbox(f"2. Select {lbl_sub}:", years)
                    year_students = {k: v for k, v in dept_students.items() if v.get("subgroup") == sel_year}
                    
                    st.markdown("---")
                    st.write(f"**Students in {sel_dept} - {sel_year} ({len(year_students)})**")
                    for sk, sv in year_students.items():
                        c1, c2 = st.columns([4, 1])
                        with c1: st.write(f"🎓 **{sv.get('name')}** (@{sv.get('username')}) | Batch: {sv.get('batch', 'N/A')}")
                        with c2:
                            if st.button("Remove", key=f"del_s_{sk}"): del students[sk]; save_data('students.json', students); st.rerun()
                                
                    st.markdown("---")
                    st.subheader("⚙️ Bulk Group Actions")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Promote Entire {lbl_sub}**")
                        new_year = st.text_input(f"New {lbl_sub} Name:", placeholder=f"e.g., 2nd Year")
                        if st.button(f"🚀 Promote {lbl_grp}", type="primary"):
                            if new_year:
                                for sk in year_students.keys(): students[sk]["subgroup"] = new_year.strip()
                                save_data('students.json', students); st.success(f"Promoted to {new_year}!"); st.rerun()
                            else: st.warning(f"Enter the new {lbl_sub} name first.")
                    with c2:
                        st.write("**Mark as Graduated / Alumni**")
                        if st.button("🎓 Graduate Group", type="primary"):
                            for sk in year_students.keys(): students[sk]["status"] = "graduated"
                            save_data('students.json', students); st.success("Students moved to Alumni Archive!"); st.rerun()

            with admin_tab5:
                st.subheader("🎓 Alumni Archive")
                students = load_data('students.json')
                inst_students = {k: v for k, v in students.items() if isinstance(v, dict) and v.get("institution") == st.session_state.institution}
                grad_students = {k: v for k, v in inst_students.items() if v.get("status") == "graduated"}
                
                if not grad_students: st.info("No graduated students on record.")
                else:
                    batches = sorted(list(set([v.get("batch", "Unknown") for v in grad_students.values()])))
                    sel_batch = st.selectbox("1. Select Batch:", batches)
                    batch_students = {k: v for k, v in grad_students.items() if v.get("batch", "Unknown") == sel_batch}
                    depts = sorted(list(set([v.get("group") for v in batch_students.values()])))
                    sel_dept = st.selectbox(f"2. Select {lbl_grp}:", depts, key="grad_dept_sel")
                    final_grads = {k: v for k, v in batch_students.items() if v.get("group") == sel_dept}
                    
                    st.markdown("---")
                    st.write(f"**Graduates of {sel_batch} - {sel_dept} ({len(final_grads)})**")
                    for sk, sv in final_grads.items():
                        c1, c2 = st.columns([4, 1])
                        with c1: st.write(f"🎓 **{sv.get('name')}** (@{sv.get('username')}) | Final {lbl_sub}: {sv.get('subgroup', 'N/A')}")
                        with c2:
                            if st.button("Delete Record", key=f"del_g_{sk}"): del students[sk]; save_data('students.json', students); st.rerun()

            with admin_tab6:
                st.subheader("Institution Account Deletion")
                with st.form("del_req_form", clear_on_submit=True):
                    st.warning("⚠️ DISCLAIMER: Your account will be scheduled for permanent deletion.")
                    confirm_del = st.checkbox("I confirm my deletion request.")
                    if st.form_submit_button("Submit Deletion Request", type="primary"):
                        if confirm_del:
                            reqs = load_data('deletion_requests.json')
                            if not isinstance(reqs, list): reqs = []
                            if not any(r.get('username') == st.session_state.institution and r.get('role') == "Admin" for r in reqs):
                                reqs.append({"username": st.session_state.institution, "role": "Admin", "institution": st.session_state.institution})
                                save_data('deletion_requests.json', reqs); st.success("✅ Request sent to Platform Administrator.")
                        else: st.error("Please check the confirmation box.")

    # === 3. PROFESSOR DASHBOARD ===
    elif st.session_state.role == "Professor":
        creds = load_data('credentials.json')
        my_prof = creds.get(st.session_state.username, {})
        my_depts, my_subs = my_prof.get("departments", ["General"]), my_prof.get("subjects", ["General"])
        
        is_school = (st.session_state.inst_type == "School")
        lbl_grp = "Class" if is_school else "Department"

        if st.session_state.prof_dept is None:
            st.header(f"🏠 Welcome, {st.session_state.username}")
            st.write(f"Select a {lbl_grp}:")
            for d in my_depts:
                if st.button(f"📁 {d}", use_container_width=True): st.session_state.prof_dept = d; st.rerun()
                
        elif st.session_state.prof_subject is None:
            st.header(f"📁 {st.session_state.prof_dept}")
            if st.button(f"⬅️ Back to {lbl_grp}es"): st.session_state.prof_dept = None; st.rerun()
            st.markdown("---")
            st.write("Select a Subject:")
            for s in my_subs:
                if st.button(f"📘 {s}", use_container_width=True): st.session_state.prof_subject = s; st.rerun()
                
        elif st.session_state.prof_test is None:
            st.header(f"📘 {st.session_state.prof_subject} (Tests & Quizzes)")
            if st.button("⬅️ Back to Subjects"): st.session_state.prof_subject = None; st.rerun()
            st.markdown("---")
            
            qs = load_data('questions.json')
            existing_tests = sorted(list(set([
                q.get("test_name") for q in qs 
                if isinstance(q, dict) and q.get("professor") == st.session_state.username 
                and q.get("department") == st.session_state.prof_dept and q.get("subject") == st.session_state.prof_subject and q.get("test_name")
            ])))
            
            st.subheader("Manage Existing Tests")
            if not existing_tests: st.info("No tests created for this subject yet.")
            for t in existing_tests:
                if st.button(f"📝 {t}", use_container_width=True): st.session_state.prof_test = t; st.rerun()
                    
            st.markdown("---")
            with st.form("new_test_form", clear_on_submit=True):
                st.subheader("Create a New Test")
                new_t = st.text_input("Enter Test Name (e.g., Chapter 1 Quiz)")
                timer_enabled = st.checkbox("Enable Time Limit for this Test", value=True)
                t_limit = st.number_input("Time Limit (in Minutes)", min_value=1, max_value=180, value=15, disabled=not timer_enabled)
                if st.form_submit_button("Create & Manage Test"):
                    if new_t: 
                        tests_db = load_data('tests.json')
                        t_key = f"{st.session_state.institution}_{st.session_state.prof_dept}_{st.session_state.prof_subject}_{new_t.strip()}"
                        # --- SAVING DATE CREATED ---
                        tests_db[t_key] = {"time_limit": t_limit, "timer_enabled": timer_enabled, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                        save_data('tests.json', tests_db)
                        st.session_state.prof_test = new_t.strip(); st.rerun()
                    else: st.warning("Please enter a name for the new test.")
                    
        else:
            col1, col2 = st.columns([3, 1])
            with col1: st.header(f"📝 {st.session_state.prof_test}")
            with col2:
                if st.button("⬅️ Change Test"): st.session_state.prof_test = None; st.rerun()
                if st.button("🏠 Home Menu"): st.session_state.update({'prof_dept': None, 'prof_subject': None, 'prof_test': None}); st.rerun()
            
            tab1, tab2, tab3 = st.tabs(["Add Question", "Bank", "Scores & Reports"])
            with tab1:
                with st.form("add_q", clear_on_submit=True):
                    q_txt = st.text_area("Question Text")
                    c1, c2 = st.columns(2)
                    oa = c1.text_input("A"); oc = c1.text_input("C"); ob = c2.text_input("B"); od = c2.text_input("D")
                    ans = st.selectbox("Correct Answer", ["A", "B", "C", "D"])
                    if st.form_submit_button("Save Question"):
                        if q_txt and oa and ob and oc and od:
                            qs = load_data('questions.json')
                            qs.append({"professor": st.session_state.username, "institution": st.session_state.institution, "department": st.session_state.prof_dept, "subject": st.session_state.prof_subject, "test_name": st.session_state.prof_test, "question": q_txt, "A": oa, "B": ob, "C": oc, "D": od, "answer": ans})
                            save_data('questions.json', qs); st.success("✅ Saved!")
                        else: st.error("Please fill out all fields.")
                
                st.markdown("---")
                if st.button("🏁 Finish Adding Questions & Return Home", type="primary", use_container_width=True):
                    st.session_state.update({'prof_dept': None, 'prof_subject': None, 'prof_test': None}); st.rerun()

            with tab2:
                qs = load_data('questions.json')
                my_qs = [q for q in qs if isinstance(q, dict) and q.get("professor") == st.session_state.username and q.get("department") == st.session_state.prof_dept and q.get("subject") == st.session_state.prof_subject and q.get("test_name") == st.session_state.prof_test]
                for i, q in enumerate(my_qs):
                    with st.expander(f"Q{i+1}: {q.get('question', '')[:50]}..."):
                        st.write(f"**A:** {q.get('A')} | **B:** {q.get('B')} | **C:** {q.get('C')} | **D:** {q.get('D')}")
                        st.success(f"Ans: {q.get('answer')}")
                        if st.button("Delete Question", key=f"del_{i}"): qs.remove(q); save_data('questions.json', qs); st.rerun()
            
            with tab3:
                scores = load_data('scores.json')
                f_scores_dict = {k: v for k, v in scores.items() if isinstance(v, dict) and v.get("department") == st.session_state.prof_dept and v.get("subject") == st.session_state.prof_subject and v.get("test_name") == st.session_state.prof_test}
                reqs = {k: v for k, v in f_scores_dict.items() if v.get("retake_status") == "requested"}
                if reqs:
                    st.error("🚨 Pending Retake Requests")
                    for k, v in reqs.items():
                        c1, c2 = st.columns([3, 1])
                        with c1: st.write(f"**{v.get('student')}** wants to retake. (Previous Score: {v.get('percentage')}%)")
                        with c2: 
                            if st.button("Approve Retake", key=f"app_ret_{k}"): scores[k]["retake_status"] = "approved"; save_data('scores.json', scores); st.rerun()
                    st.markdown("---")

                if not f_scores_dict: st.info("No scores yet.")
                else:
                    ranked_scores = sorted(list(f_scores_dict.values()), key=lambda x: (-x.get('score', 0), x.get('total_time_taken_seconds', 999999)))
                    st.subheader("🏆 Class Rankings & Reports")
                    
                    full_csv = "Rank,Student Name,Score,Total,Percentage%,Total Time Taken,Total Attempts\n"
                    for rank, s in enumerate(ranked_scores, 1):
                        attempts = len(s.get('past_attempts', [])) + 1
                        full_csv += f"{rank},{s.get('student')},{s.get('score')},{s.get('total')},{s.get('percentage')},{s.get('total_time_taken_str', 'N/A')},{attempts}\n"
                    
                    st.download_button(label="📥 Download Full Class Report (CSV)", data=full_csv, file_name=f"{st.session_state.prof_test}_Full_Report.csv", mime="text/csv", type="primary")
                    st.markdown("---")
                    
                    for rank, s in enumerate(ranked_scores, 1):
                        c1, c2 = st.columns([3, 1])
                        with c1: st.write(f"**#{rank} {s.get('student')}** | Score: {s.get('score')}/{s.get('total')} ({s.get('percentage')}%) | ⏱️ {s.get('total_time_taken_str', 'N/A')}")
                        with c2:
                            ind_csv = "Attempt,Q Number,Time on Question,Question Text,Student Answer,Correct Answer,Status\n"
                            for attempt_idx, past in enumerate(s.get('past_attempts', [])):
                                for idx, d in enumerate(past.get('details', []), 1):
                                    status = "Correct" if d.get('student_answer') == d.get('correct_answer') else "Incorrect"
                                    clean_q = str(d.get('question')).replace('"', '""')
                                    ind_csv += f"Attempt {attempt_idx+1},Q{idx},{d.get('time_spent_str', 'N/A')},\"{clean_q}\",{d.get('student_answer', 'None')},{d.get('correct_answer')},{status}\n"
                            current_idx = len(s.get('past_attempts', [])) + 1
                            for idx, d in enumerate(s.get('details', []), 1):
                                status = "Correct" if d.get('student_answer') == d.get('correct_answer') else "Incorrect"
                                clean_q = str(d.get('question')).replace('"', '""')
                                ind_csv += f"Attempt {current_idx},Q{idx},{d.get('time_spent_str', 'N/A')},\"{clean_q}\",{d.get('student_answer', 'None')},{d.get('correct_answer')},{status}\n"
                            safe_name = re.sub(r'[^A-Za-z0-9]', '_', s.get('student'))
                            st.download_button("📥 Individual Report", data=ind_csv, file_name=f"{safe_name}_{st.session_state.prof_test}.csv", key=f"dl_ind_{rank}")

    # === 4. NEW STUDENT DASHBOARD UI ===
    elif st.session_state.role == "Student":
        lbl_grp = "Class" if st.session_state.inst_type == "School" else "Department"
        lbl_sub = "Section" if st.session_state.inst_type == "School" else "Year"
        
        # Top Information Bar
        c_info, c_home = st.columns([4, 1])
        with c_info:
            st.write(f"🎓 **{st.session_state.institution}** | 👤 {st.session_state.student_name} | 📂 {lbl_grp}: {st.session_state.student_group}")
        with c_home:
            if st.session_state.student_view_subject is not None and st.session_state.active_test_key is None:
                if st.button("🏠 Home", use_container_width=True):
                    st.session_state.student_view_subject = None
                    st.session_state.student_view_test = None
                    st.rerun()
        st.markdown("---")
        
        qs = load_data('questions.json')
        dept_qs = [q for q in qs if isinstance(q, dict) and q.get("institution") == st.session_state.institution and q.get("department") == st.session_state.student_group]
        
        if not dept_qs: 
            st.info(f"No classes or tests are currently available for your {lbl_grp}.")
        else:
            # --- DASHBOARD STATE 1: SUBJECT GRID ---
            if st.session_state.student_view_subject is None:
                st.subheader("📚 My Subjects")
                subs = sorted(list(set([q.get("subject", "General") for q in dept_qs])))
                
                cols = st.columns(3)
                for i, sub in enumerate(subs):
                    with cols[i % 3]:
                        st.markdown(f"""
                        <div style="border:1px solid #444; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 15px; background-color: #0e1117;">
                            <h3 style="margin-bottom:15px; color: white;">📘 {sub}</h3>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("Open Class", key=f"sub_btn_{sub}", use_container_width=True):
                            st.session_state.student_view_subject = sub
                            st.rerun()

            # --- DASHBOARD STATE 2: TEST TIMELINE ---
            elif st.session_state.student_view_test is None:
                st.subheader(f"📘 {st.session_state.student_view_subject} (Available Tests)")
                st.markdown("---")
                
                sub_qs = [q for q in dept_qs if q.get("subject") == st.session_state.student_view_subject]
                tests = list(set([q.get("test_name", "General Test") for q in sub_qs if q.get("test_name")]))
                
                tests_db = load_data('tests.json')
                test_info = []
                for t in tests:
                    t_key = f"{st.session_state.institution}_{st.session_state.student_group}_{st.session_state.student_view_subject}_{t}"
                    c_date = tests_db.get(t_key, {}).get("created_at", "2026-01-01 12:00:00")
                    test_info.append({"name": t, "date": c_date})
                
                test_info.sort(key=lambda x: x['date'], reverse=True)
                
                for t_item in test_info:
                    try: display_date = datetime.strptime(t_item['date'], "%Y-%m-%d %H:%M:%S").strftime("%B %d, %Y")
                    except: display_date = "Previous Session"
                    
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.write(f"📝 **{t_item['name']}**")
                        st.caption(f"📅 Conducted on: {display_date}")
                    with c2:
                        if st.button("Open Test", key=f"open_t_{t_item['name']}", use_container_width=True):
                            st.session_state.student_view_test = t_item['name']
                            st.rerun()
                    st.markdown("---")

            # --- DASHBOARD STATE 3: TEST EXECUTION ENGINE ---
            else:
                sel_sub = st.session_state.student_view_subject
                sel_test = st.session_state.student_view_test
                sel_dept = st.session_state.student_group
                
                if st.session_state.active_test_key is None:
                    if st.button("⬅️ Back to Test List"):
                        st.session_state.student_view_test = None
                        st.rerun()
                        
                sub_qs = [q for q in dept_qs if q.get("subject") == sel_sub]
                final_qs = [q for q in sub_qs if q.get("test_name") == sel_test]
                
                if not final_qs: st.warning("No questions here.")
                else:
                    score_key = f"{st.session_state.institution}_{st.session_state.username}_{sel_dept}_{sel_sub}_{sel_test}"
                    scores = load_data('scores.json')
                    tests_db = load_data('tests.json')
                    t_key = f"{st.session_state.institution}_{sel_dept}_{sel_sub}_{sel_test}"
                    t_enabled = tests_db.get(t_key, {}).get("timer_enabled", True)
                    t_limit = tests_db.get(t_key, {}).get("time_limit", 15)
                    
                    score_exists = score_key in scores
                    retake_status = scores[score_key].get("retake_status", "none") if score_exists else "none"
                    
                    if score_exists and retake_status not in ["approved", "in_progress"]:
                        s_data = scores[score_key]
                        st.success("✅ Test Completed")
                        c1, c2 = st.columns(2)
                        c1.metric("Your Final Score", f"{s_data.get('score')}/{s_data.get('total')} ({s_data.get('percentage')}%)")
                        c2.metric("⏱️ Total Time Taken", s_data.get('total_time_taken_str', 'N/A'))
                        
                        with st.expander("📝 View Test Review", expanded=True):
                            for i, d in enumerate(s_data.get("details", [])):
                                st.write(f"**Q{i+1}: {d['question']}** *(Time spent: {d.get('time_spent_str', 'N/A')})*")
                                if d.get('student_answer') == d.get('correct_answer') and d.get('student_answer') is not None:
                                    st.success(f"✅ Your Answer: {d['student_answer']}) {d['options'].get(d['student_answer'])}")
                                else:
                                    st.error(f"❌ Your Answer: {d.get('student_answer', 'Blank')}")
                                    st.info(f"💡 Correct: {d.get('correct_answer')}) {d['options'].get(d.get('correct_answer'))}")
                                st.markdown("---")

                        if retake_status == "requested": st.info("⏳ Retake pending approval.")
                        elif st.button("Request Retake"):
                            scores[score_key]["retake_status"] = "requested"; save_data('scores.json', scores); st.rerun()
                            
                    elif score_exists and retake_status == "approved":
                        st.success("🎉 Retake approved!")
                        if st.button("Start Retake Now", type="primary"):
                            if 'past_attempts' not in scores[score_key]: scores[score_key]['past_attempts'] = []
                            archive = {k: v for k, v in scores[score_key].items() if k != 'past_attempts'}
                            scores[score_key]['past_attempts'].append(archive)
                            scores[score_key]['retake_status'] = "in_progress"
                            save_data('scores.json', scores); clear_test_state(); st.rerun()
                    else:
                        if st.session_state.active_test_key != score_key:
                            st.subheader(sel_test)
                            if t_enabled: st.info(f"⏱️ **Time Limit:** {t_limit} Minutes.")
                            else: st.info("⏱️ **No Time Limit** for this test.")
                            
                            if st.button("Start Test", type="primary"):
                                st.session_state.update({
                                    'active_test_key': score_key, 'test_start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'last_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'shuffled_qs': random.sample(final_qs, len(final_qs)),
                                    'current_q': 0, 's_answers': {}, 'q_times': {i: 0 for i in range(len(final_qs))}
                                })
                                st.rerun()
                        else:
                            start_dt = datetime.strptime(st.session_state.test_start_time, "%Y-%m-%d %H:%M:%S")
                            end_dt = start_dt + timedelta(minutes=t_limit)
                            now = datetime.now()
                            
                            if t_enabled and now > end_dt + timedelta(seconds=10):
                                st.error("❌ Time expired! Auto-submitting current answers.")
                                sqs = st.session_state.shuffled_qs
                                score = sum([1 for i, q in enumerate(sqs) if st.session_state.s_answers.get(i) == q.get('answer')])
                                
                                details = []
                                total_time_sec = 0
                                for i, q in enumerate(sqs):
                                    t_sec = st.session_state.q_times.get(i, 0)
                                    total_time_sec += t_sec
                                    m, s = divmod(int(t_sec), 60)
                                    details.append({"question": q.get('question'), "options": {"A": q.get('A'), "B": q.get('B'), "C": q.get('C'), "D": q.get('D')}, "student_answer": st.session_state.s_answers.get(i), "correct_answer": q.get('answer'), "time_spent_str": f"{m}m {s}s"})
                                
                                tot_m, tot_s = divmod(int(total_time_sec), 60)
                                scores = load_data('scores.json')
                                past_attempts = scores.get(score_key, {}).get("past_attempts", [])
                                scores[score_key] = {"student": st.session_state.username, "institution": st.session_state.institution, "department": sel_dept, "subject": sel_sub, "test_name": sel_test, "score": score, "total": len(sqs), "percentage": round((score/len(sqs))*100, 2), "retake_status": "none", "details": details, "total_time_taken_seconds": total_time_sec, "total_time_taken_str": f"{tot_m}m {tot_s}s (Time Expired)", "past_attempts": past_attempts}
                                save_data('scores.json', scores); clear_test_state(); st.rerun()

                            else:
                                if t_enabled: st.warning(f"⏳ **Submit before:** {end_dt.strftime('%I:%M %p')}")
                                else: st.success("🟢 Test in progress. Take your time.")
                                
                                sqs = st.session_state.shuffled_qs
                                idx = st.session_state.current_q
                                current_q = sqs[idx]
                                
                                st.progress((idx) / len(sqs))
                                st.write(f"**Question {idx + 1} of {len(sqs)}**")
                                st.markdown("---")
                                st.subheader(current_q.get('question'))
                                opts = [f"A) {current_q.get('A')}", f"B) {current_q.get('B')}", f"C) {current_q.get('C')}", f"D) {current_q.get('D')}"]
                                
                                existing_ans = st.session_state.s_answers.get(idx)
                                ans_idx = None
                                if existing_ans:
                                    for opt_i, opt_val in enumerate(opts):
                                        if opt_val.startswith(existing_ans): ans_idx = opt_i
                                        
                                choice = st.radio("Select Answer:", opts, index=ans_idx, key=f"radio_{idx}")
                                selected_letter = choice[0] if choice else None
                                
                                st.markdown("---")
                                st.info("⚠️ **Security Lock:** Once you move to the next question, your answer is locked and you cannot return.")
                                
                                def update_time_and_save():
                                    current_now = datetime.now()
                                    last_t = datetime.strptime(st.session_state.last_time, "%Y-%m-%d %H:%M:%S")
                                    st.session_state.q_times[idx] += (current_now - last_t).total_seconds()
                                    st.session_state.last_time = current_now.strftime("%Y-%m-%d %H:%M:%S")
                                    st.session_state.s_answers[idx] = selected_letter

                                if idx < len(sqs) - 1:
                                    if st.button("Lock Answer & Next ➡️", type="primary"):
                                        update_time_and_save()
                                        st.session_state.current_q += 1
                                        st.rerun()
                                else:
                                    if st.button("✅ Lock Answer & Submit Test", type="primary"):
                                        update_time_and_save()
                                        score = sum([1 for i, q in enumerate(sqs) if st.session_state.s_answers.get(i) == q.get('answer')])
                                        
                                        details = []
                                        total_time_sec = 0
                                        for i, q in enumerate(sqs):
                                            t_sec = st.session_state.q_times.get(i, 0)
                                            total_time_sec += t_sec
                                            m, s = divmod(int(t_sec), 60)
                                            details.append({"question": q.get('question'), "options": {"A": q.get('A'), "B": q.get('B'), "C": q.get('C'), "D": q.get('D')}, "student_answer": st.session_state.s_answers.get(i), "correct_answer": q.get('answer'), "time_spent_str": f"{m}m {s}s"})
                                        
                                        tot_m, tot_s = divmod(int(total_time_sec), 60)
                                        scores = load_data('scores.json')
                                        past_attempts = scores.get(score_key, {}).get("past_attempts", [])
                                        scores[score_key] = {"student": st.session_state.username, "institution": st.session_state.institution, "department": sel_dept, "subject": sel_sub, "test_name": sel_test, "score": score, "total": len(sqs), "percentage": round((score/len(sqs))*100, 2), "retake_status": "none", "details": details, "total_time_taken_seconds": total_time_sec, "total_time_taken_str": f"{tot_m}m {tot_s}s", "past_attempts": past_attempts}
                                        save_data('scores.json', scores); clear_test_state(); st.rerun()
