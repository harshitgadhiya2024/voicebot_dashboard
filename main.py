"""
    In this file handling all flask api route and maintain all of operation and sessions
"""

import os
import random
import uuid
from datetime import datetime, timedelta
from functools import wraps
from PIL import Image
import jwt
from flask import (flash, Flask, redirect, render_template, request,
                   session, url_for, send_file, jsonify, send_from_directory)
from flask_cors import CORS
from flask_mail import Mail
from string import ascii_uppercase
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from constant import constant_data
from operations.common_func import (password_validation, get_timestamp, validate_phone_number, logger_con, sending_email_mail)
from operations.mongo_connection import (mongo_connect, data_added, find_all_data, find_spec_data, update_mongo_data)
import json, requests
import pandas as pd
import audioread

secreat_id = uuid.uuid4().hex

# create a flask app instance
app = Flask(__name__)

# Apply cors policy in our app instance
CORS(app)

# setup all config variable
app.config["enviroment"] = constant_data.get("enviroment", "dev")
app.config["SECRET_KEY"] = secreat_id
app.config['MAIL_SERVER'] = constant_data["mail_configuration"].get("server_host")
app.config['MAIL_PORT'] = int(constant_data["mail_configuration"].get("server_port"))
app.config['MAIL_USERNAME'] = constant_data["mail_configuration"].get("server_username")
app.config['MAIL_PASSWORD'] = constant_data["mail_configuration"].get("server_password")
app.config['MAIL_USE_SSL'] = True
app.config["userbase_recording"] = {}
app.config['voice_folder'] = "static/uploaded_audio/"
app.config["voice_details"] = {}

# handling our application secure type like http or https
secure_type = constant_data["secure_type"]

# create mail instance for our application
mail = Mail(app)

# logger & MongoDB connection
logger_con(app=app)
client = mongo_connect(app=app)
db = client["voicebot"]

# allow only that image file extension
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif' 'svg'}

