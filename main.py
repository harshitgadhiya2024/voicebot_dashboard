"""
    In this file handling all flask api route and maintain all of operation and sessions
"""

import os
import random
import uuid
from datetime import datetime, timedelta
from functools import wraps
from PIL import Image
import jwt, re
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
from pydub import AudioSegment

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
app.config["EXPORT_UPLOAD_FOLDER"] = 'static/uploads/export_file/'
app.config["user_token"] = {}

# handling our application secure type like http or https
secure_type = constant_data["secure_type"]

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
        callback_url = "http://dailogwave.site/voice_callback"
        # cli_number = "8062364086"
        if max_retry=="0" and retry_wait_time=="0":
            url = f"https://panelv2.cloudshope.com/api/voice_call?voice_file_id={voice_file_id}&numbers={numbers}&credit_type_id=23&campaign_name={campaign_name}&callback_event={callback_url}&callback_url={callback_url}"
        else:
            url = f"https://panelv2.cloudshope.com/api/voice_call?voice_file_id={voice_file_id}&numbers={numbers}&credit_type_id=23&max_retry={max_retry}&retry_after=1&campaign_name={campaign_name}&retry_wait_time={retry_wait_time}&callback_event={callback_url}&callback_url={callback_url}"

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

def get_file_size(file_path):
    try:
        size_in_bytes = os.path.getsize(file_path)
        size_in_mb = size_in_bytes / (1024 * 1024)
        return size_in_mb
    except Exception as e:
        app.logger.debug(f"error in get file size: {e}")
        return "none"

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
        get_id = response_data["voice_clip_id"]

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
        else:
            url = "https://obdapi.ivrsms.com/api/obd/login"

            payload = json.dumps({
                "username": "snapgrid",
                "password": "admin123"
            })
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.request("POST", url, headers=headers, data=payload)
            response_data = json.loads(response.text)
            session_api_userid = response_data.get("userid", "")
            session_api_token = response_data.get("token", "")
            user_id = login_dict.get("user_id", "")
            app.config["user_token"][user_id] = {"session_userid": session_api_userid, "access_token": session_api_token}

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

