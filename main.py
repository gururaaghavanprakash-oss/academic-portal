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
    'active_test_key': None, 'test_start_time': None, 'shuffled_qs': [], 'current_q': 0, 
    's_answers': {}, 'q_times': {}, 'last_time': None
}
for key, val in keys_to_init.items():
    if key not in st.session_state: st.session_state[key] = val

process_expired_deletions()

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
                        if s_data.get("status", "active") == "graduated": st.error("Access Denied: Graduated.")
                        else:
                            i_type = insts.get(student_inst, {}).get("inst_type", "College")
                            st.session_state.update({'logged_in': True, 'role': 'Student', 'username': student_user, 'student_name': s_data.get("name", ""), 'institution': student_inst, 'student_group': s_data.get("group", ""), 'student_subgroup': s_data.get("subgroup", ""), 'inst_type': i_type})
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
                    # --- UPGRADED ADMIN VISIBILITY ---
                    with st.expander(f"🏫 {v.get('institute_name', 'Unknown')} (ID: {k}) - {v.get('inst_type', 'College')}"):
                        st.write(f"**Contact:** {v.get('contact')}")
                        st.write(f"**Email:** {v.get('email')}")
                        st.write(f"**Phone:** {v.get('phone')}")
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
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if v.get("status") == "scheduled_for_deletion": st.write(f"⚠️ **{v.get('institute_name')}** - *Pending Auto-Delete*")
                        else: st.write(f"**{v.get('institute_name')}** (Admin ID: {k})")
                    with col2:
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

    # === INSTITUTION ADMIN (Rest is same as previous phase to keep stable) ===
    elif st.session_state.role == "Admin":
        # ... [Admin code remains the same as Phase 28] ...
        pass 
    
    # === PROFESSOR & STUDENT (Same) ===
