import requests, json
from pymongo import MongoClient
import concurrent.futures

client = MongoClient("mongodb+srv://harshitgadhiya8980:harshitgadhiya8980@cluster0.xradpzd.mongodb.net/")
db = client["voicebot"]

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

api_user_id = "snapgrid"
api_password = "admin123"

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

all_response_data = get_all_audio_file(session_api_userid, session_api_token)
main_dict = {}
for var in all_response_data:
    main_dict[var["fileName"]] = var

def main_process(user_id):
    try:
        coll = db["audio_store"]
        all_audio_data = coll.find({"user_id": user_id})

        for var in all_audio_data:
            if var["file_status"] == "active":
                del var["_id"]
                filename = var["audio_file_name"]
                data_response = main_dict.get(filename, "nothing")
                if data_response=="nothing":
                    pass
                else:
                    condition_dict = {"user_id": user_id, "audio_file_name": filename}
                    coll.update_one(condition_dict, {"$set": {"status": "active"}})

    except Exception as e:
        print(e)

coll = db["user_data"]
all_user_data = coll.find({"status": "activate"})
all_user_ids = [var["user_id"] for var in all_user_data]
executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
threads = []
for user_id in all_user_ids:
    threads.append(executor.submit(main_process, user_id))

