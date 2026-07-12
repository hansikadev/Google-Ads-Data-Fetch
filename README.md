# Google Ads API Credentials Verification Tool

This tool helps you quickly verify if your Google Ads API credentials (developer token, client ID, client secret, refresh token) are valid and working.

## Setup Instructions

1. **Open the `.env` file** in this directory:
   [`.env`](file:///c:/Users/user/Desktop/googleads/.env)

2. **Fill in the missing fields**:
   - `GOOGLE_ADS_DEVELOPER_TOKEN`: Get this from the API Center in your Google Ads Manager Account (MCC).
   - `GOOGLE_ADS_REFRESH_TOKEN`: The OAuth 2.0 refresh token generated for your user account.
   - `GOOGLE_ADS_CUSTOMER_ID` (Optional): A client customer ID (10-digit number) you wish to run a query against.
   - `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (Optional): The manager account ID (10-digit number) used to authenticate access to client accounts. Highly recommended if your oauth account is a manager account.

3. **Run the tester script**:
   Open a terminal in this directory and execute the following command:
   ```powershell
   .venv\Scripts\python test_credentials.py
   ```

## Test Flow

The script performs two validation checks:
* **Step 1: List Accessible Customers**
  Tests connection to the Google Ads API using your credentials. If successful, it displays the list of customer resource names accessible to you. This confirms your OAuth flow and developer token work.
* **Step 2: Query Account Details (Optional)**
  If a `GOOGLE_ADS_CUSTOMER_ID` is provided, it executes a simple query to fetch basic account info. This verifies read permissions on that specific account.

## Troubleshooting Common Errors

- `DEVELOPER_TOKEN_NOT_APPROVED`: Your developer token is in "test" or "pending" status, and you are attempting to access a production account. Use a Test Manager Account or wait for approval.
- `USER_PERMISSION_DENIED`: The authenticated user account does not have access to the target customer ID. If targeting a client account through a manager account, ensure you configure `GOOGLE_ADS_LOGIN_CUSTOMER_ID` in the `.env` file with the manager account's ID.
- `INVALID_CREDENTIALS`: One of the OAuth credentials (client ID, client secret, or refresh token) is invalid, revoked, or expired.
