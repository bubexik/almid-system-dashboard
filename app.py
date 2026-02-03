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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database initialization
def init_db():
    conn = sqlite3.connect('/tmp/almid.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Documents table
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        file_type TEXT,
        category TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Vehicles table
    c.execute('''CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        registration TEXT UNIQUE NOT NULL,
        type TEXT,
        fuel_counter REAL DEFAULT 0,
        hours_counter REAL DEFAULT 0,
        last_service DATE,
        next_service DATE,
        insurance_expiry DATE,
        technical_inspection DATE,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Trip logs table
    c.execute('''CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER,
        driver TEXT,
        date DATE,
        distance REAL,
        fuel_used REAL,
        destination TEXT,
        purpose TEXT,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
    )''')
    
    # HR table - leaves/advances
    c.execute('''CREATE TABLE IF NOT EXISTS hr_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_name TEXT,
        type TEXT,
        amount REAL,
        date_from DATE,
        date_to DATE,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create default admin user if not exists
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        admin_pass = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password, role) VALUES ('admin', ?, 'admin')", (admin_pass,))
    
    conn.commit()
    conn.close()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Musisz się zalogować', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Get DB connection
def get_db():
    conn = sqlite3.connect('/tmp/almid.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Witaj {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nieprawidłowa nazwa użytkownika lub hasło', 'danger')
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    flash('Wylogowano pomyślnie', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    
    # Get statistics
    doc_count = conn.execute('SELECT COUNT(*) as count FROM documents').fetchone()['count']
    vehicle_count = conn.execute('SELECT COUNT(*) as count FROM vehicles').fetchone()['count']
    trip_count = conn.execute('SELECT COUNT(*) as count FROM trips').fetchone()['count']
    
    # Recent documents
    recent_docs = conn.execute('SELECT * FROM documents ORDER BY upload_date DESC LIMIT 5').fetchall()
    
    # Vehicles needing service
    vehicles = conn.execute('SELECT * FROM vehicles ORDER BY created_at DESC LIMIT 5').fetchall()
    
    conn.close()
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                 doc_count=doc_count,
                                 vehicle_count=vehicle_count,
                                 trip_count=trip_count,
                                 recent_docs=recent_docs,
                                 vehicles=vehicles)