def allowed_photos(filename):
    """
    checking file extension is correct or not

    :param filename: file name
    :return: True, False
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calling_happens(voice_file_id, numbers, max_retry, campaign_name,retry_wait_time):
    try:
        app.logger.debug("coming to call api")
        callback_url = "http://13.201.1.150/voice_callback"
        cli_number = "8062364086"
        url = f"https://panelv2.cloudshope.com/api/voice_call?voice_file_id={voice_file_id}&numbers={numbers}&credit_type_id=23&max_retry={max_retry}&retry_after=1&campaign_name={campaign_name}&retry_wait_time={retry_wait_time}&callback_event={callback_url}&callback_url={callback_url}&cli_number={cli_number}"

        payload = json.dumps({})
        headers = {
            'Authorization': 'Bearer 356950|bF0Z79Rj0BDUWcklS3uXTjPWqzqC9QBXbEkKwOuY',
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        response_text = json.loads(response.text)
        
        app.logger.debug(f"response for calling api: {response.text}")
        flag = True
        status = response_text.get("status")
        if status=="failed":
            flag=False
        campaign_id = response_text.get("Campaign_id", "")
        return flag, campaign_id

    except Exception as e:
        app.logger.debug(f"Error in calling happens function: {e}")

def get_audio_duration(file_path):
    with audioread.audio_open(file_path) as f:
        duration = f.duration
    return duration

def upload_api(filepath, filename, exten):
    try:
        url = f"https://panelv2.cloudshope.com/api/upload_voice_clip?voice_clip_path={filepath}&file_name={filename}&extension={exten}"

        payload = {}
        headers = {
            'Authorization': 'Bearer 356950|bF0Z79Rj0BDUWcklS3uXTjPWqzqC9QBXbEkKwOuY',
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        app.logger.debug(f"your audio upload request is: {response.text}")
        response_data = json.loads(response.text)
        get_id = response_data.get("voice_clip_id")

        return True, get_id
        
    except Exception as e:
        app.logger.debug(f"Error in upload audio api: {e}")
        return False, "none"


def token_required(func):
    # decorator factory which invoks update_wrapper() method and passes decorated function as an argument
    @wraps(func)
    def decorated(*args, **kwargs):
        login_dict = session.get("login_dict", "available")
        # token = app.config["mapping_user_dict"].get(login_dict.get("id", "nothing"), {}).get("token", False)
        if login_dict == "available":
            app.logger.debug("please first login in your app...")
            flash("Please login first...", "danger")
            return redirect(url_for('login', _external=True, _scheme=secure_type))
        return func(*args, **kwargs)
    return decorated

def convert_to_webp(input_image_path, output_image_path):
    # Open the image file
    with Image.open(input_image_path) as img:
        # Convert the image to WebP format
        img.save(output_image_path, 'WEBP')

    return "complete"

def generate_token(username):
    try:
        expiration_time = datetime.now() + timedelta(minutes=30)
        payload = {
            'username': username,
            'exp': expiration_time
        }
        token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm='HS256')
        return token
    except Exception as e:
        app.logger.debug(f"error in generate token {e}")

############################ Login operations ##################################

@app.route('/download/<filename>')
def download_image_path(filename):
    return send_from_directory(app.config['voice_folder'], filename, as_attachment=True)

@app.route("/", methods=["GET", "POST"])
def login():
    """
    In this route we can handling student, teacher and admin login process
    :return: login template
    """
    try:
        app.logger.debug("coming in login api route")
        login_dict = session.get("login_dict", "nothing")
        if login_dict != "nothing":
            return redirect(url_for('dashboard', _external=True, _scheme=secure_type))

        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]

            di = {"username": email}
            di_email = {"email": email}
            user_all_data = find_spec_data(app, db, "user_data", di)
            user_email_data = find_spec_data(app, db, "user_data", di_email)
            user_all_data = list(user_all_data)
            user_email_data = list(user_email_data)

            if len(user_all_data) == 0 and len(user_email_data) == 0:
                flash("Please use correct credential..", "danger")
                return render_template("login.html")
            elif len(user_all_data)>0:
                user_all_data = user_all_data[0]
                if check_password_hash(user_all_data["password"], password):
                    username = user_all_data["username"]
                    email = user_all_data["email"]
                    user_id = user_all_data["user_id"]
                    token = user_all_data["token"]
                    session["login_dict"] = {"username": username, "email": email, "user_id": user_id, "token": token}
                    app.logger.debug(f"Login Dict in session: {session.get('login_dict')}")
                    return redirect(url_for("dashboard", _external=True, _scheme=secure_type))
                else:
                    flash("Please use correct credential..", "danger")
                    return render_template("login.html")
            else:
                user_email_data = user_email_data[0]
                if check_password_hash(user_email_data["password"], password):
                    username = user_email_data["username"]
                    email = user_email_data["email"]
                    user_id = user_email_data["user_id"]
                    token = user_email_data["token"]
                    session["login_dict"] = {"username": username, "email": email, "user_id": user_id, "token": token}
                    app.logger.debug(f"Login Dict in session: {session.get('login_dict')}")
                    return redirect(url_for("dashboard", _external=True, _scheme=secure_type))
                else:
                    flash("Please use correct credential..", "danger")
                    return render_template("login.html")

        else:
            return render_template("login.html")

    except Exception as e:
        app.logger.debug(f"Error in login route: {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('login', _external=True, _scheme=secure_type))

@app.route("/otp_verification", methods=["GET", "POST"])
def otp_verification():
    """
    That funcation can use otp_verification and new_password set link generate
    """

    try:
        email = session.get("otp_dict", {}).get("email", "")
        if request.method == "POST":
            get_otp = request.form["otp"]
            get_otp = int(get_otp)
            send_otp = session.get("otp", "")
            if get_otp:
                login_dict = session.get("login_dict", "nothing")
                type = login_dict["type"]
                flash("Login Successfully...", "success")
                return redirect(url_for(f'{type}_dashboard', _external=True, _scheme=secure_type))
            else:
                flash("OTP is wrong. Please enter correct otp...", "danger")
                return render_template("authentication/otp_verification.html")
        else:
            if email:
                otp = random.randint(100000, 999999)
                session["otp"] = otp
                server_host = app.config['MAIL_SERVER']
                server_port = app.config['MAIL_PORT']
                server_username = app.config['MAIL_USERNAME']
                server_password = app.config['MAIL_PASSWORD']
                subject_title = "OTP Received"
                mail_format = f"Hello There,\n We hope this message finds you well. As part of our ongoing commitment to ensure the security of your account, we have initiated a verification process.\nYour One-Time Password (OTP) for account verification is: [{otp}]\nPlease enter this OTP on the verification page to complete the process. Note that the OTP is valid for a limited time, so we recommend entering it promptly.\nIf you did not initiate this verification or have any concerns regarding your account security, please contact our support team immediately at help@codescatter.com\n\nThank you for your cooperation.\nBest regards,\nCodescatter"
                html_format = f'<p>Hello There,</p><p>We hope this message finds you well. As part of our ongoing commitment to ensure the security of your account, we have initiated a verification process.</p><p>Your One-Time Password (OTP) for account verification is: <h2><b>{otp}</h2></b></p><p>Please enter this OTP on the verification page to complete the process. Note that the OTP is valid for a limited time, so we recommend entering it promptly.</p><p>If you did not initiate this verification or have any concerns regarding your account security, please contact our support team immediately at help@codescatter.com</p><p>Thank you for your cooperation.</p><p>Best regards,<br>Codescatter</p>'
                attachment_all_file = []
                # sending_email_mail(app, [email], subject_title, mail_format, html_format, server_username,
                #                    server_password, server_host, int(server_port), attachment_all_file)
            return render_template("authentication/otp_verification.html")

    except Exception as e:
        app.logger.debug(f"Error in otp verification route: {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('otp_verification', _external=True, _scheme=secure_type))

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        db = client["college_management"]
        if request.method == "POST":
            email = request.form["email"]
            all_login_data = find_spec_data(app, db, "login_mapping", {"email": email})
            all_login_data = list(all_login_data)
            if len(all_login_data)==0:
                flash("Entered email does not exits Please try with different mail...", "danger")
                return render_template("authentication/forgat-password.html")
            else:
                login_data = list(all_login_data)[0]
                type = login_data.get("type", "student")
                id_data = login_data.get("username", "")

                server_host = app.config['MAIL_SERVER']
                server_port = app.config['MAIL_PORT']
                server_username = app.config['MAIL_USERNAME']
                server_password = app.config['MAIL_PASSWORD']
                subject_title = "OTP Received"
                mail_format = f"Hello There,\n I hope this email finds you well. It has come to our attention that you have requested to reset your password for your APPIACS account. If you did not initiate this request, please disregard this email.\nTo reset your password,\nplease follow the link below: \nClick Here \nPlease note that this link is valid for the next 30 Minutes. After this period, you will need to submit another password reset request.\nIf you continue to experience issues or did not request a password reset, please contact our support team for further assistance.\nThank you for using Website.\n\nBest regards,\nHarshit Gadhiya"
                html_format = f"<p>Hello There,</p><p> I hope this email finds you well. It has come to our attention that you have requested to reset your password for your APPIACS account. If you did not initiate this request, please disregard this email.</p><p>To reset your password,</p><p>please follow the link below: </p><p><a href='http://13.201.1.150/update_password?id={type}-*{id_data}'><b>Click Here</b></a></p><p>Please note that this link is valid for the next 30 Minutes. After this period, you will need to submit another password reset request.</p><p>If you continue to experience issues or did not request a password reset, please contact our support team for further assistance.</p><p>Thank you for using the Website.</p><br><p>Best regards,<br>Harshit Gadhiya</p>"
                attachment_all_file = []
                sending_email_mail(app, [email], subject_title, mail_format, html_format, server_username,
                                   server_password, server_host, int(server_port), attachment_all_file)
                flash("Reset password mail sent successfully...", "success")
                return render_template("authentication/forgot-password.html")
        else:
            return render_template("authentication/forgot-password.html")

    except Exception as e:
        app.logger.debug(f"Error in add teacher data route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('student_mail', _external=True, _scheme=secure_type))

@app.route("/update_password", methods=["GET", "POST"])
def update_password():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        db = client["college_management"]
        id = request.args.get("id", "nothing")
        if request.method == "POST":
            id = session["data_id"]
            spliting_obj = id.split("-*")
            username_data = spliting_obj[-1]
            type = spliting_obj[0]
            password = request.form["password"]
            con_password = request.form["con_password"]
            if not password_validation(app=app, password=password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("forgat-password.html", password=password, con_password=con_password)

            if not password_validation(app=app, password=con_password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("forgat-password.html", password=password, con_password=con_password)

            if password==con_password:
                password = generate_password_hash(password)
                condition_dict = {"type": type, "username": username_data}
                update_mongo_data(app, db, "user_data", condition_dict, {"password": password})
                update_mongo_data(app, db, "login_mapping", condition_dict, {"password": password})
                flash("Password Reset Successfully...", "success")
                return redirect(url_for('login', _external=True, _scheme=secure_type))
            else:
                flash("Password or Confirmation Password Does Not Match. Please Enter Correct Details", "danger")
                return render_template("forgat-password.html", password=password, con_password=con_password)
        else:
            session["data_id"] = id
            return render_template("authentication/update_password.html", id=id)

    except Exception as e:
        app.logger.debug(f"Error in add teacher data route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('student_mail', _external=True, _scheme=secure_type))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    That funcation was logout session and clear user session
    """

    try:
        session.clear()
        app.logger.debug(f"session is {session}")
        return redirect(url_for('login', _external=True, _scheme=secure_type))

    except Exception as e:
        app.logger.debug(f"error is {e}")
        return redirect(url_for('login', _external=True, _scheme=secure_type))

