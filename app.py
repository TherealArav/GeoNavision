import os
import streamlit as st
import requests
from langchain_core.retrievers import BaseRetriever
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import List, Dict, Any
import numpy as np
from scipy.io.wavfile import write as write_wav
import io
import base64
import pandas as pd
from geopy.distance import great_circle
from dotenv import load_dotenv

load_dotenv()
# --- 1. CUSTOM LANGCHAIN RETRIEVER FOR POIS ---
class GoogleMapsPOIRetriever(BaseRetriever):
    """
    Custom LangChain Retriever that:
    1. Takes a user's location (lat, long) and a query (e.g., "restaurants").
    2. Fetches POIs from the Google Maps Places API (Nearby Search), including coordinates.
    3. Calculates the distance from the user to each POI.
    4. For each POI, fetches a descriptive snippet from Google Search.
    5. Returns these snippets and data as LangChain `Document` objects.
    """
    user_latitude: float
    user_longitude: float
    maps_api_key: str
    search_api_key: str
    cse_id: str
    radius: int = 1500  # 1.5km radius

    def _get_pois_from_maps(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetches POIs from Google Maps Nearby Search.
        Now we will make a real API call.
        """
        print(f"--- [Google Maps API] Searching for '{query}' near ({self.user_latitude}, {self.user_longitude}) ---")
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{self.user_latitude},{self.user_longitude}",
            "radius": self.radius,
            "keyword": query,
            "key": self.maps_api_key
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an error for bad responses
            results = response.json()
            if results.get("status") == "OK":
                return results.get("results", [])
            else:
                st.error(f"Google Maps API Error: {results.get('status')} - {results.get('error_message', '')}")
                return []
        except requests.exceptions.RequestException as e:
            st.error(f"HTTP Error calling Google Maps: {e}")
            return []

    def _get_search_snippet(self, poi_name: str, vicinity: str) -> str:
        """
        Uses Google Search API to get a snippet for a POI.
        """
        print(f"--- [Google Search API] Searching for snippet: '{poi_name} {vicinity}' ---")
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.search_api_key,
            "cx": self.cse_id,
            "q": f"{poi_name} {vicinity}",
            "num": 1
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            results = response.json()
            if "items" in results and len(results["items"]) > 0:
                return results["items"][0].get("snippet", "No description found.")
            else:
                st.write(f"No items found for query: {poi_name}")
                return "No description found."
        except requests.exceptions.RequestException as e:
            st.error(f"HTTP Error calling Google Search: {e}")
            return "Error fetching description."
        except Exception as e:
            st.error(f"Error processing search snippet: {e}")
            return "Error fetching description."

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """
        The main method for the retriever.
        """
        # 1. Retrieve POIs from Google Maps
        pois = self._get_pois_from_maps(query)
        
        documents = []
        user_location = (self.user_latitude, self.user_longitude)
        
        for poi in pois:
            poi_name = poi.get("name", "Unknown Place")
            vicinity = poi.get("vicinity", "")
            
            # 2. Get POI Location and Calculate Distance
            poi_location_data = poi.get("geometry", {}).get("location", {})
            poi_lat = poi_location_data.get("lat")
            poi_lon = poi_location_data.get("lng")
            
            distance_km = "N/A"
            if poi_lat and poi_lon:
                poi_location = (poi_lat, poi_lon)
                # Calculate distance using geopy's great_circle
                distance_km = f"{great_circle(user_location, poi_location).km:.1f}"

            # 3. Augment: For each POI, get a descriptive snippet
            snippet = self._get_search_snippet(poi_name, vicinity)
            
            # 4. Create a LangChain Document
            doc = Document(
                page_content=snippet,
                metadata={
                    "poi_name": poi_name,
                    "address": vicinity,
                    "source": "google_maps_and_search",
                    "distance_km": distance_km,
                    "latitude": poi_lat,
                    "longitude": poi_lon
                }
            )
            documents.append(doc)
            
        return documents

# --- 2. RAG CONTEXT FORMATTING ---
def format_docs_for_prompt(docs: List[Document]) -> str:
    """
    Formats the retrieved documents into a clean string for the prompt.
    NOW INCLUDES DISTANCE.
    """
    if not docs:
        return "No information found for that query."
        
    return "\n\n".join(
        f"**{doc.metadata.get('poi_name', 'Unknown Place')}** (Distance: {doc.metadata.get('distance_km', 'N/A')} km)\n"
        f"Address: {doc.metadata.get('address', 'N/A')}\n"
        f"Summary: {doc.page_content}"
        for doc in docs
    )

# --- 3. THE RAG "BRAIN" (CACHED) ---
@st.cache_data(show_spinner=False)
def get_rag_response(_query, _latitude, _longitude, _keys):
    """
    Runs the entire RAG chain.
    NOTE: We now call the retriever *first* to get the docs for the map,
    then we pass those docs to the rest of the chain.
    """
    # 1. Instantiate the Retriever with all keys and user location
    retriever = GoogleMapsPOIRetriever(
        user_latitude=_latitude,
        user_longitude=_longitude,
        maps_api_key=_keys["GOOGLE_MAPS_API_KEY"],
        search_api_key=_keys["GOOGLE_SEARCH_API_KEY"],
        cse_id=_keys["GOOGLE_CSE_ID"]
    )
    
    # 2. Instantiate LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        google_api_key=_keys["GOOGLE_API_KEY"]
    )
    
    # 3. Define Prompt Template
    template = """
    You are a friendly and engaging AI tour guide.
    Your task is to provide a short, exciting summary of Points of Interest (POIs) near the user, based *only* on the context provided.
    
    - Use the distance information to help the user understand what's nearby.
    - List each place as a bullet point.
    - Start with a friendly greeting!
    
    CONTEXT ABOUT NEARBY PLACES:
    {context}
    
    YOUR TASK:
    Write a brief, one-paragraph summary for the user, highlighting the places from the context.
    """
    prompt = PromptTemplate.from_template(template)
    
    # 4. Define the final output parser
    output_parser = StrOutputParser()
    
    # --- 5. RUN THE CHAIN IN PARTS ---
    # This is a change: we get the docs first so we can use them for the map.
    
    print("--- [RAG Chain] Step 1: Retrieving documents... ---")
    docs = retriever.invoke(_query)
    
    if not docs:
        return "Sorry, I couldn't find anything for that search.", None
    
    print(f"--- [RAG Chain] Step 2: Found {len(docs)} documents. Formatting context... ---")
    formatted_context = format_docs_for_prompt(docs)
    
    print("--- [RAG Chain] Step 3: Generating response with LLM... ---")
    # Manually run the rest of the chain
    chain = prompt | llm | output_parser
    summary = chain.invoke({"context": formatted_context})
    
    # 6. Create Map Data
    map_data = []
    for doc in docs:
        if doc.metadata.get("latitude") and doc.metadata.get("longitude"):
            map_data.append({
                "lat": doc.metadata["latitude"],
                "lon": doc.metadata["longitude"]
            })
    
    print("--- [RAG Chain] Step 4: Returning summary and map data. ---")
    return summary, map_data


# --- 4. TTS FUNCTION (CACHED) ---
@st.cache_data(show_spinner=False)
def get_tts_audio(_text, _api_key):
    """
    Calls the Gemini TTS API and returns an in-memory WAV file.
    """
    print("--- [TTS] Generating audio... ---")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={_api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": _text}]
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Kore"}
                }
            }
        },
        "model": "gemini-2.5-flash-preview-tts"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        part = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0]
        audio_data = part.get("inlineData", {}).get("data")
        mime_type = part.get("inlineData", {}).get("mimeType")
        
        if audio_data and mime_type and "rate=" in mime_type:
            sample_rate = int(mime_type.split("rate=")[1])
            # Decode the base64 audio data
            pcm_data = base64.b64decode(audio_data)
            # Convert raw PCM16 data to a numpy array
            pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # Create an in-memory WAV file
            wav_io = io.BytesIO()
            write_wav(wav_io, sample_rate, pcm_array)
            wav_io.seek(0)
            return wav_io
        else:
            st.error(f"Could not parse TTS response: {result}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"HTTP Error calling TTS API: {e}")
        return None
    except Exception as e:
        st.error(f"Error processing audio data: {e}")
        return None

# --- 5. HELPER FUNCTIONS ---

# --- UPDATED get_api_key function ---
def get_api_key(key_name):
    """
    Gets an API key from two places, in order:
    1. Streamlit secrets (st.secrets) - for deployment
    2. Environment variables (.env file) - for local testing
    """
    # 1. Try Streamlit secrets (for deployment)
    if key_name in st.secrets:
        return st.secrets[key_name]
    
    # 2. Try .env file (for local testing)
    key_value = os.environ.get(key_name)
    if key_value:
        return key_value
    
    # 3. If nothing works, fail
    st.error(f"API Key Error: '{key_name}' not found in st.secrets or .env file.")
    return None

def clear_cache():
    """
    Clears the cached responses and session state.
    """
    st.cache_data.clear()
    st.session_state.summary = ""
    st.session_state.map_data = None # Clear map data
    st.rerun()

# --- 6. MAIN APP UI ---
st.set_page_config(page_title="AI POI Guide", layout="wide")
st.title("📍 AI Point of Interest Guide")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "map_data" not in st.session_state:
    st.session_state.map_data = None
if "api_keys" not in st.session_state:
    st.session_state.api_keys = {}

# --- 7. SIDEBAR & AUTHENTICATION ---
with st.sidebar:
    st.header("Authentication")
    password = st.text_input("Enter Password", type="password")
    
    # Use the new get_api_key function to find the password
    hackathon_password = get_api_key("HACKATHON_PASSWORD")
    
    if hackathon_password and password == hackathon_password:
        st.session_state.authenticated = True
        st.success("Authenticated!")
        
        # Load all keys into session state *once*
        st.session_state.api_keys = {
            "GOOGLE_API_KEY": get_api_key("GOOGLE_API_KEY"),
            "GOOGLE_MAPS_API_KEY": get_api_key("GOOGLE_MAPS_API_KEY"),
            "GOOGLE_SEARCH_API_KEY": get_api_key("GOOGLE_SEARCH_API_KEY"),
            "GOOGLE_CSE_ID": get_api_key("GOOGLE_CSE_ID")
        }
    elif password:
        st.error("Incorrect password.")

# --- 8. MAIN APP LOGIC (Protected) ---
if st.session_state.authenticated:
    
    # Check if all keys are loaded
    # A bit redundant since get_api_key will error, but good for UX
    all_keys_provided = all(st.session_state.api_keys.values())
    
    if all_keys_provided:
        with st.sidebar:
            st.success("All API keys are configured.")
    else:
        with st.sidebar:
            # The get_api_key function will already be showing a specific error
            st.error("One or more API keys/IDs are missing.")

    # --- Main Application Area ---
    st.markdown("Enter your coordinates manually, or use the defaults for Dubai.")

    default_location = {"latitude": 25.2048, "longitude": 55.2708} # Default: Dubai

    col1, col2 = st.columns(2)
    with col1:
        latitude = st.number_input(
            "Latitude",
            value=default_location["latitude"],
            format="%.4f"
        )
    with col2:
        longitude = st.number_input(
            "Longitude",
            value=default_location["longitude"],
            format="%.4f"
        )
    
    st.success(f"Using location: ({latitude}, {longitude})")
    
    query = st.text_input("What are you looking for?", "museums")
    
    if st.button("Explore Nearby!") and all_keys_provided:
        with st.spinner("Finding POIs, calculating distances, and building your summary..."):
            summary, map_data = get_rag_response(
                query,
                latitude,
                longitude,
                st.session_state.api_keys
            )
        st.session_state.summary = summary
        st.session_state.map_data = map_data
        st.rerun() # Re-run to update the UI
            
    # --- 9. DISPLAY RESULTS (if they exist) ---
    if st.session_state.summary:
        
        # --- NEW: Display the Map ---
        if st.session_state.map_data:
            st.subheader("Map of Nearby Locations")
            try:
                df = pd.DataFrame(st.session_state.map_data)
                df = df.dropna(subset=['lat', 'lon']) # Ensure no bad data
                if not df.empty:
                    st.map(df, zoom=12) # Display the map, zoomed in
                else:
                    st.warning("Could not display map - no valid coordinates found.")
            except Exception as e:
                st.error(f"Error creating map: {e}")
        
        st.markdown("### Your AI Tour Guide Summary")
        st.markdown(st.session_state.summary)
        
        st.divider()
        
        # --- TTS Section ---
        if st.button("Click to Listen to Summary"):
            if all_keys_provided:
                with st.spinner("Generating audio..."):
                    audio_file = get_tts_audio(
                        st.session_state.summary, 
                        st.session_state.api_keys["GOOGLE_API_KEY"]
                    )
                if audio_file:
                    st.audio(audio_file, format="audio/wav")
                else:
                    st.error("Sorry, I could not generate the audio for that summary.")
            else:
                st.error("Cannot generate audio, missing API key.")
        
        # --- Clear Cache Button ---
        st.divider()
        if st.button("Clear Cache & Start Over"):
            clear_cache()

else:
    st.warning("Please enter the password in the sidebar to use the app.")