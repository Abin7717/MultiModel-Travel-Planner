import streamlit as st
import os
import google.generativeai as genai
from PIL import Image
import pandas as pd
from datetime import datetime
import google.api_core.exceptions as google_exceptions
import requests
import json
import base64

# Configure the Gemini API with the new API key
genai.configure(api_key="AIzaSyC_9FGxNvl-zvlwkovnGdDRcW_Egeb7HEg")  # Replace with your new key from Google AI Studio

# Hardcoded Pexels API key (replace with your actual Pexels API key)
PEXELS_API_KEY = "T7MSTBIBoaGYusUOvBRLlVVzELauUotQS7TT6ZfTG7FqJEtyKGWw21qE"  # Get from https://www.pexels.com/api/

# Initialize the Gemini model
model = genai.GenerativeModel('gemini-1.5-flash')  # Latest free-tier model

# Custom CSS for red and white theme
st.markdown("""
    <style>
    /* General styling */
    .stApp {
        background-color: #f1f1f1;  /* Light gray background for the app */
        font-family: 'Poppins', 'Arial', sans-serif;  /* Consistent font with fallbacks */
    }
    h1 {
        color: #e63946 !important;  /* Red title */
        font-weight: 700;
        text-align: center;
        margin-bottom: 10px;
        font-size: 36px;
        background-color: #ffffff;  /* White background for contrast */
        padding: 10px;
        border-radius: 8px;
    }
    h2 {
        color: #e63946;  /* Red for subheadings */
        font-weight: 600;
        margin-top: 20px;
    }
    h3 {
        color: #e63946;  /* Red for sub-subheadings */
        font-weight: 500;
    }
    /* Input labels */
    .stTextArea label, .stNumberInput label, .stDateInput label, .stSelectbox label, .stFileUploader label {
        color: #333333;  /* Dark gray for labels */
        font-weight: 500;
        font-size: 16px;
    }
    /* Custom class for expander label */
    .custom-expander-label {
        color: #e63946 !important;  /* Red for "Fill in your preferences" */
        font-weight: 500;
        font-size: 16px;
    }
    /* Buttons */
    .stButton>button {
        background-color: #e63946;  /* Red buttons */
        color: #ffffff;  /* White text */
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
        border: none;
        transition: background-color 0.3s;
    }
    .stButton>button:hover {
        background-color: #f4a261;  /* Light red/pink on hover */
    }
    /* Alerts */
    .stAlert {
        border-radius: 8px;
        padding: 15px;
        font-size: 15px;
        background-color: #ffffff;  /* White background for alerts */
        color: #333333;  /* Dark gray text */
        border: 1px solid #e63946;  /* Red border */
    }
    /* Image gallery styling */
    .stImage {
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);  /* Subtle shadow for images */
    }
    /* Footer styling */
    footer {
        text-align: center;
        color: #333333;  /* Dark gray footer text */
        font-size: 14px;
        margin-top: 30px;
    }
    footer a {
        color: #e63946;  /* Red links in footer */
        text-decoration: none;
    }
    footer a:hover {
        text-decoration: underline;
    }
    /* Container for better spacing */
    .section-container {
        background-color: #ffffff;  /* White background for sections */
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);  /* Subtle shadow */
        margin-bottom: 20px;
        border: 1px solid #e63946;  /* Red border for sections */
    }
    /* Ensure text visibility for other elements */
    .stMarkdown, .stWrite, .stDataFrame {
        color: #333333;  /* Dark gray for general text */
    }
    </style>
""", unsafe_allow_html=True)

# Function definitions
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except FileNotFoundError:
        return None

def get_usd_to_inr_rate():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success":
            return data["rates"]["INR"]
        else:
            st.warning("Failed to fetch exchange rate. Using default rate of 83.5 INR/USD.")
            return 83.5
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        st.warning(f"Error fetching exchange rate: {str(e)}. Using default rate of 83.5 INR/USD.")
        return 83.5