@app.route("/register_calling_system", methods=["GET", "POST"])
def register_calling_system():
    try:
        if request.method=="POST":
            fullname = request.form["fullname"]
            username = request.form["username"]
            phone = request.form["phone"]
            company_name = request.form["company_name"]
            email = request.form["email"]
            password = request.form["password"]

            spliting_email = email.split("@")[-1]
            if "." not in spliting_email:
                flash("Email is not valid...", "danger")
                return render_template("register.html", fullname=fullname, username=username, phone=phone, company_name=company_name,
                                       email=email, password=password)
            
            all_user_data = find_all_data(app, db, "user_data")
            get_all_username = [user_data["username"] for user_data in all_user_data]
            if username in get_all_username:
                flash("Username already exits...", "danger")
                return render_template("register.html", fullname=fullname, username=username, phone=phone, company_name=company_name,
                                       email=email, password=password)
            
            all_email_data = find_all_data(app, db, "user_data")
            get_all_email = [user_data["email"] for user_data in all_email_data]
            if email in get_all_email:
                flash("Email already exits...", "danger")
                return render_template("register.html", fullname=fullname, username=username, phone=phone, company_name=company_name,
                                       email=email, password=password)
            
            if not password_validation(app=app, password=password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("register.html", fullname=fullname, username=username, phone=phone, company_name=company_name,
                                       email=email, password=password)
            
            get_phone_val = validate_phone_number(app=app, phone_number=phone)
            if get_phone_val == "invalid number":
                flash("Please enter correct contact no.", "danger")
                return render_template("register.html", fullname=fullname, username=username, phone=phone, company_name=company_name,
                                       email=email, password=password)
            
            password = generate_password_hash(password)
            all_user_data = find_all_data(app, db, "user_data")
            get_all_userid = [user_data["user_id"] for user_data in all_user_data]    

            flag = True
            while flag:
                user_id = random.randint(1000000000000000, 9999999999999999)
                if str(user_id) not in get_all_userid:
                    flag = False

            register_dict = {
                "user_id": user_id,
                "fullname": fullname,
                "username": username,
                "email": email,
                "phone_number": phone,
                "password": password,
                "company_name": company_name,
                "status": "activate",
                "token": 10
            }  
            app.config["userbase_recording"][username]={}
            app.config["userbase_recording"][username]["last_number"] = 1

            data_added(app, db, "user_data", register_dict) 
            points_mapping_dict = {"user_id": user_id, "points": 10, "campaigns": 0, "calls": 0}
            app.config["voice_details"][user_id] = points_mapping_dict
            data_added(app, db, "points_mapping", points_mapping_dict)
            flash("Register Successfully...", "success")  
            return redirect("/")       
        else:
            return render_template("register.html")

    except Exception as e:
        app.logger.debug(f"Error in register route: {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('register', _external=True, _scheme=secure_type))

@app.route('/dashboard', methods=['GET', 'POST'])
@token_required
def dashboard():
    try:
        login_dict = session.get("login_dict", {})
        username = login_dict["username"]
        user_id = login_dict["user_id"]
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]
        campaigns = user_points[0]["campaigns"]
        calls = user_points[0]["calls"]
        return render_template("index.html", username=username, points=points, calls=calls, campaigns=campaigns)

    except Exception as e:
        app.logger.debug(f"error is {e}")
        return redirect(url_for('login', _external=True, _scheme=secure_type))
    
@app.route("/clean_logs", methods=["GET", "POST"])
def clean_logs():
    try:
        file_path = os.path.abspath("server.log")
        # Delete the file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)

        # Recreate the file
        with open(file_path, 'w'):
            pass

        return redirect(url_for('view_logs', _external=True, _scheme=secure_type))

    except Exception as e:
        app.logger.debug(f"Error in main route: {e}")
        return redirect(url_for('view_logs', _external=True, _scheme=secure_type))
    
@app.route('/save_audio', methods=['GET', 'POST'])
@token_required
def save_audio():
    try:
        data_status = "no_data"
        login_dict = session.get("login_dict", {})
        username = login_dict["username"]
        last_number = 1
        try:
            last_number = app.config["userbase_recording"][username]["last_number"]
        except:
            pass

        audio_file = request.files['audio']
        userfile_name = username+str(last_number)+".wav"
        filename = app.config["voice_folder"]+userfile_name
        app.config["userbase_recording"][username] = {}
        app.config["userbase_recording"][username]["last_number"] = last_number+1
        audio_file.save(filename)
        download_file_path = f"http://13.201.1.150/download/{userfile_name}"

        res_upload, voice_id = upload_api(download_file_path, userfile_name, "wav")
        # res_upload = True
        if res_upload:

            get_duraction = get_audio_duration(filename)
            get_duraction = int(get_duraction)
            get_cre = int(get_duraction/28)
            get_cre = get_cre+1
            credits = get_cre*2

            register_dict = {
                "user_id": login_dict["user_id"],
                "audio_id": voice_id,
                "audio_file": filename,
                "duration": get_duraction,
                "credits": credits,
                "download_file_path": download_file_path,
                "status": "active",
                "file_status": "active"
            }

            data_added(app, db, "audio_store", register_dict)
            all_audio_data = find_spec_data(app, db, "audio_store", {"user_id": login_dict["user_id"]})
            all_audio_list = []
            for var in all_audio_data:
                if var["file_status"] == "active":
                    del var["_id"]
                    all_audio_list.append(var)
            
            if len(all_audio_list)!=0:
                data_status = "data"

            flash("Record audio uploaded successfully", "success")
        else:
            flash("Please try again...", "danger")

        return render_template("audio_data.html", all_audio_list=all_audio_list,data_status=data_status,username=username)

    except Exception as e:
        app.logger.debug(f"error in save audio route {e}")
        return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))

