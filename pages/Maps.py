"""Interactive Maps page for the GeoNavision application. This page displays an interactive map with markers for nearby points of interest based on the user's location and search query. Each marker includes a popup with information about the location, such as its name, distance from the user, accessibility information, and a link to get directions using Google Maps. The map is generated using the Folium library and displayed in Streamlit using the streamlit-folium component. This page provides a visual representation of the search results, making it easier for users to explore their surroundings and find accessible locations."""

import streamlit as st
from streamlit_folium import st_folium

import folium

def get_directions_url(dest_lat: float, dest_lon: float) -> str:
    """
    Generate Google Maps directions link
    """
    return f"https://www.google.com/maps/dir/?api=1&destination={dest_lat},{dest_lon}"

if "docs" not in st.session_state:
    st.session_state.docs = []


def apply_page_style() -> None:

    """
    Apply Custom CSS to the Maps Page for better layout and map display.
    """
    
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

    apply_page_style()
    m = folium.Map(location=[st.session_state.user_lat, st.session_state.user_lon], zoom_start=15)

    # Define user location marker
    folium.Marker(
        [st.session_state.user_lat, st.session_state.user_lon],
        popup="Current Position",
        icon=folium.Icon(color="blue", icon="user", prefix="fa")
    ).add_to(m)

    for d in st.session_state.docs:

        maps_link: str = get_directions_url(d.metadata['latitude'], d.metadata['longitude'])
        popup_html = f"""
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

else:
    
    st.info("No nearby points of interest found. Please try a different location or query.")