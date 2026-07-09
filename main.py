import streamlit as st
import json
import os

# --- DATABASE SETUP ---
FILES = ['credentials.json', 'questions.json', 'scores.json']
for file in FILES:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            # Questions need to be a list, others can be dictionaries
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

# --- MAIN APP UI ---
st.title("⚙️ Academic Testing Portal")

if not st.session_state.logged_in:
    st.subheader("Welcome. Please select your portal:")
    portal = st.radio("Login as:", ["Student", "Professor"])

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
                st.rerun()
            else:
                st.warning("Please enter your name.")

# --- DASHBOARDS ---
if st.session_state.logged_in:
    st.success(f"Logged in as: {st.session_state.username} ({st.session_state.role})")
    
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = ""
        st.rerun()
        
    st.markdown("---")
    
    # === PHASE 2: PROFESSOR DASHBOARD ===
    if st.session_state.role == "Professor":
        st.header("👨‍🏫 Professor Dashboard")
        
        # Creates two clean tabs for organization
        tab1, tab2 = st.tabs(["Add New Question", "Manage Question Bank"])
        
        # TAB 1: ADD QUESTIONS
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
                    
                    # Safety check for file formatting
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
                    
        # TAB 2: MANAGE QUESTIONS
        with tab2:
            st.subheader("Your Question Bank")
            questions = load_data('questions.json')
            if isinstance(questions, dict): 
                questions = []
            
            # This ensures professors only see their own questions
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
                        
                        # Deletion mechanism
                        if st.button("Delete Question", key=f"del_{i}"):
                            questions.remove(q)
                            save_data('questions.json', questions)
                            st.rerun()
                            
    # === PHASE 3 PLACEHOLDER ===
    elif st.session_state.role == "Student":
        st.header("🎓 Student Test Portal")
        st.info("The testing engine is coming in Phase 3. Please wait for your professor to add questions!")