@app.route('/upload_audio_file', methods=['GET', 'POST'])
@token_required
def upload_audio_file():
    try:
        data_status = "no_data"
        login_dict = session.get("login_dict", {})
        username = login_dict["username"]
        last_number = 1
        try:
            last_number = app.config["userbase_recording"][username]["last_number"]
        except:
            pass

        audio_file = request.files['fileupload']
        userfile_name = username+str(last_number)+".wav"
        filename = app.config["voice_folder"]+userfile_name
        app.config["userbase_recording"][username] = {}
        app.config["userbase_recording"][username]["last_number"] = last_number+1
        audio_file.save(filename)
        download_file_path = f"http://13.201.1.150/download/{userfile_name}"

        res_upload,voice_id = upload_api(download_file_path, userfile_name, "wav")
        # res_upload = True
        if res_upload:
            get_duraction = get_audio_duration(filename)
            get_duraction = int(get_duraction)
            get_cre = int(get_duraction/28)
            get_cre = get_cre+1
            credits = get_cre*2
            
            register_dict = {
                "user_id": login_dict["user_id"],
                "audio_id": voice_id,
                "audio_file": filename,
                "duration": get_duraction,
                "credits": credits,
                "download_file_path": download_file_path,
                "status": "active",
                "file_status": "active"
            }

            data_added(app, db, "audio_store", register_dict)
            all_audio_data = find_spec_data(app, db, "audio_store", {"user_id": login_dict["user_id"]})
            all_audio_list = []
            for var in all_audio_data:
                if var["file_status"] == "active":
                    del var["_id"]
                    all_audio_list.append(var)
            
            if len(all_audio_list)!=0:
                data_status = "data"

            flash("Audio uploaded successfully", "success")
        else:
            flash("Please try again...", "danger")

        return render_template("audio_data.html", all_audio_list=all_audio_list,data_status=data_status,username=username)

    except Exception as e:
        app.logger.debug(f"error in save audio route {e}")
        return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))

