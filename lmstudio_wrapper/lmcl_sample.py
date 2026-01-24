import lmstudio as lms
from os import getenv

model_name = getenv("TEMPMON_MODEL_NAME")
if model_name is None:
    model_name = "google/gemma-3-27b"

with open("llm_system_prompt.md", "r", encoding = 'utf-8') as f:
    system_prompt = f.read()

image_path = "./thermo.jpeg" # Replace with the path to your image
image_handle = lms.prepare_image(image_path)
model = lms.llm(model_name)
chat = lms.Chat()
chat.add_system_prompt(system_prompt)
chat.add_user_message("analyze the image and extract the data", images=[image_handle])
prediction = model.respond(chat)
print(prediction.content)
print(prediction)
