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
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from constant import constant_data
from operations.common_func import (password_validation, get_timestamp, validate_phone_number, logger_con, sending_email_mail)
from operations.mongo_connection import (mongo_connect, data_added, find_all_data, find_spec_data, update_mongo_data)
import json, requests
import pandas as pd
import audioread
from flask_mail import Mail, Message
from elevenlabs.client import ElevenLabs
from elevenlabs import play, save
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
import concurrent.futures

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
app.config["smart_voicecall_details"] = {}
app.config["EXPORT_UPLOAD_FOLDER"] = 'static/uploads/export_file/'
app.config["user_token"] = {}
app.config["email_configuration"] = {}
app.config["IMPORT_UPLOAD_FOLDER"] = 'static/uploads/import_file/'

executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

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
            if len(user_email_data)==0:
                flash("Email does not exits Please try with different mail...", "danger")
                return render_template("forgot-password.html")
            else:
                user_id = user_email_data[0]["user_id"]
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
                "token": 50
            }  
            app.config["userbase_recording"][username]={}
            app.config["userbase_recording"][username]["last_number"] = 1

            data_added(app, db, "user_data", register_dict) 
            points_mapping_dict = {"user_id": user_id, "points": 50, "campaigns": 0, "calls": 0}
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
        all_company_data = find_spec_data(app, db, "customer_company_data", {"user_id": int(user_id)})
        all_company_data = list(all_company_data)
        if all_company_data:
            all_company_data = all_company_data[0]
            get_phonenumber = all_company_data.get("phonenumber", "nothing")
            status = all_company_data.get("status", "nothing")
            if get_phonenumber=="nothing" and status=="inactive":
                return render_template("index.html", username=username, points=points, calls=calls, campaigns=campaigns)
            else:
                return render_template("index.html", username=username, points=points, calls=calls, campaigns=campaigns, phonenumber=get_phonenumber)
        else:
            return render_template("index.html", username=username, points=points, calls=calls, campaigns=campaigns)

    except Exception as e:
        app.logger.debug(f"error is {e}")
        return redirect(url_for('login', _external=True, _scheme=secure_type))

@app.route('/inputnodeapi', methods=['GET', 'POST'])
def inputnodeapi():
    try:
        uid = request.args.get("uid", "")
        node_id = request.args.get("node_id", "")
        timestamp = request.args.get("timestamp", "")
        response_data = json.loads(request.data)
        clid = response_data.get("clid", "")
        app.logger.debug(f"clid2: {clid}")

        smart_voicecall_details=app.config["smart_voicecall_details"]
        app.logger.debug(smart_voicecall_details)
        get_text = smart_voicecall_details.get(clid, "Hello, kaise ho?").get("text")
        voice_id = smart_voicecall_details.get(clid, "").get("voice")
        # response = {
        #     "action": "tts",
        #     "value": get_text
        #  }
        # coll_apis = db["apis"]
        # all_apis = coll_apis.find({})
        # all_apis = [var["api_key"] for var in all_apis]
        # flag = True
        # while flag:
        #     try:
        #         api_key = random.choice(all_apis)
        #         client_elevenlabs = ElevenLabs(
        #             api_key=api_key,  # Defaults to ELEVEN_API_KEY
        #         )
        #         flag = False
        #     except:
        #         pass
        #
        # audio = client_elevenlabs.generate(
        #     text=get_text,
        #     voice=voice_id,
        #     model="eleven_multilingual_v2"
        # )
        # value = random.randint(111111,9999999999999)
        # filename = f"generated_{value}.mp3"
        # get_path = os.path.abspath(app.config['voice_folder'])
        # filepath = os.path.join(get_path, filename)
        # save(audio, filepath)

        response = {
            "action": "tts",
            "value": get_text
        }

        return response

    except Exception as e:
        print(f"error in inputnodeapi: {e}")
        app.logger.debug(f"error in inputnodeapi: {e}")
        response = {
            "action": "tts",
            "value": "welcome to our company"
        }
        return response