def get_live_campaign_logs(user_id, token):
    try:
        url = f"https://obdapi.ivrsms.com/api/obd/campaign/{user_id}"
        payload = {}
        headers = {
            'Authorization': f'Bearer {token}'
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        response_data = json.loads(response.text)
        return response_data

    except Exception as e:
        print(e)

def get_history_campaign_logs(user_id, token):
    try:
        url = "https://obdapi.ivrsms.com/api/obd/campaign/historical"

        payload = json.dumps({
        "userId": user_id,
        "startDate": "",
        "endDate": ""
        })
        headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        response_data = json.loads(response.text)
        return response_data

    except Exception as e:
        print(e)

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
                    if user_all_data["status"]=="activate":
                        username = user_all_data["username"]
                        email = user_all_data["email"]
                        user_id = user_all_data["user_id"]
                        token = user_all_data["token"]
                        session["login_dict"] = {"username": username, "email": email, "user_id": user_id, "token": token}
                        app.logger.debug(f"Login Dict in session: {session.get('login_dict')}")
                        url = "https://obdapi.ivrsms.com/api/obd/login"
                        payload = json.dumps({
                            "username": "snapgrid",
                            "password": "admin123"
                        })
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        response = requests.request("POST", url, headers=headers, data=payload)
                        response_data = json.loads(response.text)
                        session_api_userid = response_data.get("userid", "")
                        session_api_token = response_data.get("token", "")
                        app.config["user_token"][user_id] = {"session_userid": session_api_userid, "access_token": session_api_token}
                        return redirect(url_for("dashboard", _external=True, _scheme=secure_type))
                    else:
                        flash("Your account does not active. please wait for activation..", "danger")
                        return render_template("login.html")
                else:
                    flash("Please use correct credential..", "danger")
                    return render_template("login.html")
            else:
                user_email_data = user_email_data[0]
                if check_password_hash(user_email_data["password"], password):
                    if user_email_data["status"]=="activate":
                        username = user_email_data["username"]
                        email = user_email_data["email"]
                        user_id = user_email_data["user_id"]
                        token = user_email_data["token"]
                        session["login_dict"] = {"username": username, "email": email, "user_id": user_id, "token": token}
                        app.logger.debug(f"Login Dict in session: {session.get('login_dict')}")
                        url = "https://obdapi.ivrsms.com/api/obd/login"
                        payload = json.dumps({
                            "username": "snapgrid",
                            "password": "admin123"
                        })
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        response = requests.request("POST", url, headers=headers, data=payload)
                        response_data = json.loads(response.text)
                        session_api_userid = response_data.get("userid", "")
                        session_api_token = response_data.get("token", "")
                        app.config["user_token"][user_id] = {"session_userid": session_api_userid, "access_token": session_api_token}
                        return redirect(url_for("dashboard", _external=True, _scheme=secure_type))
                    else:
                        flash("Your account does not active. please wait for activation..", "danger")
                        return render_template("login.html")
                else:
                    flash("Please use correct credential..", "danger")
                    return render_template("login.html")

        else:
            return render_template("login.html")

    except Exception as e:
        app.logger.debug(f"Error in login route: {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('login', _external=True, _scheme=secure_type))

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        if request.method == "POST":
            email = request.form["email"]
            user_email_data = find_spec_data(app, db, "user_data", {"email": email})
            user_email_data = list(user_email_data)
            user_id = user_email_data[0]["user_id"]
            if len(user_email_data)==0:
                flash("Email does not exits Please try with different mail...", "danger")
                return render_template("forgot-password.html")
            else:
                server_host = app.config['MAIL_SERVER']
                server_port = app.config['MAIL_PORT']
                server_username = app.config['MAIL_USERNAME']
                server_password = app.config['MAIL_PASSWORD']
                subject_title = "Reset Your Password"
                mail_format = "Hello There,\n I hope this email finds you well. It has come to our attention that you have requested to reset your password for your APPIACS account. If you did not initiate this request, please disregard this email.\nTo reset your password,\nplease follow the link below: \nClick Here \nPlease note that this link is valid for the next 30 Minutes. After this period, you will need to submit another password reset request.\nIf you continue to experience issues or did not request a password reset, please contact our support team for further assistance.\nThank you for using Website.\n\nBest regards,\nHarshit Gadhiya"
                html_format = f"<p>Dear customer,<br><br>It seems you've forgotten your Dailogwave account password. No worries!<br><br>Please click the link below to reset your password: <br><br><a href='http://dailogwave.site/update_password?user_id={user_id}'><b>Click Here</b></a><br><br>If you did not request this password reset, please ignore this email.<br><br>Best regards,<br>The Dailogwave Team</p>"
                attachment_all_file = []
                sending_email_mail(app, [email], subject_title, mail_format, html_format, server_username,
                                   server_password, server_host, int(server_port), attachment_all_file)
                flash("Reset password mail sent successfully...", "success")
                return render_template("forgot_password.html")
        else:
            return render_template("forgot_password.html")

    except Exception as e:
        app.logger.debug(f"Error in forgot password route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('forgot_password', _external=True, _scheme=secure_type))

@app.route("/update_password", methods=["GET", "POST"])
def update_password():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        user_id = request.args.get("user_id", "nothing")
        if request.method == "POST":
            password = request.form["password"]
            con_password = request.form["con_password"]
            if not password_validation(app=app, password=password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("update_password.html", password=password, con_password=con_password)

            if not password_validation(app=app, password=con_password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("update_password.html", password=password, con_password=con_password)

            if password==con_password:
                password = generate_password_hash(password)
                condition_dict = {"user_id": int(user_id)}
                update_mongo_data(app, db, "user_data", condition_dict, {"password": password})
                flash("Password Update Successfully...", "success")
                return redirect(url_for('login', _external=True, _scheme=secure_type))
            else:
                flash("Password or Confirmation Password Does Not Match. Please Enter Correct Details", "danger")
                return render_template("update_password.html", password=password, con_password=con_password)
        else:
            session["user_id"] = user_id
            return render_template("update_password.html", user_id=user_id)

    except Exception as e:
        app.logger.debug(f"Error in update password route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('update_password', _external=True, _scheme=secure_type))

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

@app.route("/register", methods=["GET", "POST"])
def register():
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
                "status": "deactivate",
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
        download_file_path = f"http://dailogwave.site/download/{userfile_name}"
        all_audio_data = find_spec_data(app, db, "audio_store", {"user_id": login_dict["user_id"]})
        all_audio_list = []
        for var in all_audio_data:
            if var["file_status"] == "active":
                del var["_id"]
                all_audio_list.append(var)
        
        if len(all_audio_list)!=0:
            data_status = "data"

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
        flash("Please try again...", "danger")
        return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))

# def audio_convert_date(username, audio_path):
#     try:
#         last_number = 1
#         try:
#             last_number = random.randint(10000000000, 99999999999)
#         except:
#             pass
        
#         # Load the audio file
#         audio = AudioSegment.from_file(audio_path)

#         # Set parameters
#         bit_depth = 16
#         sample_rate = 8000
#         channels = 1  # Mono

#         # Apply parameter changes
#         audio = audio.set_frame_rate(sample_rate)
#         audio = audio.set_sample_width(bit_depth // 8)
#         audio = audio.set_channels(channels)
#         userfile_name = username+str(last_number)+".wav"
#         filename = app.config["voice_folder"]+userfile_name

#         # Export the modified audio
#         audio.export(filename, format="wav")
#         return filename

#     except Exception as e:
#         print(e)

@app.route('/upload_audio_file', methods=['POST'])
@token_required
def upload_audio_file():
    try:
        login_dict = session.get("login_dict", {})
        username = login_dict["username"]
        last_number = 1
        try:
            last_number = random.randint(10000000000, 99999999999)
        except:
            pass
        
        audio_file = request.files['fileupload']
        userfile_name = username+str(last_number)+".wav"
        filename = app.config["voice_folder"]+userfile_name
        app.config["userbase_recording"][username] = {}
        app.config["userbase_recording"][username]["last_number"] = last_number+1
        audio_file.save(filename)
        print(filename)
        # filesize = get_file_size(filename)
        # print(filesize)
        # if filesize<3:
        print("coming in here")
        print("audio save successfully")
        download_file_path = f"http://dailogwave.site/download/{userfile_name}"
        api_user_id = app.config["user_token"].get(login_dict["user_id"], {}).get("session_userid", "nothing")
        api_token = app.config["user_token"].get(login_dict["user_id"], {}).get("access_token", "nothing")
        response_status, promptId, message = upload_audio_api_file(api_user_id, api_token, userfile_name, filename)
        if response_status:
            get_duraction = get_audio_duration(filename)
            get_duraction = int(get_duraction)
            get_cre = int(get_duraction/28)
            get_cre = get_cre+1
            credits = get_cre*2
            
            register_dict = {
                "user_id": login_dict["user_id"],
                "audio_id": int(promptId),
                "audio_file_name": userfile_name,
                "audio_file_path": filename,
                "duration": get_duraction,
                "credits": credits,
                "download_file_path": download_file_path,
                "status": "inactive",
                "file_status": "active"
            }

            data_added(app, db, "audio_store", register_dict)
            flash(message, "success")
            return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))
        else:
            flash(message, "danger")
            return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))

    except Exception as e:
        app.logger.debug(f"error in save audio route {e}")
        return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))

