"""Main application file for the Context-Aware Navigation RAG system. This file sets up the Streamlit application, defines the different pages (Introduction, Main Application, Interactive Maps), and manages navigation between these pages. It serves as the entry point for the application, allowing users to explore the various features and functionalities provided by the system."""

import streamlit as st


def mainApp():
    # Define the pages of the application
    intro_page = st.Page("pages/Introduction.py", title="Introduction")
    app_page = st.Page("pages/Main_App.py", title="Main Application")
    maps_page = st.Page("pages/Maps.py", title="Interactive Maps")


    # Aranging the pages in a list for navigation
    pages = [intro_page, app_page, maps_page]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    mainApp()