@app.route('/upload_audio', methods=['GET', 'POST'])
@token_required
def upload_audio():
    try:
        login_dict = session.get("login_dict", {})
        username = login_dict["username"]
        all_audio_data = find_spec_data(app, db, "audio_store", {"user_id": login_dict["user_id"]})
        all_audio_list = []
        data_status = "no_data"
        for var in all_audio_data:
            if var["file_status"] == "active":
                del var["_id"]
                all_audio_list.append(var)

        if len(all_audio_list)!=0:
            data_status = "data"

        return render_template("audio_data.html", all_audio_list=all_audio_list, data_status=data_status,username=username)

    except Exception as e:
        app.logger.debug(f"error in upload audio route {e}")
        return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))
    
@app.route('/bulk_calling', methods=['GET', 'POST'])
@token_required
def bulk_calling():
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        all_audio_data = find_spec_data(app, db, "audio_store", {"user_id": login_dict["user_id"]})
        all_audio_ids = []
        for var in all_audio_data:
            if var["file_status"] == "active":
                all_audio_ids.append(var["audio_id"])
        if request.method=="POST":
            campaign_name = request.form["campaign_name"]
            voiceid = request.form["voiceid"]
            numberfile = request.files['numberfile']
            max_retry = request.form["max_retry"]
            retry_time = request.form["retry_time"]
            app.logger.debug("all data fetched")

            audio_user_data = find_spec_data(app, db, "audio_store", {"audio_id", int(voiceid)})
            audio_user_data = list(audio_user_data)
            points_min = audio_user_data[0]["credits"]

            file_name = numberfile.filename
            filepath = f"static/upload/{file_name}"
            numberfile.save(filepath)
            app.logger.debug("file save successfully")
            exten = file_name.split(".")[-1]
            if exten=="csv":
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
            
            all_numbers = list(df["numbers"])
            user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
            user_points = list(user_points)
            points = user_points[0]["points"]
            if len(all_numbers)>points:
                flash("Please recharge your account, don't enough points you have...", "warning")
            else:
                all_numbers_string = ""
                for var in all_numbers:
                    all_numbers_string+=f",{var}"

                flag_mapping,campaign_id  = calling_happens(voiceid, all_numbers_string, max_retry, campaign_name, retry_time)
                app.logger.debug("completed")
                if flag_mapping:
                    register_dict_calling = {
                        "user_id": user_id,
                        "campaign_id": str(campaign_id),
                        "total_calls": len(all_numbers),
                        "total_answered": 0,
                        "total_busy": 0,
                        "timestamp": get_timestamp(app)
                    }
                    data_added(app, db, "campaign_details", register_dict_calling)

                    for number_call in all_numbers:
                        new_mapping_dict = {
                            "user_id": user_id,
                            "campaign_id": str(campaign_id),
                            "number_id": "-",
                            "number": str(number_call),
                            "answer_time": "-",
                            "status": "-",
                            "extension": "-",
                            "timestamp": get_timestamp(app)
                        }
                        data_added(app, db, "user_campaign_details", new_mapping_dict)

                    all_points_data = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
                    all_points_data = list(all_points_data)
                    campaigns_total = all_points_data[0]["campaigns"]
                    totalcalls = all_points_data[0]["calls"]

                    points_data_mapping = {"campaign_id": str(campaign_id), "points_min": points_min}
                    data_added(app, db, "data_points_mapping", points_data_mapping)

                    update_mongo_data(app, db, "points_mapping", {"user_id": user_id}, {"campaigns": int(campaigns_total)+1, "calls": int(totalcalls)+len(all_numbers)})

                    flash("Calling start successfully...", "success")
                else:
                    flash("Voice call Schedulled Time between 7AM to 7PM")
            return render_template("calling_system.html", all_audio_ids=all_audio_ids, username=username)
        else:
            return render_template("calling_system.html", all_audio_ids=all_audio_ids, username=username)
        
    except Exception as e:
        app.logger.debug(f"error in upload audio route {e}")
        return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
    
