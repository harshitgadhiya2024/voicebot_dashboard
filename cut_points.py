import requests, json
from pymongo import MongoClient
import concurrent.futures

client = MongoClient("mongodb+srv://harshitgadhiya8980:harshitgadhiya8980@cluster0.xradpzd.mongodb.net/")
db = client["voicebot"]

api_user_id = "snapgrid"
api_password = "admin123"


def get_all_live_logs(user_id, token):
    try:
        url = f"https://obdapi.ivrsms.com/api/obd/campaign/{user_id}"

        payload = {}
        headers = {
            'Authorization': f'Bearer {token}'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        return json.loads(response.text)

    except Exception as e:
        print(e)
        return {}

def get_past_logs(user_id, token):
    try:
        url = "https://obdapi.ivrsms.com/api/obd/campaign/historical"

        payload = json.dumps({
            "userId": f"{user_id}",
            "startDate": "",
            "endDate": ""
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        return json.loads(response.text)

    except Exception as e:
        print(e)
        return {}

def get_all_campaign_ids(user_id, session_api_userid, session_api_token):
    try:
        coll = db["data_points_mapping"]
        all_data = coll.find({"user_id": int(user_id), "points_cut": False})
        all_campaign_ids = [var["campaign_id"] for var in all_data]

        all_live_logs = get_all_live_logs(session_api_userid, session_api_token)
        all_past_live_logs = get_past_logs(session_api_userid, session_api_token)
        all_live_logs_dict = {}
        for var1 in all_live_logs:
            all_live_logs_dict[var1["campaignId"]] = var1

        for var2 in all_past_live_logs:
            all_live_logs_dict[var2["campaignId"]] = var2

        all_previous_data = list(all_live_logs_dict.keys())
        # all_live_logs_dict = [{var1.get("campaignId", ""): var1} for var1 in all_live_logs]
        if all_campaign_ids and all_previous_data:
            for campaign_id in all_campaign_ids:
                coll_points = db["points_mapping"]
                all_user_data_points = coll_points.find({"user_id": int(user_id)})
                all_user_data_points = all_user_data_points[0]
                points = all_user_data_points["points"]
                get_data = all_live_logs_dict[int(campaign_id)]
                answer_calls = get_data["callsConnected"]
                collection_dict = {"user_id": user_id, "campaign_id": campaign_id, "previous_points": points,
                                   "connected_calls": answer_calls}
                remaining_points = int(points)-int(answer_calls)
                collection_dict["remianing_points"] = remaining_points
                coll_new = db["points_history"]
                coll_new.insert_one(collection_dict)
                coll_points.update_one({"user_id": user_id}, {"$set":{"points": remaining_points}})
                coll.update_one({"user_id": user_id, "campaign_id": str(campaign_id)}, {"$set": {"points_cut": True}})

    except Exception as e:
        print(e)

coll = db["user_data"]
all_user_data = coll.find({"status": "activate"})
all_user_ids = [var["user_id"] for var in all_user_data]
executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
threads = []
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
for user_id in all_user_ids:
    get_all_campaign_ids(user_id, session_api_userid, session_api_token)
#     threads.append(executor.submit(get_all_campaign_ids, user_id))

