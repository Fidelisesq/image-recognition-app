import json
import boto3
import os
import uuid
from datetime import datetime
from botocore.config import Config

# Use regional endpoint for CORS compatibility
s3_config = Config(
    region_name='us-east-1',
    s3={'addressing_style': 'virtual'}
)
s3_client = boto3.client('s3', config=s3_config, region_name='us-east-1')
BUCKET_NAME = os.environ.get('BUCKET_NAME')


def lambda_handler(event, context):
    """
    Generate a presigned URL for uploading an image to S3.
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        filename = body.get('filename', 'image.jpg')
        content_type = body.get('contentType', 'image/jpeg')
        mode = body.get('mode', 'celebrity')  # 'celebrity' or 'labels'
        
        # Validate content type
        if content_type not in ['image/jpeg', 'image/png']:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Only JPEG and PNG images are supported'})
            }
        
        # Validate mode
        if mode not in ['celebrity', 'labels']:
            mode = 'celebrity'
        
        # Generate unique image ID
        image_id = f"{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        # Get file extension
        ext = filename.split('.')[-1].lower() if '.' in filename else 'jpg'
        # Include mode in path: uploads/{mode}/{imageId}.{ext}
        object_key = f"uploads/{mode}/{image_id}.{ext}"
        
        # Generate presigned URL (valid for 5 minutes, max 5MB)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key,
                'ContentType': content_type
            },
            ExpiresIn=300,
            HttpMethod='PUT'
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'uploadUrl': presigned_url,
                'imageId': image_id,
                'objectKey': object_key
            })
        }
        
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to generate upload URL',
                'message': str(e)
            })
        }