@app.route('/get_phone_number', methods=['GET', 'POST'])
@token_required
def get_phone_number():
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict["user_id"]
        if request.method=="POST":
            company_name = request.form["company_name"]
            owner_name = request.form["owner_name"]
            company_cin = request.form["company_cin"]
            company_gst = request.form["company_gst"]

            if company_cin=="" and company_gst=="":
                flash("Please provide any one like company CIN and GST", "danger")
                return redirect(url_for('dashboard', _external=True, _scheme=secure_type))
            else:
                mapping_dict = {
                    "user_id": user_id,
                    "company_name": company_name,
                    "owner_name": owner_name,
                    "company_cin": company_cin,
                    "company_gst": company_gst,
                    "phonenumber": "",
                    "status": "inactive"
                }

                data_added(app,db,"customer_company_data",mapping_dict)
                flash("Your details submitted successfully... Please wait to get new company number...", "success")
                return redirect(url_for('dashboard', _external=True, _scheme=secure_type))
        else:
            return {"message": "Methods not allowed..."}

    except Exception as e:
        app.logger.debug(f"error is {e}")
        return redirect(url_for('dashboard', _external=True, _scheme=secure_type))
   

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
            credits = get_cre*1

            register_dict = {
                "user_id": login_dict["user_id"],
                "audio_id": voice_id,
                "audio_file": filename,
                "duration": get_duraction,
                "credits": 1,
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
            credits = get_cre*1
            
            register_dict = {
                "user_id": login_dict["user_id"],
                "audio_id": int(promptId),
                "audio_file_name": userfile_name,
                "audio_file_path": filename,
                "duration": get_duraction,
                "credits": 1,
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

@app.route('/upload_smart_audio_file', methods=['POST'])
@token_required
def upload_smart_audio_file():
    try:
        login_dict = session.get("login_dict", {})
        username = login_dict["username"]
        last_number = 1
        try:
            last_number = random.randint(10000000000, 99999999999)
        except:
            pass

        speech_text = request.form['speechtext']
        voicename = request.form['voicename']

        coll_apis = db["apis"]
        all_apis = coll_apis.find({})
        all_apis = [var["api_key"] for var in all_apis]
        flag = True
        while flag:
            try:
                api_key = random.choice(all_apis)
                client = ElevenLabs(
                    api_key=api_key,  # Defaults to ELEVEN_API_KEY
                )
                flag = False
            except:
                pass

        audio = client.generate(
          text=speech_text,
          voice=voicename,
          model="eleven_multilingual_v2"
        )

        # Saving the converted audio in a file
        userfile_name = username + str(last_number) + ".wav"
        filename = app.config["voice_folder"] + userfile_name
        app.config["userbase_recording"][username] = {}
        app.config["userbase_recording"][username]["last_number"] = last_number + 1
        save(audio, filename)
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
            get_cre = int(get_duraction / 28)
            get_cre = get_cre + 1
            credits = get_cre * 2

            register_dict = {
                "user_id": login_dict["user_id"],
                "audio_id": int(promptId),
                "audio_file_name": userfile_name,
                "audio_file_path": filename,
                "duration": get_duraction,
                "credits": 1,
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
        user_id = login_dict["user_id"]
        all_audio_data = find_spec_data(app, db, "audio_store", {"user_id": int(login_dict["user_id"])})
        all_audio_list = []
        data_status = "no_data"
        coll_apis = db["apis"]
        all_apis = coll_apis.find({})
        all_apis = [var["api_key"] for var in all_apis]
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]
        flag = True
        while flag:
            try:
                api_key = random.choice(all_apis)
                client = ElevenLabs(
                    api_key=api_key,  # Defaults to ELEVEN_API_KEY
                )

                response = client.voices.get_all()
                flag = False
            except:
                pass

        all_audios_data = []
        for var in list(response.voices):
            get_audio = dict(var)
            voice_id = get_audio["name"]
            all_audios_data.append(voice_id)

        for var in all_audio_data:
            if var["file_status"] == "active":
                del var["_id"]
                all_audio_list.append(var)

        if len(all_audio_list)!=0:
            data_status = "data"
        print(data_status)
        print(all_audio_list)

        return render_template("audio_data.html",points=points,all_audios_data=all_audios_data, all_audio_list=all_audio_list, data_status=data_status,username=username)

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
            if var["status"] == "active":
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

                        points_data_mapping = {"user_id": user_id, "campaign_id": str(campaignId), "points_min": 1, "points_cut": False}
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

@app.route('/smart_calling', methods=['GET', 'POST'])
@token_required
def smart_calling():
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        if request.method == "POST":
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
                if exten == "csv":
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)

                all_numbers = list(df["number"])
                user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
                user_points = list(user_points)
                points = user_points[0]["points"]
                required_points = len(all_numbers) * int(points_min)
                if required_points > points:
                    flash("Please recharge your account, don't enough points you have...", "warning")
                else:
                    status_api, campaignId, message = bulk_calling_with_api(api_user_id, api_token, campaign_name,
                                                                            baseid, voiceid, max_retry)
                    app.logger.debug("completed")
                    if status_api:
                        all_points_data = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
                        all_points_data = list(all_points_data)
                        campaigns_total = all_points_data[0]["campaigns"]
                        totalcalls = all_points_data[0]["calls"]

                        points_data_mapping = {"user_id": user_id, "campaign_id": str(campaignId),
                                               "points_min": 1, "points_cut": False}
                        data_added(app, db, "data_points_mapping", points_data_mapping)

                        update_mongo_data(app, db, "points_mapping", {"user_id": user_id},
                                          {"campaigns": int(campaigns_total) + 1,
                                           "calls": int(totalcalls) + len(all_numbers)})

                        flash(message, "success")
                        return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
                    else:
                        flash(message, "danger")
                        return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
            else:
                flash(message, "danger")
                return redirect(url_for('bulk_calling', _external=True, _scheme=secure_type))
        else:
            return render_template("smart_calling.html", username=username)

    except Exception as e:
        app.logger.debug(f"error in smart calling route {e}")
        return redirect(url_for('smart_calling', _external=True, _scheme=secure_type))

@app.route('/sample_file', methods=['GET', 'POST'])
def sample_file():
    try:
        type = request.args.get("type", "")
        if type=="smart_numbersfile":
            server_file_name = "static/sample_file/sample_smart_number_file.csv"
        else:
            server_file_name = "static/sample_file/sample_number_file.csv"
        file = os.path.abspath(server_file_name)
        return send_file(file, as_attachment=True)

    except Exception as e:
        app.logger.debug(f"error in sample file download {e}")
        return redirect(url_for('sample_file', _external=True, _scheme=secure_type))
    
# @app.route('/voice_callback', methods=['GET', 'POST'])
# def voice_callback():
#     try:
#         number_id = request.args.get("number_id")
#         campaign_id = request.args.get("campaign_id")
#         answer_time = request.args.get("answer_time")
#         status = request.args.get("status")
#         extention = request.args.get("extention")
#         number = request.args.get("number")
#         number = number[1:]
#         app.logger.debug(f"data for calling: number_id:{number_id}, campaign_id: {campaign_id}, answer: {answer_time}, status: {status}, extension: {extention}, number: {number}")
#         if status=="ANSWERED" or status=="BUSY":
#             all_user_campaign = find_spec_data(app, db, "campaign_details", {"campaign_id": campaign_id})
#             all_user_campaign = list(all_user_campaign)
#             user_id = all_user_campaign[0]["user_id"]
#
#             all_user_data = find_spec_data(app, db, "points_mapping", {"user_id": int(user_id)})
#             all_user_data = list(all_user_data)
#             points = all_user_data[0]["points"]
#
#             all_point_user_data = find_spec_data(app, db, "data_points_mapping", {"campaign_id": campaign_id})
#             all_point_user_data = list(all_point_user_data)
#             points_min = all_point_user_data[0]["points_min"]
#
#             all_campaign_data = find_spec_data(app, db, "campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id})
#             all_campaign_data = list(all_campaign_data)
#             total_answered = all_campaign_data[0]["total_answered"]
#             total_busy = all_campaign_data[0]["total_busy"]
#
#             if status=="ANSWERED":
#                 update_mongo_data(app, db, "points_mapping", {"user_id": int(user_id)}, {"points": int(points)-int(points_min)})
#                 update_mongo_data(app, db, "campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id}, {"total_answered": int(total_answered)+1})
#
#             if status == "BUSY":
#                 update_mongo_data(app, db, "campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id}, {"total_busy": int(total_busy)+1})
#
#             new_user_mapping_dict = {
#                 "number_id": number_id,
#                 "answer_time": answer_time,
#                 "status": status,
#                 "extension": extention,
#                 "timestamp": get_timestamp(app)
#             }
#
#             update_mongo_data(app, db, "user_campaign_details", {"user_id": int(user_id), "campaign_id": campaign_id, "number": str(number)}, new_user_mapping_dict)
#
#         return {"status_code": 200}
#
#     except Exception as e:
#         app.logger.debug(f"error in voice callback {e}")
#         return redirect(url_for('voice_callback', _external=True, _scheme=secure_type))
#
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
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]
        api_user_id = app.config["user_token"].get(login_dict["user_id"], {}).get("session_userid", "nothing")
        api_token = app.config["user_token"].get(login_dict["user_id"], {}).get("access_token", "nothing")
        all_compaign_data = get_history_campaign_logs(api_user_id, api_token)
        if all_compaign_data == None:
            all_compaign_data = []
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
                    "total_answered": datavar["callsConnected"],
                    "total_busy": int(datavar["numbersUploaded"]) - int(datavar["numbersProcessed"])
                }
                all_user_id_data.append(mapping_dict)
                data_check = find_spec_data(app, db, "points_mapping", {"user_id": int(user_id)})
                data_check = list(data_check)
                points = data_check[0]["points"]

        all_user_id_data = all_user_id_data[::-1]
        return render_template("campaign_details.html",points=points, username=username,all_user_id_data=all_user_id_data)

    except Exception as e:
        app.logger.debug(f"error in campaign_details route: {e}")
        return redirect(url_for('campaign_details', _external=True, _scheme=secure_type))


