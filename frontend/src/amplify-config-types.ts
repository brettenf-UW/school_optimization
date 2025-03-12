// Type definitions for AWS Amplify configuration
export interface AmplifyAuthConfig {
  region: string;
  userPoolId: string;
  userPoolWebClientId: string;
  mandatorySignIn?: boolean;
  signUpVerificationMethod?: string;
  authenticationFlowType?: string;
}

export interface AmplifyOAuthConfig {
  domain?: string;
  scope?: string[];
  redirectSignIn?: string;
  redirectSignOut?: string;
  responseType?: string;
}

export interface AmplifyConfig {
  Auth: AmplifyAuthConfig;
  aws_project_region?: string;
  aws_cognito_identity_pool_id?: string;
  aws_cognito_region?: string;
  aws_user_pools_id?: string;
  aws_user_pools_web_client_id?: string;
  oauth?: AmplifyOAuthConfig;
}