@app.route('/documents')
@login_required
def documents():
    conn = get_db()
    docs = conn.execute('SELECT * FROM documents ORDER BY upload_date DESC').fetchall()
    conn.close()
    return render_template_string(DOCUMENTS_TEMPLATE, documents=docs)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('Nie wybrano pliku', 'danger')
        return redirect(url_for('documents'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Nie wybrano pliku', 'danger')
        return redirect(url_for('documents'))
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Save to database
        conn = get_db()
        conn.execute('INSERT INTO documents (filename, filepath, file_type, category, user_id) VALUES (?, ?, ?, ?, ?)',
                    (filename, filepath, request.form.get('file_type', 'other'), 
                     request.form.get('category', 'inne'), session['user_id']))
        conn.commit()
        conn.close()
        
        flash(f'Plik {filename} został przesłany!', 'success')
    
    return redirect(url_for('documents'))

@app.route('/fleet')
@login_required
def fleet():
    conn = get_db()
    vehicles = conn.execute('SELECT * FROM vehicles ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string(FLEET_TEMPLATE, vehicles=vehicles)

@app.route('/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    name = request.form.get('name')
    registration = request.form.get('registration')
    v_type = request.form.get('type')
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO vehicles (name, registration, type) VALUES (?, ?, ?)',
                    (name, registration, v_type))
        conn.commit()
        flash(f'Pojazd {name} został dodany!', 'success')
    except sqlite3.IntegrityError:
        flash('Pojazd o tym numerze rejestracyjnym już istnieje', 'danger')
    conn.close()
    
    return redirect(url_for('fleet'))

@app.route('/trips')
@login_required
def trips():
    conn = get_db()
    trips_data = conn.execute('''SELECT trips.*, vehicles.name as vehicle_name, vehicles.registration
                                  FROM trips 
                                  LEFT JOIN vehicles ON trips.vehicle_id = vehicles.id
                                  ORDER BY trips.date DESC''').fetchall()
    vehicles = conn.execute('SELECT * FROM vehicles').fetchall()
    conn.close()
    return render_template_string(TRIPS_TEMPLATE, trips=trips_data, vehicles=vehicles)

@app.route('/add_trip', methods=['POST'])
@login_required
def add_trip():
    vehicle_id = request.form.get('vehicle_id')
    driver = request.form.get('driver')
    date = request.form.get('date')
    distance = request.form.get('distance')
    destination = request.form.get('destination')
    
    conn = get_db()
    conn.execute('INSERT INTO trips (vehicle_id, driver, date, distance, destination) VALUES (?, ?, ?, ?, ?)',
                (vehicle_id, driver, date, distance, destination))
    conn.commit()
    conn.close()
    
    flash('Przejazd został dodany!', 'success')
    return redirect(url_for('trips'))

@app.route('/hr')
@login_required
def hr():
    conn = get_db()
    records = conn.execute('SELECT * FROM hr_records ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string(HR_TEMPLATE, records=records)

@app.route('/add_hr', methods=['POST'])
@login_required
def add_hr():
    employee = request.form.get('employee')
    hr_type = request.form.get('type')
    amount = request.form.get('amount', 0)
    date_from = request.form.get('date_from')
    date_to = request.form.get('date_to')
    
    conn = get_db()
    conn.execute('INSERT INTO hr_records (employee_name, type, amount, date_from, date_to) VALUES (?, ?, ?, ?, ?)',
                (employee, hr_type, amount, date_from, date_to))
    conn.commit()
    conn.close()
    
    flash('Wpis HR został dodany!', 'success')
    return redirect(url_for('hr'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


# Templates
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ALMID - Logowanie</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card shadow">
                    <div class="card-header bg-primary text-white text-center">
                        <h4>ALMID System</h4>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }}">{{ message }}</div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">Użytkownik</label>
                                <input type="text" name="username" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Hasło</label>
                                <input type="password" name="password" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Zaloguj</button>
                        </form>
                        <div class="mt-3 text-center text-muted">
                            <small>Domyślny login: admin / admin123</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ALMID - Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">ALMID System</a>
            <div class="navbar-nav ms-auto">
                <span class="nav-link text-white">Witaj, {{ session.username }}</span>
                <a class="nav-link" href="/logout">Wyloguj</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-3">
                <div class="list-group">
                    <a href="/dashboard" class="list-group-item list-group-item-action active">Dashboard</a>
                    <a href="/documents" class="list-group-item list-group-item-action">Dokumenty / OCR</a>
                    <a href="/fleet" class="list-group-item list-group-item-action">Flota Pojazdów</a>
                    <a href="/trips" class="list-group-item list-group-item-action">Ewidencja Przejazdów</a>
                    <a href="/hr" class="list-group-item list-group-item-action">HR / Kadry</a>
                </div>
            </div>
            <div class="col-md-9">
                <div class="row text-center">
                    <div class="col-md-4">
                        <div class="card bg-info text-white mb-4">
                            <div class="card-body">
                                <h3>{{ doc_count }}</h3>
                                <p>Dokumentów</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card bg-success text-white mb-4">
                            <div class="card-body">
                                <h3>{{ vehicle_count }}</h3>
                                <p>Pojazdów</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card bg-warning text-white mb-4">
                            <div class="card-body">
                                <h3>{{ trip_count }}</h3>
                                <p>Przejazdów</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card mt-4">
                    <div class="card-header bg-light">Ostatnie pojazdy</div>
                    <div class="card-body">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Nazwa</th>
                                    <th>Rejestracja</th>
                                    <th>Typ</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for v in vehicles %}
                                <tr>
                                    <td>{{ v.name }}</td>
                                    <td>{{ v.registration }}</td>
                                    <td>{{ v.type }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

DOCUMENTS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ALMID - Dokumenty</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">ALMID System</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/logout">Wyloguj</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-3">
                <div class="list-group">
                    <a href="/dashboard" class="list-group-item list-group-item-action">Dashboard</a>
                    <a href="/documents" class="list-group-item list-group-item-action active">Dokumenty / OCR</a>
                    <a href="/fleet" class="list-group-item list-group-item-action">Flota Pojazdów</a>
                    <a href="/trips" class="list-group-item list-group-item-action">Ewidencja Przejazdów</a>
                    <a href="/hr" class="list-group-item list-group-item-action">HR / Kadry</a>
                </div>
            </div>
            <div class="col-md-9">
                <div class="card mb-4">
                    <div class="card-header bg-primary text-white">Prześlij dokument</div>
                    <div class="card-body">
                        <form action="/upload" method="POST" enctype="multipart/form-data" class="row g-3">
                            <div class="col-md-6">
                                <input type="file" name="file" class="form-control" required>
                            </div>
                            <div class="col-md-4">
                                <select name="category" class="form-select">
                                    <option value="faktura">Faktura</option>
                                    <option value="umowa">Umowa</option>
                                    <option value="wniosek">Wniosek</option>
                                    <option value="inne">Inne</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <button type="submit" class="btn btn-primary w-100">Wyślij</button>
                            </div>
                        </form>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">Lista dokumentów</div>
                    <div class="card-body">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Nazwa</th>
                                    <th>Kategoria</th>
                                    <th>Data</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for doc in documents %}
                                <tr>
                                    <td>{{ doc.filename }}</td>
                                    <td>{{ doc.category }}</td>
                                    <td>{{ doc.upload_date }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

FLEET_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ALMID - Flota</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">ALMID System</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/logout">Wyloguj</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-3">
                <div class="list-group">
                    <a href="/dashboard" class="list-group-item list-group-item-action">Dashboard</a>
                    <a href="/documents" class="list-group-item list-group-item-action">Dokumenty / OCR</a>
                    <a href="/fleet" class="list-group-item list-group-item-action active">Flota Pojazdów</a>
                    <a href="/trips" class="list-group-item list-group-item-action">Ewidencja Przejazdów</a>
                    <a href="/hr" class="list-group-item list-group-item-action">HR / Kadry</a>
                </div>
            </div>
            <div class="col-md-9">
                <button class="btn btn-success mb-3" data-bs-toggle="modal" data-bs-target="#addVehicleModal">Dodaj Pojazd</button>
                
                <div class="card">
                    <div class="card-header">Flota ALMID</div>
                    <div class="card-body">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Nazwa</th>
                                    <th>Nr Rejestracyjny</th>
                                    <th>Typ</th>
                                    <th>Licznik Paliwa</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for v in vehicles %}
                                <tr>
                                    <td>{{ v.name }}</td>
                                    <td>{{ v.registration }}</td>
                                    <td>{{ v.type }}</td>
                                    <td>{{ v.fuel_counter }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal -->
    <div class="modal fade" id="addVehicleModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form action="/add_vehicle" method="POST">
                    <div class="modal-header">
                        <h5 class="modal-title">Dodaj nowy pojazd</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">Nazwa (np. Mercedes Sprinter)</label>
                            <input type="text" name="name" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Numer Rejestracyjny</label>
                            <input type="text" name="registration" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Typ</label>
                            <select name="type" class="form-select">
                                <option value="bus">Bus / Dostawczy</option>
                                <option value="osobowy">Osobowy</option>
                            </select>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Anuluj</button>
                        <button type="submit" class="btn btn-primary">Zapisz</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

TRIPS_TEMPLATE = '''<!DOCTYPE html><html><head><title>ALMID - Przejazdy</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head><body>
<nav class="navbar navbar-expand-lg navbar-dark bg-primary"><div class="container"><a class="navbar-brand" href="/">ALMID System</a></div></nav>
<div class="container mt-4"><div class="row"><div class="col-md-3"><div class="list-group"><a href="/dashboard" class="list-group-item list-group-item-action">Dashboard</a><a href="/trips" class="list-group-item list-group-item-action active">Ewidencja Przejazdów</a></div></div>
<div class="col-md-9"><h3>Ewidencja Przejazdów</h3><form action="/add_trip" method="POST" class="row g-3 mb-4"><div class="col-md-4"><select name="vehicle_id" class="form-select">{% for v in vehicles %}<option value="{{ v.id }}">{{ v.name }} ({{ v.registration }})</option>{% endfor %}</select></div>
<div class="col-md-3"><input type="text" name="driver" class="form-control" placeholder="Kierowca" required></div><div class="col-md-3"><input type="date" name="date" class="form-control" required></div><div class="col-md-2"><button type="submit" class="btn btn-primary w-100">Dodaj</button></div></form>
<table class="table"><thead><tr><th>Data</th><th>Pojazd</th><th>Kierowca</th><th>Dystans</th></tr></thead><tbody>{% for t in trips %}<tr><td>{{ t.date }}</td><td>{{ t.vehicle_name }}</td><td>{{ t.driver }}</td><td>{{ t.distance }} km</td></tr>{% endfor %}</tbody></table></div></div></div></body></html>'''

HR_TEMPLATE = '''<!DOCTYPE html><html><head><title>ALMID - HR</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head><body>
<nav class="navbar navbar-expand-lg navbar-dark bg-primary"><div class="container"><a class="navbar-brand" href="/">ALMID System</a></div></nav>
<div class="container mt-4"><div class="row"><div class="col-md-3"><div class="list-group"><a href="/dashboard" class="list-group-item list-group-item-action">Dashboard</a><a href="/hr" class="list-group-item list-group-item-action active">HR / Kadry</a></div></div>
<div class="col-md-9"><h3>Zaliczki / Urlopy</h3><form action="/add_hr" method="POST" class="row g-3 mb-4"><div class="col-md-4"><input type="text" name="employee" class="form-control" placeholder="Pracownik" required></div>
<div class="col-md-3"><select name="type" class="form-select"><option value="zaliczka">Zaliczka</option><option value="urlop">Urlop</option></select></div><div class="col-md-3"><input type="number" name="amount" class="form-control" placeholder="Kwota (dla zaliczek)"></div><div class="col-md-2"><button type="submit" class="btn btn-primary w-100">Dodaj</button></div></form>
<table class="table"><thead><tr><th>Pracownik</th><th>Typ</th><th>Kwota/Data</th><th>Status</th></tr></thead><tbody>{% for r in records %}<tr><td>{{ r.employee_name }}</td><td>{{ r.type }}</td><td>{{ r.amount or r.date_from }}</td><td>{{ r.status }}</td></tr>{% endfor %}</tbody></table></div></div></div></body></html>'''
