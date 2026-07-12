import os
import sys
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

def print_banner(text):
    print("=" * 60)
    print(f" {text}")
    print("=" * 60)

def main():
    print_banner("Google Ads Credentials Tester")
    
    # 1. Load .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded credentials from {env_path}\n")
    else:
        print(f"Warning: .env file not found at {env_path}. Using environment variables instead.\n")

    # Retrieve values
    dev_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    # Validate mandatory values
    missing = []
    if not dev_token: missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not client_id: missing.append("GOOGLE_ADS_CLIENT_ID")
    if not client_secret: missing.append("GOOGLE_ADS_CLIENT_SECRET")
    if not refresh_token: missing.append("GOOGLE_ADS_REFRESH_TOKEN")

    if missing:
        print("[ERROR] Missing required configuration variable(s) in .env:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease update the .env file with your credentials and run the script again.")
        sys.exit(1)

    # 2. Build configuration dictionary
    config = {
        "developer_token": dev_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }

    if login_customer_id:
        # Strip spaces or hyphens from login customer id if present
        clean_login_id = login_customer_id.replace("-", "").strip()
        config["login_customer_id"] = clean_login_id
        print(f"Using Login Customer ID (Manager): {clean_login_id}")
    
    print("Initializing Google Ads Client...")
    try:
        client = GoogleAdsClient.load_from_dict(config)
    except Exception as e:
        print(f"[ERROR] Failed to initialize Google Ads Client: {e}")
        sys.exit(1)

    # Step 1: Verify Authentication and Developer Token
    print_banner("Step 1: Listing Accessible Customers")
    print("Sending request to list accessible accounts...")
    
    accessible_customers = []
    step_1_passed = False
    
    try:
        customer_service = client.get_service("CustomerService")
        response = customer_service.list_accessible_customers()
        
        print("\nSuccess! Successfully connected to Google Ads API.")
        print(f"Total Accessible Customer Resource Names: {len(response.resource_names)}")
        for resource_name in response.resource_names:
            print(f"  - {resource_name}")
            accessible_customers.append(resource_name)
        
        step_1_passed = True
        print("\n[PASSED] Step 1: Authentication and Developer Token are valid.")
        
    except GoogleAdsException as ex:
        print("\n[FAILED] Step 1: Google Ads API request failed.")
        print(f"Request ID: {ex.request_id}")
        print(f"Status Name: {ex.error.code().name}")
        
        for error in ex.failure.errors:
            print(f"Error Message: {error.message}")
            error_code = error.error_code
            # Extract details of the error code object if possible
            for field, val in error_code.__class__.__dict__.items():
                if not field.startswith('_') and getattr(error_code, field, None) is not None:
                    code_val = getattr(error_code, field)
                    if code_val != 0:
                        print(f"Error Code Type: {field} (value: {code_val})")
            
            # Print helpful guidance on common error codes
            err_str = str(error_code).lower()
            if "developer_token_not_approved" in err_str:
                print("\nSuggestion: The Developer Token is not approved. If it is a test token, make sure you are only accessing a Test Manager or Test Client account.")
            elif "not_on_allowlist-list" in err_str or "developer_token" in err_str:
                print("\nSuggestion: Check if your developer token is correct and active.")
            elif "invalid_credentials" in err_str or "unauthorized" in err_str:
                print("\nSuggestion: Check if your Client ID, Client Secret, or Refresh Token are correct and have not expired/been revoked.")
            elif "permission_denied" in err_str or "user_permission_denied" in err_str:
                print("\nSuggestion: The authorized Google Account does not have permission to access the requested resources or the Login Customer ID is incorrect/missing.")

    except Exception as e:
        print(f"\n[FAILED] Step 1: An unexpected error occurred: {e}")

    # Step 2: Validate Search Query Capability on a Specific Customer
    print_banner("Step 2: Checking Search Query Capability")
    
    if not customer_id:
        print("GOOGLE_ADS_CUSTOMER_ID is not set in .env.")
        print("Skipping detailed search query validation.")
        print("To test running queries against a specific account, please update GOOGLE_ADS_CUSTOMER_ID in .env.")
        if step_1_passed:
            print("\nVerification Summary: Credentials look good! Step 1 was successful.")
        return

    clean_customer_id = customer_id.replace("-", "").strip()
    print(f"Targeting Customer ID: {clean_customer_id}")
    print("Running a basic test query (fetching customer ID and name)...")
    
    try:
        googleads_service = client.get_service("GoogleAdsService")
        query = "SELECT customer.id, customer.descriptive_name FROM customer LIMIT 1"
        
        # Run search query
        response = googleads_service.search(customer_id=clean_customer_id, query=query)
        
        row_found = False
        for row in response:
            row_found = True
            print("\nSuccess! Query executed and returned data:")
            print(f"  Customer ID: {row.customer.id}")
            print(f"  Descriptive Name: {row.customer.descriptive_name}")
            break
        
        if not row_found:
            print("\nQuery executed successfully but returned 0 rows (which is normal for inactive/empty accounts).")
            
        print("\n[PASSED] Step 2: Query capability validated on Customer ID", clean_customer_id)
        print("\nALL TESTS PASSED! Your Google Ads Credentials are fully operational.")

    except GoogleAdsException as ex:
        print("\n[FAILED] Step 2: Query failed on customer account.")
        print(f"Request ID: {ex.request_id}")
        for error in ex.failure.errors:
            print(f"Error Message: {error.message}")
            print(f"Error Code Details: {error.error_code}")
            
            err_str = str(error.error_code).lower()
            if "user_permission_denied" in err_str:
                print("\nSuggestion: If the authenticated Google Account is a Manager (MCC) account, make sure you specify that Manager Account's ID as the GOOGLE_ADS_LOGIN_CUSTOMER_ID in .env.")
            elif "developer_token_prohibited" in err_str or "unapproved" in err_str:
                print("\nSuggestion: Ensure you are using a Test Manager Account / Test Client Account if your developer token is in 'Basic' or 'Test' status.")
    except Exception as e:
        print(f"\n[FAILED] Step 2: An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
