import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date

# --- CONFIGURATION ---
JSON_FILE = 'meal_plans.json'
CSV_FILE = 'history.csv'

# --- HELPER FUNCTIONS ---
def load_json():
    if not os.path.exists(JSON_FILE):
        st.error(f"File not found: {JSON_FILE}. Please make sure the file exists.")
        st.stop()
    with open(JSON_FILE, 'r') as f:
        return json.load(f)

def load_history():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    else:
        return pd.DataFrame(columns=[
            'Date', 'Week', 'Day_Type', 'Diet_Status', 
            'Calories_In', 'Calories_Burned', 'Net_Deficit', 
            'Predicted_Weight', 'Actual_Weight'
        ])

def save_entry(new_data):
    df = load_history()
    # Check if today is already logged to prevent duplicates
    if not df.empty and str(new_data['Date']) in df['Date'].astype(str).values:
        st.warning("You have already logged data for today.")
        return False
        
    new_row = pd.DataFrame([new_data])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)
    return True

# --- MAIN APP LOGIC ---
st.title("📉 Weight Tracker")

# 1. Load Data
data = load_json()
history = load_history()
profiles = data['profiles']
cheats = data['cheat_tiers']

# 2. Sidebar: Context
st.sidebar.header("User Stats")
if 'user_stats' in data:
    bmr = data['user_stats']['bmr']
    activity_factor = data['user_stats']['daily_activity_multiplier']
    base_tdee = bmr * activity_factor
    st.sidebar.info(f"Base TDEE: {int(base_tdee)} kcal")
else:
    base_tdee = 2000
    st.sidebar.warning("User stats missing")

st.subheader(f"Log for {date.today().strftime('%A, %b %d')}")

# --- A. DIET SECTION ---
st.write("### 🍎 Diet")
col1, col2 = st.columns(2)

with col1:
    # Auto-select day based on today's name
    day_mapping = {"Mon": "mon_wed_fri", "Tue": "tue_thu_sat", "Wed": "mon_wed_fri", "Thu": "tue_thu_sat", "Fri": "mon_wed_fri", "Sat": "tue_thu_sat", "Sun": "sunday"}
    today_short = date.today().strftime("%a")
    key_list = list(profiles.keys())
    
    # Select the correct index safely
    default_key = day_mapping.get(today_short, key_list[0])
    default_index = key_list.index(default_key) if default_key in key_list else 0
        
    day_type = st.selectbox("Which Meal Plan?", key_list, index=default_index)

with col2:
    # We keep the Diet status as Radio because it has 3 options (Yes/Partial/No)
    diet_status = st.radio("Did you follow the plan?", ["Yes", "Partial", "No"], horizontal=True)

# Calculation Logic
selected_profile = profiles[day_type]
base_cals = selected_profile['total_calories']
final_intake = base_cals 

if diet_status == "Partial":
    skipped = st.selectbox("Which meal did you skip?", list(selected_profile['meals'].keys()))
    final_intake = base_cals - selected_profile['meals'][skipped]
    st.info(f"Skipped {skipped}: -{selected_profile['meals'][skipped]} kcal")
    
elif diet_status == "No":
    st.write("Replacement / Cheat Details:")
    meal_replaced = st.selectbox("Which meal did you replace?", ["None (Extra Food)"] + list(selected_profile['meals'].keys()))
    cheat_size = st.select_slider("Cheat Size", options=["small", "medium", "large"])
    
    added_cals = cheats[cheat_size]['calories']
    removed_cals = 0
    if meal_replaced != "None (Extra Food)":
        removed_cals = selected_profile['meals'][meal_replaced]
        
    final_intake = base_cals - removed_cals + added_cals
    st.write(f"**Total Intake: {final_intake} kcal**")

# --- B. TRAINING SECTION ---
st.write("---")
st.write("### 🏋️ Training")

# RESTORED: Checkbox
trained = st.checkbox("Did you train today?")
burn_cals = 0

if trained:
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        train_type = st.selectbox("Type", ["Lifting (Legs)", "Lifting (Upper)", "Cardio (LISS)", "Cardio (HIIT)"])
    with t_col2:
        duration = st.number_input("Duration (mins)", min_value=10, value=60, step=5)
        
    multipliers = {"Lifting (Legs)": 7, "Lifting (Upper)": 4, "Cardio (LISS)": 6, "Cardio (HIIT)": 10}
    burn_cals = duration * multipliers[train_type]
    st.success(f"Estimated Burn: {burn_cals} kcal")

# --- C. WEIGHT LOGGING ---
st.write("---")
# RESTORED: Checkbox + FIXED Spelling
log_weight = st.checkbox("Log Body Weight?")

current_weight = None
if log_weight:
    current_weight = st.number_input("Current Scale Weight (kg)", format="%.1f")

# --- D. SAVE BUTTON ---
st.write("")
if st.button("💾 Save Day to History", type="primary"):
    total_out = base_tdee + burn_cals
    net_deficit = total_out - final_intake 
    
    # Prediction Logic
    if not history.empty and pd.notna(history.iloc[-1]['Predicted_Weight']):
        last_weight = history.iloc[-1]['Predicted_Weight']
    elif current_weight:
        last_weight = current_weight
    else:
        last_weight = 80.0 
        
    weight_change = net_deficit / 7700
    new_predicted = last_weight - weight_change
    
    entry = {
        'Date': date.today(),
        'Week': date.today().isocalendar()[1],
        'Day_Type': day_type,
        'Diet_Status': diet_status,
        'Calories_In': final_intake,
        'Calories_Burned': burn_cals,
        'Net_Deficit': net_deficit,
        'Predicted_Weight': round(new_predicted, 2),
        'Actual_Weight': current_weight if log_weight else None
    }
    
    if save_entry(entry):
        st.success("✅ Data Saved!")
        # AUTO-REFRESH: This fixes the issue where you had to manually refresh
        st.rerun()

# --- E. CHART ---
st.write("---")
if not history.empty:
    chart_data = history[['Date', 'Predicted_Weight']].copy()
    chart_data['Date'] = pd.to_datetime(chart_data['Date'])
    chart_data.set_index('Date', inplace=True)
    st.line_chart(chart_data)