def upload_audio_api_file(user_id, token, filename, filepath):
    try:
        url = "https://obdapi.ivrsms.com/api/obd/promptupload"
        filename_without = filename.split(".")[0]
        filename_without = remove_special_characters(filename_without)
        payload = {'userId': str(user_id),
        'fileName': filename_without,
        'promptCategory': 'welcome'}
        files=[
        ('waveFile',(filename,open(filepath,'rb'),'audio/wav'))
        ]
        headers = {
        'Authorization': f'Bearer {token}'
        }

        response = requests.request("POST", url, headers=headers, data=payload, files=files)

        response_data = json.loads(response.text)
        promptId = response_data.get("promptId", "nothing")
        message = response_data.get("message", "nothing")
        if promptId=="nothing":
            return False, "nothing",message
        else:
            return True, promptId,message
        
    except Exception as e:
        print(e)

def get_all_audio_file(user_id, token):
    try:
        url = f"https://obdapi.ivrsms.com/api/obd/prompts/{user_id}"

        payload = {}
        headers = {
        'Authorization': f'Bearer {token}'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        response_data = json.loads(response.text)
        return response_data
        
    except Exception as e:
        print(e)

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
        print(data_status)
        print(all_audio_list)

        return render_template("audio_data.html", all_audio_list=all_audio_list, data_status=data_status,username=username)

    except Exception as e:
        app.logger.debug(f"error in upload audio route {e}")
        return redirect(url_for('upload_audio', _external=True, _scheme=secure_type))
    
def bulk_calling_with_api(user_id, token, campaignname, baseid, audioid, max_retry):
    try:
        url = "https://obdapi.ivrsms.com/api/obd/campaign/compose"
        # Get current date and time
        current_datetime = datetime.now()

        # Format the date and time as per your requirement
        formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

        payload = json.dumps({
        "userId": str(user_id),
        "campaignName": str(campaignname),
        "templateId": "0",
        "dtmf": "",
        "baseId": str(baseid),
        "welcomePId": str(audioid),
        "menuPId": "",
        "noInputPId": "",
        "wrongInputPId": "",
        "thanksPId": "",
        "scheduleTime": formatted_datetime,
        "smsSuccessApi": "",
        "smsFailApi": "",
        "smsDtmfApi": "",
        "callDurationSMS": 0,
        "retries": max_retry,
        "retryInterval": 900,
        "agentRows": "\"\"",
        "channels": "20",
        "menuWaitTime": "",
        "rePrompt": ""
        })
        headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        response_data = json.loads(response.text)
        
        campaignId = response_data.get("campaignId", "nothing")
        message = response_data.get("message", "nothing")
        if campaignId=="nothing":
            return False, campaignId, message
        else:
            return True, campaignId, message

    except Exception as e:
        print(e)
        return False, campaignId, message

def remove_special_characters(text):
    # Remove special characters and spaces
    cleaned_text = re.sub(r'[^a-zA-Z0-9]', '', text)
    return cleaned_text

def get_baseid(user_id, filename, filepath, token):
    try:
        url = "https://obdapi.ivrsms.com/api/obd/baseupload"
        base_filename = filename.split(".")[0]
        base_filename = remove_special_characters(base_filename)
        payload = {'userId': int(user_id),
        'baseName': base_filename,
        'contactList': ''}
        files=[
            ('baseFile',(filename,open(os.path.abspath(filepath),'rb'),'text/csv'))
        ]
        headers = {
        'Authorization': f'Bearer {token}'
        }
        response = requests.request("POST", url, headers=headers, data=payload, files=files)

        response_data = json.loads(response.text)
        baseid = response_data.get("baseId", "nothing")
        message = response_data.get("message", "nothing")
        if baseid=="nothing":
            return False, baseid, message
        else:
            return True, baseid, message
        
    except Exception as e:
        print(e)
        return False, baseid, message
    
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
            max_retry = request.form.get("max_retry", "0")
            app.logger.debug(f"all data fetched and voiceid is {voiceid}")
            app.logger.debug(f"all data fetched and voiceid is {max_retry}")

            audio_user_data = find_spec_data(app, db, "audio_store", {"audio_id": int(voiceid)})
            audio_user_data = list(audio_user_data)
            app.logger.debug(f"data of audio user: {audio_user_data}")
            points_min = audio_user_data[0]["credits"]

            file_name = numberfile.filename
            filepath = f"static/upload/{file_name}"
            numberfile.save(filepath)
            app.logger.debug("file save successfully")
            exten = file_name.split(".")[-1]
            api_user_id = app.config["user_token"].get(login_dict["user_id"], {}).get("session_userid", "nothing")
            api_token = app.config["user_token"].get(login_dict["user_id"], {}).get("access_token", "nothing")
            status, baseid, message = get_baseid(api_user_id, file_name, filepath, api_token) 
            if status: 
                if exten=="csv":
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)
                
                all_numbers = list(df["number"])
                user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
                user_points = list(user_points)
                points = user_points[0]["points"]
                required_points = len(all_numbers)*int(points_min)
                if required_points>points:
                    flash("Please recharge your account, don't enough points you have...", "warning")
                else:
                    status_api, campaignId, message = bulk_calling_with_api(api_user_id, api_token, campaign_name, baseid, voiceid, max_retry)
                    app.logger.debug("completed")
                    if status_api:
                        all_points_data = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
                        all_points_data = list(all_points_data)
                        campaigns_total = all_points_data[0]["campaigns"]
                        totalcalls = all_points_data[0]["calls"]

                        points_data_mapping = {"user_id": user_id, "campaign_id": str(campaignId), "points_min": points_min, "points_cut": False}
                        data_added(app, db, "data_points_mapping", points_data_mapping)

                        update_mongo_data(app, db, "points_mapping", {"user_id": user_id}, {"campaigns": int(campaigns_total)+1, "calls": int(totalcalls)+len(all_numbers)})

                        flash(message, "success")
                        return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
                    else:
                        flash(message, "danger")
                        return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
            else:
                flash(message, "danger")
                return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
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
            points_min = all_point_user_data[0]["points_min"]

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
            condition_dict = {"user_id": user_id, "audio_file_path": audio_path}
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
        api_user_id = app.config["user_token"].get(login_dict["user_id"], {}).get("session_userid", "nothing")
        api_token = app.config["user_token"].get(login_dict["user_id"], {}).get("access_token", "nothing")
        all_compaign_data = get_history_campaign_logs(api_user_id, api_token)
        coll = db["data_points_mapping"]
        all_user_based_data = coll.find({"user_id": user_id})
        # all_campaign_ids = [var["campaign_id"] for var in all_user_based_data]
        all_campaign_ids = []
        all_campaign_ids_dict = {}
        for var in all_user_based_data:
            all_campaign_ids.append(var["campaign_id"])
            all_campaign_ids_dict[var["campaign_id"]] = var
        all_user_id_data = []
        for datavar in all_compaign_data:
            campaignId = datavar.get("campaignId", "nothing")
            if str(campaignId) in all_campaign_ids:
                mapping_dict = {
                    "campaign_id": datavar["campaignId"],
                    "campaign_name": datavar["campaignName"],
                    "total_calls": datavar["numbersUploaded"],
                    "processed_number": datavar["numbersProcessed"],
                    "total_answered": datavar["numbersProcessed"],
                    "total_busy": int(datavar["numbersUploaded"]) - int(datavar["numbersProcessed"])
                }
                all_user_id_data.append(mapping_dict)
                data_check = find_spec_data(app, db, "points_mapping", {"user_id": int(user_id)})
                data_check = list(data_check)
                points = data_check[0]["points"]
                if not all_campaign_ids_dict[str(campaignId)]["points_cut"]:
                    if int(datavar["numbersUploaded"])==int(datavar["numbersProcessed"]):
                        answered_calls = int(datavar["numbersProcessed"])
                        points_min = all_campaign_ids_dict[str(campaignId)]["points_min"]
                        cut_point = answered_calls*int(points_min)
                        update_mongo_data(app, db, "points_mapping", {"user_id": user_id}, {"points": int(points)-int(cut_point)})
                        update_mongo_data(app, db, "data_points_mapping", {"user_id": int(user_id), "campaign_id": str(campaignId)}, {"points_cut": True})

        all_user_id_data = all_user_id_data[::-1]
        return render_template("campaign_details.html", username=username,all_user_id_data=all_user_id_data)

    except Exception as e:
        app.logger.debug(f"error in campaign_details route: {e}")
        return redirect(url_for('campaign_details', _external=True, _scheme=secure_type))
  
