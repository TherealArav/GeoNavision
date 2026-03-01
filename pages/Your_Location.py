import streamlit as st
from streamlit_geolocation import streamlit_geolocation

st.title("User Location Tracker")

# Renders a button that prompts the user for location access
location = streamlit_geolocation()


# The component returns a dictionary with the data
if location and location.get('latitude'):
    st.success("Location retrieved!")
    st.write(f"**Latitude:** {location['latitude']}")
    st.write(f"**Longitude:** {location['longitude']}")
    st.write(f"**Accuracy:** {location['accuracy']} meters")
else:
    st.info("Please click the button to share your location.")