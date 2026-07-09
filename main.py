import streamlit as st
import json
import os
import re
from datetime import datetime, timedelta

# --- DATABASE SETUP ---
FILES = ['credentials.json', 'questions.json', 'scores.json', 'institutions.json', 'deletion_requests.json']
for file in FILES:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            if file in ['questions.json', 'deletion_requests.json']:
                json.dump([], f)
            else:
                json.dump({}, f)

# --- HELPER FUNCTIONS ---
def load_data(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def process_expired_deletions():
    insts = load_data('institutions.json')
    creds = load_data('credentials.json')
    qs = load_data('questions.json')
    if not isinstance(qs, list): qs = []
    scores = load_data('scores.json')
    changed = False
    
    now = datetime.now()
    keys_to_delete = []
    
    for k, v in insts.items():
        if v.get("status") == "scheduled_for_deletion" and "deletion_date" in v:
            del_date = datetime.strptime(v["deletion_date"], "%Y-%m-%d %H:%M:%S")
            if now >= del_date:
                keys_to_delete.append(k)
    
    for k in keys_to_delete:
        changed = True
        del insts[k]
        creds = {p: data for p, data in creds.items() if not (isinstance(data, dict) and data.get("institution") == k)}
        qs = [q for q in qs if q.get("institution") != k]
        scores = {s: data for s, data in scores.items() if data.get("institution") != k}
        
    if changed:
        save_data('institutions.json', insts)
        save_data('credentials.json', creds)
        save_data('questions.json', qs)
        save_data('scores.json', scores)

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'institution' not in st.session_state:
    st.session_state.institution = ""
if 'test_submitted' not in st.session_state:
    st.session_state.test_submitted = False
if 'student_score' not in st.session_state:
    st.session_state.student_score = 0
if 'test_total' not in st.session_state:
    st.session_state.test_total = 0

process_expired_deletions()

# --- MAIN APP UI ---
st.title("⚙️ Academic Testing Portal")

if not st.session_state.logged_in:
    st.subheader("Welcome. Please select your portal:")
    portal = st.radio("Login as:", ["Student", "Professor", "Admin"])

    if portal == "Professor":
        st.info("Enter your assigned ID and passcode to log in.")
        prof_id = st.text_input("Professor ID")
        passcode = st.text_input("Passcode", type="password")
        
        if st.button("Professor Login"):
            if prof_id and passcode:
                creds = load_data('credentials.json')
                if prof_id in creds and isinstance(creds[prof_id], dict):
                    if creds[prof_id]["passcode"] == passcode:
                        st.session_state.logged_in = True
                        st.session_state.role = "Professor"
                        st.session_state.username = prof_id
                        st.session_state.institution = creds[prof_id]["institution"]
                        st.rerun()
                    else:
                        st.error("Incorrect passcode.")
                else:
                    st.error("Account not found. Please contact your Institution Administrator.")
            else:
                st.warning("Please enter both ID and passcode.")

    elif portal == "Student":
        insts = load_data('institutions.json')
        approved_insts = [k for k, v in insts.items() if v.get("status") == "approved"]
        
        if not approved_insts:
            st.warning("No institutions are currently active on the platform.")
        else:
            student_inst = st.selectbox("Select Your Institution", approved_insts)
            student_name = st.text_input("Enter your full name to begin:")
            if st.button("Student Login"):
                if student_name:
                    st.session_state.logged_in = True
                    st.session_state.role = "Student"
                    st.session_state.username = student_name
                    st.session_state.institution = student_inst
                    st.session_state.test_submitted = False
                    st.rerun()
                else:
                    st.warning("Please enter your name.")
                
    elif portal == "Admin":
        st.info("Administrative Access Portal")
        admin_id = st.text_input("Admin ID")
        admin_pass = st.text_input("Passcode", type="password")
        
        if st.button("Admin Login"):
            if admin_id == "ADMIN" and admin_pass == "ATP2026":
                st.session_state.logged_in = True
                st.session_state.role = "SuperAdmin"
                st.session_state.username = "Platform Administrator"
                st.rerun()
            else:
                insts = load_data('institutions.json')
                if admin_id in insts:
                    if insts[admin_id]["password"] == admin_pass:
                        if insts[admin_id]["status"] in ["approved", "scheduled_for_deletion"]:
                            st.session_state.logged_in = True
                            st.session_state.role = "Admin"
                            st.session_state.username = admin_id 
                            st.session_state.institution = admin_id
                            st.rerun()
                        else:
                            st.warning("Your institution's registration is still pending approval.")
                    else:
                        st.error("Incorrect password.")
                else:
                    st.error("Admin ID not found or account has been permanently deleted.")

    st.markdown("---")
    with st.expander("Register a School/College/University"):
        st.write("Submit your institution for approval to use the platform.")
        inst_name = st.text_input("Full Institute Name")
        contact_name = st.text_input("Your Name (Admin Contact)")
        inst_email = st.text_input("Email Address")
        inst_phone = st.text_input("Phone Number")
        inst_pass = st.text_input("Set Institution Admin Password", type="password")
        
        if st.button("Submit Registration Request"):
            if inst_name and contact_name and inst_email and inst_pass:
                generated_id = re.sub(r'[^A-Z0-9]', '_', inst_name.upper())
                insts = load_data('institutions.json')
                
                if generated_id in insts:
                    st.error(f"An institution with a similar name ({generated_id}) is already registered.")
                else:
                    insts[generated_id] = {
                        "institute_name": inst_name,
                        "contact": contact_name,
                        "email": inst_email,
                        "phone": inst_phone,
                        "password": inst_pass,
                        "status": "pending"
                    }
                    save_data('institutions.json', insts)
                    st.success(f"Registration Submitted! Please save your Admin ID: **{generated_id}**")
                    st.info("You will be able to log in once the Platform Administrator approves your request.")
            else:
                st.warning("Please fill in all required fields.")

# --- DASHBOARDS ---
if st.session_state.logged_in:
    col_a, col_b = st.columns([4, 1])
    with col_a:
        if st.session_state.role == "SuperAdmin":
            st.success(f"Logged in as: {st.session_state.username} (God Mode)")
        else:
            st.success(f"Logged in as: {st.session_state.username} | Role: {st.session_state.role} | Inst: {st.session_state.institution}")
    with col_b:
        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.username = ""
            st.session_state.institution = ""
            st.rerun()
            
    st.markdown("---")
    
    # === 1. SUPER ADMIN DASHBOARD ===
    if st.session_state.role == "SuperAdmin":
        st.header("👑 Platform Administrator Dashboard")
        
        sa_tab1, sa_tab2, sa_tab3 = st.tabs(["Pending Registrations", "Manage Active Institutions", "Institution Deletion Requests"])
        insts = load_data('institutions.json')
        
        with sa_tab1:
            pending = {k: v for k, v in insts.items() if v.get("status") == "pending"}
            if not pending:
                st.info("No pending registrations.")
            else:
                for k, v in pending.items():
                    with st.expander(f"🏫 {v['institute_name']} (ID: {k})"):
                        st.write(f"**Contact:** {v['contact']} | **Email:** {v['email']} | **Phone:** {v['phone']}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Approve", key=f"app_{k}"):
                                insts[k]["status"] = "approved"
                                save_data('institutions.json', insts)
                                st.rerun()
                        with col2:
                            if st.button("Reject & Delete", key=f"rej_{k}"):
                                del insts[k]
                                save_data('institutions.json', insts)
                                st.rerun()
                                
        with sa_tab2:
            approved = {k: v for k, v in insts.items() if v.get("status") in ["approved", "scheduled_for_deletion"]}
            if not approved:
                st.info("No approved institutions yet.")
            else:
                for k, v in approved.items():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if v.get("status") == "scheduled_for_deletion":
                            st.write(f"⚠️ **{v['institute_name']}** (Admin ID: {k}) - *Pending Auto-Delete on {v.get('deletion_date')}*")
                        else:
                            st.write(f"**{v['institute_name']}** (Admin ID: {k})")
                    with col2:
                        if st.button("Force Remove Immediately", key=f"force_del_{k}"):
                            del insts[k]
                            save_data('institutions.json', insts)
                            
                            creds = load_data('credentials.json')
                            for p in [p for p, data in creds.items() if isinstance(data, dict) and data.get("institution") == k]:
                                del creds[p]
                            save_data('credentials.json', creds)
                            
                            qs = load_data('questions.json')
                            if not isinstance(qs, list): qs = []
                            save_data('questions.json', [q for q in qs if q.get("institution") != k])
                            
                            scores = load_data('scores.json')
                            save_data('scores.json', {s: data for s, data in scores.items() if data.get("institution") != k})
                            st.rerun()
                            
        with sa_tab3:
            reqs = load_data('deletion_requests.json')
            if not isinstance(reqs, list): reqs = []
            
            admin_reqs = [r for r in reqs if r['role'] == "Admin"]
            if not admin_reqs:
                st.info("No institution deletion requests pending.")
            else:
                for r in admin_reqs:
                    inst_id = r['username']
                    st.warning(f"Institution **{inst_id}** has requested platform deletion.")
                    if st.button("Approve Request & Start 3-Day Countdown", key=f"wipe_{inst_id}"):
                        if inst_id in insts:
                            insts[inst_id]["status"] = "scheduled_for_deletion"
                            del_date = datetime.now() + timedelta(days=3)
                            insts[inst_id]["deletion_date"] = del_date.strftime("%Y-%m-%d %H:%M:%S")
                            save_data('institutions.json', insts)
                        
                        reqs.remove(r)
                        save_data('deletion_requests.json', reqs)
                        st.success(f"Countdown started for {inst_id}.")
                        st.rerun()

    # === 2. INSTITUTION ADMIN DASHBOARD ===
    elif st.session_state.role == "Admin":
        insts = load_data('institutions.json')
        my_inst = insts.get(st.session_state.institution)
        
        if my_inst and my_inst.get("status") == "scheduled_for_deletion":
            st.error("🚨 ACCOUNT SCHEDULED FOR DELETION 🚨")
            st.write(f"Your institution and all associated data is scheduled to be permanently deleted on **{my_inst.get('deletion_date')}**.")
            st.write("If you want to cancel the request and recover your account, click the button below.")
            
            if st.button("Cancel Deletion Request & Recover Account", type="primary"):
                insts[st.session_state.institution]["status"] = "approved"
                del insts[st.session_state.institution]["deletion_date"]
                save_data('institutions.json', insts)
                st.success("Deletion request cancelled successfully. Full access restored.")
                st.rerun()
        else:
            st.header(f"🛡️ {st.session_state.institution} Admin Dashboard")
            admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Manage Existing Professors", "Register New Professor", "Account Settings"])
            
            with admin_tab1:
                creds = load_data('credentials.json')
                inst_profs = {p: data for p, data in creds.items() if isinstance(data, dict) and data.get("institution") == st.session_state.institution}
                if not inst_profs:
                    st.info("You haven't registered any professors yet.")
                else:
                    for prof in list(inst_profs.keys()):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"👨‍🏫 **Professor ID:** {prof}")
                        with col2:
                            if st.button("Remove Account", key=f"del_prof_{prof}"):
                                del creds[prof]
                                save_data('credentials.json', creds)
                                questions = load_data('questions.json')
                                if not isinstance(questions, list): questions = []
                                save_data('questions.json', [q for q in questions
