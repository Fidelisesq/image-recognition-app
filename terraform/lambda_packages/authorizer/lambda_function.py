import json
import os
import boto3
import hashlib
from botocore.exceptions import ClientError
import time

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('API_KEYS_TABLE', 'rekognition-web-api-keys')

# Allowed origins that don't need API key
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'https://rekognition.fozdigitalz.com').split(',')

def lambda_handler(event, context):
    """
    Lambda authorizer for API Gateway HTTP API.
    - Allows requests from whitelisted origins without API key
    - Requires valid API key for external requests
    """
    
    headers = event.get('headers', {})
    
    # Normalize headers to lowercase
    headers_lower = {k.lower(): v for k, v in headers.items()}
    
    # Get origin and referer
    origin = headers_lower.get('origin', '')
    referer = headers_lower.get('referer', '')
    
    # Check if request is from allowed origin (your website)
    for allowed in ALLOWED_ORIGINS:
        allowed = allowed.strip()
        if origin.startswith(allowed) or referer.startswith(allowed):
            print(f"Allowed origin: {origin or referer}")
            return {
                'isAuthorized': True,
                'context': {
                    'principalId': 'website-user',
                    'source': 'website'
                }
            }
    
    # For external requests, check API key
    api_key = headers_lower.get('x-api-key', '')
    
    if not api_key:
        print(f"No API key provided. Origin: {origin}, Referer: {referer}")
        return {
            'isAuthorized': False,
            'context': {
                'principalId': 'anonymous',
                'error': 'API key required'
            }
        }
    
    # Validate API key
    validation_result = validate_api_key(api_key)
    if validation_result['valid']:
        return {
            'isAuthorized': True,
            'context': {
                'principalId': validation_result.get('owner', api_key[:8]),
                'source': 'api-key',
                'keyId': api_key[:8]
            }
        }
    
    print(f"Invalid API key: {api_key[:8]}...")
    return {
        'isAuthorized': False,
        'context': {
            'principalId': 'invalid-key',
            'error': 'Invalid API key'
        }
    }


def validate_api_key(api_key):
    """Check if API key exists and is active in DynamoDB."""
    try:
        table = dynamodb.Table(table_name)
        
        # Hash the API key for secure storage comparison
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        response = table.get_item(
            Key={'keyHash': key_hash}
        )
        
        item = response.get('Item')
        if item and item.get('active', False):
            # Update last used timestamp and usage count
            try:
                table.update_item(
                    Key={'keyHash': key_hash},
                    UpdateExpression='SET lastUsed = :now, usageCount = if_not_exists(usageCount, :zero) + :inc',
                    ExpressionAttributeValues={
                        ':now': int(time.time()),
                        ':zero': 0,
                        ':inc': 1
                    }
                )
            except Exception as e:
                print(f"Failed to update usage stats: {e}")
            
            return {'valid': True, 'owner': item.get('owner', 'unknown')}
        
        return {'valid': False}
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return {'valid': False}
    except Exception as e:
        print(f"Validation error: {e}")
        return {'valid': False}
