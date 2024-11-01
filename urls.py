from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
from collections import defaultdict
from models import *
from werkzeug.security import generate_password_hash, check_password_hash
from utils.generate_uid import generate_uid
import time
from collections import defaultdict
from datetime import datetime
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SECRET_KEY'] = 'secret'

response = requests.get("https://aiml.mentoring.codasauras.in/api/aiml").json()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if not user:
        
        # Hash the password before storing it
            hashed_password = generate_password_hash(password)
            
            new_user = User(uid = generate_uid('superadmin'), username=username, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            
            return redirect('/dashboard')
        
        else:
            flash("User already exists!!")
            return redirect(url_for('login'))
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            if check_password_hash(user.password, password):
                session['user_uid'] = user.uid
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Incorrect password")
        else:
            flash("User does not exist")
            return redirect(url_for('register'))
    
    return render_template('auth/login.html')

@app.route('/')
def index():
    if 'user_uid' in session:    
        user = User.query.filter_by(uid = session['user_uid']).first()
        if user:
            return redirect('/dashboard')
    return redirect('login')

@app.route('/details/aiml')
def aiml():
    details = requests.get('http://aiml.mentoring.codasauras.in/api/aiml').json()
    # print(details)
    return render_template('aiml.html', entries = details['entries'])

@app.route('/dashboard')
def admin_dashboard():
    api_endpoints = {
        'aiml': 'http://aiml.mentoring.codasauras.in/api/aiml',
        'it': 'http://129.213.151.29:5004/api/it',
        'bme': 'http://bme.mentoring.codasauras.in/api/bme',
        'me': 'http://me.mentoring.codasauras.in/api/me',
        'ee': 'http://127.0.0.1:5006/api/ee',
        # Add more APIs here in the future as needed
    }

    # Fetch data from all APIs dynamically
    responses = {}
    for dept, url in api_endpoints.items():
        try:
            responses[dept] = requests.get(url).json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from {dept}: {e}")
            responses[dept] = {}  # If any API fails, use an empty dict

    # Save response to a file for debugging (optional)
    with open('response.txt', 'w') as f:
        f.write(str(responses))

    if 'user_uid' not in session:
        flash("Please login first", "info")
        return redirect('login')

    user = User.query.filter_by(uid=session['user_uid']).first()

    # Combine all the data from different API responses
    combined_data = {
        'users': [],
        'sessions': [],
        'attendance': [],
        'meetings': [],
    }
    
    for data in responses.values():
        combined_data['users'].extend(data.get('users', []))
        combined_data['sessions'].extend(data.get('sessions', []))
        combined_data['attendance'].extend(data.get('attendance', []))
        combined_data['meetings'].extend(data.get('meetings', []))

    # Filter users based on roles
    students = [user for user in combined_data['users'] if user['role'] == 'student']
    mentors = [user for user in combined_data['users'] if user['role'] == 'mentor']
    admins = [user for user in combined_data['users'] if user['role'] == 'admin']

    # Sort mentoring sessions based on 'date' and 'time'
    mentoring_sessions = sorted(combined_data['sessions'], key=lambda x: (x['date'], x['time']), reverse=True)

    # Get mentoring session IDs from mentoring_sessions
    mentoring_session_ids = [session['id'] for session in mentoring_sessions]

    # Filter attendances based on mentoring session IDs
    attendances = [attendance for attendance in combined_data.get('attendance', []) if attendance['session_id'] in mentoring_session_ids]

    # Prepare data for the chart
    daily_sessions_count = defaultdict(int)
    daily_students_count = defaultdict(set)

    # Populate daily data based on mentorship sessions
    for each_session in mentoring_sessions:
        session_date = datetime.strptime(each_session['date'], "%Y-%m-%d").strftime("%A")
        daily_sessions_count[session_date] += 1

    # Populate attendance data
    for attendance in attendances:
        each_session = next((s for s in mentoring_sessions if s['id'] == attendance['session_id']), None)
        if each_session:
            session_date = datetime.strptime(each_session['date'], "%Y-%m-%d").strftime("%A")
            daily_students_count[session_date].add(attendance['student_id'])

    # Convert set of student IDs to counts
    daily_students_count = {day: len(students) for day, students in daily_students_count.items()}

    # Ensure all days are included with 0 if missing
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_sessions_count = {day: daily_sessions_count.get(day, 0) for day in day_order}
    daily_students_count = {day: daily_students_count.get(day, 0) for day in day_order}

    # Fetch online meetings and sort by 'id'
    online_meetings = sorted(combined_data['meetings'], key=lambda x: x['id'], reverse=True)

    # Find latest mentor, mentee, and admin based on 'id'
    latest_mentor = next((user for user in mentors if user['id'] == max([mentor['id'] for mentor in mentors])), None)
    latest_mentee = next((user for user in students if user['id'] == max([student['id'] for student in students])), None)
    latest_admin = next((user for user in admins if user['id'] == max([admin['id'] for admin in admins])), None)

    # Render the template with the gathered data
    return render_template(
        'admin/dashboard.html',
        entries=combined_data,
        students=students,
        mentors=mentors,
        admins=admins,
        mentorship_sessions=mentoring_sessions,
        attendance_dict=attendances,
        total_entries=len(combined_data['users']),
        total_students=len(students),
        total_mentors=len(mentors),
        daily_sessions_count=daily_sessions_count,
        daily_students_count=daily_students_count,
        total_sessions=len(mentoring_sessions),
        online_meetings=online_meetings,
        latest_mentor=latest_mentor,
        latest_mentee=latest_mentee,
        latest_admin=latest_admin,
        user=user
    )

@app.route('/entries', methods=['GET', 'POST'])
def entry_details():
    api_endpoints = {
        'aiml': 'http://aiml.mentoring.codasauras.in/api/aiml',
        'cst': 'http://127.0.0.1:5002/api/cst',
        # Add more APIs here in the future if needed
    }

    # Fetch data from all APIs dynamically
    responses = {}
    for dept, url in api_endpoints.items():
        try:
            responses[dept] = requests.get(url).json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from {dept}: {e}")
            responses[dept] = {}  # Use an empty dict in case of failure

    if 'user_uid' not in session:
        flash("Please login first", "info")
        return redirect('login')

    user = User.query.filter_by(uid=session['user_uid']).first()

    # Handle POST request to filter entries by admission year
    if request.method == 'POST':
        admission_year = request.form['admission_year']
        
        # Filter entries for AIML and CST departments based on admission year
        aiml_entries = [entry for entry in responses.get('aiml', {}).get('entries', []) 
                        if entry['department'] == 'CSE (AIML)' and entry['admission_year'] == admission_year]
        cst_entries = [entry for entry in responses.get('cst', {}).get('entries', []) 
                       if entry['department'] == 'CST' and entry['admission_year'] == admission_year]
        
        return render_template('admin/entry_details.html', aiml_entries=aiml_entries, cst_entries=cst_entries)

    # Handle GET request: Fetch all AIML and CST entries
    aiml_entries = [entry for entry in responses.get('aiml', {}).get('entries', []) if entry['department'] == 'CSE (AIML)']
    cst_entries = [entry for entry in responses.get('cst', {}).get('entries', []) if entry['department'] == 'CST']

    return render_template('admin/entry_details.html', aiml_entries=aiml_entries, cst_entries=cst_entries, user=user)



@app.route('/admins')
def mentee_details():
    response_aiml = requests.get("http://127.0.0.1:5001/api/aiml").json()
    response_it = requests.get("http://129.213.151.29:5004/api/it").json()
    response_bme = requests.get("http://bme.mentoring.codasauras.in/api/bme").json()
    response_me = requests.get("http://me.mentoring.codasauras.in/api/me").json()
    # response_ee = requests.get("http://127.0.0.1:5006/api/ee").json()
    if 'user_uid' not in session:
        flash("Please login first", "info")
        return redirect('login')
    
    user = User.query.filter_by(uid=session['user_uid']).first()
    
    entries_aiml = [u for u in response_aiml['users'] if u['role'] == 'admin']
    entries_it = [u for u in response_it['users'] if u['role'] == 'admin']
    entries_bme = [u for u in response_bme['users'] if u['role'] == 'admin']
    entries_me = [u for u in response_me['users'] if u['role'] == 'admin']
    # entries_ee = [u for u in response_ee['users'] if u['role'] == 'admin']
    
    print(response['department'])
    
    return render_template('admin/mentee_details.html', user=user, aiml=response_aiml['department'], it=response_it['department'], bme=response_bme['department'], me=response_me['department'], entries_aiml=entries_aiml, entries_it=entries_it, entries_bme=entries_bme, entries_me=entries_me)#, entries_ee=entries_ee)


@app.route('/mentors')
def mentor_details():
    response = requests.get("http://127.0.0.1:5001/api/aiml").json()
    mentors = [u for u in response['users'] if u['role'] == 'mentor']
    
    return render_template('admin/mentor_details.html', mentors=mentors)


@app.route('/sessions')
def session_log():
    response = requests.get("http://127.0.0.1:5001/api/aiml").json()
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
    response = requests.get("http://127.0.0.1:5001/api/aiml").json()
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

@app.route('/edit/<string:uid>', methods=['POST'])
def admin_edit(uid):
    # Fetching data from multiple department APIs
    response_aiml = requests.get("http://127.0.0.1:5001/api/aiml").json()
    response_it = requests.get("http://129.213.151.29:5004/api/it").json()
    response_bme = requests.get("http://bme.mentoring.codasauras.in/api/bme").json()
    response_me = requests.get("http://me.mentoring.codasauras.in/api/me").json()
    # response_ee = requests.get("http://127.0.0.1:5006/api/ee").json()
    
    user = None  # Initialize user as None
    
    # Iterate over each department's users and check for matching uid
    for department in [response_aiml['users'], response_it['users'], response_bme['users'], response_me['users']]:#, response_ee['users']]:
        for u in department:
            if u['uid'] == uid:
                user = u  # Assign the matched user
                break
        if user:
            break  # Break outer loop once user is found
    
    # If no user is found, return with an error
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        role = request.form.get("role")
        department = request.form['department']
        
        # Depending on the department, make the appropriate POST request to update the user role
        if department.lower() == 'aiml':
            requests.post('http://127.0.0.1:5001/remote_user_update/aiml',
                          json={'uid': user['uid'], 'role': role})
        elif department.lower() == 'it':
            requests.post('http://129.213.151.29:5004/remote_user_update/it',
                          json={'uid': user['uid'], 'role': role})
        elif department.lower() == 'bme':
            requests.post('https://bme.mentoring.codasauras.in/remote_user_update/bme',
                          json={'uid': user['uid'], 'role': role})
        elif department.lower() == 'me':
            requests.post('https://me.mentoring.codasauras.in/remote_user_update/me',
                          json={'uid': user['uid'], 'role': role})
        elif department.lower() == 'ee':
            requests.post('https://127.0.0.1:5006/remote_user_update/ee',
                          json={'uid': user['uid'], 'role': role})
        else:
            flash("Invalid department", "danger")
            return redirect(url_for('edit', uid=uid))
        
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/edit.html', user=user)

@app.route('/add_admin', methods=['GET', 'POST'])
def add_admin():
    response = requests.get("http://aiml.mentoring.codasauras.in/api/aiml").json()
    if 'user_uid' not in session:
        flash("Please login first", "info")
        return redirect('login')
    
    user = User.query.filter_by(uid=session['user_uid']).first()
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        department = request.form['department']
        
        if department.lower() == "aiml":
            requests.post('http://127.0.0.1:5001/register_admin/aiml', json={'username': username, 'email': email, 'password': password})
            
            flash("Admin added successfully", "success")
            
            return redirect(url_for('admin_dashboard'))
        
        elif department.lower() == "it":
            requests.post('http://129.213.151.29:5004/register_admin/it', json={'username': username, 'email': email, 'password': password})
            
            flash("Admin added successfully", "success")
            
            return redirect(url_for('admin_dashboard'))
        
        elif department.lower() == "bme":
            requests.post('http://bme.mentoring.codasauras.in/register_admin/bme', json={'username': username, 'email': email, 'password': password})
            
            flash("Admin added successfully", "success")
            
            return redirect(url_for('admin_dashboard'))
        
        elif department.lower() == "me":
            requests.post('http://me.mentoring.codasauras.in/register_admin/me', json={'username': username, 'email': email, 'password': password})
            
            flash("Admin added successfully", "success")
            
            return redirect(url_for('admin_dashboard'))
        elif department.lower() == "ee":
            requests.post('http://127.0.0.1:5006/register_admin/ee', json={'username': username, 'email': email, 'password': password})
            
            flash("Admin added successfully", "success")
            
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Add Department to Proceed", "danger")
            return redirect(url_for('add_admin'))
        
    return render_template('admin/add_admin.html', user=user)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    response = requests.get("http://127.0.0.1:5001/api/aiml").json()
    if 'user_uid' not in session:
        flash("Please login first", "info")
        return redirect('login')
    
    user = User.query.filter_by(uid=session['user_uid']).first()
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        
        user.username = username
        user.email = email
        # user.password = generate_password_hash(password)
        
        db.session.commit()
        
        flash("Profile updated successfully", "success")
        
        return redirect(url_for('profile'))
    
    return render_template('admin/profile.html', user=user)

@app.route('/update_password', methods=['GET', 'POST'])
def update_password():
    response = requests.get("http://127.0.0.1:5001/api/aiml").json()
    if 'user_uid' not in session:
        flash("Please login first", "info")
        return redirect('login')
    
    user = User.query.filter_by(uid=session['user_uid']).first()
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        
        if check_password_hash(user.password, current_password):
            user.password = generate_password_hash(new_password)
            db.session.commit()
            
            flash("Password updated successfully", "success")
            
            return redirect(url_for('profile'))
        else:
            flash("Incorrect password", "danger")
            return redirect(url_for('profile'))
    
    return render_template('admin/update_password.html', user=user)


@app.route('/logout')
def logout():
    session.pop('user_uid', None)
    return redirect(url_for('login'))