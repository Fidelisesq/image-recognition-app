// Configuration - Auto-populated by CI/CD pipeline
// Do NOT hardcode values here - they are injected during deployment

const CONFIG = {
    // API Gateway endpoint (injected by GitHub Actions during deployment)
    API_ENDPOINT: '__API_ENDPOINT__',
    
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