@app.route('/campaign_info', methods=['GET', 'POST'])
@token_required
def campaign_info():
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        campaign_id = request.args.get("campaign_id", "")
        all_campaign_data = find_spec_data(app, db, "user_campaign_details", {"campaign_id": campaign_id})
        all_campaign_data = list(all_campaign_data)
        all_campaign_data = all_campaign_data[::-1]
        return render_template("each_compaign.html", all_campaign_data=all_campaign_data, username=username)
        
    except Exception as e:
        app.logger.debug(f"error in upload audio route {e}")
        return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
    
def export_panel_data(app, database_data, panel, type):
    """
    export data for different format like csv, excel and csv

    :param app: app-name
    :param database_data: database data
    :param type: excel, csv, json
    :return: filename
    """

    try:
        if type == "excel":
            output_path = os.path.join(app.config["EXPORT_UPLOAD_FOLDER"], f"export_{panel}_excel.xlsx")
            df = pd.DataFrame(database_data)
            df.to_excel(output_path, index=False)
        elif type == "csv":
            output_path = os.path.join(app.config["EXPORT_UPLOAD_FOLDER"], f"export_{panel}_csv.csv")
            df = pd.DataFrame(database_data)
            df.to_csv(output_path, index=False)
        else:
            output_path = os.path.join(app.config["EXPORT_UPLOAD_FOLDER"], f"export_{panel}_json.json")
            with open(output_path, 'w') as json_file:
                json.dump(database_data, json_file, indent=2)

        return output_path

    except Exception as e:
        app.logger.debug(f"Error in export data from database: {e}")
    
