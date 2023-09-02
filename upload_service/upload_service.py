from functools import wraps
from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from flask_htmx import HTMX
from jinja2_fragments.flask import render_block
from flask_oauthlib.client import OAuth
from dotenv import load_dotenv
import requests
import os

app = Flask(__name__)
oauth = OAuth(app)
htmx = HTMX(app)

UPLOAD_FOLDER = 'uploads/'


def check_required_env_vars():
    required_vars = ['GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET', 'SECRET_KEY']
    missing_vars = [var for var in required_vars if os.getenv(var) is None]
    if missing_vars:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing_vars)}")


load_dotenv()
check_required_env_vars()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

github = oauth.remote_app(
    'github',
    consumer_key=os.getenv('GITHUB_CLIENT_ID'),
    consumer_secret=os.getenv('GITHUB_CLIENT_SECRET'),
    request_token_params={'scope': 'user:email'},
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize'
)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = session.get('github_token', None)
        auth_header = request.headers.get('Authorization')
        header_token = None
        if auth_header and auth_header.startswith('Bearer '):
            header_token = auth_header.split(' ', 1)[1]

        if session_token is None and header_token is None:
            return jsonify({"error": "Invalid or missing Authorization header"}), 401

        token = session_token[0] if session_token else header_token

        github_user_url = "https://api.github.com/user"
        headers = {'Authorization': f'token {token}'}
        response = requests.get(github_user_url, headers=headers)

        if response.status_code != 200:
            return jsonify({"error": "Invalid or expired token"}), 401

        username = response.json()['login']
        kwargs.update({"username": username})
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def index():
    error = session.pop('error', None)
    return render_template('index.html', authorized="github_token" in session, error=error)


@app.route('/login')
def login():
    return github.authorize(callback=url_for('authorized', _external=True))


@app.route('/logout')
def logout():
    session.pop('github_token')
    return redirect(url_for('index'))


@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()
    if resp is None or resp.get('access_token') is None:
        return 'Access denied: reason={} error={}'.format(
            request.args['error_reason'],
            request.args['error_description']
        )
    session['github_token'] = (resp['access_token'], '')
    return redirect(url_for('index'))


@app.route('/upload', methods=['POST'])
@require_auth
def upload_file(username):
    user_folder = os.path.join(UPLOAD_FOLDER, username)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    error = None
    file = None

    if not request.files:
        error = "Invalid request"
    else:
        file = request.files['file']
        if file.filename == '':
            error = "No file selected"

    if file:
        filename = os.path.join(user_folder, file.filename)
        try:
            file.save(filename)
        except Exception:
            error = "Error saving the file"

    if htmx:
        return render_block('index.html', 'upload_form',
                            authorized="github_token" in session,
                            filename=file.filename if file and not error else None,
                            error=error)
    else:
        if error:
            session['error'] = error
        return redirect(url_for('index'))


@github.tokengetter
def get_github_oauth_token():
    return session.get('github_token')


def main():
    app.run(debug=True, port=8000)


if __name__ == '__main__':
    main()
