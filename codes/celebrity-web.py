import json
import boto3
import os
import traceback
import urllib.request
import urllib.parse
from datetime import datetime
from decimal import Decimal
from urllib.parse import unquote_plus

# Initialize AWS clients
s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

# Configuration
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_REKOGNITION_SIZE = 15 * 1024 * 1024
MIN_CONFIDENCE = 70.0
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png'}
WIKIPEDIA_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'rekognition-results')


def get_wikipedia_summary(celebrity_name):
    """Fetch biography from Wikipedia."""
    try:
        encoded_name = urllib.parse.quote(celebrity_name.replace(' ', '_'))
        url = f"{WIKIPEDIA_API_URL}{encoded_name}"
        
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'AWS-Lambda-Celebrity-Demo/1.0'}
        )
        
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            extract = data.get('extract', '')
            
            if extract:
                sentences = extract.split('. ')
                short_bio = '. '.join(sentences[:3])
                if not short_bio.endswith('.'):
                    short_bio += '.'
                return short_bio
            return None
            
    except Exception as e:
        print(f"Wikipedia error for {celebrity_name}: {str(e)}")
        return None


def save_to_dynamodb(image_id, object_key, filename, results, status):
    """Save recognition results to DynamoDB."""
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        # Convert floats to Decimal for DynamoDB
        def convert_floats(obj):
            if isinstance(obj, float):
                return Decimal(str(round(obj, 2)))
            elif isinstance(obj, dict):
                return {k: convert_floats(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats(i) for i in obj]
            return obj
        
        item = {
            'imageId': image_id,
            'objectKey': object_key,
            'filename': filename,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'status': status,
            'results': convert_floats(results),
            'ttl': int(datetime.utcnow().timestamp()) + (7 * 24 * 60 * 60)  # 7 days TTL
        }
        
        table.put_item(Item=item)
        print(f"Saved results to DynamoDB: {image_id}")
        
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")


def lambda_handler(event, context):
    """Process S3 event and recognize celebrities."""
    start_time = datetime.utcnow()
    filename = None
    image_id = None
    object_key = None
    
    try:
        # Extract S3 event information
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        object_key = unquote_plus(record['s3']['object']['key'])
        object_size = record['s3']['object'].get('size', 0)
        filename = object_key.split('/')[-1]
        
        # Extract image_id from object key (uploads/20240513-123456-abc12345.jpg)
        image_id = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        print(f"[START] {start_time.isoformat()}Z Processing: {filename}")
        
        # Validate file format
        file_extension = ('.' + filename.rsplit('.', 1)[1].lower()) if '.' in filename else ''
        if file_extension not in SUPPORTED_FORMATS:
            print(f"[ERROR] Unsupported format: {file_extension}")
            save_to_dynamodb(image_id, object_key, filename, 
                           {'error': f'Unsupported format: {file_extension}'}, 'error')
            return {'statusCode': 200, 'body': 'Skipped - unsupported format'}
        
        # Check file size
        if object_size > MAX_REKOGNITION_SIZE:
            print(f"[ERROR] File too large: {object_size / 1_000_000:.1f}MB")
            save_to_dynamodb(image_id, object_key, filename,
                           {'error': 'File too large (max 15MB)'}, 'error')
            return {'statusCode': 200, 'body': 'Skipped - file too large'}
        
        # Call Rekognition
        print(f"[INFO] Calling Rekognition for: {filename}")
        
        response = rekognition_client.recognize_celebrities(
            Image={'S3Object': {'Bucket': bucket_name, 'Name': object_key}}
        )
        
        celebrity_faces = response.get('CelebrityFaces', [])
        unrecognized_faces = response.get('UnrecognizedFaces', [])
        
        # Filter by confidence
        recognized = [c for c in celebrity_faces if c.get('MatchConfidence', 0) >= MIN_CONFIDENCE]
        
        # Build results
        results = {
            'celebrities': [],
            'unrecognizedFaces': len(unrecognized_faces),
            'processingTime': 0
        }
        
        for celeb in recognized:
            celeb_data = {
                'name': celeb['Name'],
                'confidence': celeb.get('MatchConfidence', 0),
                'gender': celeb.get('KnownGender', {}).get('Type', 'Unknown'),
                'urls': celeb.get('Urls', [])
            }
            
            # Get Wikipedia bio
            wiki_bio = get_wikipedia_summary(celeb['Name'])
            if wiki_bio:
                celeb_data['biography'] = wiki_bio
            
            results['celebrities'].append(celeb_data)
            print(f"[CELEBRITY] {celeb['Name']}: {celeb.get('MatchConfidence', 0):.1f}%")
        
        # Calculate processing time
        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        results['processingTime'] = duration_ms
        
        # Determine status
        status = 'success' if recognized else 'no_celebrities'
        
        # Save to DynamoDB
        save_to_dynamodb(image_id, object_key, filename, results, status)
        
        print(f"[SUMMARY] Recognized {len(recognized)} celebrity(ies)")
        print(f"[END] SUCCESS - Duration: {duration_ms}ms")
        
        return {'statusCode': 200, 'body': f'Processed {len(recognized)} celebrities'}
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(traceback.format_exc())
        
        if image_id:
            save_to_dynamodb(image_id, object_key or '', filename or '',
                           {'error': error_msg}, 'error')
        
        return {'statusCode': 200, 'body': f'Failed - {error_msg}'}
