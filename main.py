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
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'role' not in st.session_state: st.session_state.role = None
if 'username' not in st.session_state: st.session_state.username = ""
if 'institution' not in st.session_state: st.session_state.institution = ""
if 'test_submitted' not in st.session_state: st.session_state.test_submitted = False
if 'student_score' not in st.session_state: st.session_state.student_score = 0
if 'test_total' not in st.session_state: st.session_state.test_total = 0
# NEW: Professor Navigation State
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
            if prof_id and passcode:
                creds = load_data('credentials.json')
                if prof_id in creds and isinstance(creds[prof_id], dict):
                    if creds[prof_id]["passcode"] == passcode:
                        st.session_state.logged_in = True
                        st.session_state.role = "Professor"
                        st.session_state.username = prof_id
                        st.session_state.institution = creds[prof_id]["institution"]
                        # Reset nav on login
                        st.session_state.prof_dept = None
                        st.session_state.prof_subject = None
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
            st.session_state.prof_dept = None
            st.session_state.prof_subject = None
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
                            st.write(f"⚠️ **{v['institute_name']}** - *Pending Auto-Delete on {v.get('deletion_date')}*")
                        else:
                            st.write(f"**{v['institute_name']}** (Admin ID: {k})")
                    with col2:
                        if st.button("Force Remove", key=f"force_del_{k}"):
                            del insts[k]
                            save_data('institutions.json', insts)
                            st.rerun()
                            
        with sa_tab3:
            reqs = load_data('deletion_requests.json')
            if not isinstance(reqs, list): reqs = []
            admin_reqs = [r for r in reqs if r['role'] == "Admin"]
            if not admin_reqs:
                st.info("No institution deletion requests pending.")
            else:
                for r in admin_reqs:
                    if st.button(f"Approve Request for {r['username']}", key=f"wipe_{r['username']}"):
                        if r['username'] in insts:
                            insts[r['username']]["status"] = "scheduled_for_deletion"
                            insts[r['username']]["deletion_date"] = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
                            save_data('institutions.json', insts)
                        reqs.remove(r)
                        save_data('deletion_requests.json', reqs)
                        st.rerun()

    # === 2. INSTITUTION ADMIN DASHBOARD ===
    elif st.session_state.role == "Admin":
        insts = load_data('institutions.json')
        my_inst = insts.get(st.session_state.institution)
        
        if my_inst and my_inst.get("status") == "scheduled_for_deletion":
            st.error("🚨 ACCOUNT SCHEDULED FOR DELETION 🚨")
            if st.button("Cancel Deletion Request & Recover Account", type="primary"):
                insts[st.session_state.institution]["status"] = "approved"
                del insts[st.session_state.institution]["deletion_date"]
                save_data('institutions.json', insts)
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
                    for prof, data in inst_profs.items():
                        with st.expander(f"👨‍🏫 {prof}"):
                            st.write(f"**Departments:** {', '.join(data.get('departments', ['N/A']))}")
                            st.write(f"**Subjects:** {', '.join(data.get('subjects', ['N/A']))}")
                            if st.button("Remove Account", key=f"del_prof_{prof}"):
                                del creds[prof]
                                save_data('credentials.json', creds)
                                qs = load_data('questions.json')
                                save_data('questions.json', [q for q in qs if not (q.get("professor") == prof and q.get("institution") == st.session_state.institution)])
                                st.rerun()
                                
            with admin_tab2:
                # NEW: Admin sets up the Professor's Departments and Subjects here
                new_prof_id = st.text_input("New Professor ID (Name)")
                new_prof_pass = st.text_input("Assign Passcode", type="password")
                st.info("Separate multiple entries with commas (e.g. Computer Science, Mechanical)")
                new_depts = st.text_input("Assigned Departments")
                new_subs = st.text_input("Assigned Subjects")
                
                if st.button("Create Account"):
                    if new_prof_id and new_prof_pass and new_depts and new_subs:
                        creds = load_data('credentials.json')
                        if new_prof_id in creds:
                            st.warning("This ID exists. Please add a unique identifier (like a last name).")
                        else:
                            dept_list = [d.strip() for d in new_depts.split(",")]
                            sub_list = [s.strip() for s in new_subs.split(",")]
                            creds[new_prof_id] = {
                                "passcode": new_prof_pass, 
                                "institution": st.session_state.institution,
                                "departments": dept_list,
                                "subjects": sub_list
                            }
                            save_data('credentials.json', creds)
                            st.success(f"Professor '{new_prof_id}' added successfully!")
                    else:
                        st.warning("Please fill out all fields.")
                        
            with admin_tab3:
                st.subheader("Institution Account Deletion")
                confirm_del = st.checkbox("I confirm my request to delete this institution.")
                if st.button("Submit Deletion Request", type="primary"):
                    if confirm_del:
                        reqs = load_data('deletion_requests.json')
                        if not isinstance(reqs, list): reqs = []
                        if not any(r['username'] == st.session_state.institution and r['role'] == "Admin" for r in reqs):
                            reqs.append({"username": st.session_state.institution, "role": "Admin", "institution": st.session_state.institution})
                            save_data('deletion_requests.json', reqs)
                            st.success("Request sent to Platform Administrator.")
                    else:
                        st.error("Please check the confirmation box.")

    # === 3. PROFESSOR DASHBOARD (Drill-Down Navigation) ===
    elif st.session_state.role == "Professor":
        creds = load_data('credentials.json')
        my_profile = creds.get(st.session_state.username, {})
        my_depts = my_profile.get("departments", ["General"])
        my_subs = my_profile.get("subjects", ["General"])

        # State 1: Choose Department
        if st.session_state.prof_dept is None:
            st.header(f"🏠 Welcome, Professor {st.session_state.username}")
            st.write("Please select the Department you want to manage:")
            for d in my_depts:
                if st.button(f"📁 {d}", use_container_width=True):
                    st.session_state.prof_dept = d
                    st.rerun()
                    
        # State 2: Choose Subject
        elif st.session_state.prof_subject is None:
            st.header(f"📁 Department: {st.session_state.prof_dept}")
            st.write("Now select the Subject:")
            if st.button("⬅️ Go Back to Departments"):
                st.session_state.prof_dept = None
                st.rerun()
            st.markdown("---")
            for s in my_subs:
                if st.button(f"📘 {s}", use_container_width=True):
                    st.session_state.prof_subject = s
                    st.rerun()
                    
        # State 3: The Dashboard for that Specific Dept/Subject
        else:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.header(f"📘 {st.session_state.prof_dept} - {st.session_state.prof_subject}")
            with col2:
                if st.button("🏠 Home Menu"):
                    st.session_state.prof_dept = None
                    st.session_state.prof_subject = None
                    st.rerun()
            
            tab1, tab2, tab3 = st.tabs(["Add New Question", "Manage Question Bank", "Student Scores"])
            
            # --- AUTO-CLEARING FORM ---
            with tab1:
                st.subheader(f"Add Question to {st.session_state.prof_subject}")
                # Wrapping inputs in st.form automatically clears them when submitted!
                with st.form("add_question_form", clear_on_submit=True):
                    question_text = st.text_area("Question Text")
                    col1, col2 = st.columns(2)
                    with col1:
                        opt_a = st.text_input("Option A")
                        opt_c = st.text_input("Option C")
                    with col2:
                        opt_b = st.text_input("Option B")
                        opt_d = st.text_input("Option D")
                    correct_answer = st.selectbox("Correct Answer", ["A", "B", "C", "D"])
                    
                    submitted = st.form_submit_button("Save Question")
                    
                    if submitted:
                        if question_text and opt_a and opt_b and opt_c and opt_d:
                            questions = load_data('questions.json')
                            if not isinstance(questions, list): questions = []
                            
                            new_q = {
                                "professor": st.session_state.username, 
                                "institution": st.session_state.institution,
                                "department": st.session_state.prof_dept, 
                                "subject": st.session_state.prof_subject, 
                                "question": question_text,
                                "A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d, "answer": correct_answer
                            }
                            questions.append(new_q)
                            save_data('questions.json', questions)
                            st.success("✅ Question saved successfully! Form cleared for next entry.")
                        else:
                            st.error("Please fill out all question fields.")
                        
            with tab2:
                questions = load_data('questions.json')
                if not isinstance(questions, list): questions = []
                
                # Only show questions for this specific Dept/Subject combo!
                my_questions = [q for q in questions if q.get("professor") == st.session_state.username and q.get("institution") == st.session_state.institution and q.get("department") == st.session_state.prof_dept and q.get("subject") == st.session_state.prof_subject]
                
                if not my_questions:
                    st.info(f"No questions added for {st.session_state.prof_subject} yet.")
                else:
                    for i, q in enumerate(my_questions):
                        with st.expander(f"Q: {q['question'][:50]}..."):
                            st.write(f"**A:** {q['A']}")
                            st.write(f"**B:** {q['B']}")
                            st.write(f"**C:** {q['C']}")
                            st.write(f"**D:** {q['D']}")
                            st.success(f"**Correct Answer:** {q['answer']}")
                            if st.button("Delete Question", key=f"del_{i}"):
                                questions.remove(q)
                                save_data('questions.json', questions)
                                st.rerun()
                                
            with tab3:
                scores = load_data('scores.json')
                inst_scores = {k: v for k, v in scores.items() if v.get("institution") == st.session_state.institution}
                
                # Auto-filter scores for this department
                filtered_scores = {k: v for k, v in inst_scores.items() if v.get("department") == st.session_state.prof_dept and v.get("subject") == st.session_state.prof_subject}
                
                if not filtered_scores:
                    st.info("No scores found for this class yet.")
                else:
                    percentages = [d['percentage'] for d in filtered_scores.values()]
                    avg_score = round(sum(percentages) / len(percentages), 1)
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Tests Taken", len(percentages))
                    c2.metric("Average Score", f"{avg_score}%")
                    c3.metric("Highest Score", f"{max(percentages)}%")
                        
                    st.markdown("---")
                    csv_data = "Student Name,Department,Subject,Score,Total,Percentage%\n"
                    
                    for key, data in filtered_scores.items():
                        student_name = data.get("student", key) 
                        st.write(f"**{student_name}**: {data['score']}/{data['total']} ({data['percentage']}%)")
                        csv_data += f"{student_name},{st.session_state.prof_dept},{st.session_state.prof_subject},{data['score']},{data['total']},{data['percentage']}\n"
                    
                    st.download_button(
                        label="📥 Download Class Report (CSV)",
                        data=csv_data,
                        file_name=f"Report_{st.session_state.prof_subject.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.csv",
                        mime="text/csv"
                    )

    # === 4. STUDENT TEST PORTAL ===
    elif st.session_state.role == "Student":
        st.header(f"🎓 {st.session_state.institution} Test Portal")
        
        questions = load_data('questions.json')
        if not isinstance(questions, list): questions = []
        inst_questions = [q for q in questions if q.get("institution") == st.session_state.institution]
        
        if not inst_questions:
            st.info("Your professors haven't added any questions yet.")
        elif st.session_state.test_submitted:
            st.success("Test Submitted Successfully!")
            st.metric(label="Your Score", value=f"{st.session_state.student_score} / {st.session_state.test_total}")
            if st.button("Take Another Test"):
                st.session_state.test_submitted = False
                st.rerun()
        else:
            # Student follows the same drill-down path!
            departments = sorted(list(set([q.get("department", "General") for q in inst_questions])))
            selected_dept = st.selectbox("1. Select your Department:", departments)
            
            dept_questions = [q for q in inst_questions if q.get("department", "General") == selected_dept]
            subjects = sorted(list(set([q.get("subject", "General") for q in dept_questions])))
            selected_sub = st.selectbox("2. Select your Subject:", subjects)
            
            final_questions = [q for q in dept_questions if q.get("subject", "General") == selected_sub]
            
            if not final_questions:
                st.warning("No questions available.")
            else:
                st.write(f"Taking test for: **{selected_sub}**")
                st.markdown("---")
                with st.form("test_form"):
                    student_answers = {}
                    for i, q in enumerate(final_questions):
                        st.subheader(f"Q{i+1}: {q['question']}")
                        options = [f"A) {q['A']}", f"B) {q['B']}", f"C) {q['C']}", f"D) {q['D']}"]
                        choice = st.radio("Select your answer:", options, key=f"q_{i}", index=None)
                        student_answers[i] = choice
                        st.markdown("---")
                        
                    submitted = st.form_submit_button("Submit Test")
                    if submitted:
                        score = 0
                        for i, q in enumerate(final_questions):
                            ans = student_answers[i]
                            if ans:
                                if ans[0] == q['answer']: score += 1
                                    
                        st.session_state.student_score = score
                        st.session_state.test_total = len(final_questions)
                        st.session_state.test_submitted = True
                        
                        scores = load_data('scores.json')
                        score_key = f"{st.session_state.institution}_{st.session_state.username}_{selected_dept}_{selected_sub}"
                        scores[score_key] = {
                            "student": st.session_state.username,
                            "institution": st.session_state.institution,
                            "department": selected_dept,
                            "subject": selected_sub,
                            "score": score,
                            "total": len(final_questions),
                            "percentage": round((score/len(final_questions))*100, 2) if len(final_questions) > 0 else 0
                        }
                        save_data('scores.json', scores)
                        st.rerun()
