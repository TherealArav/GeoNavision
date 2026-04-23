"""Interactive Maps page for the GeoNavision application. This page displays an interactive map with markers for nearby points of interest based on the user's location and search query. Each marker includes a popup with information about the location, such as its name, distance from the user, accessibility information, and a link to get directions using Google Maps. The map is generated using the Folium library and displayed in Streamlit using the streamlit-folium component. This page provides a visual representation of the search results, making it easier for users to explore their surroundings and find accessible locations."""

import streamlit as st
from streamlit_folium import st_folium
import requests

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

    st.markdown(
        """
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
""",
        unsafe_allow_html=True,
    )


def add_route_to_map(m: folium.Map, start_lat: float, start_lon: float, dest_lat: float, dest_lon: float) -> None:
    """
    Fetches driving route from OSRM and adds a PolyLine to the provided Folium map.
    """
    # OSRM API requires coordinates in Longitude, Latitude order
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
    
    try:
        # Add a timeout so the Streamlit app doesn't hang indefinitely if the API is down
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 'Ok':
            # 1. Extract the route geometry
            route_coords = data['routes'][0]['geometry']['coordinates']
            
            # 2. Convert [lon, lat] from OSRM to [lat, lon] for Folium
            folium_coords = [[lat, lon] for lon, lat in route_coords]
            
            # 3. Extract metadata for the tooltip
            distance_km = data['routes'][0]['distance'] / 1000
            duration_min = data['routes'][0]['duration'] / 60
            tooltip_info = f"Route: {distance_km:.2f} km (~{duration_min:.0f} mins)"

            st.sidebar.markdown(f"**Route Info:** {tooltip_info}")  # Display route info in the sidebar for quick reference
            
            # 4. Draw the line on the map
            folium.PolyLine(
                locations=folium_coords,
                color='#3b82f6', # A clean, visible blue
                weight=6,
                opacity=0.8,
                tooltip=tooltip_info
            ).add_to(m)
            
        else:
            st.warning(f"Could not calculate route: {data.get('message', 'Unknown routing error')}")
            
    except requests.exceptions.RequestException as e:
        # If the network call fails, show an error in the Streamlit UI instead of crashing
        st.error("Failed to connect to the routing service. Showing straight-line distance instead.")
        
        # Fallback: Draw a simple straight line if the API fails
        folium.PolyLine(
            locations=[[start_lat, start_lon], [dest_lat, dest_lon]],
            color='gray',
            weight=4,
            dash_array='10',
            tooltip="API Offline - Showing straight line"
        ).add_to(m)


poi_list: dict[str,tuple[float,float]] = {}


st.set_page_config(page_title="GeoNavision - Maps", page_icon="static/maps.svg")
if st.session_state.docs:
    apply_page_style()

    # Create a mapping of POI names to their cordinates for easy access when creating markers
    poi_list = {
        d.metadata["poi_name"]: (d.metadata["latitude"], d.metadata["longitude"])
        for d in st.session_state.docs
    }

    st.sidebar.title("Route Navigation")
    selected_poi_name = st.sidebar.selectbox(
        "Select your destination:",
        options=list(poi_list.keys()),
        index=None, 
        placeholder="Choose a POI..."
    )


    m = folium.Map(
        location=[st.session_state.user_lat, st.session_state.user_lon], zoom_start=15
    )

    if selected_poi_name:
        dest_lat = poi_list[selected_poi_name][0]
        dest_lon = poi_list[selected_poi_name][1]
        add_route_to_map(m, st.session_state.user_lat, st.session_state.user_lon, dest_lat, dest_lon)


    # Define user location marker
    folium.Marker(
        [st.session_state.user_lat, st.session_state.user_lon],
        popup="Current Position",
        icon=folium.Icon(color="blue", icon="user", prefix="fa"),
    ).add_to(m)

    for d in st.session_state.docs:

        maps_link: str = get_directions_url(
            d.metadata["latitude"], d.metadata["longitude"]
        )
        popup_html = f"""
        <div style="font-family: Arial; width: 200px;">
            <b>{d.metadata['poi_name']}</b><br>
            Distance: {d.metadata['distance_km']} km<br>
            Accessibility: {d.metadata['wheelchair']}<br>
            <a href='{maps_link}' target='_blank'>Get Directions</a>
        </div>
        """

        folium.Marker(
            [d.metadata["latitude"], d.metadata["longitude"]],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="orange", icon="location-dot", prefix="fa"),
        ).add_to(m)

    # Display the map at the center
    st_folium(m, width="100%", height=1000, returned_objects=[])

else:

    st.info(
        "No nearby points of interest found. Please try a different location or query."
    )