def fetch_pexels_images(query, max_images=5):
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": query, "per_page": max_images}
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        photos = data.get("photos", [])
        return [(photo["src"]["medium"], photo["alt"] or query) for photo in photos]
    except requests.RequestException as e:
        st.warning(f"Error fetching images from Pexels: {str(e)}. No images will be displayed.")
        return []

def list_available_models():
    try:
        models = genai.list_models()
        return [m.name for m in models if 'generateContent' in m.supported_generation_methods]
    except google_exceptions.GoogleAPIError as e:
        st.error(f"Error listing models: {str(e)}")
        return []

def extract_destination(preferences):
    preferences = preferences.lower()
    if "paris" in preferences:
        return "Paris"
    elif "goa" in preferences:
        return "Goa"
    elif "himachal" in preferences:
        return "Himachal Pradesh"
    else:
        return preferences.split(" in ")[-1] if " in " in preferences else preferences

def generate_itinerary(preferences, budget, start_date, end_date, num_travelers, activities, image=None):
    trip_duration = (end_date - start_date).days + 1
    destination = extract_destination(preferences)
    prompt = (
        f"Generate a travel itinerary for a {trip_duration}-day trip tailored for Indian travelers based on the following details:\n"
        f"Preferences: {preferences}\n"
        f"Budget: ₹{budget} INR (approximately ${budget / usd_to_inr_rate:.2f} USD)\n"
        f"Start Date: {start_date.strftime('%Y-%m-%d')}\n"
        f"End Date: {end_date.strftime('%Y-%m-%d')}\n"
        f"Number of Travelers: {num_travelers}\n"
        f"Preferred Activities: {', '.join(activities) if activities else 'None specified'}\n"
        f"Note: Ensure the itinerary is cost-effective and suitable for Indian travelers, considering local travel options, cultural preferences, and budget constraints. "
        f"Include popular attractions in {destination} (e.g., for Paris, include Eiffel Tower, Louvre, Notre-Dame) relevant to the preferences and activities."
    )
    
    try:
        if image:
            img = Image.open(image)
            prompt += "\nThe user also uploaded an image that represents their desired destination. Analyze the image and incorporate its context (e.g., beach, mountain, city) into the itinerary."
            response = model.generate_content([prompt, img])
        else:
            response = model.generate_content(prompt)

        itinerary_text = response.text if hasattr(response, 'text') else "No itinerary generated. Please try again."
        pexels_images = fetch_pexels_images(destination)
        days = itinerary_text.split("\n") if itinerary_text else []
        itinerary_df = pd.DataFrame(days, columns=["Itinerary"]) if days else pd.DataFrame()

        return itinerary_text, itinerary_df, pexels_images

    except google_exceptions.GoogleAPIError as e:
        st.error(f"Error generating itinerary: {str(e)}")
        return None, pd.DataFrame(), []

# Header image (you can replace with a travel-themed image URL or local path)
header_image_url = "https://images.pexels.com/photos/338504/pexels-photo-338504.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1"
st.markdown(
    f"""
    <div style='text-align: center;'>
        <img src='{header_image_url}' style='width: 100%; max-height: 300px; object-fit: cover; border-radius: 10px; margin-bottom: 20px; border: 2px solid #e63946;' alt='Travel Banner'>
    </div>
    """,
    unsafe_allow_html=True
)

# Title without highlighting "Travel Planner"
st.markdown(
    """
    <h1 style='color: #e63946; font-size: 36px; text-align: center; font-family: Arial, sans-serif; background-color: #ffffff; padding: 10px; border-radius: 8px;'>
        🌍 Multimodal Travel Planner for India
    </h1>
    """,
    unsafe_allow_html=True
)

# Subtitle
st.write("Plan your dream trip with a personalized itinerary and stunning visuals of top attractions!")

