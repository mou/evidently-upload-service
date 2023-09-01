from functools import wraps
from flask import Flask, redirect, url_for, session, request, jsonify
from flask_oauthlib.client import OAuth
from dotenv import load_dotenv
import requests
import os

app = Flask(__name__)
oauth = OAuth(app)

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


def require_bearer(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header is None or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Invalid or missing Authorization header"}), 401

        token = auth_header.split(' ', 1)[1]
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
    return 'Welcome to the file upload service.'


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
@require_bearer
def upload_file(username):
    user_folder = os.path.join(UPLOAD_FOLDER, username)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    if not request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = os.path.join(user_folder, file.filename)
        try:
            file.save(filename)
            return jsonify({"success": True}), 200
        except Exception:
            return jsonify({"error": "Error saving the file"}), 500


@github.tokengetter
def get_github_oauth_token():
    return session.get('github_token')


def main():
    app.run(debug=True, port=8080)


if __name__ == '__main__':
    main()
