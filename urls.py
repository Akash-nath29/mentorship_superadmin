from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
from collections import defaultdict

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)

response = requests.get("http://127.0.0.1:5001/api/aiml").json()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/details/aiml')
def aiml():
    details = requests.get('http://127.0.0.1:5001/api/aiml').json()
    # print(details)
    return render_template('aiml.html', entries = details['entries'])


@app.route('/dashboard')
def admin_dashboard():
    # Get the entries and users data from the API response
    entries = response['entries']
    students = [user for user in response['users'] if user['role'] == 'student']
    mentors = [user for user in response['users'] if user['role'] == 'mentor']
    admins = [user for user in response['users'] if user['role'] == 'admin']

    # Sort the sessions based on 'date' and 'time' in descending order
    sessions = sorted(response['sessions'], key=lambda x: (x['date'], x['time']), reverse=True)

    # Get session IDs from sessions
    session_ids = [session['id'] for session in sessions]

    # Filter attendances based on session IDs
    # Safely access 'attendances' with a fallback to an empty list if the key doesn't exist
    attendances = [attendance for attendance in response.get('attendances', []) if attendance['session_id'] in session_ids]

    # Create attendance_dict to group attendances by session_id
    attendance_dict = {session_id: [] for session_id in session_ids}
    for attendance in attendances:
        attendance_dict[attendance['session_id']].append(attendance)

    # Prepare data for the chart
    daily_sessions_count = defaultdict(int)
    daily_students_count = defaultdict(set)

    # Populate daily data based on mentorship sessions
    for session in sessions:
        session_date = datetime.strptime(session['date'], "%Y-%m-%d").strftime("%A")
        daily_sessions_count[session_date] += 1

    # Populate attendance data
    for attendance in attendances:
        session = next((s for s in sessions if s['id'] == attendance['session_id']), None)
        if session:
            session_date = datetime.strptime(session['date'], "%Y-%m-%d").strftime("%A")
            daily_students_count[session_date].add(attendance['student_id'])

    # Convert set of student IDs to counts
    daily_students_count = {day: len(students) for day, students in daily_students_count.items()}

    # Order days of the week for the chart
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_sessions_count = {day: daily_sessions_count.get(day, 0) for day in day_order}
    daily_students_count = {day: daily_students_count.get(day, 0) for day in day_order}

    # Fetch online meetings and sort by 'id' descending
    online_meetings = sorted(response['meetings'], key=lambda x: x['id'], reverse=True)

    # Find latest mentor, mentee, and admin based on 'id'
    latest_mentor = next((user for user in mentors if user['id'] == max([mentor['id'] for mentor in mentors])), None)
    latest_mentee = next((user for user in students if user['id'] == max([student['id'] for student in students])), None)
    latest_admin = next((user for user in admins if user['id'] == max([admin['id'] for admin in admins])), None)

    # Render the template with the gathered data
    return render_template(
        'admin/dashboard.html',
        entries=entries,
        students=students,
        mentors=mentors,
        admins=admins,
        mentorship_sessions=sessions,
        attendance_dict=attendance_dict,
        total_entries=len(entries),
        total_students=len(students),
        total_mentors=len(mentors),
        daily_sessions_count=daily_sessions_count,
        daily_students_count=daily_students_count,
        total_sessions=len(sessions),
        online_meetings=online_meetings,
        latest_mentor=latest_mentor,
        latest_mentee=latest_mentee,
        latest_admin=latest_admin
    )

@app.route('/entries', methods=['GET', 'POST'])
def entry_details():
    
    # Handling POST request for filtered entries based on admission year
    if request.method == 'POST':
        admission_year = request.form['admission_year']
        
        # Filter AIML and CST entries based on admission year
        aiml_entries = [entry for entry in response['entries'] if entry['department'] == 'CSE (AIML)' and entry['admission_year'] == admission_year]
        cst_entries = [entry for entry in response['entries'] if entry['department'] == 'CST' and entry['admission_year'] == admission_year]
        
        return render_template('admin/entry_details.html', aiml_entries=aiml_entries, cst_entries=cst_entries)
    
    # For GET request: Fetch all AIML and CST entries
    aiml_entries = [entry for entry in response['entries'] if entry['department'] == 'CSE (AIML)']
    cst_entries = [entry for entry in response['entries'] if entry['department'] == 'CST']
    
    return render_template('admin/entry_details.html', aiml_entries=aiml_entries, cst_entries=cst_entries)


@app.route('/mentees')
def mentee_details():
    entries = [u for u in response['users'] if u['role'] == 'student']
    
    return render_template('admin/mentee_details.html', entries=entries)


@app.route('/mentors')
def mentor_details():
    mentors = [u for u in response['users'] if u['role'] == 'mentor']
    
    return render_template('admin/mentor_details.html', mentors=mentors)


@app.route('/sessions')
def session_log():
    # Fetch all sessions, sorted by date and time (descending)
    sessions = sorted(response['sessions'], key=lambda x: (x['date'], x['time']), reverse=True)
    
    # Collect session IDs
    session_ids = [session['id'] for session in sessions]
    
    # Filter attendances based on session IDs
    attendances = [attendance for attendance in response['attendances'] if attendance['session_id'] in session_ids]
    
    # Create attendance dictionary to map session_id to attendances
    attendance_dict = {session_id: [] for session_id in session_ids}
    for attendance in attendances:
        attendance_dict[attendance['session_id']].append(attendance)
    
    return render_template('admin/session_log.html', sessions=sessions, attendance_dict=attendance_dict)


@app.route('/view/<string:uid>')
def view_details(uid):
    user_details = next((user for user in response['users'] if user['uid'] == uid), None)
    
    if user_details:
        # Find the entry corresponding to the user’s email
        entry = next((entry for entry in response['entries'] if entry['email'] == user_details['email']), None)
        return render_template('admin/view_details.html', entry=entry)
    else:
        return "User not found", 404


# @app.route('/edit_session/<string:uid>', methods=['GET', 'POST'])
# def edit_session(uid):
#     # Fetch the mentorship session from the API response based on the UID
#     mentorship_session = next((session for session in response['sessions'] if session['uid'] == uid), None)

#     if request.method == 'POST':
#         # Update the session details from the form inputs
#         mentorship_session['date'] = request.form['date']
#         mentorship_session['time'] = request.form['time']
#         mentorship_session['time_duration'] = request.form['duration']
#         mentorship_session['session_type'] = request.form['session_type']
#         mentorship_session['session_content'] = request.form['session_content']
        
#         # In a real scenario, you would send a PUT/POST request to update this data in the database

#         # Process attendance
#         attendances = request.form.getlist('attendance')
#         for attendance in attendances:
#             new_attendance = {
#                 'session_id': mentorship_session['id'], 
#                 'student_id': attendance
#             }
#             # In a real scenario, you would send a request to add this attendance to the database
        
#         return redirect(url_for('index'))

#     # Filter attendances for this session
#     attendances = [attendance for attendance in response['attendances'] if attendance['session_id'] == mentorship_session['id']]

#     return render_template('admin/edit_session.html', session=mentorship_session, attendances=attendances)

