from flask import Flask, render_template, redirect, url_for
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-almid-2026')

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ALMID System Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container">
                <a class="navbar-brand" href="/">ALMID Dashboard</a>
            </div>
        </nav>
        <div class="container mt-5">
            <div class="row">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h3>System Zarządzania ALMID Sp. z o.o.</h3>
                        </div>
                        <div class="card-body">
                            <h5>Witaj w systemie zarządzania dokumentami, flotą i HR</h5>
                            <p>System w budowie - podstawowa wersja działa poprawnie!</p>
                            <hr>
                            <h6>Funkcje (w przygotowaniu):</h6>
                            <ul>
                                <li>✅ Zarządzanie użytkownikami</li>
                                <li>✅ Upload i przetwarzanie dokumentów (PDF, JPG, PNG)</li>
                                <li>✅ OCR - rozpoznawanie tekstu z dokumentów</li>
                                <li>✅ AI - automatyczna klasyfikacja dokumentów</li>
                                <li>✅ Zarządzanie flotą pojazdów</li>
                                <li>✅ System HR - urlopy, zaliczki, ewidencja czasu</li>
                                <li>✅ Dashboard z raportami i statystykami</li>
                            </ul>
                            <div class="alert alert-success mt-3">
                                <strong>Status:</strong> Aplikacja uruchomiona pomyślnie na Render.com
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return {'status': 'ok', 'message': 'ALMID System is running'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
