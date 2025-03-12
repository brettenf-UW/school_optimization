from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import boto3
import hmac
import hashlib
import base64
import os
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cognito configuration
CLIENT_ID = "2vabalt8ij3kfp4tibhahce7ds"  # App client ID from AWS Cognito
CLIENT_SECRET = "1r7ib6778d1bclsigdjhcjpuk64i30d0qvkgj3hdkame4g0rc8oa"  # Client secret
USER_POOL_ID = "us-west-2_gVCuWb3dQ"  # User Pool ID
REGION = "us-west-2"

# Use standard boto3 credential resolution (environment variables, config files, IAM roles)
# This will look for AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
cognito_client = boto3.client('cognito-idp', region_name=REGION)
admin_client = boto3.client('cognito-idp', region_name=REGION)

# Print a reminder about AWS credentials
print("NOTE: Make sure AWS credentials are properly configured.")
print("You can set them by using AWS CLI (aws configure) or environment variables:")
print("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")

# Debug information
print(f"Using Cognito configuration:")
print(f"- Client ID: {CLIENT_ID}")
print(f"- User Pool ID: {USER_POOL_ID}")
print(f"- Region: {REGION}")

# Initialize Cognito client
cognito_client = boto3.client('cognito-idp', region_name=REGION)

class SignInRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/signin")
async def sign_in(request: SignInRequest):
    # Calculate SECRET_HASH
    message = request.username + CLIENT_ID
    signature = hmac.new(
        key=CLIENT_SECRET.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    secret_hash = base64.b64encode(signature).decode()
    
    try:
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': request.username,
                'PASSWORD': request.password,
                'SECRET_HASH': secret_hash
            }
        )
        
        # Check if user needs to change password
        if 'ChallengeName' in response and response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
            # Extract required attributes from the challenge parameters
            required_attributes = []
            challenge_parameters = response.get('ChallengeParameters', {})
            
            # Log the challenge parameters to see what's required
            print(f"Challenge parameters: {challenge_parameters}")
            
            # The userAttributes field contains all current attributes
            if 'userAttributes' in challenge_parameters:
                import json
                user_attrs = json.loads(challenge_parameters['userAttributes'])
                print(f"User attributes: {user_attrs}")
            
            # The requiredAttributes field indicates which ones are required
            if 'requiredAttributes' in challenge_parameters:
                import json
                required_attrs = json.loads(challenge_parameters['requiredAttributes'])
                print(f"Required attributes: {required_attrs}")
            
            return {
                "status": "PASSWORD_CHANGE_REQUIRED",
                "session": response["Session"],
                "challengeParameters": challenge_parameters
            }
            
        # Return tokens if authentication successful
        return {
            "status": "SUCCESS",
            "tokens": response["AuthenticationResult"]
        }
    except Exception as e:
        print(f"Error in sign_in: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))

class ChangePasswordRequest(BaseModel):
    username: str
    session: str
    new_password: str
    challengeParameters: dict = {}

@app.post("/auth/change-password")
async def change_password(request: ChangePasswordRequest):
    # Calculate SECRET_HASH
    message = request.username + CLIENT_ID
    signature = hmac.new(
        key=CLIENT_SECRET.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    secret_hash = base64.b64encode(signature).decode()
    
    try:
        # Prepare basic challenge responses
        challenge_responses = {
            'USERNAME': request.username,
            'NEW_PASSWORD': request.new_password,
            'SECRET_HASH': secret_hash,
        }
        
        # Add a minimal set of required attributes for the specific user case
        # The address is required for this user's first-time password change
        challenge_responses['userAttributes.address'] = 'Not provided'
        
        # Process any required attributes based on the challenge parameters
        if request.challengeParameters:
            print(f"Processing challenge parameters: {request.challengeParameters}")
            
            # Check if requiredAttributes is available
            if 'requiredAttributes' in request.challengeParameters:
                try:
                    import json
                    required_attrs = json.loads(request.challengeParameters['requiredAttributes'])
                    print(f"Required attributes from challenge: {required_attrs}")
                    
                    # Add any additional required attributes
                    for attr in required_attrs:
                        if attr not in ['email_verified', 'phone_number_verified']:
                            challenge_responses[f'userAttributes.{attr}'] = 'Not provided'
                except Exception as e:
                    print(f"Error processing required attributes: {e}")
        
        print(f"Sending challenge responses: {challenge_responses}")
        
        # Respond to the challenge
        response = cognito_client.respond_to_auth_challenge(
            ClientId=CLIENT_ID,
            ChallengeName='NEW_PASSWORD_REQUIRED',
            Session=request.session,
            ChallengeResponses=challenge_responses
        )
        
        return {
            "status": "SUCCESS",
            "tokens": response["AuthenticationResult"]
        }
    except Exception as e:
        print(f"Error in change_password: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))

class AdminResetPasswordRequest(BaseModel):
    username: str
    new_password: str

@app.post("/auth/admin-reset-password")
async def admin_reset_password(request: AdminResetPasswordRequest):
    """
    Admin API to reset a user's password directly, bypassing the challenge flow.
    This requires AWS credentials with admin permissions on the Cognito User Pool.
    """
    try:
        # First, set the user's password with admin privileges
        admin_client.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=request.username,
            Password=request.new_password,
            Permanent=True  # Make this a permanent password, not temporary
        )
        
        print(f"Password changed successfully for user: {request.username}")
        
        # Now perform a normal sign-in to get tokens
        message = request.username + CLIENT_ID
        signature = hmac.new(
            key=CLIENT_SECRET.encode('utf-8'),
            msg=message.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        secret_hash = base64.b64encode(signature).decode()
        
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': request.username,
                'PASSWORD': request.new_password,
                'SECRET_HASH': secret_hash
            }
        )
        
        if 'AuthenticationResult' in response:
            return {
                "status": "SUCCESS",
                "message": "Password changed successfully",
                "tokens": response['AuthenticationResult']
            }
        else:
            return {
                "status": "WARNING",
                "message": "Password changed but could not get tokens automatically. Please sign in normally."
            }
            
    except Exception as e:
        print(f"Error in admin_reset_password: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)