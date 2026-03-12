from flask import Flask, redirect, url_for, render_template, request, jsonify, send_file, abort, session, make_response
from flask_session import Session
from playwright.sync_api import sync_playwright
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "secret123"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
phone_loc = "phone_contracts"
laptop_loc = "laptop_contracts"



# ── LOGIN REQUIRED DECORATOR ──────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated


def load_users(filepath="users.txt"):
    """
    Load users from a text file.
    Each line: username:password:display_name
    Returns a dict: { username: { "password": ..., "display_name": ... } }
    """
    users = {}
    if not os.path.exists(filepath):
        return users
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":", 2)
            if len(parts) == 3:
                uname, pwd, display = parts
                users[uname.strip().lower()] = {
                    "password": pwd.strip(),
                    "display_name": display.strip()
                }
    return users


# ── PUBLIC ROUTES (no login needed) ──────────────────────────────────────────

@app.route('/')
def home():
    # If already logged in, skip the login page
    if session.get("username"):
        return redirect(url_for('main_dashboard'))
    return render_template('login.html', the_title='FGF TechCare Login')


@app.route('/login.html', methods=['POST'])
def login():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()
    print("LOGIN ATTEMPT:", username, password)

    users = load_users()
    user = users.get(username)

    if user and user["password"] == password:
        session["username"] = username
        session["display_name"] = user["display_name"]
        print("SESSION AFTER SET:", dict(session))

        response = make_response(redirect(url_for('main_dashboard')))
        response.set_cookie("agent_name", user["display_name"], samesite="Lax")
        return response
    else:
        return render_template('login.html', the_title='FGF TechCare Login', error="Invalid username or password.")


@app.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for('home')))
    response.delete_cookie("agent_name")
    return response


# ── PROTECTED ROUTES (login required) ────────────────────────────────────────

@app.route('/dashboard')
@login_required
def main_dashboard():
    username = session.get("username")
    display_name = session.get("display_name", "")
    return render_template('dashboard.html', the_title='Dashboard', username=username, display_name=display_name)


@app.route('/phone-contract')
@login_required
def phone_contract():
    username = session.get("username")
    display_name = session.get("display_name", "")
    print("USERNAME:", username, "DISPLAY NAME:", display_name)
    return render_template('phone_contract.html', the_title='Phone Contract', username=username, display_name=display_name)


@app.route('/laptop-contract')
@login_required
def laptop_contracts():
    return render_template('laptop_contract.html', the_title='Laptop Use Policy')


@app.route("/phone-submit", methods=["POST"])
@login_required
def submit():
    data = request.json
    agent_name = data.get("name", "Contract")
    phone_model = data.get("phone_model", "Phone")

    save_dir = phone_loc
    os.makedirs(save_dir, exist_ok=True)

    file_name = f"{agent_name} - {phone_model}"
    pdf_path = f"{save_dir}/{file_name}.pdf"

    html_content = data.get("html")
    if not html_content:
        return jsonify({"status": "error", "message": "No HTML content provided"}), 400

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        browser.close()

    return jsonify({"status": "success", "file": pdf_path})

@app.route("/laptop-submit", methods=["POST"])
@login_required
def laptop_submit():
    data = request.json
    agent_name = data.get("name", "Contract")
    laptop_model = data.get("laptop_name", "laptop")

    save_dir = laptop_loc
    os.makedirs(save_dir, exist_ok=True)

    file_name = f"{agent_name} - {laptop_model}"
    pdf_path = f"{save_dir}/{file_name}.pdf"

    html_content = data.get("html")
    if not html_content:
        return jsonify({"status": "error", "message": "No HTML content provided"}), 400

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        browser.close()

    return jsonify({"status": "success", "file": pdf_path})



@app.route("/download")
@login_required
def download():
    """Serve the generated PDF as a file download."""
    file_path = request.args.get("file", "")

    abs_path = os.path.abspath(file_path)
    contracts_dir = os.path.abspath(phone_loc)

    # Normalize for Windows case differences
    if not abs_path.lower().startswith(contracts_dir.lower()):
        abort(403)

    if not os.path.exists(abs_path):
        abort(404)

    return send_file(
        abs_path,
        as_attachment=True,
        download_name=os.path.basename(abs_path),
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)