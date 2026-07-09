import streamlit as st
import json
import os
import re
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
        
    if changed:
        save_data('institutions.json', insts); save_data('credentials.json', creds)
        save_data('questions.json', qs); save_data('scores.json', scores)

# --- SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'role' not in st.session_state: st.session_state.role = None
if 'username' not in st.session_state: st.session_state.username = ""
if 'institution' not in st.session_state: st.session_state.institution = ""
if 'test_submitted' not in st.session_state: st.session_state.test_submitted = False
if 'student_score' not in st.session_state: st.session_state.student_score = 0
if 'test_total' not in st.session_state: st.session_state.test_total = 0
if 'prof_dept' not in st.session_state: st.session_state.prof_dept = None
if 'prof_subject' not in st.session_state: st.session_state.prof_subject = None

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
            creds = load_data('credentials.json')
            if prof_id in creds and isinstance(creds[prof_id], dict) and creds[prof_id].get("passcode") == passcode:
                st.session_state.update({'logged_in': True, 'role': 'Professor', 'username': prof_id, 
                                         'institution': creds[prof_id].get("institution", ""), 'prof_dept': None, 'prof_subject': None})
                st.rerun()
            else: st.error("Invalid credentials.")

    elif portal == "Student":
        insts = load_data('institutions.json')
        approved = [k for k, v in insts.items() if isinstance(v, dict) and v.get("status") == "approved"]
        if not approved: st.warning("No institutions active.")
        else:
            student_inst = st.selectbox("Select Institution", approved)
            student_name = st.text_input("Enter your full name:")
            if st.button("Student Login") and student_name:
                st.session_state.update({'logged_in': True, 'role': 'Student', 'username': student_name, 'institution': student_inst})
                st.rerun()
                
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
                    st.session_state.update({'logged_in': True, 'role': 'Admin', 'username': admin_id, 'institution': admin_id})
                    st.rerun()
                else: st.error("Access Denied.")

# --- DASHBOARDS ---
if st.session_state.logged_in:
    col_a, col_b = st.columns([4, 1])
    with col_a: st.success(f"User: {st.session_state.username} | Role: {st.session_state.role} | Inst: {st.session_state.institution}")
    with col_b: 
        if st.button("Log Out"):
            for key in ['logged_in', 'role', 'username', 'institution', 'prof_dept', 'prof_subject']: st.session_state[key] = None
            st.rerun()
            
    st.markdown("---")
    
    # === PROFESSOR DASHBOARD (Simplified) ===
    if st.session_state.role == "Professor":
        creds = load_data('credentials.json')
        my_prof = creds.get(st.session_state.username, {})
        my_depts, my_subs = my_prof.get("departments", ["General"]), my_prof.get("subjects", ["General"])

        if st.session_state.prof_dept is None:
            for d in my_depts:
                if st.button(f"📁 {d}", use_container_width=True): st.session_state.prof_dept = d; st.rerun()
        elif st.session_state.prof_subject is None:
            if st.button("⬅️ Back"): st.session_state.prof_dept = None; st.rerun()
            for s in my_subs:
                if st.button(f"📘 {s}", use_container_width=True): st.session_state.prof_subject = s; st.rerun()
        else:
            if st.button("🏠 Home Menu"): st.session_state.prof_dept = None; st.session_state.prof_subject = None; st.rerun()
            tab1, tab2, tab3 = st.tabs(["Add Question", "Bank", "Scores"])
            with tab1:
                with st.form("add_q", clear_on_submit=True):
                    q_txt = st.text_area("Question"); c1, c2 = st.columns(2)
                    oa = c1.text_input("A"); oc = c1.text_input("C"); ob = c2.text_input("B"); od = c2.text_input("D")
                    ans = st.selectbox("Correct", ["A", "B", "C", "D"])
                    if st.form_submit_button("Save"):
                        qs = load_data('questions.json')
                        qs.append({"professor": st.session_state.username, "institution": st.session_state.institution, 
                                   "department": st.session_state.prof_dept, "subject": st.session_state.prof_subject, 
                                   "question": q_txt, "A": oa, "B": ob, "C": oc, "D": od, "answer": ans})
                        save_data('questions.json', qs); st.success("Saved!")
            with tab2:
                qs = load_data('questions.json')
                my_qs = [q for q in qs if isinstance(q, dict) and q.get("professor") == st.session_state.username and q.get("department") == st.session_state.prof_dept and q.get("subject") == st.session_state.prof_subject]
                for i, q in enumerate(my_qs):
                    with st.expander(q.get("question", "")[:30]):
                        st.write(f"A:{q.get('A')}, B:{q.get('B')}, C:{q.get('C')}, D:{q.get('D')}"); st.success(f"Ans: {q.get('answer')}")
            with tab3:
                scores = load_data('scores.json')
                f_scores = [v for v in scores.values() if isinstance(v, dict) and v.get("department") == st.session_state.prof_dept and v.get("subject") == st.session_state.prof_subject]
                for s in f_scores: st.write(f"**{s.get('student')}**: {s.get('percentage')}%")
