import json
import boto3
import traceback
from datetime import datetime
from urllib.parse import unquote_plus

# Initialize AWS clients
s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')

# Configuration
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB (for demo uploads)
MAX_REKOGNITION_SIZE = 15 * 1024 * 1024  # 15 MB (Rekognition limit)
MIN_CONFIDENCE = 70.0  # Minimum confidence threshold
MAX_LABELS = 50  # Maximum labels to request
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png'}


def lambda_handler(event, context):
    """
    Process S3 event and analyze image with Amazon Rekognition.
    
    This function is triggered when an image is uploaded to S3.
    It retrieves the image, sends it to Rekognition for analysis,
    and logs the detected labels to CloudWatch.
    """
    start_time = datetime.utcnow()
    filename = None
    
    try:
        # Extract S3 event information
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        object_key = unquote_plus(record['s3']['object']['key'])
        object_size = record['s3']['object'].get('size', 0)
        filename = object_key.split('/')[-1]  # Get just the filename
        
        # Log start of processing
        log_start(start_time, filename)
        
        # Validate file format
        file_extension = get_file_extension(filename)
        if file_extension not in SUPPORTED_FORMATS:
            log_error(f"Unsupported file format: {file_extension}. Supported formats: JPEG, PNG")
            log_completion("SKIPPED", start_time, filename)
            return create_response(200, f"Skipped - unsupported format: {file_extension}")
        
        # Check file size (from event, may not always be present)
        if object_size > MAX_REKOGNITION_SIZE:
            log_error(f"Image exceeds maximum size: {object_size / 1_000_000:.1f}MB (max: 15MB)")
            log_completion("SKIPPED", start_time, filename)
            return create_response(200, "Skipped - file too large for Rekognition")
        
        if object_size > MAX_UPLOAD_SIZE:
            log_warning(f"Image size ({object_size / 1_000_000:.1f}MB) exceeds recommended 5MB for demo")
        
        # Call Amazon Rekognition
        print(f"[INFO] Calling Rekognition for: {filename}")
        
        response = rekognition_client.detect_labels(
            Image={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': object_key
                }
            },
            MaxLabels=MAX_LABELS
        )
        
        # Filter labels by confidence threshold
        all_labels = response.get('Labels', [])
        filtered_labels = [
            label for label in all_labels 
            if label['Confidence'] >= MIN_CONFIDENCE
        ]
        
        # Check if any labels were detected
        if not filtered_labels:
            log_info(f"No objects detected with confidence >= {MIN_CONFIDENCE}% in {filename}")
            if all_labels:
                log_info(f"(Found {len(all_labels)} labels below threshold)")
            log_completion("SUCCESS", start_time, filename)
            return create_response(200, "No high-confidence labels detected")
        
        # Log each detected label
        print(f"\n{'='*50}")
        print(f"📸 IMAGE: {filename}")
        print(f"{'='*50}")
        
        for label in filtered_labels:
            label_name = label['Name']
            confidence = label['Confidence']
            print(f"[LABEL] {label_name}: {confidence:.1f}%")
        
        print(f"{'='*50}")
        print(f"[SUMMARY] Detected {len(filtered_labels)} labels for {filename}")
        print(f"{'='*50}\n")
        
        # Log successful completion
        log_completion("SUCCESS", start_time, filename)
        
        return create_response(200, f"Successfully processed {len(filtered_labels)} labels")
        
    except rekognition_client.exceptions.InvalidS3ObjectException as e:
        log_error(f"Invalid S3 object for Rekognition: {str(e)}")
        log_completion("FAILED", start_time, filename)
        return create_response(200, "Failed - invalid image for Rekognition")
        
    except rekognition_client.exceptions.ImageTooLargeException as e:
        log_error(f"Image too large for Rekognition: {str(e)}")
        log_completion("FAILED", start_time, filename)
        return create_response(200, "Failed - image too large")
        
    except s3_client.exceptions.NoSuchKey as e:
        log_error(f"S3 object not found: bucket={bucket_name}, key={object_key}")
        log_completion("FAILED", start_time, filename)
        return create_response(200, "Failed - S3 object not found")
        
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        log_error(f"Unexpected error: {error_type} - {error_message}")
        log_error(f"Stack trace:\n{traceback.format_exc()}")
        log_completion("FAILED", start_time, filename)
        return create_response(200, f"Failed - {error_type}")


def get_file_extension(filename):
    """Extract and normalize file extension."""
    if '.' in filename:
        return '.' + filename.rsplit('.', 1)[1].lower()
    return ''


def log_start(start_time, filename):
    """Log the start of processing."""
    timestamp = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f"[START] {timestamp} Processing: {filename}")


def log_completion(status, start_time, filename=None):
    """Log the completion of processing with duration."""
    end_time = datetime.utcnow()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)
    file_info = f" for {filename}" if filename else ""
    print(f"[END] {status}{file_info} - Duration: {duration_ms}ms")


def log_error(message):
    """Log an error message."""
    print(f"[ERROR] {message}")


def log_warning(message):
    """Log a warning message."""
    print(f"[WARNING] {message}")


def log_info(message):
    """Log an informational message."""
    print(f"[INFO] {message}")


def create_response(status_code, message):
    """Create a standardized response object."""
    return {
        'statusCode': status_code,
        'body': json.dumps({'message': message})
    }