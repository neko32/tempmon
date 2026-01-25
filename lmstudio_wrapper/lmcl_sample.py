import lmstudio as lms
from os import getenv
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(filename)s:%(lineno)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

model_name = getenv("TEMPMON_MODEL_NAME")
if model_name is None:
    model_name = "google/gemma-3-27b"

with open("llm_system_prompt.md", "r", encoding = 'utf-8') as f:
    system_prompt = f.read()

image_path = "./thermo.jpeg" # Replace with the path to your image
#image_handle = lms.prepare_image(image_path)
#model = lms.llm(model_name)
#chat = lms.Chat()
#chat.add_system_prompt(system_prompt)
#chat.add_user_message("analyze the image and extract the data", images=[image_handle])
#prediction = model.respond(chat)
#print(prediction.content)
#print(prediction)

image_handle = lms.prepare_image(image_path)
model_name = "google/gemma-3-27b"
with lms.Client(api_host = "192.168.0.158:1234") as lms_cl:

    model = lms_cl.llm.model(model_name) if model_name else lms_cl.llm.model()
    # Chatはhistoryモジュールから直接インポートして使用
    chat = lms.Chat()
    print("chat created via chat()")
    chat.add_system_prompt(system_prompt)
    chat.add_user_message("analyze the image and extract the data.", images=[image_handle])
    print("added system and user messages")
    prediction = model.respond(chat)
    print("respond() called")
    #print(prediction.content)

    content = prediction.content.replace("```json", "").replace("```", "").strip()

    for l in content.splitlines():
        print(l)

    js = json.loads(content)
    print(js)

    print("done.")
