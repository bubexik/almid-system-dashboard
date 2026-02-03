from flask import Flask, render_template_string, redirect, url_for, request, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'almid-secret-2026-production')
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_db():
    # Use persistent path if possible, but for free tier /tmp is okay (resets on restart)
    db_path = '/tmp/almid.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT DEFAULT "user")')
    c.execute('CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, category TEXT, upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    c.execute('CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, registration TEXT UNIQUE, type TEXT, fuel_counter REAL DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS hr_records (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_name TEXT, type TEXT, amount REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    
    # Check admin
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES ('admin', ?, 'admin')", (generate_password_hash('admin123'),))
    conn.commit()
    conn.close()

# INITIALIZE DB ON STARTUP (outside if __main__)
init_db()

def get_db():
    conn = sqlite3.connect('/tmp/almid.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'user_id' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = get_db().execute('SELECT * FROM users WHERE username = ?', (request.form.get('username'),)).fetchone()
        if user and check_password_hash(user['password'], request.form.get('password')):
            session['user_id'], session['username'] = user['id'], user['username']
            return redirect(url_for('dashboard'))
        flash('Błąd logowania')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    stats = {
        'docs': db.execute('SELECT COUNT(*) FROM documents').fetchone()[0],
        'vehicles': db.execute('SELECT COUNT(*) FROM vehicles').fetchone()[0]
    }
    vehicles = db.execute('SELECT * FROM vehicles ORDER BY id DESC LIMIT 5').fetchall()
    return render_template_string(DASHBOARD_TEMPLATE, stats=stats, vehicles=vehicles)

@app.route('/documents')
@login_required
def documents():
    docs = get_db().execute('SELECT * FROM documents ORDER BY upload_date DESC').fetchall()
    return render_template_string(DOCUMENTS_TEMPLATE, documents=docs)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        db = get_db()
        db.execute('INSERT INTO documents (filename, category) VALUES (?, ?)', (filename, request.form.get('category')))
        db.commit()
    return redirect(url_for('documents'))

@app.route('/fleet')
@login_required
def fleet():
    vehicles = get_db().execute('SELECT * FROM vehicles ORDER BY id DESC').fetchall()
    return render_template_string(FLEET_TEMPLATE, vehicles=vehicles)

@app.route('/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    db = get_db()
    db.execute('INSERT INTO vehicles (name, registration, type) VALUES (?, ?, ?)', 
               (request.form.get('name'), request.form.get('registration'), request.form.get('type')))
    db.commit()
    return redirect(url_for('fleet'))

@app.route('/hr')
@login_required
def hr():
    records = get_db().execute('SELECT * FROM hr_records ORDER BY created_at DESC').fetchall()
    return render_template_string(HR_TEMPLATE, records=records)

@app.route('/add_hr', methods=['POST'])
@login_required
def add_hr():
    db = get_db()
    db.execute('INSERT INTO hr_records (employee_name, type, amount) VALUES (?, ?, ?)',
               (request.form.get('employee'), request.form.get('type'), request.form.get('amount')))
    db.commit()
    return redirect(url_for('hr'))

LOGIN_TEMPLATE = '''
<!DOCTYPE html><html><head><title>ALMID Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
<body class="bg-light"><div class="container mt-5"><div class="row justify-content-center"><div class="col-md-4"><div class="card shadow">
<div class="card-header bg-primary text-white text-center"><h4>ALMID System</h4></div><div class="card-body">
<form method="POST"><div class="mb-3"><label>Użytkownik</label><input type="text" name="username" class="form-control" required></div>
<div class="mb-3"><label>Hasło</label><input type="password" name="password" class="form-control" required></div>
<button class="btn btn-primary w-100">Zaloguj</button></form><div class="mt-3 text-center text-muted small">admin / admin123</div></div></div></div></div></div></body></html>'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html><html><head><title>ALMID Dashboard</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
<body><nav class="navbar navbar-dark bg-primary mb-4"><div class="container"><a class="navbar-brand">ALMID System</a><a href="/logout" class="btn btn-outline-light btn-sm">Wyloguj</a></div></nav>
<div class="container"><div class="row"><div class="col-md-3"><div class="list-group mb-4"><a href="/dashboard" class="list-group-item active">Dashboard</a><a href="/documents" class="list-group-item">Dokumenty</a><a href="/fleet" class="list-group-item">Flota</a><a href="/hr" class="list-group-item">HR</a></div></div>
<div class="col-md-9"><div class="row mb-4"><div class="col-md-6"><div class="card bg-info text-white"><div class="card-body text-center"><h3>{{ stats.docs }}</h3><p>Dokumentów</p></div></div></div><div class="col-md-6"><div class="card bg-success text-white"><div class="card-body text-center"><h3>{{ stats.vehicles }}</h3><p>Pojazdów</p></div></div></div></div>
<h4>Ostatnie pojazdy</h4><table class="table">{% for v in vehicles %}<tr><td>{{ v.name }}</td><td>{{ v.registration }}</td></tr>{% endfor %}</table></div></div></div></body></html>'''

DOCUMENTS_TEMPLATE = '''
<!DOCTYPE html><html><head><title>ALMID Dokumenty</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
<body><nav class="navbar navbar-dark bg-primary mb-4"><div class="container"><a class="navbar-brand" href="/">ALMID System</a></div></nav>
<div class="container"><div class="row"><div class="col-md-3"><div class="list-group"><a href="/dashboard" class="list-group-item">Dashboard</a><a href="/documents" class="list-group-item active">Dokumenty</a></div></div>
<div class="col-md-9"><div class="card mb-4"><div class="card-body"><form action="/upload" method="POST" enctype="multipart/form-data" class="row g-2">
<div class="col-md-6"><input type="file" name="file" class="form-control" required></div><div class="col-md-4"><select name="category" class="form-select"><option>Faktura</option><option>Umowa</option></select></div>
<div class="col-md-2"><button class="btn btn-primary w-100">Upload</button></div></form></div></div>
<table class="table">{% for d in documents %}<tr><td>{{ d.filename }}</td><td>{{ d.category }}</td><td>{{ d.upload_date }}</td></tr>{% endfor %}</table></div></div></div></body></html>'''

FLEET_TEMPLATE = '''
<!DOCTYPE html><html><head><title>ALMID Flota</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
<body><nav class="navbar navbar-dark bg-primary mb-4"><div class="container"><a class="navbar-brand" href="/">ALMID System</a></div></nav>
<div class="container"><div class="row"><div class="col-md-3"><div class="list-group"><a href="/dashboard" class="list-group-item">Dashboard</a><a href="/fleet" class="list-group-item active">Flota</a></div></div>
<div class="col-md-9"><div class="card mb-4"><div class="card-body"><form action="/add_vehicle" method="POST" class="row g-2">
<div class="col-md-4"><input name="name" placeholder="Nazwa" class="form-control" required></div><div class="col-md-4"><input name="registration" placeholder="Nr Rej" class="form-control" required></div>
<div class="col-md-2"><select name="type" class="form-select"><option>Bus</option><option>Osobowy</option></select></div><div class="col-md-2"><button class="btn btn-success w-100">Dodaj</button></div></form></div></div>
<table class="table">{% for v in vehicles %}<tr><td>{{ v.name }}</td><td>{{ v.registration }}</td><td>{{ v.type }}</td></tr>{% endfor %}</table></div></div></div></body></html>'''

HR_TEMPLATE = '''
<!DOCTYPE html><html><head><title>ALMID HR</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
<body><nav class="navbar navbar-dark bg-primary mb-4"><div class="container"><a class="navbar-brand" href="/">ALMID System</a></div></nav>
<div class="container"><div class="row"><div class="col-md-3"><div class="list-group"><a href="/dashboard" class="list-group-item">Dashboard</a><a href="/hr" class="list-group-item active">HR</a></div></div>
<div class="col-md-9"><div class="card mb-4"><div class="card-body"><form action="/add_hr" method="POST" class="row g-2">
<div class="col-md-5"><input name="employee" placeholder="Pracownik" class="form-control" required></div><div class="col-md-3"><select name="type" class="form-select"><option>Zaliczka</option><option>Urlop</option></select></div>
<div class="col-md-2"><input name="amount" type="number" placeholder="Kwota" class="form-control"></div><div class="col-md-2"><button class="btn btn-primary w-100">Dodaj</button></div></form></div></div>
<table class="table">{% for r in records %}<tr><td>{{ r.employee_name }}</td><td>{{ r.type }}</td><td>{{ r.amount }}</td><td>{{ r.created_at }}</td></tr>{% endfor %}</table></div></div></div></body></html>'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