@app.route('/live_campaign_details', methods=['GET', 'POST'])
@token_required
def live_campaign_details():
    try:
        login_dict = session.get("login_dict", {})
        username = login_dict.get("username", "")
        user_id = login_dict.get("user_id", "")
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]
        api_user_id = app.config["user_token"].get(login_dict["user_id"], {}).get("session_userid", "nothing")
        api_token = app.config["user_token"].get(login_dict["user_id"], {}).get("access_token", "nothing")
        all_compaign_data = get_live_campaign_logs(api_user_id, api_token)
        if all_compaign_data == None:
            all_compaign_data = []
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
                    "total_answered": datavar["callsConnected"],
                    "total_busy": int(datavar["numbersUploaded"]) - int(datavar["numbersProcessed"])
                }
                all_user_id_data.append(mapping_dict)
                data_check = find_spec_data(app, db, "points_mapping", {"user_id": int(user_id)})
                data_check = list(data_check)
                points = data_check[0]["points"]

        all_user_id_data = all_user_id_data[::-1]
        return render_template("live_campaign_details.html",points=points, username=username,all_user_id_data=all_user_id_data)

    except Exception as e:
        app.logger.debug(f"error in campaign_details route: {e}")
        return redirect(url_for('live_campaign_details', _external=True, _scheme=secure_type))

 