@app.route('/sample_file', methods=['GET', 'POST'])
def sample_file():
    try:
        server_file_name = "static/sample_file/sample_number_file.csv"
        file = os.path.abspath(server_file_name)
        return send_file(file, as_attachment=True)

    except Exception as e:
        app.logger.debug(f"error in sample file download {e}")
        return redirect(url_for('sample_file', _external=True, _scheme=secure_type))
    
@app.route('/voice_callback', methods=['GET', 'POST'])
def voice_callback():
    try:
        number_id = request.args.get("number_id")
        campaign_id = request.args.get("campaign_id")
        answer_time = request.args.get("answer_time")
        status = request.args.get("status")
        extention = request.args.get("extention")
        number = request.args.get("number")
        number = number[1:]
        app.logger.debug(f"data for calling: number_id:{number_id}, campaign_id: {campaign_id}, answer: {answer_time}, status: {status}, extension: {extention}, number: {number}")
        if status=="ANSWERED" or status=="BUSY":
            all_user_campaign = find_spec_data(app, db, "campaign_details", {"campaign_id": campaign_id})
            all_user_campaign = list(all_user_campaign)
            user_id = all_user_campaign[0]["user_id"]

            all_user_data = find_spec_data(app, db, "points_mapping", {"user_id": int(user_id)})
            all_user_data = list(all_user_data)
            points = all_user_data[0]["points"]

            all_point_user_data = find_spec_data(app, db, "data_points_mapping", {"campaign_id": campaign_id})
            all_point_user_data = list(all_point_user_data)
            points_min = all_user_data[0]["points_min"]

            all_campaign_data = find_spec_data(app, db, "campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id})
            all_campaign_data = list(all_campaign_data)
            total_answered = all_campaign_data[0]["total_answered"]
            total_busy = all_campaign_data[0]["total_busy"]

            if status=="ANSWERED":
                update_mongo_data(app, db, "points_mapping", {"user_id": int(user_id)}, {"points": int(points)-int(points_min)})
                update_mongo_data(app, db, "campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id}, {"total_answered": int(total_answered)+1})

            if status == "BUSY":
                update_mongo_data(app, db, "campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id}, {"total_busy": int(total_busy)+1})

            new_user_mapping_dict = {
                "number_id": number_id,
                "answer_time": answer_time,
                "status": status,
                "extension": extention,
                "timestamp": get_timestamp(app)
            }

            update_mongo_data(app, db, "user_campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id, "number": str(number)}, new_user_mapping_dict)

        return {"status_code": 200}        

    except Exception as e:
        app.logger.debug(f"error in voice callback {e}")
        return redirect(url_for('voice_callback', _external=True, _scheme=secure_type))
    
@app.route("/view_logs", methods=['GET'])
def view_logs():
    try:
        file = os.path.abspath("server.log")
        lines = []
        with open(file, "r") as f:
            lines += f.readlines()
        return render_template("logs.html", lines=lines)

    except Exception as e:
        app.logger.debug(f"Error in show log api route : {e}")
        return redirect(url_for('view_logs', _external=True, _scheme=secure_type))
    
@app.route("/download_logs", methods=['GET'])
def download_logs():
    try:
        file = os.path.abspath("server.log")
        return send_file(file, as_attachment=True)

    except Exception as e:
        app.logger.debug(f"Error in download api route : {e}")
        return redirect(url_for('download_logs', _external=True, _scheme=secure_type))

@app.route("/deletedata", methods=["GET", "POST"])
def deletedata():
    try:
        login_dict = session["login_dict"]
        user_id = login_dict.get("user_id")
        type = request.args.get("type")
        if type=="audio":
            audio_path = request.args.get("audio_path")
            condition_dict = {"user_id": user_id, "audio_file": audio_path}
            update_mongo_data(app, db, "audio_store", condition_dict, {"file_status": "inactive"})
            flash("Delete data successfully...", "success")
            return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))

    except Exception as e:
        app.logger.debug(f"error in sample file download {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('dashboard', _external=True, _scheme=secure_type))

@app.route('/campaign_details', methods=['GET', 'POST'])
@token_required
def campaign_details():
    try:
        login_dict = session.get("login_dict", {})
        username = login_dict.get("username", "")
        user_id = login_dict.get("user_id", "")
        all_user_id_data = find_spec_data(app, db, "campaign_details", {"user_id": user_id})
        all_user_id_data = list(all_user_id_data)
        all_user_id_data = all_user_id_data[::-1]
        return render_template("campaign_details.html", username=username,all_user_id_data=all_user_id_data)

    except Exception as e:
        app.logger.debug(f"error in campaign_details route: {e}")
        return redirect(url_for('campaign_details', _external=True, _scheme=secure_type))
  


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)