# Main container for inputs
with st.container():
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    # Travel Details subheading in black
    st.markdown(
        """
        <h2 style='color: #000000; font-weight: 600; margin-top: 20px;'>
            ✨ Travel Details
        </h2>
        """,
        unsafe_allow_html=True
    )
    
    # Additional user inputs in an expander with red label
    st.markdown(
        """
        <style>
        div[data-testid="stExpander"] > div > div > div > p {
            color: #e63946 !important;
            font-weight: 500;
            font-size: 16px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    with st.expander("Fill in your preferences", expanded=True):
        user_preferences = st.text_area("Enter your travel preferences (e.g., 'beach vacation in Goa' or 'trip to Paris'):", placeholder="e.g., hill station in Himachal")
        budget = st.number_input("Enter your total budget (in ₹ INR):", min_value=0.0, step=1000.0, value=83000.0)  # Default ~1000 USD * 83.5
        
        # Fetch and display USD equivalent
        usd_to_inr_rate = get_usd_to_inr_rate()
        budget_usd = budget / usd_to_inr_rate if usd_to_inr_rate else 0
        st.write(f"💵 Approximate budget in USD: **${budget_usd:.2f}** (at 1 USD = ₹{usd_to_inr_rate:.2f})")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date of your trip:", min_value=datetime(2025, 5, 31), value=datetime(2025, 6, 1))
        with col2:
            end_date = st.date_input("End date of your trip:", min_value=start_date, value=start_date)
        
        num_travelers = st.number_input("Number of travelers:", min_value=1, step=1, value=1)
        activities = st.multiselect("Preferred activities:", options=["Sightseeing", "Adventure", "Relaxation", "Cultural Experiences", "Food Tours"], default=["Sightseeing"])
        
        # Image upload
        uploaded_image = st.file_uploader("📸 Upload an image of your desired destination or scenery (optional):", type=["jpg", "png", "jpeg"])
    
    st.markdown('</div>', unsafe_allow_html=True)

# Buttons for actions
col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
    generate_btn = st.button("🚀 Generate Itinerary")
with col_btn2:
    model_btn = st.button("🔍 List Available Models")

# Debug section for listing models
if model_btn:
    with st.spinner("Fetching available models..."):
        available_models = list_available_models()
        if available_models:
            with st.container():
                st.markdown('<div class="section-container">', unsafe_allow_html=True)
                st.subheader("Available Models")
                st.write(available_models)
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning("No models retrieved. Check API key or network connection.")

# Generate itinerary
if generate_btn:
    if user_preferences and start_date <= end_date:
        with st.spinner("Crafting your dream itinerary... 🌟"):
            itinerary_text, itinerary_df, pexels_images = generate_itinerary(
                user_preferences, budget, start_date, end_date, num_travelers, activities, uploaded_image
            )
        
        if itinerary_text:
            with st.container():
                st.markdown('<div class="section-container">', unsafe_allow_html=True)
                st.subheader("📜 Your Personalized Travel Itinerary")
                st.write(itinerary_text)
                st.markdown('</div>', unsafe_allow_html=True)

                if not itinerary_df.empty:
                    with st.container():
                        st.markdown('<div class="section-container">', unsafe_allow_html=True)
                        st.subheader("📅 Itinerary Overview")
                        st.dataframe(itinerary_df, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                if pexels_images:
                    with st.container():
                        st.markdown('<div class="section-container">', unsafe_allow_html=True)
                        st.subheader(f"📸 Explore Places to Visit in {extract_destination(user_preferences)}")
                        cols = st.columns(min(len(pexels_images), 5))
                        for idx, (img_url, img_alt) in enumerate(pexels_images):
                            with cols[idx % 5]:
                                st.image(img_url, caption=img_alt, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)

            st.success("Itinerary generated successfully! 🎉")
    else:
        if not user_preferences:
            st.error("Please enter your travel preferences to generate an itinerary.")
        if start_date > end_date:
            st.error("End date must be on or after the start date.")

# Footer with attributions
st.markdown("""
    <footer>
        Powered by Google Gemini API, Streamlit, 
        <a href="https://www.exchangerate-api.com" target="_blank">Rates By Exchange Rate API</a>, 
        and <a href="https://www.pexels.com/api/" target="_blank">Pexels API</a>
    </footer>
""", unsafe_allow_html=True)