@app.route('/campaign_info', methods=['GET', 'POST'])
@token_required
def campaign_info():
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        campaign_id = request.args.get("campaign_id", "")
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]
        all_campaign_data = find_spec_data(app, db, "user_campaign_details", {"campaign_id": campaign_id})
        all_campaign_data = list(all_campaign_data)
        all_campaign_data = all_campaign_data[::-1]
        return render_template("each_compaign.html",points=points, all_campaign_data=all_campaign_data, username=username)
        
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

def remove_file(response, local_filename):
    try:
        os.remove(local_filename)
    except Exception as error:
        app.logger.error("Error removing or closing downloaded file handle", error)
    return response
    
@app.route('/export_data', methods=['GET', 'POST'])
@token_required
def export_data():
    try:
        login_dict = session.get("login_dict", {})
        campaign_id = request.args.get("campaign_id", "")
        type = request.args.get("type", "")
        output_path = ""
        api_user_id = app.config["user_token"].get(login_dict["user_id"], {}).get("session_userid", "nothing")
        api_token = app.config["user_token"].get(login_dict["user_id"], {}).get("access_token", "nothing")
        url = "https://obdapi.ivrsms.com/api/obd/report/generate"
        payload = json.dumps({
            "campaignId": int(campaign_id),
            "reportType": "full"
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_token}'
        }
        response = requests.request("POST", url, headers=headers, data=payload)

        url = f"https://obdapi.ivrsms.com/api/obd/report/download/{api_user_id}"

        payload = {}
        headers = {
            'Authorization': f'Bearer {api_token}'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        response_text = json.loads(response.text)
        flag = False
        report_url = ""
        for report in response_text:
            status = report.get("status")
            reportType = report.get("reportType")
            campaignId = report.get("campaignId")
            if campaignId == int(campaign_id):
                if status=="2" and reportType=="full":
                    flag = True
                    report_url = report.get("reportUrl")

        if flag:
            return {"report_url": report_url, "status": 200}
        else:
            flash("Please wait..Your report will generated in few times", "warning")
            return {"status": 403}
        # print(campaign_id)
        # db = client["voicebot"]
        # coll = db["user_campaign_details"]
        # all_campaign_data = coll.find({"campaign_id": campaign_id})
        # all_campaign_data = list(all_campaign_data)
        # print(all_campaign_data)
        # all_data = []
        # for each_res in all_campaign_data:
        #     del each_res["_id"]
        #     all_data.append(each_res)
        # panel = "data"
        # output_path = export_panel_data(app, all_data, panel, type)

    except Exception as e:
        app.logger.debug(f"error in upload audio route {e}")
        return {"status": 403}

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
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]
        if request.method == "POST":
            password = request.form["password"]
            con_password = request.form["con_password"]
            if not password_validation(app=app, password=password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("user_update_password.html",points=points, password=password, con_password=con_password)

            if not password_validation(app=app, password=con_password):
                flash("Please choose strong password. Add at least 1 special character, number, capitalize latter..", "danger")
                return render_template("user_update_password.html",points=points, password=password, con_password=con_password)

            if password==con_password:
                password = generate_password_hash(password)
                condition_dict = {"user_id": int(user_id)}
                update_mongo_data(app, db, "user_data", condition_dict, {"password": password})
                flash("Password Update Successfully...", "success")
                return redirect(url_for('login', _external=True, _scheme=secure_type))
            else:
                flash("Password or Confirmation Password Does Not Match. Please Enter Correct Details", "danger")
                return render_template("user_update_password.html",points=points, password=password, con_password=con_password)
        else:
            session["user_id"] = user_id
            return render_template("user_update_password.html",points=points, user_id=user_id, username=username)

    except Exception as e:
        app.logger.debug(f"Error in user update password route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('user_update_password', _external=True, _scheme=secure_type))

@app.route("/user_points", methods=["GET", "POST"])
@token_required
def user_points():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        coll = db["points_history"]
        new_data = coll.find({"user_id": int(user_id)})
        new_data = list(new_data)
        all_user_id_data = []
        for var in new_data:
            del var["_id"]
            all_user_id_data.append(var)
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]

        return render_template("user_points.html",points=points, user_id=user_id, username=username, all_user_id_data=all_user_id_data)

    except Exception as e:
        app.logger.debug(f"Error in user points route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('user_points', _external=True, _scheme=secure_type))

@app.route("/user_data", methods=["GET", "POST"])
@token_required
def user_data():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        customer_data = find_spec_data(app, db, "customer_data", {"user_id": str(user_id)})
        customer_data = list(customer_data)
        group_name = request.args.get("group", "none")
        all_group_names = [d["group"] for d in customer_data]
        all_group_names = set(all_group_names)
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        all_audio_data = find_spec_data(app, db, "audio_store", {"user_id": login_dict["user_id"]})
        all_audio_ids = []
        for var in all_audio_data:
            if var["status"] == "active":
                all_audio_ids.append(var["audio_id"])
        points = user_points[0]["points"]
        coll_apis = db["apis"]
        all_apis = coll_apis.find({})
        all_apis = [var["api_key"] for var in all_apis]
        flag = True
        while flag:
            try:
                api_key = random.choice(all_apis)
                client = ElevenLabs(
                    api_key=api_key,  # Defaults to ELEVEN_API_KEY
                )

                response = client.voices.get_all()
                flag = False
            except:
                pass

        all_audios_data = []
        for var in list(response.voices):
            get_audio = dict(var)
            voice_id = get_audio["name"]
            all_audios_data.append(voice_id)
        if customer_data:
            customer_show_data = []
            if group_name=="none":
                group_name = customer_data[0]["group"]
            for var in customer_data:
                del var["_id"]
                if var["group"]==group_name:
                    all_keys = list(var.keys())
                    all_values = list(var.values())
                    all_values.insert(0, var["phone"])
                    customer_show_data.append(all_values)

            set_email_config = session.get("set_email_config", "none")
            if set_email_config!="none":
                mail_dict = app.config["email_configuration"][str(user_id)]
                return render_template("user_data.html",all_audios_data=all_audios_data,all_audio_ids=all_audio_ids,points=points,all_keys=all_keys,group_name=group_name,customer_show_data=customer_show_data, user_id=user_id, username=username,
                                       server_username=mail_dict["server_username"], server_password=mail_dict["server_password"],all_group_names=all_group_names,
                                       server_host=mail_dict["server_host"], server_port=mail_dict["server_port"])
            else:
                return render_template("user_data.html",all_audios_data=all_audios_data,all_audio_ids=all_audio_ids,points=points,all_keys=all_keys,group_name=group_name,all_group_names=all_group_names,customer_show_data=customer_show_data, user_id=user_id, username=username)
        else:
            set_email_config = session.get("set_email_config", "none")
            if set_email_config != "none":
                mail_dict = app.config["email_configuration"][str(user_id)]
                return render_template("user_data.html",all_audios_data=all_audios_data,all_audio_ids=all_audio_ids,points=points, user_id=user_id, username=username,
                                       server_username=mail_dict["server_username"],group_name="No Group",
                                       server_password=mail_dict["server_password"],all_group_names=all_group_names,
                                       server_host=mail_dict["server_host"], server_port=mail_dict["server_port"])
            else:
                return render_template("user_data.html",all_audios_data=all_audios_data,all_audio_ids=all_audio_ids,points=points,group_name="No Group",all_group_names=all_group_names, user_id=user_id, username=username)


    except Exception as e:
        app.logger.debug(f"Error in user points route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('user_data', _external=True, _scheme=secure_type))

@app.route("/add_email_configuration", methods=["GET", "POST"])
@token_required
def add_email_configuration():
    """
    In this route we can handling student register process
    :return: register template
    """
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        if request.method == "POST":
            server_username = request.form["server_username"]
            server_password = request.form["server_password"]
            server_host = request.form["server_host"]
            server_port = request.form["server_port"]
            app.config["email_configuration"][str(user_id)] = {"server_username": server_username,
                                                               "server_port": int(server_port),
                                                               "server_host": server_host,
                                                               "server_password": server_password}
            session["set_email_config"] = "value"

            flash("Email-Server configure successfully...", "success")
            return redirect(url_for('user_data', _external=True, _scheme=secure_type))
        else:
            return redirect(url_for('user_data', _external=True, _scheme=secure_type))

    except Exception as e:
        app.logger.debug(f"Error in add_email_configuration route: {e}")
        return redirect(url_for('user_data', _external=True, _scheme=secure_type))

@app.route("/import_data", methods=["GET", "POST"])
@token_required
def import_data():
    """
    That funcation can use delete from student, teacher and admin from admin panel
    """

    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        if request.method == "POST":
            ## Getting file from request
            file = request.files["file"]
            ## Checking if file is selected, if yes, secure the filename
            if file.filename != "":
                ## Securing file and getting file extension
                file_name = secure_filename(file.filename)
                if not os.path.isdir(app.config['IMPORT_UPLOAD_FOLDER']):
                    os.makedirs(app.config['IMPORT_UPLOAD_FOLDER'], exist_ok=True)
                file_path = os.path.join(app.config['IMPORT_UPLOAD_FOLDER'], file_name)
                file.save(file_path)
                file_extension = os.path.splitext(file_name)[1]

                if file_extension == ".xlsx":
                    dataload_excel = pd.read_excel(file_path)
                    json_record_data = dataload_excel.to_json(orient='records')
                    json_data = json.loads(json_record_data)
                elif file_extension == ".csv":
                    dataload = pd.read_csv(file_path)
                    json_record_data = dataload.to_json(orient='records')
                    json_data = json.loads(json_record_data)
                else:
                    with open(file_path, encoding='utf-8') as json_file:
                        json_data = json.load(json_file)

                get_user_new_data = find_all_data(app, db, "customer_data")
                get_user_data = []
                for login_data in get_user_new_data:
                    get_user_data.append(login_data["phone"])
                flag = True
                for record in json_data:
                    try:
                        group = record["group"]
                        email = record["email"]
                        phone = record["phone"]
                        if phone not in get_user_data:
                            try:
                                id = record["_id"]
                                del record["_id"]
                            except:
                                pass
                            record["user_id"] = str(user_id)
                            data_added(app, db, "customer_data", record)
                    except:
                        flag = False

                if flag:
                    flash("Data added successfully...", "success")
                else:
                    flash("group column required...", "warning")
                return redirect(f'/user_data')
            else:
                flash("No file selected, please select a file", "danger")
                return redirect(f'/user_data')

    except Exception as e:
        app.logger.debug(f"Error in import data from database: {e}")
        return redirect(f'/user_data')
    
def export_panel_data(app, database_data, type):
    """
    export data for different format like csv, excel and csv

    :param app: app-name
    :param database_data: database data
    :param type: excel, csv, json
    :return: filename
    """

    try:
        if type == "excel":
            output_path = os.path.join(app.config["EXPORT_UPLOAD_FOLDER"], f"export_data_excel.xlsx")
            df = pd.DataFrame(database_data)
            df.to_excel(output_path, index=False)
        elif type == "csv":
            output_path = os.path.join(app.config["EXPORT_UPLOAD_FOLDER"], f"export_data_csv.csv")
            df = pd.DataFrame(database_data)
            df.to_csv(output_path, index=False)
        else:
            output_path = os.path.join(app.config["EXPORT_UPLOAD_FOLDER"], f"export_data_json.json")
            with open(output_path, 'w') as json_file:
                json.dump(database_data, json_file, indent=2)

        return output_path

    except Exception as e:
        app.logger.debug(f"Error in export data from database: {e}")

    
@app.route("/exportdata", methods=["GET", "POST"])
@token_required
def exportdata():
    """
    That funcation can use delete from student, teacher and admin from admin panel
    """

    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        data = json.loads(request.data)
        type = data.get("type", "excel")
        selectrecord = data.get("selectrecord", "csv")
        res = find_spec_data(app, db, "customer_data", {"user_id": str(user_id)})
        all_data = []
        for each_res in res:
            if each_res["phone"] in selectrecord:
                del each_res["_id"]
                all_data.append(each_res)
        output_path = export_panel_data(app, all_data, type)
        return jsonify({"output_path":output_path})


    except Exception as e:
        app.logger.debug(f"Error in export data from database: {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('exportdata', _external=True, _scheme=secure_type))

@app.route("/sample_document", methods=["GET", "POST"])
@token_required
def sample_document():
    """
    That funcation can use delete from student, teacher and admin from admin panel
    """

    try:
        type = request.args.get("type")
        if type=="excel":
            output_path = os.path.abspath("static/sample_file/sample_excel.xlsx")
        elif type=="csv":
            output_path = os.path.abspath("static/sample_file/sample_csv.csv")
        elif type=="json":
            output_path = os.path.abspath("static/sample_file/sample_json.json")
        return send_file(output_path, as_attachment=True)

    except Exception as e:
        app.logger.debug(f"Error in sample document data from database: {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('sample_document', _external=True, _scheme=secure_type))

@app.route("/deleteuserdata", methods=["GET", "POST"])
@token_required
def deleteuserdata():
    """
    That funcation can use delete from student, teacher and admin from admin panel
    """

    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        data = json.loads(request.data)
        selectrecord = data.get("selectrecord", "csv")
        for var in selectrecord:
            coll = db["customer_data"]
            try:
                phone = int(var)
                coll.delete_one({"phone": phone, "user_id": str(user_id)})
            except:
                coll.delete_one({"phone": var, "user_id": str(user_id)})

        flash("Delete data successfully...", "success")
        return jsonify({"message": "done"})


    except Exception as e:
        app.logger.debug(f"Error in delete data from database: {e}")
        flash("Please try again...", "danger")
        return redirect(url_for('deleteuserdata', _external=True, _scheme=secure_type))

@app.route("/text_to_speech", methods=["GET", "POST"])
@token_required
def text_to_speech():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        coll = db["apis"]
        all_apis = coll.find({})
        all_apis = [var["api_key"] for var in all_apis]
        flag = True
        user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
        user_points = list(user_points)
        points = user_points[0]["points"]
        while flag:
            try:
                api_key = random.choice(all_apis)
                client = ElevenLabs(
                    api_key=api_key,  # Defaults to ELEVEN_API_KEY
                )

                response = client.voices.get_all()
                flag = False
            except:
                pass

        all_audios_data = []
        for var in list(response.voices):
            get_audio = dict(var)
            voice_id = get_audio["voice_id"]
            name = get_audio["name"]
            category = get_audio["category"]
            gender = get_audio["labels"]["gender"]
            preview_url = get_audio["preview_url"]
            print(name, category, gender)
            all_audios_data.append([voice_id, name, category, gender, preview_url])

        return render_template("text_to_speech.html",points=points, all_audios_data=all_audios_data, user_id=user_id, username=username)

    except Exception as e:
        app.logger.debug(f"Error in user points route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('user_data', _external=True, _scheme=secure_type))

def sending_email_mail(app, to_m, subject_main, body_text, html_text, attachment_all_file):
    try:
        mail = Mail(app)

        msg = Message(subject_main, sender=app.config['MAIL_USERNAME'],
                      recipients=to_m)
        msg.html = html_text

        for file_path in attachment_all_file:
            with open(file_path, 'rb') as f:
                filename = f.name.split("\\")[-1]
                msg.attach(filename=filename, content_type='application/octet-stream', data=f.read())

        try:
            mail.send(msg)
            app.logger.debug(f"Email sent successfully!")
        except Exception as e:
            app.logger.debug(f"Error in sending mail function: {e}")

        return "success"

    except Exception as e:
        app.logger.debug(f"Error in sending mail function: {e}")
        return "failure"

def send_mail_user(email_sender, email_password, to_m, server, port, file_paths, subject, html_content):
    try:
        # Create the email
        message = MIMEMultipart()
        message['From'] = email_sender
        message['To'] = to_m
        message['Subject'] = subject

        # Add body to the email
        body = 'This is the body of the email'
        message.attach(MIMEText(html_content, 'html'))

        # Attach each file in the list
        for file_path in file_paths:
            try:
                with open(file_path, 'rb') as attachment:
                    # Create a MIMEBase object
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())

                # Encode the payload using base64 encoding
                encoders.encode_base64(part)
                filename = file_path.split("\\")[-1]
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}',
                )

                # Attach the file to the email
                message.attach(part)
            except Exception as e:
                print(f'Failed to attach {file_path}: {e}')

        # Connect to the SMTP server and send the email
        try:
            print("connect smtp")
            with smtplib.SMTP(server, port) as server:
                server.starttls()  # Secure the connection
                server.login(email_sender, email_password)  # Log in to the server
                print("connected")
                server.sendmail(email_sender, to_m, message.as_string())  # Send the email
            print('Email sent successfully!')
        except Exception as e:
            print(f'Failed to send email: {e}')

    except Exception as e:
        print(e)

@app.route("/email_sending", methods=["GET", "POST"])
@token_required
def email_sending():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        if request.method == "POST":
            subject_title = request.form["emailsubject"]
            mail_format = request.form["subjectmail"]
            selectrecord = request.form["selectrecord"]
            selectrecord = selectrecord.split(",")
            res = find_all_data(app, db, "customer_data")

            attachment_all_file = []
            if 'file' in request.files:
                images = request.files.getlist("file")
                for file in images:
                    if file.filename != '':
                        attach_file_path = os.path.join("static/uploads", file.filename)
                        attachment_all_file.append(attach_file_path)
                        file.save(attach_file_path)

            mail_split = mail_format.split("\n")
            all_message_list = []
            for message in mail_split:
                if message != "\r":
                    message = message.replace("\r", "")
                    all_message_list.append(message)

            html_format = ""
            for msg in all_message_list:
                html_format = html_format + "<p>" + msg + "</p>"

            for each_res in res:
                del each_res["_id"]
                if each_res["phone"] in selectrecord:
                    all_keys = list(each_res.keys())
                    for key in all_keys:
                        html_format = html_format.replace("{"+key+"}", each_res[key])

                    try:
                        all_configuration = app.config["email_configuration"][str(user_id)]
                        executor.submit(send_mail_user, all_configuration["server_username"], all_configuration["server_password"], each_res["email"], all_configuration["server_host"], all_configuration["server_port"], attachment_all_file, subject_title, html_format)
                    except:
                        flash("Please set mail configuration...", "danger")
                        return jsonify({"message": "error"})
                    # send_mail_user(all_configuration["server_username"], all_configuration["server_password"], each_res["email"], all_configuration["server_host"], all_configuration["server_port"], attachment_all_file, subject_title, html_format)

            flash("Campaign start successfully...", "success")
            return jsonify({"message": "done"})

    except Exception as e:
        app.logger.debug(f"Error in user points route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('user_data', _external=True, _scheme=secure_type))

def move_call(phone):
    try:
        value = random.randint(111111111111,999999999999)
        refernce_id = "test_"+str(value)
        url = "https://obd-api.myoperator.co/obd-api-v1"

        payload = json.dumps({
            "company_id": "664f0f2ecb1f7268",
            "secret_token": "f2517fe344bad049067105d94703b2b37d95b9c2de388a53fc429bff6e02b971",
            "type": "2",
            "number": phone,
            "public_ivr_id": "6667fe83b1ac9842",
            "reference_id": refernce_id,
            "region": "Guj",
            "caller_id": "<caller id number of a call>",
            "group": "<group of a dedicated number>"
        })
        headers = {
            'x-api-key': 'oomfKA3I2K6TCJYistHyb7sDf0l0F6c8AZro5DJh',
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        print(response.text)
        return {"message": "done"}

    except Exception as e:
        print(e)

@app.route("/smart_bulk_calling", methods=["GET", "POST"])
@token_required
def smart_bulk_calling():
    """
    Handling teacher register process
    :return: teacher register template
    """
    try:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        login_dict = session.get("login_dict", {})
        user_id = login_dict.get("user_id", "")
        username = login_dict.get("username", "")
        if request.method == "POST":
            simplecampaignname = request.form["simplecampaignname"]
            simplemaxretry = request.form["simplemaxretry"]
            smarttext = request.form["smarttext"]
            simplevoiceid = request.form["simplevoiceid"]
            smartvoiceselected = request.form["smartvoiceselected"]
            selectrecord = request.form["selectrecord"]
            if type(selectrecord)==list:
                pass
            else:
                selectrecord = selectrecord.split(",")
            res = find_all_data(app, db, "customer_data")
            if simplevoiceid.lower() == "select voiceid" and smarttext=="":
                flash("Please select atleast 1 calling service", "danger")
                return jsonify({"message": "error"})
            elif simplevoiceid.lower() == "select voiceid":
                try:
                    userid_dict = app.config["smart_voicecall_details"][user_id]
                except:
                    app.config["smart_voicecall_details"][user_id] = {}
                for each_res in res:
                    try:
                        del each_res["_id"]
                        if str(each_res["phone"]) in selectrecord:
                            phone = str(each_res["phone"])
                            all_keys = list(each_res.keys())
                            for key in all_keys:
                                smarttext = smarttext.replace("{" + key + "}", str(each_res[key]))
                            try:
                                if "91" == str(phone)[:2]:
                                    phone = "+"+str(phone)
                                elif "+91" not in str(phone):
                                    phone = "+91"+str(phone)
                            except:
                                pass

                            executor.submit(move_call, str(phone))
                            phone = str(phone).replace("+91", "")
                            app.config["smart_voicecall_details"][str(phone)] = {"text": smarttext, "voice": smartvoiceselected}
                            app.logger.debug(f"set config for a call: {app.config['smart_voicecall_details'][str(phone)]}")
                            app.logger.debug(f"set config value for a call: {smarttext, smartvoiceselected}")
                    except Exception as e:
                        app.logger.debug(f"Error on set config value: {e}")
                flash("Your compaign run successfully...", "success")
                return jsonify({"message": "done"})
            else:
                audio_user_data = find_spec_data(app, db, "audio_store", {"audio_id": int(simplevoiceid)})
                audio_user_data = list(audio_user_data)
                app.logger.debug(f"data of audio user: {audio_user_data}")
                points_min = audio_user_data[0]["credits"]
                allnumbers = []
                for var in selectrecord:
                    var = str(var)
                    var = var.replace("+91", "")
                    if len(var)>10:
                        if "91" == var[:2]:
                            var = var[2:]
                        var = var.replace("+91", "")
                    allnumbers.append(var)
                selectrecord = allnumbers
                df = pd.DataFrame({"number": selectrecord})
                value = random.randint(111,999999999999)
                file_name = "record_call_"+ str(value)+".csv"
                filepath = f"static/upload/{file_name}"
                df.to_csv(filepath, index=False)
                app.logger.debug("file save successfully")
                exten = file_name.split(".")[-1]
                api_user_id = app.config["user_token"].get(login_dict["user_id"], {}).get("session_userid", "nothing")
                api_token = app.config["user_token"].get(login_dict["user_id"], {}).get("access_token", "nothing")
                status, baseid, message = get_baseid(api_user_id, file_name, filepath, api_token)
                if status:
                    all_numbers = selectrecord
                    user_points = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
                    user_points = list(user_points)
                    points = user_points[0]["points"]
                    required_points = len(all_numbers) * int(points_min)
                    if required_points > points:
                        flash("Please recharge your account, don't enough points you have...", "warning")
                        return jsonify({"message": "done"})
                    else:
                        status_api, campaignId, message = bulk_calling_with_api(api_user_id, api_token, simplecampaignname,
                                                                                baseid, simplevoiceid, simplemaxretry)
                        app.logger.debug("completed")
                        if status_api:
                            all_points_data = find_spec_data(app, db, "points_mapping", {"user_id": user_id})
                            all_points_data = list(all_points_data)
                            campaigns_total = all_points_data[0]["campaigns"]
                            totalcalls = all_points_data[0]["calls"]

                            points_data_mapping = {"user_id": user_id, "campaign_id": str(campaignId), "points_min": 1,
                                                   "points_cut": False}
                            data_added(app, db, "data_points_mapping", points_data_mapping)
                            update_mongo_data(app, db, "points_mapping", {"user_id": user_id},
                                              {"campaigns": int(campaigns_total) + 1,
                                               "calls": int(totalcalls) + len(all_numbers)})

                            flash(message, "success")
                            return jsonify({"message": "done"})
                        else:
                            flash(message, "danger")
                            return jsonify({"message": "done"})
                else:
                    flash("Please try again..", "danger")
                    return {"message": "error"}

    except Exception as e:
        app.logger.debug(f"Error in user points route: {e}")
        flash("Please try again...","danger")
        return redirect(url_for('user_data', _external=True, _scheme=secure_type))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)
