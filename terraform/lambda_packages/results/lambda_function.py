import json
import boto3
import os
from decimal import Decimal
from botocore.config import Config

dynamodb = boto3.resource('dynamodb')

# Use regional endpoint for CORS compatibility
s3_config = Config(
    region_name='eu-west-2',
    s3={'addressing_style': 'virtual'}
)
s3_client = boto3.client('s3', config=s3_config, region_name='eu-west-2')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
BUCKET_NAME = os.environ.get('BUCKET_NAME')


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    """
    Handle recognition results from DynamoDB.
    - GET /results - List all results
    - GET /results/{imageId} - Get specific result
    - DELETE /results/{imageId} - Delete a result
    """
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Check HTTP method
        http_method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
        
        # Check if specific imageId requested
        path_params = event.get('pathParameters') or {}
        image_id = path_params.get('imageId')
        
        # Handle DELETE request
        if http_method == 'DELETE' and image_id:
            return delete_result(table, image_id)
        
        if image_id:
            # Get specific result
            response = table.get_item(Key={'imageId': image_id})
            item = response.get('Item')
            
            if not item:
                return create_response(404, {'error': 'Result not found'})
            
            # Generate presigned URL for the image
            if item.get('objectKey'):
                item['imageUrl'] = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': item['objectKey']},
                    ExpiresIn=3600
                )
            
            return create_response(200, item)
        
        else:
            # List all results (most recent first)
            response = table.scan()
            items = response.get('Items', [])
            
            # Sort by timestamp descending
            items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Limit to last 50 results
            items = items[:50]
            
            # Generate presigned URLs for images
            for item in items:
                if item.get('objectKey'):
                    item['imageUrl'] = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': BUCKET_NAME, 'Key': item['objectKey']},
                        ExpiresIn=3600
                    )
            
            return create_response(200, {'results': items, 'count': len(items)})
        
    except Exception as e:
        print(f"Error getting results: {str(e)}")
        return create_response(500, {'error': 'Failed to get results', 'message': str(e)})


def delete_result(table, image_id):
    """Delete a result from DynamoDB and S3."""
    try:
        # Get the item first to find the S3 object key
        response = table.get_item(Key={'imageId': image_id})
        item = response.get('Item')
        
        if not item:
            return create_response(404, {'error': 'Result not found'})
        
        # Delete from S3 if object key exists
        object_key = item.get('objectKey')
        if object_key:
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=object_key)
                print(f"Deleted S3 object: {object_key}")
            except Exception as e:
                print(f"Error deleting S3 object: {str(e)}")
        
        # Delete from DynamoDB
        table.delete_item(Key={'imageId': image_id})
        print(f"Deleted DynamoDB item: {image_id}")
        
        return create_response(200, {'message': 'Result deleted successfully', 'imageId': image_id})
        
    except Exception as e:
        print(f"Error deleting result: {str(e)}")
        return create_response(500, {'error': 'Failed to delete result', 'message': str(e)})


def create_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET, DELETE, OPTIONS'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }
