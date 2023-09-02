import base64
import os
import uuid
from functools import wraps

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from flask_htmx import HTMX
from flask_oauthlib.client import OAuth
from jinja2_fragments.flask import render_block
from marshmallow import Schema, fields, ValidationError

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


class FileSchema(Schema):
    filename = fields.String(required=True)
    content = fields.String(required=True)


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
def ui_upload_file(username):
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


def save_files(user_folder, uploads):
    for upload in uploads:
        filename = os.path.join(user_folder, upload['filename'])
        content = base64.b64decode(upload['content'])
        with open(filename, 'wb') as f:
            f.write(content)


@app.route('/api/upload', methods=['PUT'])
@require_auth
def api_upload_file(username):
    folder = os.path.join(UPLOAD_FOLDER, username)
    return store_uploads(folder)


@app.route('/api/upload_temporary', methods=['PUT'])
@require_auth
def api_upload_file_temporary(username):
    temp_token = str(uuid.uuid4())
    folder = os.path.join(UPLOAD_FOLDER, username, temp_token)
    error, code = store_uploads(folder)
    if code != 200:
        return error, code
    else:
        return jsonify({"token": temp_token}), 200


def store_uploads(folder):
    request_data = request.json
    schema = FileSchema(many=True)
    try:
        result = schema.load(request_data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
        save_files(folder, result)
    except Exception as err:
        return jsonify({"error": str(err)}), 500
    return jsonify({"success": True}), 200


@github.tokengetter
def get_github_oauth_token():
    return session.get('github_token')


def main():
    app.run(debug=True, port=8000)


if __name__ == '__main__':
    main()
