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
if 'prof_test' not in st.session_state: st.session_state.prof_test = None

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
                                         'institution': creds[prof_id].get("institution", ""), 'prof_dept': None, 'prof_subject': None, 'prof_test': None})
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

    st.markdown("---")
    with st.expander("Register a School/College/University"):
        st.write("Submit your institution for approval to use the platform.")
        with st.form("inst_reg_form", clear_on_submit=True):
            inst_name = st.text_input("Full Institute Name")
            contact_name = st.text_input("Your Name (Admin Contact)")
            inst_email = st.text_input("Email Address")
            inst_phone = st.text_input("Phone Number")
            inst_pass = st.text_input("Set Institution Admin Password", type="password")
            
            if st.form_submit_button("Submit Registration Request"):
                if inst_name and contact_name and inst_email and inst_pass:
                    generated_id = re.sub(r'[^A-Z0-9]', '_', inst_name.upper())
                    insts = load_data('institutions.json')
                    if generated_id in insts:
                        st.error(f"An institution with a similar name ({generated_id}) is already registered.")
                    else:
                        insts[generated_id] = {
                            "institute_name": inst_name, "contact": contact_name, "email": inst_email,
                            "phone": inst_phone, "password": inst_pass, "status": "pending"
                        }
                        save_data('institutions.json', insts)
                        st.success(f"✅ Registration Submitted! Please save your Admin ID: **{generated_id}**")
                else:
                    st.warning("Please fill in all required fields.")

