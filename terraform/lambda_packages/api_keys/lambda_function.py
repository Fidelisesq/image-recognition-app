import json
import os
import boto3
import hashlib
import secrets
import time
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('API_KEYS_TABLE', 'rekognition-web-api-keys')

# Admin secret for managing API keys (set in environment)
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', '')

def lambda_handler(event, context):
    """
    API Key management endpoint.
    Requires admin secret in x-admin-secret header.
    
    POST /api-keys - Create new API key
    GET /api-keys - List all API keys (without revealing full keys)
    DELETE /api-keys/{keyId} - Revoke an API key
    """
    
    headers = event.get('headers', {})
    headers_lower = {k.lower(): v for k, v in headers.items()}
    
    # Verify admin secret
    admin_secret = headers_lower.get('x-admin-secret', '')
    if not ADMIN_SECRET or admin_secret != ADMIN_SECRET:
        return response(403, {'error': 'Unauthorized. Invalid admin secret.'})
    
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    path_params = event.get('pathParameters', {}) or {}
    body = {}
    
    if event.get('body'):
        try:
            body = json.loads(event['body'])
        except:
            body = {}
    
    try:
        if method == 'POST':
            return create_api_key(body)
        elif method == 'GET':
            return list_api_keys()
        elif method == 'DELETE':
            key_id = path_params.get('keyId', '')
            return revoke_api_key(key_id)
        else:
            return response(405, {'error': 'Method not allowed'})
    except Exception as e:
        print(f"Error: {e}")
        return response(500, {'error': str(e)})


def create_api_key(body):
    """Create a new API key."""
    table = dynamodb.Table(table_name)
    
    owner = body.get('owner', 'anonymous')
    description = body.get('description', '')
    
    # Generate a secure API key
    api_key = f"rk_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_id = api_key[:11]  # rk_ + first 8 chars for identification
    
    item = {
        'keyHash': key_hash,
        'keyId': key_id,
        'owner': owner,
        'description': description,
        'active': True,
        'createdAt': int(time.time()),
        'lastUsed': None,
        'usageCount': 0
    }
    
    table.put_item(Item=item)
    
    # Return the full API key only once - it cannot be retrieved again
    return response(201, {
        'message': 'API key created successfully',
        'apiKey': api_key,
        'keyId': key_id,
        'owner': owner,
        'warning': 'Save this API key now. It cannot be retrieved again.'
    })


def list_api_keys():
    """List all API keys (without revealing full keys)."""
    table = dynamodb.Table(table_name)
    
    result = table.scan(
        ProjectionExpression='keyId, #owner, description, active, createdAt, lastUsed, usageCount',
        ExpressionAttributeNames={'#owner': 'owner'}
    )
    
    keys = []
    for item in result.get('Items', []):
        keys.append({
            'keyId': item.get('keyId'),
            'owner': item.get('owner'),
            'description': item.get('description'),
            'active': item.get('active'),
            'createdAt': item.get('createdAt'),
            'lastUsed': item.get('lastUsed'),
            'usageCount': item.get('usageCount', 0)
        })
    
    return response(200, {'keys': keys, 'count': len(keys)})


def revoke_api_key(key_id):
    """Revoke an API key by keyId."""
    if not key_id:
        return response(400, {'error': 'keyId is required'})
    
    table = dynamodb.Table(table_name)
    
    # Find the key by keyId
    result = table.scan(
        FilterExpression='keyId = :kid',
        ExpressionAttributeValues={':kid': key_id}
    )
    
    items = result.get('Items', [])
    if not items:
        return response(404, {'error': 'API key not found'})
    
    # Deactivate the key
    key_hash = items[0]['keyHash']
    table.update_item(
        Key={'keyHash': key_hash},
        UpdateExpression='SET active = :false, revokedAt = :now',
        ExpressionAttributeValues={
            ':false': False,
            ':now': int(time.time())
        }
    )
    
    return response(200, {'message': f'API key {key_id} has been revoked'})


def response(status_code, body):
    """Generate API response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type, x-admin-secret'
        },
        'body': json.dumps(body)
    }
