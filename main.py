import streamlit as st
import json
import os

# --- DATABASE SETUP ---
FILES = ['credentials.json', 'questions.json', 'scores.json']
for file in FILES:
    if not os.path.exists(file):
        with open(file, 'w') as f:
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
        st.info("Default setup: Enter a new passcode to register a new Professor account, or enter your existing passcode to log in.")
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
        
    if st.session_state.role == "Professor":
        st.write("Welcome to the Professor Dashboard. (Question builder coming in Phase 2)")
    elif st.session_state.role == "Student":
        st.write("Welcome to the Test Portal. (Test taking engine coming in Phase 3)")