@app.route('/export_data', methods=['GET', 'POST'])
@token_required
def export_data():
    try:
        login_dict = session.get("login_dict", {})
        type = request.args.get("type", "")
        campaign_id = request.args.get("campaign_id", "")
        print(campaign_id)
        db = client["voicebot"]
        coll = db["user_campaign_details"]
        all_campaign_data = coll.find({"campaign_id": campaign_id})
        all_campaign_data = list(all_campaign_data)
        print(all_campaign_data)
        all_data = []
        for each_res in all_campaign_data:
            del each_res["_id"]
            all_data.append(each_res)
        panel = "data"
        output_path = export_panel_data(app, all_data, panel, type)
        return send_file(output_path, as_attachment=True)
        
    except Exception as e:
        app.logger.debug(f"error in upload audio route {e}")
        return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
  
@app.route("/user_update_password", methods=["GET", "POST"])
@token_required
def user_update_password():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        if request.method == "POST":
            password = request.form["password"]
            con_password = request.form["con_password"]
            if not password_validation(app=app, password=password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("user_update_password.html", password=password, con_password=con_password)

            if not password_validation(app=app, password=con_password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("user_update_password.html", password=password, con_password=con_password)

            if password==con_password:
                password = generate_password_hash(password)
                condition_dict = {"user_id": int(user_id)}
                update_mongo_data(app, db, "user_data", condition_dict, {"password": password})
                flash("Password Update Successfully...", "success")
                return redirect(url_for('login', _external=True, _scheme=secure_type))
            else:
                flash("Password or Confirmation Password Does Not Match. Please Enter Correct Details", "danger")
                return render_template("user_update_password.html", password=password, con_password=con_password)
        else:
            session["user_id"] = user_id
            return render_template("user_update_password.html", user_id=user_id, username=username)

    except Exception as e:
        app.logger.debug(f"Error in user update password route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('user_update_password', _external=True, _scheme=secure_type))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80, debug=True)
