"""
 maintain all constant value in here
"""
import os
from dotenv import load_dotenv

load_dotenv()

constant_data = {
    "enviroment": os.getenv("enviroment"),
    "log_file_name": "server.log",
    "secure_type": os.getenv("secure_type"),
    "search_dict": {
        "student": "student_data",
        "teacher": "teacher_data",
        "admin": "admin_data"
    },
    "city_province_mapping": {
      "Aalsmeer": "North Holland",
      "Alkmaar": "North Holland",
      "Almelo": "Overijssel",
      "Almere": "Flevoland",
      "Amersfoort": "Utrecht",
      "Amsterdam": "North Holland",
      "Apeldoorn": "Gelderland",
      "Arnhem": "Gelderland",
      "Assen": "Drenthe",
      "Breda": "North Brabant",
      "Delft": "South Holland",
      "Den Bosch ('s-Hertogenbosch)": "North Brabant",
      "Den Haag (The Hague)": "South Holland",
      "Deventer": "Overijssel",
      "Dordrecht": "South Holland",
      "Ede": "Gelderland",
      "Eindhoven": "North Brabant",
      "Emmen": "Drenthe",
      "Enschede": "Overijssel",
      "Gouda": "South Holland",
      "Groningen": "Groningen",
      "Haarlem": "North Holland",
      "Haarlemmermeer": "North Holland",
      "Heerlen": "Limburg",
      "Helmond": "North Brabant",
      "Hengelo": "Overijssel",
      "Hilversum": "North Holland",
      "Hoofddorp": "North Holland",
      "Leeuwarden": "Friesland",
      "Leiden": "South Holland",
      "Lelystad": "Flevoland",
      "Maastricht": "Limburg",
      "Nijmegen": "Gelderland",
      "Oss": "North Brabant",
      "Roosendaal": "North Brabant",
      "Rotterdam": "South Holland",
      "Schiedam": "South Holland",
      "Sittard": "Limburg",
      "Tilburg": "North Brabant",
      "Utrecht": "Utrecht",
      "Venlo": "Limburg",
      "Vlaardingen": "South Holland",
      "Zaandam": "North Holland",
      "Zoetermeer": "South Holland",
      "Zwolle": "Overijssel"
    },
    "search_dict_data": ["allcountrycode", "alldata"],
    "show_data_dict": {
        "admin_data": ["photo_link", "username", "gender", "contact_no", "email", "address"],
        "students_data": ["photo_link", "username", "gender", "contact_no", "email", "address"],
        "teacher_data": ["photo_link", "username", "gender", "contact_no", "email", "address"],
        "user_data": ["photo_link", "username", "gender", "contact_no", "email", "address", "type"],
        "event_data": ["event_name", "event_date", "event_time", "department", "classes", "event_description"],
        "department_data": ["department_name", "HOD_name"],
        "class_data": ["class_name", "subject_name", "teacher_name", "updated_on"],
        "subject_data": ["subject_name", "department_name"],
        "homework_data": ["title", "teacher_name", "class_name", "subject_name"],
        "feedback_data": ["username", "type", "feedback_msg", "all_attechment_files", "inserted_on"],
        "attendance_data": ["username", "class_name", "attendance_date", "status", "reason"]
    },
    "mail_configuration": {
        "server_host": os.getenv("mail_server"),
        "server_port": os.getenv("mail_port"),
        "server_username": os.getenv("mail_username"),
        "server_password": os.getenv("mail_password"),
    },
    "filter_mapping_dict": {
        "userpanel": {"username": "A-Z", "gender": "A-Z", "email": "A-Z", "address": "A-Z"},
        "admin": {"username": "A-Z", "gender": "A-Z", "email": "A-Z", "address": "A-Z"},
        "student": {"username": "A-Z", "gender": "A-Z", "email": "A-Z", "address": "A-Z"},
        "teacher": {"username": "A-Z", "gender": "A-Z", "email": "A-Z", "address": "A-Z"},
        "class": {"class_name": "A-Z", "subject_name": "A-Z", "teacher_name": "A-Z", "updated_on": "A-Z"},
        "homework": {"class_name": "A-Z", "subject_name": "A-Z", "teacher_name": "A-Z", "title": "A-Z"},
        "attendance": {"attendance_date": "A-Z", "status": "A-Z"}
    }
}