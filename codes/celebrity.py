import json
import boto3
import traceback
import urllib.request
import urllib.parse
from datetime import datetime
from urllib.parse import unquote_plus

# Initialize AWS clients
s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')

# Configuration
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB (for demo uploads)
MAX_REKOGNITION_SIZE = 15 * 1024 * 1024  # 15 MB (Rekognition limit)
MIN_CONFIDENCE = 70.0  # Minimum confidence threshold for celebrity match
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png'}
WIKIPEDIA_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def get_wikipedia_summary(celebrity_name):
    try:
        # URL-encode the celebrity name for the API call
        encoded_name = urllib.parse.quote(celebrity_name.replace(' ', '_'))
        url = f"{WIKIPEDIA_API_URL}{encoded_name}"
        
        # Create request with a user agent (Wikipedia requires this)
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'AWS-Lambda-Celebrity-Demo/1.0'}
        )
        
        # Make the API call with a timeout
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Get the extract (summary) from the response
            extract = data.get('extract', '')
            
            if extract:
                # Limit to first 2-3 sentences for readability
                sentences = extract.split('. ')
                short_bio = '. '.join(sentences[:3])
                if not short_bio.endswith('.'):
                    short_bio += '.'
                return short_bio
            
            return None
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log_info(f"Wikipedia article not found for: {celebrity_name}")
        else:
            log_warning(f"Wikipedia API error for {celebrity_name}: {e.code}")
        return None
    except Exception as e:
        log_warning(f"Failed to fetch Wikipedia info for {celebrity_name}: {str(e)}")
        return None


def lambda_handler(event, context):
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
        
        # Call Amazon Rekognition Celebrity Recognition
        print(f"[INFO] Calling Rekognition Celebrity Recognition for: {filename}")
        
        response = rekognition_client.recognize_celebrities(
            Image={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': object_key
                }
            }
        )
        
        # Get celebrity faces from response
        celebrity_faces = response.get('CelebrityFaces', [])
        unrecognized_faces = response.get('UnrecognizedFaces', [])
        
        # Filter celebrities by confidence threshold
        recognized_celebrities = [
            celeb for celeb in celebrity_faces 
            if celeb.get('MatchConfidence', 0) >= MIN_CONFIDENCE
        ]
        
        # Check if any celebrities were detected
        if not recognized_celebrities:
            log_info(f"No celebrities detected with confidence >= {MIN_CONFIDENCE}% in {filename}")
            if unrecognized_faces:
                log_info(f"(Found {len(unrecognized_faces)} unrecognized face(s) in the image)")
            log_completion("SUCCESS", start_time, filename)
            return create_response(200, "No celebrities detected")
        
        # Log each detected celebrity with Wikipedia bio
        print(f"\n{'='*60}")
        print(f"🌟 IMAGE: {filename}")
        print(f"{'='*60}")
        
        for celeb in recognized_celebrities:
            celeb_name = celeb['Name']
            confidence = celeb.get('MatchConfidence', 0)
            
            # Get additional info if available
            urls = celeb.get('Urls', [])
            known_gender = celeb.get('KnownGender', {}).get('Type', 'Unknown')
            
            print(f"\n[CELEBRITY] {celeb_name}")
            print(f"    Confidence: {confidence:.1f}%")
            if known_gender != 'Unknown':
                print(f"    Gender: {known_gender}")
            
            # Fetch and display Wikipedia biography
            print(f"    [Fetching Wikipedia bio...]")
            wiki_bio = get_wikipedia_summary(celeb_name)
            if wiki_bio:
                print(f"\n    📖 BIOGRAPHY:")
                # Word wrap the bio for better readability
                words = wiki_bio.split()
                line = "       "
                for word in words:
                    if len(line) + len(word) + 1 > 80:
                        print(line)
                        line = "       " + word
                    else:
                        line += " " + word if line.strip() else word
                if line.strip():
                    print(line)
            else:
                print(f"    📖 Biography not available on Wikipedia")
            
            if urls:
                print(f"\n    🔗 More info: {urls[0]}")
        
        print(f"\n{'='*60}")
        print(f"[SUMMARY] Recognized {len(recognized_celebrities)} celebrity(ies) in {filename}")
        if unrecognized_faces:
            print(f"[INFO] Also found {len(unrecognized_faces)} unrecognized face(s)")
        print(f"{'='*60}\n")
        
        # Log successful completion
        log_completion("SUCCESS", start_time, filename)
        
        return create_response(200, f"Successfully recognized {len(recognized_celebrities)} celebrity(ies)")
        
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
