import streamlit as st


# Define the pages of the application
intro_page = st.Page("pages/Introduction.py", title="Introduction")
app_page = st.Page("pages/Main_App.py", title="Main Application")
maps_page = st.Page("pages/Maps.py", title="Interactive Maps")


# Aranging the pages in a list for navigation
pages = [intro_page, app_page, maps_page]
pg = st.navigation(pages)
pg.run()