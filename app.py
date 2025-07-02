import flask
from flask import Flask, render_template, request, redirect, session, make_response
import sqlite3
import os
import json
import openpyxl
from fpdf import FPDF
import matplotlib.pyplot as plt
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'secret123'

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY, 
                    username TEXT, 
                    score INTEGER, 
                    answers TEXT, 
                    start_time TEXT, 
                    end_time TEXT, 
                    time_per_question TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    # Check if admin user exists
    c.execute("DELETE FROM admin WHERE username = 'admin'")
    c.execute("SELECT * FROM admin WHERE username = 'vamsi'")
    if c.fetchone() is None:
        c.execute("INSERT INTO admin (username, password) VALUES ('vamsi', '1234')")
    conn.commit()
    conn.close()

def load_questions():
    with open('questions.json') as f:
        return json.load(f)['questions']

def log_login(username):
    if not os.path.exists('login_details.xlsx'):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Login Details"
        sheet.append(['Username', 'Login Time'])
        workbook.save('login_details.xlsx')
    
    workbook = openpyxl.load_workbook('login_details.xlsx')
    sheet = workbook.active
    sheet.append([username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    workbook.save('login_details.xlsx')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        conn.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['username'] = username
            log_login(username)
            session['start_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return redirect('/test')
    return render_template('login.html')

@app.route('/test', methods=['GET', 'POST'])
def test():
    if 'username' not in session:
        return redirect('/login')
    
    questions = load_questions()
    
    if request.method == 'POST':
        answers = request.form
        end_time = datetime.now()
        start_time_str = session.get('start_time')
        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
        
        time_per_question = {}
        for i in range(1, 41):
            time_per_question[f'q{i}'] = request.form.get(f'q{i}_time', '0')

        score = 0
        user_answers = {}
        for i, q in enumerate(questions):
            user_answer = answers.get(f'q{i+1}')
            user_answers[f'q{i+1}'] = {
                "question": q['question'],
                "options": q['options'],
                "selected": user_answer,
                "correct_answer": q['answer'],
                "time_taken": time_per_question.get(f'q{i+1}', '0')
            }
            if user_answer == q['answer']:
                score += 1

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''INSERT INTO results (username, score, answers, start_time, end_time, time_per_question) 
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                  (session['username'], score, json.dumps(user_answers), start_time_str, end_time.strftime('%Y-%m-%d %H:%M:%S'), json.dumps(time_per_question)))
        conn.commit()
        result_id = c.lastrowid
        conn.close()
        
        return redirect(f'/report/{result_id}')

    return render_template('test.html', questions=questions)

@app.route('/report/<int:result_id>')
def report(result_id):
    if not session.get('admin_logged_in'):
        if 'username' in session:
            return "Your test has been submitted. Only an admin can view the detailed report."
        return redirect('/admin/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM results WHERE id=?', (result_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        return "Report not found", 404

    username, score, answers_json, start_time, end_time, time_per_question_json = result[1:]
    answers = json.loads(answers_json)
    time_per_question = json.loads(time_per_question_json)

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Test Report for {username}", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Score: {score}/40", ln=True)
    pdf.cell(200, 10, txt=f"Start Time: {start_time}", ln=True)
    pdf.cell(200, 10, txt=f"End Time: {end_time}", ln=True)
    
    total_time = sum(int(t) for t in time_per_question.values())
    pdf.cell(200, 10, txt=f"Total Time Spent: {total_time} seconds", ln=True)

    pdf.ln(10)
    pdf.cell(200, 10, txt="Question Analysis", ln=True)
    
    correct_count = 0
    wrong_count = 0
    unattempted_count = 0

    for q_id, data in answers.items():
        question_num = q_id.replace('q', '')
        pdf.ln(5)
        pdf.multi_cell(0, 5, f"Q{question_num}: {data['question']}")
        
        for opt, text in data['options'].items():
            pdf.cell(0, 5, f"  {opt}) {text}", ln=True)
            
        pdf.cell(0, 5, f"  Selected Answer: {data['selected'] if data['selected'] else 'Unattempted'}", ln=True)
        pdf.cell(0, 5, f"  Correct Answer: {data['correct_answer']}", ln=True)
        pdf.cell(0, 5, f"  Time Taken: {data['time_taken']} seconds", ln=True)
        
        if data['selected'] == data['correct_answer']:
            correct_count += 1
            pdf.cell(0, 5, "  Result: Correct (+1)", ln=True)
        elif not data['selected']:
            unattempted_count += 1
            pdf.cell(0, 5, "  Result: Unattempted (0)", ln=True)
        else:
            wrong_count += 1
            pdf.cell(0, 5, "  Result: Wrong (0)", ln=True)

    # Pie chart for efficiency
    labels = 'Correct', 'Wrong', 'Unattempted'
    sizes = [correct_count, wrong_count, unattempted_count]
    colors = ['#99ff99','#ff9999','#66b3ff']
    
    fig1, ax1 = plt.subplots()
    ax1.pie(sizes, colors=colors, labels=labels, autopct='%1.1f%%', startangle=90)
    ax1.axis('equal')
    
    chart_path = f'efficiency_{result_id}.png'
    plt.savefig(chart_path)
    plt.close()

    pdf.add_page()
    pdf.set_font("Arial", 'B', size=16)
    pdf.cell(200, 10, txt="Efficiency Chart", ln=True, align='C')
    pdf.image(chart_path, x=10, y=30, w=190)
    os.remove(chart_path)

    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'attachment', filename=f'report_{username}_{result_id}.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT * FROM admin WHERE username=? AND password=?', (username, password))
        admin = c.fetchone()
        conn.close()
        if admin:
            session['admin_logged_in'] = True
            return redirect('/admin')
    return render_template('admin_login.html')

@app.route('/admin')
def admin():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, username, score, start_time, end_time FROM results')
    results = c.fetchall()
    conn.close()
    return render_template('admin.html', results=results)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')