# --- DASHBOARDS ---
if st.session_state.logged_in:
    col_a, col_b = st.columns([4, 1])
    with col_a: st.success(f"User: {st.session_state.username} | Role: {st.session_state.role} | Inst: {st.session_state.institution}")
    with col_b: 
        if st.button("Log Out"):
            for key in ['logged_in', 'role', 'username', 'institution', 'prof_dept', 'prof_subject', 'prof_test']: 
                st.session_state[key] = None
            st.rerun()
            
    st.markdown("---")
    
    # === 1. SUPER ADMIN DASHBOARD ===
    if st.session_state.role == "SuperAdmin":
        st.header("👑 Platform Administrator Dashboard")
        sa_tab1, sa_tab2, sa_tab3 = st.tabs(["Pending Registrations", "Manage Active Institutions", "Institution Deletion Requests"])
        insts = load_data('institutions.json')
        
        with sa_tab1:
            pending = {k: v for k, v in insts.items() if isinstance(v, dict) and v.get("status") == "pending"}
            if not pending: st.info("No pending registrations.")
            else:
                for k, v in pending.items():
                    with st.expander(f"🏫 {v.get('institute_name', 'Unknown')} (ID: {k})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Approve", key=f"app_{k}"):
                                insts[k]["status"] = "approved"; save_data('institutions.json', insts); st.rerun()
                        with col2:
                            if st.button("Reject & Delete", key=f"rej_{k}"):
                                del insts[k]; save_data('institutions.json', insts); st.rerun()
                                
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
                        if st.button("Force Remove", key=f"force_del_{k}"):
                            del insts[k]; save_data('institutions.json', insts); st.rerun()
                            
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

    # === 2. INSTITUTION ADMIN DASHBOARD ===
    elif st.session_state.role == "Admin":
        insts = load_data('institutions.json')
        my_inst = insts.get(st.session_state.institution, {})
        
        if my_inst.get("status") == "scheduled_for_deletion":
            st.error("🚨 ACCOUNT SCHEDULED FOR DELETION 🚨")
            if st.button("Cancel Deletion Request & Recover Account", type="primary"):
                insts[st.session_state.institution]["status"] = "approved"
                if "deletion_date" in insts[st.session_state.institution]: del insts[st.session_state.institution]["deletion_date"]
                save_data('institutions.json', insts); st.rerun()
        else:
            st.header(f"🛡️ {st.session_state.institution} Admin Dashboard")
            admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Manage Existing Professors", "Register New Professor", "Account Settings"])
            
            with admin_tab1:
                creds = load_data('credentials.json')
                inst_profs = {p: data for p, data in creds.items() if isinstance(data, dict) and data.get("institution") == st.session_state.institution}
                if not inst_profs: st.info("You haven't registered any professors yet.")
                else:
                    for prof, data in inst_profs.items():
                        with st.expander(f"👨‍🏫 {prof}"):
                            upd_depts = st.text_input("Departments", value=", ".join(data.get('departments', [])), key=f"upd_dept_{prof}")
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
                    new_prof_id = st.text_input("New Professor ID (Name)")
                    new_prof_pass = st.text_input("Assign Passcode", type="password")
                    st.info("Separate multiple entries with commas (e.g. Computer Science, Mechanical)")
                    new_depts = st.text_input("Assigned Departments")
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
                                save_data('credentials.json', creds)
                                st.success(f"✅ Professor '{new_prof_id}' added successfully!")
                        else: st.warning("Please fill out all fields.")
                        
            with admin_tab3:
                st.subheader("Institution Account Deletion")
                with st.form("del_req_form", clear_on_submit=True):
                    st.warning("⚠️ DISCLAIMER: Your account will be scheduled for permanent deletion inside a 3-day window once approved by the Platform Administrator. You can undo this request anytime within the due date by logging back into this Admin portal and clicking Recover Account.")
                    confirm_del = st.checkbox("I have read the disclaimer and confirm my deletion request.")
                    
                    if st.form_submit_button("Submit Deletion Request", type="primary"):
                        if confirm_del:
                            reqs = load_data('deletion_requests.json')
                            if not isinstance(reqs, list): reqs = []
                            if not any(r.get('username') == st.session_state.institution and r.get('role') == "Admin" for r in reqs):
                                reqs.append({"username": st.session_state.institution, "role": "Admin", "institution": st.session_state.institution})
                                save_data('deletion_requests.json', reqs)
                                st.success("✅ Request sent to Platform Administrator.")
                        else: st.error("Please check the confirmation box to proceed.")

    # === 3. PROFESSOR DASHBOARD ===
    elif st.session_state.role == "Professor":
        creds = load_data('credentials.json')
        my_prof = creds.get(st.session_state.username, {})
        my_depts, my_subs = my_prof.get("departments", ["General"]), my_prof.get("subjects", ["General"])

        if st.session_state.prof_dept is None:
            st.header(f"🏠 Welcome, Professor {st.session_state.username}")
            st.write("Select a Department:")
            for d in my_depts:
                if st.button(f"📁 {d}", use_container_width=True): st.session_state.prof_dept = d; st.rerun()
                
        elif st.session_state.prof_subject is None:
            st.header(f"📁 {st.session_state.prof_dept}")
            if st.button("⬅️ Back to Departments"): st.session_state.prof_dept = None; st.rerun()
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
                if st.form_submit_button("Create & Manage Test"):
                    if new_t: st.session_state.prof_test = new_t.strip(); st.rerun()
                    else: st.warning("Please enter a name for the new test.")
                    
        else:
            col1, col2 = st.columns([3, 1])
            with col1: st.header(f"📝 {st.session_state.prof_test}")
            with col2:
                if st.button("⬅️ Change Test"): st.session_state.prof_test = None; st.rerun()
                if st.button("🏠 Home Menu"): 
                    st.session_state.prof_dept = None
                    st.session_state.prof_subject = None
                    st.session_state.prof_test = None
                    st.rerun()
            
            tab1, tab2, tab3 = st.tabs(["Add Question", "Bank", "Scores & Retakes"])
            with tab1:
                with st.form("add_q", clear_on_submit=True):
                    q_txt = st.text_area("Question Text")
                    c1, c2 = st.columns(2)
                    oa = c1.text_input("A"); oc = c1.text_input("C"); ob = c2.text_input("B"); od = c2.text_input("D")
                    ans = st.selectbox("Correct Answer", ["A", "B", "C", "D"])
                    if st.form_submit_button("Save Question"):
                        if q_txt and oa and ob and oc and od:
                            qs = load_data('questions.json')
                            qs.append({
                                "professor": st.session_state.username, "institution": st.session_state.institution, 
                                "department": st.session_state.prof_dept, "subject": st.session_state.prof_subject, 
                                "test_name": st.session_state.prof_test,
                                "question": q_txt, "A": oa, "B": ob, "C": oc, "D": od, "answer": ans
                            })
                            save_data('questions.json', qs); st.success("✅ Saved! Form cleared.")
                        else: st.error("Please fill out all fields.")
            with tab2:
                qs = load_data('questions.json')
                my_qs = [
                    q for q in qs if isinstance(q, dict) and q.get("professor") == st.session_state.username 
                    and q.get("department") == st.session_state.prof_dept and q.get("subject") == st.session_state.prof_subject and q.get("test_name") == st.session_state.prof_test
                ]
                
                if not my_qs: st.info("No questions in this test bank yet.")
                for i, q in enumerate(my_qs):
                    with st.expander(q.get("question", "")[:50]):
                        st.write(f"**A:** {q.get('A')} | **B:** {q.get('B')} | **C:** {q.get('C')} | **D:** {q.get('D')}")
                        st.success(f"Ans: {q.get('answer')}")
                        if st.button("Delete Question", key=f"del_{i}"): qs.remove(q); save_data('questions.json', qs); st.rerun()
            
            with tab3:
                scores = load_data('scores.json')
                f_scores = {
                    k: v for k, v in scores.items() if isinstance(v, dict) and v.get("department") == st.session_state.prof_dept 
                    and v.get("subject") == st.session_state.prof_subject and v.get("test_name") == st.session_state.prof_test
                }
                
                reqs = {k: v for k, v in f_scores.items() if v.get("retake_status") == "requested"}
                if reqs:
                    st.error("🚨 Pending Retake Requests")
                    for k, v in reqs.items():
                        c1, c2 = st.columns([3, 1])
                        with c1: st.write(f"**{v.get('student')}** wants to retake. (Previous Score: {v.get('percentage')}%)")
                        with c2: 
                            if st.button("Approve Retake", key=f"app_ret_{k}"):
                                scores[k]["retake_status"] = "approved"; save_data('scores.json', scores); st.rerun()
                    st.markdown("---")

                if not f_scores: st.info("No scores yet.")
                else:
                    for k, s in f_scores.items(): st.write(f"**{s.get('student')}**: {s.get('score')}/{s.get('total')} ({s.get('percentage')}%)")

    # === 4. STUDENT TEST PORTAL ===
    elif st.session_state.role == "Student":
        st.header(f"🎓 {st.session_state.institution} Portal")
        qs = load_data('questions.json')
        inst_qs = [q for q in qs if isinstance(q, dict) and q.get("institution") == st.session_state.institution]
        
        if not inst_qs: st.info("No questions available.")
        else:
            depts = sorted(list(set([q.get("department", "General") for q in inst_qs])))
            sel_dept = st.selectbox("1. Select Department:", depts)
            dept_qs = [q for q in inst_qs if q.get("department") == sel_dept]
            
            subs = sorted(list(set([q.get("subject", "General") for q in dept_qs])))
            sel_sub = st.selectbox("2. Select Subject:", subs)
            sub_qs = [q for q in dept_qs if q.get("subject") == sel_sub]
            
            tests = sorted(list(set([q.get("test_name", "General Test") for q in sub_qs if q.get("test_name")])))
            sel_test = st.selectbox("3. Select Test:", tests)
            
            final_qs = [q for q in sub_qs if q.get("test_name") == sel_test]
            
            if not final_qs: st.warning("No questions here.")
            else:
                score_key = f"{st.session_state.institution}_{st.session_state.username}_{sel_dept}_{sel_sub}_{sel_test}"
                scores = load_data('scores.json')
                
                if score_key in scores and scores[score_key].get("retake_status") != "approved":
                    s_data = scores[score_key]
                    st.success("✅ Test Completed")
                    st.metric("Your Final Score", f"{s_data.get('score')}/{s_data.get('total')} ({s_data.get('percentage')}%)")
                    
                    # --- NEW TEST REVIEW SECTION ---
                    with st.expander("📝 View Test Review", expanded=True):
                        st.subheader("Your Answers vs. Correct Answers")
                        for i, d in enumerate(s_data.get("details", [])):
                            st.write(f"**Q{i+1}: {d['question']}**")
                            
                            if not d.get('student_answer'):
                                st.error("❌ You did not answer this question.")
                                st.info(f"💡 Correct Answer: {d['correct_answer']}) {d['options'].get(d['correct_answer'])}")
                            elif d['student_answer'] == d['correct_answer']:
                                st.success(f"✅ Your Answer: {d['student_answer']}) {d['options'].get(d['student_answer'])} (Correct!)")
                            else:
                                st.error(f"❌ Your Answer: {d['student_answer']}) {d['options'].get(d['student_answer'])}")
                                st.info(f"💡 Correct Answer: {d['correct_answer']}) {d['options'].get(d['correct_answer'])}")
                            st.markdown("---")

                    status = s_data.get("retake_status", "none")
                    if status == "requested":
                        st.info("⏳ Your request to retake this test is pending professor approval.")
                    else:
                        if st.button("Request Retake"):
                            scores[score_key]["retake_status"] = "requested"
                            save_data('scores.json', scores)
                            st.rerun()
                            
                elif score_key in scores and scores[score_key].get("retake_status") == "approved":
                    st.success("🎉 Your professor has approved your retake request!")
                    if st.button("Start Retake Now", type="primary"):
                        del scores[score_key] 
                        save_data('scores.json', scores)
                        st.rerun()
                        
                else:
                    st.write(f"Taking test: **{sel_test}**")
                    st.markdown("---")
                    with st.form("test_form"):
                        s_ans = {}
                        for i, q in enumerate(final_qs):
                            st.subheader(f"Q{i+1}: {q.get('question')}")
                            s_ans[i] = st.radio("Answer:", [f"A) {q.get('A')}", f"B) {q.get('B')}", f"C) {q.get('C')}", f"D) {q.get('D')}"], index=None, key=f"q_{i}")
                        if st.form_submit_button("Submit Test"):
                            score = 0
                            details = []
                            for i, q in enumerate(final_qs):
                                ans_full = s_ans[i]
                                ans_letter = ans_full[0] if ans_full else None
                                if ans_letter == q.get('answer'): 
                                    score += 1
                                # Capturing snapshot for the review
                                details.append({
                                    "question": q.get('question'),
                                    "options": {"A": q.get('A'), "B": q.get('B'), "C": q.get('C'), "D": q.get('D')},
                                    "student_answer": ans_letter,
                                    "correct_answer": q.get('answer')
                                })
                                
                            scores = load_data('scores.json')
                            scores[score_key] = {
                                "student": st.session_state.username, "institution": st.session_state.institution,
                                "department": sel_dept, "subject": sel_sub, "test_name": sel_test,
                                "score": score, "total": len(final_qs),
                                "percentage": round((score/len(final_qs))*100, 2), "retake_status": "none",
                                "details": details # Saves the review snapshot
                            }
                            save_data('scores.json', scores); st.rerun()
