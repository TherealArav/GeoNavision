import streamlit as st
import folium
from streamlit_folium import st_folium

def get_directions_url(dest_lat: float, dest_lon: float) -> str:
    """
    Generate Google Maps directions link
    """
    return f"https://www.google.com/maps/dir/?api=1&destination={dest_lat},{dest_lon}"

if "docs" not in st.session_state:
    st.session_state.docs = []


st.markdown("""
    <style>
        /* 1. Remove standard Streamlit padding */
        .block-container {
            padding-top: 0rem;
            padding-bottom: 0rem;
            padding-left: 0rem;
            padding-right: 0rem;
        }

        /* 2. Force the map (iframe) to fill the height */
        iframe {
            height: 100vh !important;
            width: 100% !important;
        }
        

    </style>
""", unsafe_allow_html=True)

# Map Visualization
if st.session_state.docs:
    m = folium.Map(location=[st.session_state.user_lat, st.session_state.user_lon], zoom_start=15)

    # Define user location marker
    folium.Marker(
        [st.session_state.user_lat, st.session_state.user_lon],
        popup="Current Position",
        icon=folium.Icon(color="blue", icon="user", prefix="fa")
    ).add_to(m)

    for d in st.session_state.docs:
        maps_link = get_directions_url(d.metadata['latitude'], d.metadata['longitude'])
        popup_html: str = f"""
        <div style="font-family: Arial; width: 200px;">
            <b>{d.metadata['poi_name']}</b><br>
            Distance: {d.metadata['distance_km']} km<br>
            Accessibility: {d.metadata['wheelchair']}<br>
            <a href='{maps_link}' target='_blank'>Get Directions</a>
        </div>
        """
        folium.Marker(
            [d.metadata['latitude'], d.metadata['longitude']],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="orange", icon="location-dot", prefix="fa")
        ).add_to(m)
    
    # Display the map at the center
    st_folium(m,width= "100%",height=1000,returned_objects=[])