import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Set page layout and config
st.set_page_config(
    page_title="Google Ads Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
        
        /* Font styling */
        html, body, [class*="css"], .stMarkdown {
            font-family: 'Outfit', sans-serif;
        }
        
        /* Main header gradient */
        .main-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 2rem;
            border-radius: 12px;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        }
        
        /* Metric Card styling */
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        div[data-testid="stMetric"]:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            border-color: #3b82f6;
        }
        
        /* Sidebar styling */
        .css-1d391kg {
            background-color: #f8fafc;
        }
        
        /* Table headers */
        thead tr th {
            background-color: #f1f5f9 !important;
            color: #1e293b !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

# 1. Load Credentials
# 1. Load Credentials
def init_google_ads_client():
    # Look for .env in current, parent, or grandparent directories
    paths_to_try = [
        os.path.join(os.path.dirname(__file__), '.env'),       # /frontend/.env
        os.path.join(os.path.dirname(__file__), '..', '.env'),  # /.env
        '.env'
    ]
    
    loaded = False
    for path in paths_to_try:
        if os.path.exists(path):
            load_dotenv(path, override=True)
            loaded = True
            break
            
    if not loaded:
        load_dotenv(override=True) # Fallback to override standard environment loading

    dev_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    if not all([dev_token, client_id, client_secret, refresh_token]):
        return None, "Missing configuration. Please check your .env file.", None, None, None, None, None

    config = {
        "developer_token": dev_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }

    if login_customer_id:
        config["login_customer_id"] = login_customer_id.replace("-", "").strip()

    try:
        client = GoogleAdsClient.load_from_dict(config)
        return client, None, dev_token, client_id, client_secret, refresh_token, login_customer_id
    except Exception as e:
        return None, f"Failed to initialize client: {str(e)}", None, None, None, None, None

# Initialize Google Ads Client
client, init_error, dev_token, client_id, client_secret, refresh_token, login_customer_id = init_google_ads_client()

# Sidebar Setup
with st.sidebar:
    st.image("https://www.gstatic.com/images/branding/googlelogo/svg/googlelogo_clr_74x24px.svg", width=120)
    st.title("Connection Control")
    
    # Add a refresh cache button for convenience
    if st.button("🔄 Force Clear Cache & Reload"):
        st.cache_data.clear()
        st.rerun()
    
    if init_error:
        st.error(f"🔴 Connection Failed\n\n{init_error}")
        st.info("Ensure the `.env` file exists and has correct values.")
        st.stop()
    else:
        st.success("🟢 Connected to Google Ads API")
        if login_customer_id:
            st.caption(f"Manager Account Login ID: **{login_customer_id}**")

# Helper to query descriptive name for account
@st.cache_data(ttl=600)
def fetch_account_details(_client, customer_id, cache_key):
    try:
        googleads_service = _client.get_service("GoogleAdsService")
        query = "SELECT customer.descriptive_name, customer.currency_code FROM customer LIMIT 1"
        response = googleads_service.search(customer_id=customer_id, query=query)
        for row in response:
            return {
                "name": row.customer.descriptive_name or f"Unnamed ({customer_id})",
                "currency": row.customer.currency_code or "USD"
            }
    except Exception:
        pass
    return {"name": f"Account {customer_id}", "currency": "USD"}

# Get accessible customers
@st.cache_data(ttl=600)
def get_accessible_customers(_client, dev_token, client_id, client_secret, refresh_token, login_customer_id):
    accounts = []
    cache_key = f"{dev_token}-{client_id}-{refresh_token}-{login_customer_id}"
    
    # If a login customer ID (Manager Account) is specified, query its managed accounts hierarchy
    if login_customer_id:
        try:
            googleads_service = _client.get_service("GoogleAdsService")
            clean_login_id = login_customer_id.replace("-", "").strip()
            # Query all customer clients under this manager
            query = """
                SELECT
                    customer_client.client_customer,
                    customer_client.descriptive_name,
                    customer_client.manager,
                    customer_client.currency_code
                FROM customer_client
                WHERE customer_client.level <= 1
            """
            response = googleads_service.search(customer_id=clean_login_id, query=query)
            for row in response:
                cc = row.customer_client
                cid = cc.client_customer.split("/")[-1]
                
                # Skip listing the manager account itself in the client dropdown if we have child clients
                if cid == clean_login_id and cc.manager:
                    continue
                    
                accounts.append({
                    "id": cid,
                    "name": cc.descriptive_name or f"Unnamed Account ({cid})",
                    "currency": cc.currency_code or "USD",
                    "display": f"{cc.descriptive_name or 'Unnamed'} ({cid}) {'[Manager]' if cc.manager else '[Client]'}"
                })
            if accounts:
                return accounts, None
        except Exception as e:
            # Fallback to list_accessible_customers if hierarchy query fails
            pass

    # Fallback/Default: Get root accessible customers
    try:
        customer_service = _client.get_service("CustomerService")
        response = customer_service.list_accessible_customers()
        for resource_name in response.resource_names:
            cid = resource_name.split("/")[-1]
            details = fetch_account_details(_client, cid, cache_key)
            accounts.append({
                "id": cid,
                "name": details["name"],
                "currency": details["currency"],
                "display": f"{details['name']} ({cid})"
            })
        return accounts, None
    except GoogleAdsException as ex:
        return [], ex
    except Exception as e:
        return [], e

if client:
    accounts, err = get_accessible_customers(client, dev_token, client_id, client_secret, refresh_token, login_customer_id)
    if err:
        st.error("### Error Fetching Accessible Accounts")
        st.write(err)
        st.stop()
        
    if not accounts:
        st.warning("No accessible Google Ads accounts found for these credentials.")
        st.stop()

    # Dropdown for selecting customer
    with st.sidebar:
        st.subheader("Select Customer Account")
        account_options = {acc["display"]: acc for acc in accounts}
        selected_display = st.selectbox("Customer Account", list(account_options.keys()))
        selected_account = account_options[selected_display]
        
        st.subheader("Filter Date Range")
        date_range_map = {
            "Last 7 Days": "LAST_7_DAYS",
            "Last 30 Days": "LAST_30_DAYS",
            "This Month": "THIS_MONTH",
            "Last Month": "LAST_MONTH",
            "Today": "TODAY",
            "Yesterday": "YESTERDAY"
        }
        selected_range = st.selectbox("Date Range", list(date_range_map.keys()), index=1)
        api_date_range = date_range_map[selected_range]

# Main Area Header
st.markdown(f"""
    <div class="main-header">
        <h1>Google Ads Analytics Dashboard</h1>
        <p>Real-time insights for account: <b>{selected_account['name']} ({selected_account['id']})</b></p>
    </div>
""", unsafe_allow_html=True)

# Fetch performance data
def fetch_performance_metrics(client, customer_id, date_range):
    googleads_service = client.get_service("GoogleAdsService")
    
    # 1. Fetch campaigns details
    campaign_query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.cost_micros,
            metrics.average_cpc,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date DURING {date_range}
    """
    
    campaign_data = []
    errors = []
    try:
        response = googleads_service.search(customer_id=customer_id, query=campaign_query)
        for row in response:
            cost = row.metrics.cost_micros / 1000000.0
            conv_value = row.metrics.conversions_value
            roas = conv_value / cost if cost > 0 else 0.0
            
            campaign_data.append({
                "ID": row.campaign.id,
                "Campaign": row.campaign.name,
                "Status": row.campaign.status.name,
                "Impressions": row.metrics.impressions,
                "Clicks": row.metrics.clicks,
                "CTR (%)": round(row.metrics.ctr * 100, 2),
                "Spend": round(cost, 2),
                "Avg CPC": round(row.metrics.average_cpc / 1000000.0, 2) if row.metrics.average_cpc else 0.0,
                "Conversions": round(row.metrics.conversions, 2),
                "Conv. Value": round(conv_value, 2),
                "ROAS": round(roas, 2)
            })
    except GoogleAdsException as ex:
        err_msg = f"API Error: {ex.error.code().name}"
        details = [error.message for error in ex.failure.errors]
        errors.append((err_msg, details))
        return pd.DataFrame(), pd.DataFrame(), errors
    except Exception as e:
        errors.append(("Unexpected Error", [str(e)]))
        return pd.DataFrame(), pd.DataFrame(), errors
        
    # 2. Fetch daily performance trends for charts
    trend_query = f"""
        SELECT
            segments.date,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM customer
        WHERE segments.date DURING {date_range}
    """
    trend_data = []
    try:
        response = googleads_service.search(customer_id=customer_id, query=trend_query)
        for row in response:
            trend_data.append({
                "Date": row.segments.date,
                "Impressions": row.metrics.impressions,
                "Clicks": row.metrics.clicks,
                "Spend": row.metrics.cost_micros / 1000000.0,
                "Conversions": row.metrics.conversions,
                "Value": row.metrics.conversions_value
            })
    except Exception:
        # Some accounts might not allow direct trends queries, we fallback
        pass
        
    df_campaigns = pd.DataFrame(campaign_data)
    df_trends = pd.DataFrame(trend_data)
    
    if not df_trends.empty:
        df_trends["Date"] = pd.to_datetime(df_trends["Date"])
        df_trends = df_trends.sort_values("Date")
        
    return df_campaigns, df_trends, None

# Load Data
with st.spinner("Fetching performance data..."):
    df_campaigns, df_trends, errors = fetch_performance_metrics(client, selected_account["id"], api_date_range)

currency_symbol = "$" if selected_account["currency"] == "USD" else f"{selected_account['currency']} "

# Determine if we should show demo data
show_demo = False

if errors:
    st.error("### 🔴 Google Ads API Permission Error")
    for err_msg, details in errors:
        st.subheader(err_msg)
        for detail in details:
            st.markdown(f"**Details**: {detail}")
            
            # Show helpful explanation for Test Account errors
            if "approved for use with test accounts" in detail.lower() or "developer_token_prohibited" in detail.lower() or "developer_token_not_approved" in detail.lower():
                st.info("""
                    💡 **Why this happens:** 
                    Your Developer Token is in a **'Test' or 'Pending' status**. 
                    * Google Ads policy prohibits test developer tokens from accessing live/production customer accounts.
                    * You can only access **Google Ads Test Accounts** using this token.
                    
                    **How to resolve this:**
                    1. Create a **Test Manager Account** by visiting: [Google Ads Test Account Creator](https://ads.google.com/um/Start_Test_Manager).
                    2. Create a test client account under that Test Manager.
                    3. Authenticate using OAuth credentials authorized to access that test account hierarchy.
                """)
    
    st.markdown("---")
    st.warning("⚠️ Since the API request failed due to permissions, the dashboard will display **Demo Mode (Mock Data)** below so you can preview the UI features.")
    show_demo = True

elif df_campaigns.empty:
    st.warning("No campaign data found for this customer account in the selected date range.")
    st.info("This is common for inactive, new, or test accounts. Click below to preview the dashboard using mock data.")
    if st.checkbox("Generate sample data to preview dashboard design", value=True):
        show_demo = True

if show_demo:
    dummy_campaigns = pd.DataFrame([
        {"ID": "1001", "Campaign": "Search - Brand Promo", "Status": "ENABLED", "Impressions": 25000, "Clicks": 1250, "CTR (%)": 5.0, "Spend": 500.0, "Avg CPC": 0.40, "Conversions": 75, "Conv. Value": 2250.0, "ROAS": 4.5},
        {"ID": "1002", "Campaign": "Performance Max - Core Products", "Status": "ENABLED", "Impressions": 84000, "Clicks": 4200, "CTR (%)": 5.0, "Spend": 1800.0, "Avg CPC": 0.43, "Conversions": 190, "Conv. Value": 7200.0, "ROAS": 4.0},
        {"ID": "1003", "Campaign": "Display - Dynamic Remarketing", "Status": "PAUSED", "Impressions": 150000, "Clicks": 750, "CTR (%)": 0.5, "Spend": 300.0, "Avg CPC": 0.40, "Conversions": 10, "Conv. Value": 450.0, "ROAS": 1.5},
        {"ID": "1004", "Campaign": "YouTube - Product Launch Video", "Status": "ENABLED", "Impressions": 320000, "Clicks": 1600, "CTR (%)": 0.5, "Spend": 950.0, "Avg CPC": 0.59, "Conversions": 15, "Conv. Value": 600.0, "ROAS": 0.63}
    ])
    
    dates = pd.date_range(end=pd.Timestamp.today(), periods=30)
    dummy_trends = pd.DataFrame({
        "Date": dates,
        "Spend": [50 + i * 2 + (15 if i % 7 == 0 else 0) for i in range(30)],
        "Clicks": [120 + i * 5 + (40 if i % 7 == 0 else 0) for i in range(30)],
        "Impressions": [2000 + i * 100 for i in range(30)],
        "Conversions": [5 + i // 3 for i in range(30)],
        "Value": [150 + i * 15 for i in range(30)]
    })
    df_campaigns = dummy_campaigns
    df_trends = dummy_trends
    st.info("📊 **Demo Mode Active**: Viewing sample mock data.")

if not df_campaigns.empty:
        # Calculate Totals
        total_spend = df_campaigns["Spend"].sum()
        total_clicks = df_campaigns["Clicks"].sum()
        total_impressions = df_campaigns["Impressions"].sum()
        total_conversions = df_campaigns["Conversions"].sum()
        total_value = df_campaigns["Conv. Value"].sum()
        
        overall_ctr = (total_clicks / total_impressions) * 100 if total_impressions > 0 else 0.0
        overall_cpc = total_spend / total_clicks if total_clicks > 0 else 0.0
        overall_roas = total_value / total_spend if total_spend > 0 else 0.0

        # KPI Metrics Cards Row
        st.subheader("Performance Highlights")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Spend (Cost)", f"{currency_symbol}{total_spend:,.2f}")
        col2.metric("Clicks", f"{total_clicks:,}")
        col3.metric("Impressions", f"{total_impressions:,}")
        col4.metric("Conversions", f"{total_conversions:,.1f}")

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Avg. CTR", f"{overall_ctr:.2f}%")
        col6.metric("Avg. CPC", f"{currency_symbol}{overall_cpc:.2f}")
        col7.metric("Conversion Value", f"{currency_symbol}{total_value:,.2f}")
        col8.metric("ROAS (Return on Spend)", f"{overall_roas:.2f}x")

        st.markdown("---")

        # Visualizations Row
        st.subheader("Performance Trends")
        if df_trends is not None and not df_trends.empty:
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # Spend and Click Trend Chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_trends["Date"], y=df_trends["Spend"],
                    name=f"Spend ({selected_account['currency']})",
                    line=dict(color='#2563eb', width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=df_trends["Date"], y=df_trends["Clicks"],
                    name="Clicks",
                    line=dict(color='#10b981', width=3),
                    yaxis="y2"
                ))
                
                fig.update_layout(
                    title="Daily Spend & Clicks Trend",
                    xaxis=dict(title="Date"),
                    yaxis=dict(title=dict(text=f"Spend ({selected_account['currency']})", font=dict(color="#2563eb")), tickfont=dict(color="#2563eb")),
                    yaxis2=dict(title=dict(text="Clicks", font=dict(color="#10b981")), tickfont=dict(color="#10b981"), anchor="x", overlaying="y", side="right"),
                    legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
                    margin=dict(l=40, r=40, t=40, b=40),
                    hovermode="x unified"
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_chart2:
                # ROAS and Conversion Trend Chart
                fig_conv = go.Figure()
                fig_conv.add_trace(go.Bar(
                    x=df_trends["Date"], y=df_trends["Conversions"],
                    name="Conversions",
                    marker_color='#f59e0b',
                    opacity=0.8
                ))
                
                # Calculate daily ROAS
                df_trends["Daily_ROAS"] = df_trends.apply(lambda r: r["Value"] / r["Spend"] if r["Spend"] > 0 else 0, axis=1)
                
                fig_conv.add_trace(go.Scatter(
                    x=df_trends["Date"], y=df_trends["Daily_ROAS"],
                    name="ROAS",
                    line=dict(color='#8b5cf6', width=3),
                    yaxis="y2"
                ))
                
                fig_conv.update_layout(
                    title="Daily Conversions & ROAS Trend",
                    xaxis=dict(title="Date"),
                    yaxis=dict(title=dict(text="Conversions", font=dict(color="#f59e0b")), tickfont=dict(color="#f59e0b")),
                    yaxis2=dict(title=dict(text="ROAS (x)", font=dict(color="#8b5cf6")), tickfont=dict(color="#8b5cf6"), anchor="x", overlaying="y", side="right"),
                    legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
                    margin=dict(l=40, r=40, t=40, b=40),
                    hovermode="x unified"
                )
                st.plotly_chart(fig_conv, use_container_width=True)
        else:
            st.info("No daily trend data available for charting. Showing only campaign-level breakdowns.")

        st.markdown("---")

        # Campaign Details Table
        st.subheader("Campaign Performance Breakdown")
        
        # Interactive table sorting/filtering via dataframe display
        st.dataframe(
            df_campaigns.style.format({
                "Spend": f"{currency_symbol}{{:.2f}}",
                "Avg CPC": f"{currency_symbol}{{:.2f}}",
                "Conv. Value": f"{currency_symbol}{{:.2f}}",
                "CTR (%)": "{:.2f}%",
                "ROAS": "{:.2f}x",
                "Impressions": "{:,}",
                "Clicks": "{:,}",
                "Conversions": "{:,.1f}"
            }),
            use_container_width=True,
            hide_index=True
        )

        # Plotly Campaign Spend Distribution
        st.subheader("Campaign Spend Share")
        fig_pie = px.pie(
            df_campaigns,
            values="Spend",
            names="Campaign",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)
