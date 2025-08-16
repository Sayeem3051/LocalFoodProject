import streamlit as st
import pandas as pd
import sqlite3

# ---------------- DB Connection ----------------
def get_conn():
    return sqlite3.connect("food_wastage.db")

def run_query(query, params=None):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params or ())
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return pd.DataFrame([dict(row) for row in rows])

def run_commit(query, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params or ())
    conn.commit()
    lastrow = cur.lastrowid
    cur.close()
    conn.close()
    return lastrow

# Helper: Distinct values for filters
def get_distinct_values(table, column):
    df = run_query(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
    if df.empty:
        return []
    return sorted(df[df.columns[0]].dropna().astype(str).tolist())

# ---------------- Browse Listings ----------------
def browse_listings():
    st.header("Browse Food Listings")
    st.markdown("Find available food items and submit claims to reduce waste")
    
    cities = ["All"] + get_distinct_values("food_listings", "Location")
    providers = ["All"] + get_distinct_values("providers", "Name")
    food_types = ["Non-Vegetarian", "Vegetarian", "Vegan"]  # Fixed food types
    meal_types = ["All"] + get_distinct_values("food_listings", "Meal_Type")

    col1, col2, col3 = st.columns(3)
    with col1:
        city = st.selectbox("City", cities)
    with col2:
        provider = st.selectbox("Provider", providers)
    with col3:
        food_type = st.multiselect("Food Type", options=food_types)

    meal = st.selectbox("Meal Type", meal_types)

    base_q = """
      SELECT f.Food_ID, f.Food_Name, f.Quantity, f.Expiry_Date, f.Meal_Type, f.Food_Type, f.Location,
             p.Provider_ID, p.Name as Provider_Name, p.Contact as Provider_Contact, p.Address as Provider_Address
      FROM food_listings f
      JOIN providers p ON f.Provider_ID = p.Provider_ID
    """
    where = []
    params = []
    if city and city != "All":
        where.append("f.Location = ?"); params.append(city)
    if provider and provider != "All":
        where.append("p.Name = ?"); params.append(provider)
    if food_type:
        where.append("f.Food_Type IN (" + ",".join(["?"]*len(food_type)) + ")")
        params.extend(food_type)
    if meal and meal != "All":
        where.append("f.Meal_Type = ?"); params.append(meal)

    if where:
        base_q += " WHERE " + " AND ".join(where)
    base_q += " ORDER BY f.Expiry_Date ASC;"

    df = run_query(base_q, tuple(params))
    
    st.subheader(f"Search Results ({len(df)} listings found)")
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No listings found matching your criteria. Try adjusting your filters.")

    if not df.empty:
        sel = st.selectbox("Select a listing to see details / claim", df['Food_ID'].astype(str).tolist())
        row = df[df['Food_ID'] == int(sel)].iloc[0]
        
        st.subheader(row['Food_Name'])
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Quantity:** {row['Quantity']} servings")
            st.write(f"**Expiry Date:** {row['Expiry_Date']}")
            st.write(f"**Food Type:** {row['Food_Type']}")
        with col2:
            st.write(f"**Provider:** {row['Provider_Name']}")
            st.write(f"**Meal Type:** {row['Meal_Type']}")
            st.write(f"**Location:** {row['Location']}")
        
        with st.expander("Provider Contact Details"):
            st.write(f"**Contact:** {row['Provider_Contact']}")
            st.write(f"**Address:** {row['Provider_Address']}")

        st.divider()
        with st.form("claim_form"):
            receiver_id = st.text_input("Enter your Receiver ID")
            submit = st.form_submit_button("Submit Claim")
            if submit:
                if not receiver_id:
                    st.error("Please provide your Receiver ID.")
                else:
                    insert_q = "INSERT INTO claims (Food_ID, Receiver_ID, Status, Timestamp) VALUES (?, ?, 'Pending', datetime('now'));"
                    last_id = run_commit(insert_q, (int(sel), int(receiver_id)))
                    log_activity("Add", "claims", last_id, f"Food claim submitted: Food ID {sel} by Receiver ID {receiver_id}")
                    st.success("Claim submitted. Provider will be notified.")

# ---------------- Admin Food Listings ----------------
def admin_food_listings():
    st.header("Food Listings Management")
    st.markdown("Add, edit, and delete food listings to help reduce waste")

    # Add new
    with st.expander("Add new listing"):
        with st.form("add_food"):
            name = st.text_input("Food Name")
            qty = st.number_input("Quantity", min_value=1, value=1)
            expiry = st.date_input("Expiry Date")
            provider_id = st.selectbox("Provider", get_distinct_values("providers", "Provider_ID"))
            provider_type = st.text_input("Provider Type")
            location = st.text_input("Location")
            food_type = st.selectbox("Food Type", ["Non-Vegetarian", "Vegetarian", "Vegan"])
            meal_type = st.text_input("Meal Type")
            submit_add = st.form_submit_button("Add Listing")
            if submit_add:
                q = """INSERT INTO food_listings
                       (Food_Name, Quantity, Expiry_Date, Provider_ID, Provider_Type, Location, Food_Type, Meal_Type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?);"""
                last_id = run_commit(q, (name, int(qty), expiry.strftime("%Y-%m-%d"), int(provider_id), provider_type, location, food_type, meal_type))
                log_activity("Add", "food_listings", last_id, f"Added food listing: {name} ({qty} servings, {food_type})")
                st.success("Listing added.")

    # Edit existing
    st.divider()
    df = run_query("SELECT Food_ID, Food_Name FROM food_listings ORDER BY Food_ID DESC;")
    if not df.empty:
        chosen = st.selectbox("Choose listing to edit", df['Food_ID'].astype(str).tolist())
        if chosen:
            # Convert chosen to int, handling float values from database
            food_id = int(float(chosen))
            rec = run_query("SELECT * FROM food_listings WHERE Food_ID = ?", (food_id,)).iloc[0]
            with st.form("edit_food"):
                name = st.text_input("Food Name", value=rec['Food_Name'])
                qty = st.number_input("Quantity", min_value=0, value=int(rec['Quantity']))
                expiry = st.date_input("Expiry Date", value=pd.to_datetime(rec['Expiry_Date']).date() if rec['Expiry_Date'] else None)
                provider_id = st.text_input("Provider_ID", value=str(rec['Provider_ID']))
                provider_type = st.text_input("Provider Type", value=rec.get('Provider_Type', ''))
                location = st.text_input("Location", value=rec.get('Location', ''))
                food_type = st.selectbox("Food Type", ["Non-Vegetarian", "Vegetarian", "Vegan"], index=["Non-Vegetarian", "Vegetarian", "Vegan"].index(rec.get('Food_Type', 'Vegetarian')) if rec.get('Food_Type', 'Vegetarian') in ["Non-Vegetarian", "Vegetarian", "Vegan"] else 1)
                meal_type = st.text_input("Meal Type", value=rec.get('Meal_Type', ''))
                submit_edit = st.form_submit_button("Save changes")
                if submit_edit:
                    upd_q = """UPDATE food_listings SET Food_Name=?, Quantity=?, Expiry_Date=?,
                               Provider_ID=?, Provider_Type=?, Location=?, Food_Type=?, Meal_Type=?
                               WHERE Food_ID=?;"""
                    run_commit(upd_q, (name, int(qty), expiry.strftime("%Y-%m-%d"), int(provider_id),
                                       provider_type, location, food_type, meal_type, food_id))
                    log_activity("Edit", "food_listings", food_id, f"Updated food listing: {name} ({qty} servings, {food_type})")
                    st.success("Listing updated.")

    # Delete
    st.divider()
    del_id = st.number_input("Enter Food_ID to delete", min_value=0, value=0)
    if st.button("Delete listing"):
        if del_id > 0:
            # Get listing details before deletion for logging
            listing_details = run_query("SELECT Food_Name, Quantity, Food_Type FROM food_listings WHERE Food_ID = ?", (int(del_id),))
            if not listing_details.empty:
                details = listing_details.iloc[0]
                log_activity("Delete", "food_listings", int(del_id), f"Deleted food listing: {details['Food_Name']} ({details['Quantity']} servings, {details['Food_Type']})")
            
            run_commit("DELETE FROM food_listings WHERE Food_ID = ?", (int(del_id),))
            st.success(f"Deleted listing {del_id}.")

# ---------------- Provider Portal ----------------
def provider_portal():
    st.header("Provider Portal")
    st.markdown("Manage your listings")
    
    provider_id = st.text_input("Provider ID")
    contact = st.text_input("Provider Contact (for verification)")

    if st.button("Login as Provider"):
        df = run_query("SELECT * FROM providers WHERE Provider_ID = ? AND Contact = ?", (provider_id, contact))
        if df.empty:
            st.error("Invalid Provider ID or contact.")
            return
        st.success(f"Logged in as {df.iloc[0]['Name']}")
        st.session_state['provider_id'] = int(provider_id)

    if st.session_state.get('provider_id'):
        pid = st.session_state['provider_id']
        st.subheader("Your Listings")
        my_listings = run_query("SELECT * FROM food_listings WHERE Provider_ID = ?", (pid,))
        st.dataframe(my_listings)
        if not my_listings.empty:
            sel = st.selectbox("Select your Food_ID to edit/delete", my_listings['Food_ID'].astype(str).tolist())
            # Convert sel to int, handling float values from database
            food_id = int(float(sel))
            rec = my_listings[my_listings['Food_ID'] == food_id].iloc[0]
            with st.form("provider_edit"):
                name = st.text_input("Food Name", value=rec['Food_Name'])
                qty = st.number_input("Quantity", value=int(rec['Quantity']), min_value=0)
                expiry = st.date_input("Expiry Date", value=pd.to_datetime(rec['Expiry_Date']).date() if rec['Expiry_Date'] else None)
                submit = st.form_submit_button("Save")
                if submit:
                    run_commit("""UPDATE food_listings SET Food_Name=?, Quantity=?, Expiry_Date=? WHERE Food_ID=?""",
                               (name, int(qty), expiry.strftime("%Y-%m-%d"), food_id))
                    st.success("Updated listing.")
            if st.button("Delete selected listing"):
                run_commit("DELETE FROM food_listings WHERE Food_ID = ?", (food_id,))
                st.success("Listing deleted.")

# ---------------- Admin Providers ----------------
def admin_providers():
    st.header("Providers Management")
    st.markdown("Manage food providers and their information")
    
    with st.expander("Add new provider"):
        with st.form("add_provider"):
            name = st.text_input("Provider Name")
            ptype = st.text_input("Type")
            address = st.text_area("Address")
            city = st.text_input("City")
            contact = st.text_input("Contact")
            submit_add = st.form_submit_button("Add Provider")
            if submit_add:
                q = """INSERT INTO providers (Name, Type, Address, City, Contact) VALUES (?, ?, ?, ?, ?);"""
                last_id = run_commit(q, (name, ptype, address, city, contact))
                log_activity("Add", "providers", last_id, f"Added provider: {name} ({ptype}) in {city}")
                st.success("Provider added.")

    st.divider()
    df = run_query("SELECT Provider_ID, Name FROM providers ORDER BY Provider_ID DESC;")
    if not df.empty:
        chosen = st.selectbox("Choose provider to edit", df['Provider_ID'].astype(str).tolist())
        if chosen:
            # Convert chosen to int, handling float values from database
            provider_id = int(float(chosen))
            rec = run_query("SELECT * FROM providers WHERE Provider_ID = ?", (provider_id,)).iloc[0]
            with st.form("edit_provider"):
                name = st.text_input("Provider Name", value=rec['Name'])
                ptype = st.text_input("Type", value=rec['Type'])
                address = st.text_area("Address", value=rec['Address'])
                city = st.text_input("City", value=rec['City'])
                contact = st.text_input("Contact", value=rec['Contact'])
                submit_edit = st.form_submit_button("Save changes")
                if submit_edit:
                    upd_q = """UPDATE providers SET Name=?, Type=?, Address=?, City=?, Contact=? WHERE Provider_ID=?;"""
                    run_commit(upd_q, (name, ptype, address, city, contact, provider_id))
                    log_activity("Edit", "providers", provider_id, f"Updated provider: {name} ({ptype}) in {city}")
                    st.success("Provider updated.")

    st.divider()
    del_id = st.number_input("Enter Provider_ID to delete", min_value=0, value=0)
    if st.button("Delete provider"):
        if del_id > 0:
            # Get provider details before deletion for logging
            provider_details = run_query("SELECT Name, Type, City FROM providers WHERE Provider_ID = ?", (int(del_id),))
            if not provider_details.empty:
                details = provider_details.iloc[0]
                log_activity("Delete", "providers", int(del_id), f"Deleted provider: {details['Name']} ({details['Type']}) in {details['City']}")
            
            run_commit("DELETE FROM providers WHERE Provider_ID = ?", (int(del_id),))
            st.success(f"Deleted provider {del_id}.")

# ---------------- Admin Receivers ----------------
def admin_receivers():
    st.header("Receivers Management")
    st.markdown("Manage food receivers and their information")
    
    with st.expander("Add new receiver"):
        with st.form("add_receiver"):
            name = st.text_input("Receiver Name")
            rtype = st.text_input("Type")
            city = st.text_input("City")
            contact = st.text_input("Contact")
            submit_add = st.form_submit_button("Add Receiver")
            if submit_add:
                q = """INSERT INTO receivers (Name, Type, City, Contact) VALUES (?, ?, ?, ?);"""
                last_id = run_commit(q, (name, rtype, city, contact))
                log_activity("Add", "receivers", last_id, f"Added receiver: {name} ({rtype}) in {city}")
                st.success("Receiver added.")

    st.divider()
    df = run_query("SELECT Receiver_ID, Name FROM receivers ORDER BY Receiver_ID DESC;")
    if not df.empty:
        chosen = st.selectbox("Choose receiver to edit", df['Receiver_ID'].astype(str).tolist())
        if chosen:
            # Convert chosen to int, handling float values from database
            receiver_id = int(float(chosen))
            rec = run_query("SELECT * FROM receivers WHERE Receiver_ID = ?", (receiver_id,)).iloc[0]
            with st.form("edit_receiver"):
                name = st.text_input("Receiver Name", value=rec['Name'])
                rtype = st.text_input("Type", value=rec['Type'])
                city = st.text_input("City", value=rec['City'])
                contact = st.text_input("Contact", value=rec['Contact'])
                submit_edit = st.form_submit_button("Save changes")
                if submit_edit:
                    upd_q = """UPDATE receivers SET Name=?, Type=?, City=?, Contact=? WHERE Receiver_ID=?;"""
                    run_commit(upd_q, (name, rtype, city, contact, receiver_id))
                    log_activity("Edit", "receivers", receiver_id, f"Updated receiver: {name} ({rtype}) in {city}")
                    st.success("Receiver updated.")

    st.divider()
    del_id = st.number_input("Enter Receiver_ID to delete", min_value=0, value=0)
    if st.button("Delete receiver"):
        if del_id > 0:
            # Get receiver details before deletion for logging
            receiver_details = run_query("SELECT Name, Type, City FROM receivers WHERE Receiver_ID = ?", (int(del_id),))
            if not receiver_details.empty:
                details = receiver_details.iloc[0]
                log_activity("Delete", "receivers", int(del_id), f"Deleted receiver: {details['Name']} ({details['Type']}) in {details['City']}")
            
            run_commit("DELETE FROM receivers WHERE Receiver_ID = ?", (int(del_id),))
            st.success(f"Deleted receiver {del_id}.")

# ---------------- Activity History ----------------
def log_activity(action_type, table_name, record_id, details, user_type="Admin"):
    """Log user activities for audit trail"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    activity_log = f"{timestamp} | {user_type} | {action_type} | {table_name} | ID: {record_id} | {details}"
    
    # Store in session state for this session
    if 'activity_history' not in st.session_state:
        st.session_state['activity_history'] = []
    
    st.session_state['activity_history'].append({
        'timestamp': timestamp,
        'user_type': user_type,
        'action': action_type,
        'table': table_name,
        'record_id': record_id,
        'details': details
    })

def activity_history_page():
    st.header("Activity History")
    st.markdown("Track all system activities and changes for audit purposes")
    
    # Filter options with enhanced styling
    st.markdown("""
    <div class="filter-section">
        <h3>Filter Activities</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        action_filter = st.selectbox("Filter by Action", ["All", "Add", "Edit", "Delete"])
    with col2:
        table_filter = st.selectbox("Filter by Table", ["All", "food_listings", "providers", "receivers", "claims"])
    with col3:
        user_filter = st.selectbox("Filter by User", ["All", "Admin", "Provider", "Receiver"])
    
    # Get activity history
    if 'activity_history' in st.session_state and st.session_state['activity_history']:
        activities = st.session_state['activity_history']
        
        # Apply filters
        if action_filter != "All":
            activities = [a for a in activities if a['action'] == action_filter]
        if table_filter != "All":
            activities = [a for a in activities if a['table'] == table_filter]
        if user_filter != "All":
            activities = [a for a in activities if a['user_type'] == user_filter]
        
        # Display activities in a nice format
        if activities:
            st.subheader(f"Showing {len(activities)} activities")
            
            for activity in reversed(activities):  # Show newest first
                action_class = activity['action'].lower()
                with st.expander(f"{activity['action']} - {activity['table']} (ID: {activity['record_id']})"):
                    st.write(f"**User Type:** {activity['user_type']}")
                    st.write(f"**Table:** {activity['table']}")
                    st.write(f"**Record ID:** {activity['record_id']}")
                    st.write(f"**Details:** {activity['details']}")
                    
                    if activity['action'] == 'Add':
                        st.success("✅ New record created")
                    elif activity['action'] == 'Edit':
                        st.info("✏️ Record updated")
                    else:
                        st.error("��️ Record deleted")
            
            # Export functionality
            st.markdown("""
            <div class="export-section">
                <h4>Export Activity Log</h4>
                <p>Download the filtered activity log as a CSV file for external analysis.</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("Export Activity Log"):
                # Create CSV data
                import io
                csv_data = io.StringIO()
                csv_data.write("Timestamp,User Type,Action,Table,Record ID,Details\n")
                for activity in activities:
                    csv_data.write(f"{activity['timestamp']},{activity['user_type']},{activity['action']},{activity['table']},{activity['record_id']},{activity['details']}\n")
                
                st.download_button(
                    label="Download CSV",
                    data=csv_data.getvalue(),
                    file_name=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No activity history available yet. Activities will appear here as you use the system.")

# ---------------- Analytics ----------------
ANALYTICS_QUERIES = {
    "Provider count per city": "SELECT City, COUNT(*) AS provider_count FROM providers GROUP BY City ORDER BY provider_count DESC;",
    "Receiver count per city": "SELECT City, COUNT(*) AS receiver_count FROM receivers GROUP BY City;",
    "Most contributing provider type": """SELECT p.Type AS provider_type, SUM(f.Quantity) AS total_qty
                                         FROM providers p JOIN food_listings f ON p.Provider_ID=f.Provider_ID
                                         GROUP BY p.Type ORDER BY total_qty DESC LIMIT 10;""",
    "Total available food quantity": "SELECT SUM(Quantity) AS total_available FROM food_listings;",
    "City with most listings": "SELECT Location AS city, COUNT(*) AS listings FROM food_listings GROUP BY Location ORDER BY listings DESC LIMIT 10;",
    "Most common food types": "SELECT Food_Type, COUNT(*) AS freq FROM food_listings GROUP BY Food_Type ORDER BY freq DESC LIMIT 10;",
    "Claims per food item": "SELECT f.Food_ID, f.Food_Name, COUNT(c.Claim_ID) AS claim_count FROM food_listings f LEFT JOIN claims c ON f.Food_ID=c.Food_ID GROUP BY f.Food_ID ORDER BY claim_count DESC LIMIT 20;",
    "Provider with most completed claims": "SELECT p.Provider_ID, p.Name, COUNT(c.Claim_ID) AS completed_claims FROM providers p JOIN food_listings f ON p.Provider_ID=f.Provider_ID JOIN claims c ON f.Food_ID=c.Food_ID WHERE c.Status='Completed' GROUP BY p.Provider_ID ORDER BY completed_claims DESC LIMIT 10;",
    "Claim status percent": "SELECT Status, COUNT(*)*100.0/(SELECT COUNT(*) FROM claims) AS percent FROM claims GROUP BY Status;",
    "Avg quantity claimed per receiver": "SELECT c.Receiver_ID, r.Name, AVG(f.Quantity) AS avg_quantity FROM claims c JOIN food_listings f ON c.Food_ID=f.Food_ID JOIN receivers r ON c.Receiver_ID=r.Receiver_ID GROUP BY c.Receiver_ID ORDER BY avg_quantity DESC LIMIT 20;",
    "Most claimed meal type": "SELECT f.Meal_Type, COUNT(c.Claim_ID) AS times_claimed FROM food_listings f JOIN claims c ON f.Food_ID=c.Food_ID GROUP BY f.Meal_Type ORDER BY times_claimed DESC;",
    "Total quantity donated by provider": "SELECT p.Provider_ID, p.Name, SUM(f.Quantity) AS total_donated FROM providers p JOIN food_listings f ON p.Provider_ID=f.Provider_ID GROUP BY p.Provider_ID ORDER BY total_donated DESC LIMIT 20;",
    "Listings near expiry (next 2 days)": "SELECT * FROM food_listings WHERE Expiry_Date BETWEEN date('now') AND date('now','+2 day') ORDER BY Expiry_Date ASC;",
    "Top locations by quantity": "SELECT Location, SUM(Quantity) AS total_qty FROM food_listings GROUP BY Location ORDER BY total_qty DESC LIMIT 10;",
    "Receivers with most claims": "SELECT r.Receiver_ID, r.Name, COUNT(c.Claim_ID) AS num_claims FROM receivers r JOIN claims c ON r.Receiver_ID=c.Receiver_ID GROUP BY r.Receiver_ID ORDER BY num_claims DESC LIMIT 20;"
}

def analytics_page():
    st.header("Analytics Dashboard")
    st.markdown("View system statistics and insights to track food waste reduction")
    
    for title, q in ANALYTICS_QUERIES.items():
        with st.expander(title):
            df = run_query(q)
            st.write(df)
            if not df.empty and df.shape[1] >= 2:
                col2 = df.columns[1]
                if pd.api.types.is_numeric_dtype(df[col2]):
                    try:
                        chart_df = df.set_index(df.columns[0])[col2]
                        st.bar_chart(chart_df)
                    except Exception:
                        pass

# ---------------- Main App ----------------
# Get current time and date first
from datetime import datetime
current_time = datetime.now().strftime("%H:%M:%S")
current_date = datetime.now().strftime("%B %d, %Y")

st.set_page_config(
    page_title="Local Food Wastage System", 
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🍽️"
)

# Custom CSS for dark theme with animations
st.markdown("""
<style>
    /* Dark theme base styles */
    .main .block-container {
        background: #1a1a1a;
        color: #ffffff;
    }
    
    .stApp {
        background: #1a1a1a;
    }
    
         .main-header {
         background: linear-gradient(135deg, #2d2d2d, #1a1a1a);
         padding: 2rem;
         border-radius: 12px;
         border: 1px solid #404040;
         margin-bottom: 2rem;
         text-align: center;
         box-shadow: 0 8px 32px rgba(0,0,0,0.3);
         animation: slideInDown 0.6s ease-out;
     }
     
     .notification-banner {
         background: rgba(76, 175, 80, 0.1);
         border: 1px solid rgba(76, 175, 80, 0.3);
         border-radius: 8px;
         padding: 0.75rem 1.5rem;
         margin-top: 1rem;
         display: inline-flex;
         align-items: center;
         gap: 0.5rem;
         animation: fadeInUp 0.8s ease-out;
     }
     
     .notification-icon {
         font-size: 1.2rem;
         animation: pulse 2s infinite;
     }
     
     .notification-text {
         color: #4CAF50;
         font-size: 0.9rem;
         font-weight: 500;
     }
    
    .metric-card {
        background: #2d2d2d;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #404040;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        animation: fadeInUp 0.5s ease-out;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        border-color: #666666;
    }
    
    .info-box {
        background: #2d2d2d;
        border: 1px solid #404040;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
        animation: fadeIn 0.6s ease-out;
    }
    
    .info-box:hover {
        border-color: #666666;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #4a90e2, #357abd);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
        animation: pulse 2s infinite;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #357abd, #2d5aa0);
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(74, 144, 226, 0.4);
    }
    
    .stExpander {
        border: 1px solid #404040;
        border-radius: 12px;
        margin: 1rem 0;
        background: #2d2d2d;
        transition: all 0.3s ease;
        animation: slideInLeft 0.5s ease-out;
    }
    
    .stExpander:hover {
        border-color: #666666;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    .stExpander > div > div {
        background: #2d2d2d;
        border-radius: 12px;
    }
    
    .stForm {
        background: #2d2d2d;
        padding: 2rem;
        border-radius: 12px;
        border: 1px solid #404040;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
        animation: fadeInUp 0.6s ease-out;
    }
    
    .stForm:hover {
        border-color: #666666;
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    }
    
    .stSelectbox > div > div {
        border-radius: 8px;
        border: 1px solid #404040;
        background: #2d2d2d;
        transition: all 0.3s ease;
    }
    
    .stSelectbox > div > div:hover {
        border-color: #4a90e2;
        box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
    }
    
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #404040;
        background: #2d2d2d;
        color: #ffffff;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #4a90e2;
        box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
    }
    
    .stNumberInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #404040;
        background: #2d2d2d;
        color: #ffffff;
        transition: all 0.3s ease;
    }
    
    .stNumberInput > div > div > input:focus {
        border-color: #4a90e2;
        box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
    }
    
    .stDateInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #404040;
        background: #2d2d2d;
        color: #ffffff;
        transition: all 0.3s ease;
    }
    
    .stDateInput > div > div > input:focus {
        border-color: #4a90e2;
        box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
    }
    
    .stTextArea > div > div > textarea {
        border-radius: 8px;
        border: 1px solid #404040;
        background: #2d2d2d;
        color: #ffffff;
        transition: all 0.3s ease;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #4a90e2;
        box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
    }
    
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        background: #2d2d2d;
        border: 1px solid #404040;
        animation: fadeIn 0.8s ease-out;
    }
    
    .stDataFrame:hover {
        border-color: #666666;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    h1, h2, h3 {
        color: #ffffff;
        font-weight: 600;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .stMarkdown {
        color: #e0e0e0;
    }
    
         /* Enhanced Sidebar styling */
     .css-1d391kg {
         background: #1a1a1a;
     }
     
     .css-1lcbmhc {
         background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%);
         border-right: 1px solid #404040;
         padding: 1rem;
     }
     
     /* Sidebar Header */
     .sidebar-header {
         text-align: center;
         padding: 1.5rem 0;
         border-bottom: 1px solid #404040;
         margin-bottom: 1.5rem;
         animation: fadeInDown 0.6s ease-out;
     }
     
     .sidebar-header h2 {
         color: #ffffff;
         margin: 0;
         font-size: 1.5rem;
         font-weight: 700;
         text-shadow: 0 2px 4px rgba(0,0,0,0.3);
     }
     
     .sidebar-subtitle {
         color: #4a90e2;
         font-size: 0.9rem;
         margin-top: 0.5rem;
         font-weight: 500;
     }
     
     /* Sidebar Stats */
     .sidebar-stats {
         margin-bottom: 2rem;
     }
     
     .stat-item {
         display: flex;
         align-items: center;
         padding: 1rem;
         margin-bottom: 0.75rem;
         background: rgba(74, 144, 226, 0.1);
         border: 1px solid rgba(74, 144, 226, 0.2);
         border-radius: 10px;
         transition: all 0.3s ease;
         animation: slideInLeft 0.5s ease-out;
     }
     
     .stat-item:hover {
         background: rgba(74, 144, 226, 0.15);
         border-color: rgba(74, 144, 226, 0.3);
         transform: translateX(5px);
     }
     
     .stat-icon {
         font-size: 1.5rem;
         margin-right: 1rem;
         width: 40px;
         text-align: center;
     }
     
     .stat-content {
         flex: 1;
     }
     
     .stat-label {
         color: #a0a0a0;
         font-size: 0.8rem;
         font-weight: 500;
         margin-bottom: 0.25rem;
     }
     
     .stat-value {
         color: #ffffff;
         font-size: 0.9rem;
         font-weight: 600;
     }
     
     /* Sidebar Sections */
     .sidebar-section {
         margin-bottom: 1.5rem;
         padding-bottom: 1rem;
         border-bottom: 1px solid #404040;
     }
     
     .sidebar-section h4 {
         color: #4a90e2;
         font-size: 1rem;
         margin-bottom: 1rem;
         font-weight: 600;
         text-transform: uppercase;
         letter-spacing: 0.5px;
     }
     
     .info-item {
         display: flex;
         justify-content: space-between;
         align-items: center;
         padding: 0.5rem 0;
         margin-bottom: 0.5rem;
     }
     
     .info-label {
         color: #a0a0a0;
         font-size: 0.85rem;
     }
     
     .info-value {
         color: #ffffff;
         font-size: 0.85rem;
         font-weight: 500;
     }
     
     .status-active {
         color: #4CAF50;
         font-weight: 600;
     }
     
     /* Sidebar Footer */
     .sidebar-footer {
         margin-top: auto;
         padding-top: 1.5rem;
         border-top: 1px solid #404040;
         text-align: center;
         animation: fadeInUp 0.6s ease-out;
     }
     
     .creator-info {
         margin-bottom: 1rem;
     }
     
     .creator-name {
         color: #ffffff;
         font-size: 1rem;
         font-weight: 600;
         margin-bottom: 0.25rem;
     }
     
     .creator-title {
         color: #4a90e2;
         font-size: 0.8rem;
         font-weight: 500;
     }
     
     .footer-divider {
         height: 1px;
         background: linear-gradient(90deg, transparent, #404040, transparent);
         margin: 1rem 0;
     }
     
     .footer-text {
         color: #a0a0a0;
         font-size: 0.75rem;
         font-weight: 500;
     }
     
     .time-display {
         font-family: 'Courier New', monospace;
         color: #4a90e2 !important;
         font-weight: 600;
     }
     
     /* Quick action buttons */
     .quick-actions {
         margin: 1rem 0;
         padding: 1rem;
         background: rgba(74, 144, 226, 0.05);
         border: 1px solid rgba(74, 144, 226, 0.1);
         border-radius: 10px;
     }
     
     .quick-action-btn {
         display: block;
         width: 100%;
         padding: 0.5rem;
         margin: 0.25rem 0;
         background: rgba(74, 144, 226, 0.1);
         border: 1px solid rgba(74, 144, 226, 0.2);
         border-radius: 6px;
         color: #ffffff;
         text-decoration: none;
         text-align: center;
         font-size: 0.85rem;
         transition: all 0.3s ease;
     }
     
     .quick-action-btn:hover {
         background: rgba(74, 144, 226, 0.2);
         border-color: rgba(74, 144, 226, 0.3);
         transform: translateY(-1px);
     }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideInDown {
        from {
            opacity: 0;
            transform: translateY(-50px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translateX(-30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    
    /* Success and error messages */
    .stSuccess {
        background: #1e3a1e;
        border: 1px solid #4a7c59;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        animation: slideInRight 0.5s ease-out;
    }
    
    .stError {
        background: #3a1e1e;
        border: 1px solid #7c4a4a;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        animation: slideInRight 0.5s ease-out;
    }
    
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    /* Loading animation */
    .stSpinner {
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    /* Activity History Styling */
    .activity-expander {
        background: #2d2d2d;
        border: 1px solid #404040;
        border-radius: 12px;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
    }
    
    .activity-expander:hover {
        border-color: #4a90e2;
        box-shadow: 0 4px 20px rgba(74, 144, 226, 0.2);
    }
    
    .activity-timestamp {
        color: #4a90e2;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .activity-action {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .activity-action.add {
        background: rgba(76, 175, 80, 0.2);
        color: #4CAF50;
        border: 1px solid rgba(76, 175, 80, 0.3);
    }
    
    .activity-action.edit {
        background: rgba(33, 150, 243, 0.2);
        color: #2196F3;
        border: 1px solid rgba(33, 150, 243, 0.3);
    }
    
    .activity-action.delete {
        background: rgba(244, 67, 54, 0.2);
        color: #F44336;
        border: 1px solid rgba(244, 67, 54, 0.3);
    }
    
    .activity-details {
        background: rgba(74, 144, 226, 0.05);
        border: 1px solid rgba(74, 144, 226, 0.1);
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        color: #e0e0e0;
    }
    
    .filter-section {
        background: #2d2d2d;
        border: 1px solid #404040;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        animation: fadeInUp 0.6s ease-out;
    }
    
    .export-section {
        background: rgba(76, 175, 80, 0.1);
        border: 1px solid rgba(76, 175, 80, 0.2);
        border-radius: 10px;
        padding: 1rem;
        margin-top: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Main header with notifications
st.markdown("""
<div class="main-header">
    <h1>Local Food Wastage Management System</h1>
    <p>Connecting food providers with those in need • Reducing waste, one meal at a time</p>
    <div class="notification-banner">
        <span class="notification-icon">🔔</span>
        <span class="notification-text">System is running smoothly • Last updated: """ + current_time + """</span>
    </div>
</div>
""", unsafe_allow_html=True)

PAGES = {
    "Home": lambda: st.markdown("""
        <div class="info-box">
            <h2>Welcome to Local Food Wastage Management System</h2>
            <p>This platform connects food providers with those in need, helping to reduce food waste and support our community.</p>
            <h3>Available Features:</h3>
            <ul>
                <li><strong>Browse Listings:</strong> View and filter available food listings</li>
                <li><strong>Admin - Providers:</strong> Manage food providers</li>
                <li><strong>Admin - Listings:</strong> Manage food listings</li>
                <li><strong>Admin - Receivers:</strong> Manage food receivers</li>
                <li><strong>Analytics:</strong> View system statistics and insights</li>
                <li><strong>Activity History:</strong> Track all system changes and activities</li>
            </ul>
                         <p><em>Created by Abkari mohammed Sayeem</em></p>
        </div>
    """, unsafe_allow_html=True),
    "Browse Listings": browse_listings,
    "Admin - Providers": admin_providers,
    "Admin - Listings": admin_food_listings,
    "Admin - Receivers": admin_receivers,
    "Analytics": analytics_page,
    "Activity History": activity_history_page,
}

# Sidebar with enhanced styling
st.sidebar.markdown("""
<div class="sidebar-header">
    <h2>Food Wastage System</h2>
    <div class="sidebar-subtitle">Management Dashboard</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div class="sidebar-stats">
    <div class="stat-item">
        <div class="stat-icon">🍽️</div>
        <div class="stat-content">
            <div class="stat-label">Food Types</div>
            <div class="stat-value">3 Categories</div>
        </div>
    </div>
    <div class="stat-item">
        <div class="stat-icon">♻️</div>
        <div class="stat-content">
            <div class="stat-label">Purpose</div>
            <div class="stat-value">Reduce Waste</div>
        </div>
    </div>
    <div class="stat-item">
        <div class="stat-icon">🤝</div>
        <div class="stat-content">
            <div class="stat-label">Community</div>
            <div class="stat-value">Connect All</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div class="sidebar-section">
    <h4>Navigation</h4>
</div>
""", unsafe_allow_html=True)

choice = st.sidebar.selectbox("Select Page", list(PAGES.keys()), label_visibility="collapsed")

# Quick Actions Section
st.sidebar.markdown("""
<div class="sidebar-section">
    <h4>Quick Actions</h4>
    <div class="quick-actions">
        <a href="#" class="quick-action-btn" onclick="window.location.reload()">🔄 Refresh Page</a>
        <a href="#" class="quick-action-btn" onclick="window.print()">🖨️ Print Report</a>
        <a href="#" class="quick-action-btn" onclick="window.open('mailto:admin@foodwastage.com')">📧 Contact Admin</a>
    </div>
</div>
""", unsafe_allow_html=True)



st.sidebar.markdown("""
<div class="sidebar-section">
    <h4>System Info</h4>
    <div class="info-item">
        <span class="info-label">Version:</span>
        <span class="info-value">1.0.0</span>
    </div>
    <div class="info-item">
        <span class="info-label">Status:</span>
        <span class="info-value status-active">Active</span>
    </div>
    <div class="info-item">
        <span class="info-label">Date:</span>
        <span class="info-value">""" + current_date + """</span>
    </div>
    <div class="info-item">
        <span class="info-label">Time:</span>
        <span class="info-value time-display">""" + current_time + """</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div class="sidebar-footer">
    <div class="creator-info">
        <div class="creator-name">Abkari mohammed Sayeem</div>
        <div class="creator-title">System Developer</div>
    </div>
    <div class="footer-divider"></div>
    <div class="footer-text">Food Wastage Management System</div>
</div>
""", unsafe_allow_html=True)

PAGES[choice]()

