import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv()

# Define the exact JSON structure the backend needs
class SceneAnalysis(BaseModel):
    immediate_hazards: list[str]
    path_layout: str
    dynamic_obstacles: list[str]
    navigational_signage: list[str]

# - the AI Studio client (automatically picks up GEMINI_API_KEY)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_street_scene(image_path: str):
    # The prompt instructs the model to act as a navigation assistant
    prompt = (
        "Analyze this street scene for a pedestrian with low vision. "
        "Focus on spatial geometry, immediate trip/collision hazards within 3 meters, "
        "the texture of the walking path, and any relevant signs or crosswalks."
    )
    
    # Upload the file to AI Studio's temporary storage
    print(f"Uploading {image_path}...")
    uploaded_image = client.files.upload(file=image_path)
    
    print("Analyzing scene...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[uploaded_image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SceneAnalysis,
            temperature=0.1, # Low temperature for factual, safety-critical analysis
        ),
    )
    
    return response.text

if __name__ == "__main__":
    # Replace with the path to a test image on your local machine
    test_image = "test_intersection.jpg" 
    
    if os.path.exists(test_image):
        result_json = analyze_street_scene(test_image)
        print("\n--- Structured JSON Output ---")
        print(result_json)
    else:
        print(f"Please place an image named '{test_image}' in this directory.")