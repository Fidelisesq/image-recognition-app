// Configuration - This file will be updated after Terraform deployment
// Replace API_ENDPOINT with your actual API Gateway URL

const CONFIG = {
    // API Gateway endpoint (update after terraform apply)
    API_ENDPOINT: 'https://oxa9vjcw2d.execute-api.eu-west-2.amazonaws.com',
    
    // Polling interval for checking results (milliseconds)
    POLL_INTERVAL: 2000,
    
    // Maximum polling attempts
    MAX_POLL_ATTEMPTS: 30,
    
    // Supported file types
    SUPPORTED_TYPES: ['image/jpeg', 'image/png'],
    
    // Maximum file size (5MB)
    MAX_FILE_SIZE: 5 * 1024 * 1024
};

// Don't modify below this line
window.CONFIG = CONFIG;
