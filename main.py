import streamlit as st
import json
import os

# --- DATABASE SETUP ---
FILES = ['credentials.json', 'questions.json', 'scores.json']
for file in FILES:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            if file == 'questions.json':
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

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'test_submitted' not in st.session_state:
    st.session_state.test_submitted = False
if 'student_score' not in st.session_state:
    st.session_state.student_score = 0

# --- MAIN APP UI ---
st.title("⚙️ Academic Testing Portal")

if not st.session_state.logged_in:
    st.subheader("Welcome. Please select your portal:")
    # ADDED: Admin option to the radio button
    portal = st.radio("Login as:", ["Student", "Professor", "Admin"])

    if portal == "Professor":
        st.info("Default setup: Enter a new passcode to register, or enter your existing passcode to log in.")
        prof_id = st.text_input("Professor ID (Your Name)")
        passcode = st.text_input("Passcode", type="password")
        
        if st.button("Professor Login"):
            if prof_id and passcode:
                creds = load_data('credentials.json')
                if prof_id in creds:
                    if creds[prof_id] == passcode:
                        st.session_state.logged_in = True
                        st.session_state.role = "Professor"
                        st.session_state.username = prof_id
                        st.rerun()
                    else:
                        st.error("Incorrect passcode.")
                else:
                    creds[prof_id] = passcode
                    save_data('credentials.json', creds)
                    st.success(f"Professor {prof_id} registered! Click login again.")
            else:
                st.warning("Please enter both ID and passcode.")

    elif portal == "Student":
        student_name = st.text_input("Enter your full name to begin:")
        if st.button("Student Login"):
            if student_name:
                st.session_state.logged_in = True
                st.session_state.role = "Student"
                st.session_state.username = student_name
                st.session_state.test_submitted = False
                st.rerun()
            else:
                st.warning("Please enter your name.")
                
    # ADDED: Admin Login Flow
    elif portal == "Admin":
        st.info("System Administrator Access")
        admin_pass = st.text_input("Admin Passcode", type="password")
        if st.button("Admin Login"):
            if admin_pass == "admin123": # Hardcoded admin password for simplicity
                st.session_state.logged_in = True
                st.session_state.role = "Admin"
                st.session_state.username = "Administrator"
                st.rerun()
            else:
                st.error("Access Denied: Incorrect Admin Passcode.")

# --- DASHBOARDS ---
if st.session_state.logged_in:
    st.success(f"Logged in as: {st.session_state.username} ({st.session_state.role})")
    
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = ""
        st.session_state.test_submitted = False
        st.rerun()
        
    st.markdown("---")
    
    # === ADMIN DASHBOARD ===
    if st.session_state.role == "Admin":
        st.header("🛡️ System Administrator Dashboard")
        st.subheader("Manage Professor Accounts")
        
        creds = load_data('credentials.json')
        if not creds:
            st.info("No professors have registered yet.")
        else:
            for prof in list(creds.keys()):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"👨‍🏫 **Professor ID:** {prof}")
                with col2:
                    if st.button("Remove Account", key=f"del_prof_{prof}"):
                        # 1. Delete the professor's account
                        del creds[prof]
                        save_data('credentials.json', creds)
                        
                        # 2. Delete all questions created by this professor
                        questions = load_data('questions.json')
                        if isinstance(questions, list):
                            filtered_questions = [q for q in questions if q.get("professor") != prof]
                            save_data('questions.json', filtered_questions)
                        
                        st.rerun()

    # === PROFESSOR DASHBOARD ===
    elif st.session_state.role == "Professor":
        st.header("👨‍🏫 Professor Dashboard")
        
        tab1, tab2, tab3 = st.tabs(["Add New Question", "Manage Question Bank", "Student Scores"])
        
        with tab1:
            st.subheader("Create a Question")
            subject = st.text_input("Subject Area (e.g., Physics, Mechanical Design)")
            question_text = st.text_area("Question Text")
            
            col1, col2 = st.columns(2)
            with col1:
                opt_a = st.text_input("Option A")
                opt_c = st.text_input("Option C")
            with col2:
                opt_b = st.text_input("Option B")
                opt_d = st.text_input("Option D")
                
            correct_answer = st.selectbox("Correct Answer", ["A", "B", "C", "D"])
            
            if st.button("Save Question"):
                if subject and question_text and opt_a and opt_b and opt_c and opt_d:
                    questions = load_data('questions.json')
                    if isinstance(questions, dict): 
                        questions = []
                        
                    new_q = {
                        "professor": st.session_state.username,
                        "subject": subject,
                        "question": question_text,
                        "A": opt_a,
                        "B": opt_b,
                        "C": opt_c,
                        "D": opt_d,
                        "answer": correct_answer
                    }
                    questions.append(new_q)
                    save_data('questions.json', questions)
                    st.success("Question saved successfully to the database!")
                else:
                    st.warning("Please fill out all fields before saving.")
                    
        with tab2:
            st.subheader("Your Question Bank")
            questions = load_data('questions.json')
            if isinstance(questions, dict): 
                questions = []
            
            my_questions = [q for q in questions if q.get("professor") == st.session_state.username]
            
            if not my_questions:
                st.info("You haven't added any questions yet.")
            else:
                for i, q in enumerate(my_questions):
                    with st.expander(f"Q: {q['question'][:50]}... ({q['subject']})"):
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
            st.subheader("Test Results")
            scores = load_data('scores.json')
            if not scores:
                st.info("No students have completed the test yet.")
            else:
                for student, data in scores.items():
                    st.write(f"**{student}**: {data['score']}/{data['total']} ({data['percentage']}%)")

    # === STUDENT TEST PORTAL ===
    elif st.session_state.role == "Student":
        st.header("🎓 Student Test Portal")
        
        questions = load_data('questions.json')
        if isinstance(questions, dict) or not questions:
            st.info("There are no questions available right now. Please wait for your professor to add some!")
        
        elif st.session_state.test_submitted:
            st.success("Test Submitted Successfully!")
            st.metric(label="Your Score", value=f"{st.session_state.student_score} / {len(questions)}")
            if st.button("Take Test Again"):
                st.session_state.test_submitted = False
                st.rerun()
        
        else:
            st.write("Please select the best answer for each question.")
            st.markdown("---")
            
            with st.form("test_form"):
                student_answers = {}
                for i, q in enumerate(questions):
                    st.subheader(f"Q{i+1}: {q['question']}")
                    options = [f"A) {q['A']}", f"B) {q['B']}", f"C) {q['C']}", f"D) {q['D']}"]
                    choice = st.radio("Select your answer:", options, key=f"q_{i}", index=None)
                    student_answers[i] = choice
                    st.markdown("---")
                    
                submitted = st.form_submit_button("Submit Test")
                
                if submitted:
                    score = 0
                    for i, q in enumerate(questions):
                        ans = student_answers[i]
                        if ans:
                            chosen_letter = ans[0] 
                            if chosen_letter == q['answer']:
                                score += 1
                                
                    st.session_state.student_score = score
                    st.session_state.test_submitted = True
                    
                    scores = load_data('scores.json')
                    scores[st.session_state.username] = {
                        "score": score,
                        "total": len(questions),
                        "percentage": round((score/len(questions))*100, 2) if len(questions) > 0 else 0
                    }
                    save_data('scores.json', scores)
                    
                    st.rerun()
