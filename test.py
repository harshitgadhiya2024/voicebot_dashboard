from elevenlabs.client import ElevenLabs
from elevenlabs import play, save
import os

client = ElevenLabs(
  api_key="3ec564f4c92a2876c6111a5bfbda785c", # Defaults to ELEVEN_API_KEY
)

# response = client.voices.get_all()
# # audio = client.generate(text="Hello there!", voice=response.voices[0])
# # print(response.voices)
# for var in list(response.voices):
#     get_audio = dict(var)
#     voice_id = get_audio["voice_id"]
#     name = get_audio["name"]
#     category = get_audio["category"]
#     gender = get_audio["labels"]["gender"]
#     preview_url = get_audio["preview_url"]
#     print(name, category, gender)

#     # audio = client.generate(
#     #   text="જય સ્વામિનારાયણ. હુ તરવડા ગુરુકુળ થી હિરેન સર વાત કરુ છુ.",
#     #   voice=name,
#     #   model="eleven_multilingual_v2"
#     # )
#     # audio = client.generate(
#     #   text="जय स्वामीनारायण. मै तरवड़ा गुरुकुल से हिरेन सर बोल रहा हू।",
#     #   voice=name,
#     #   model="eleven_multilingual_v2"
#     # )
#     # play(audio)
# #


# voice = client.clone(
#     name="Harshit",
#     description="An old American male voice with a slight hoarseness in his throat. Perfect for news", # Optional
#     files=["output1.wav", "output2.wav", "output3.mp3"],
# )
#
# audio = client.generate(text="Hi! I'm a cloned voice!", voice=voice)
# save(audio, "new_")
# play(audio)


# from pymongo import MongoClient
#
# client = MongoClient("mongodb+srv://harshitgadhiya8980:harshitgadhiya8980@cluster0.xradpzd.mongodb.net/")
#
# db = client["voicebot"]
#
# api_keys = ["d2651a626925b19b51e05dcebe8e55de", "b8ee48ae1a4e9dac3863df94b352a112", "e7db30899929abc5e2686b49df484cad", "3ec564f4c92a2876c6111a5bfbda785c",
#             "7a7a282c029efd6607497c3d14bfdc0f", "7e76e8641d6c5bfbc50509c8c2565a38", "13a57f9730e84268af6250acb5c2a5d2", "15d9f9d4d851637296eddb8808d520e3",
#             "10ca77b01a67f8ba61eedfad867f8cb8", "91063bdfd92b1392b32b43ad97cd5d43", "7849e55b1eb033ba0f27aaf09f8562d2", "08a0ec7acaf27b57e24ec0617a9d3667",
#             "d2651a626925b19b51e05dcebe8e55de", "1186ffd2e692cc92bbe0187d202de81d", "359ebd8bc4c51251e5892c81027b3c90", "bb76e1faea3f20c59636ebfb26d6b1b5",
#             "94271c227fdaffd4a32022adc0c571df", "920128f27a8f648fff7237262e15e672", "7c02da8f141f20da2e88d208d94d5d18", "793ecf8e57bb8557513a0b93233fc4d0", "db2c3d306b5701ebc5a6aab6f3947456"]
#
# for var in api_keys:
#     coll = db["apis"]
#     coll.insert_one({"api_key": var, "insert_date": "28-05-2024"})