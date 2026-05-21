# AI Image Recognition API Documentation

## Overview

This API provides AI-powered image recognition capabilities using Amazon Rekognition. It supports:
- **Celebrity Recognition**: Identify famous people in images with Wikipedia bios
- **Object & Scene Detection**: Detect objects, scenes, and activities in images

**Base URL**: `https://oxa9vjcw2d.execute-api.eu-west-2.amazonaws.com`

---

## Authentication

### For Website Users
Requests from `https://rekognition.fozdigitalz.com` are automatically authenticated - no API key required.

### For External API Users
All other requests require an API key in the `x-api-key` header:

```bash
curl -H "x-api-key: rk_your_api_key_here" https://oxa9vjcw2d.execute-api.eu-west-2.amazonaws.com/results
```

To obtain an API key, contact the administrator.

---

## Endpoints

### 1. Get Presigned Upload URL

Request a presigned URL to upload an image directly to S3.

**Endpoint**: `POST /upload`

**Headers**:
- `Content-Type: application/json`
- `x-api-key: your_api_key` (required for external requests)

**Request Body**:
```json
{
  "filename": "photo.jpg",
  "contentType": "image/jpeg",
  "mode": "celebrity"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| filename | string | Yes | Original filename (used for extension) |
| contentType | string | Yes | MIME type: `image/jpeg` or `image/png` |
| mode | string | No | Recognition mode: `celebrity` (default) or `labels` |

**Response** (200 OK):
```json
{
  "uploadUrl": "https://bucket.s3.eu-west-2.amazonaws.com/uploads/celebrity/20240101-120000-abc123.jpg?...",
  "imageId": "20240101-120000-abc123",
  "key": "uploads/celebrity/20240101-120000-abc123.jpg"
}
```

**Usage**:
1. Call this endpoint to get a presigned URL
2. Upload your image directly to the `uploadUrl` using PUT
3. Poll `/results/{imageId}` for recognition results

---

### 2. Upload Image to S3

After getting the presigned URL, upload your image:

```bash
curl -X PUT \
  -H "Content-Type: image/jpeg" \
  --data-binary @photo.jpg \
  "PRESIGNED_URL_HERE"
```

---

### 3. Get All Results

Retrieve all recognition results (most recent first).

**Endpoint**: `GET /results`

**Headers**:
- `x-api-key: your_api_key` (required for external requests)

**Response** (200 OK):
```json
{
  "results": [
    {
      "imageId": "20240101-120000-abc123",
      "status": "completed",
      "mode": "celebrity",
      "timestamp": "2024-01-01T12:00:00Z",
      "imageUrl": "https://...",
      "result": { ... }
    }
  ],
  "count": 1
}
```

---

### 4. Get Single Result

Retrieve a specific recognition result by image ID.

**Endpoint**: `GET /results/{imageId}`

**Headers**:
- `x-api-key: your_api_key` (required for external requests)

**Path Parameters**:
- `imageId`: The image identifier returned from the upload endpoint

**Response** (200 OK) - Celebrity Mode:
```json
{
  "imageId": "20240101-120000-abc123",
  "status": "completed",
  "mode": "celebrity",
  "timestamp": "2024-01-01T12:00:00Z",
  "imageUrl": "https://...",
  "result": {
    "celebrities": [
      {
        "name": "Elon Musk",
        "confidence": 99.5,
        "urls": ["https://www.imdb.com/name/nm1907769"],
        "knownFor": {
          "summary": "Elon Musk is a business magnate and investor...",
          "wikiUrl": "https://en.wikipedia.org/wiki/Elon_Musk"
        },
        "boundingBox": {
          "Width": 0.25,
          "Height": 0.45,
          "Left": 0.35,
          "Top": 0.1
        }
      }
    ],
    "unrecognizedFaces": 0
  }
}
```

**Response** (200 OK) - Labels Mode:
```json
{
  "imageId": "20240101-120000-abc123",
  "status": "completed",
  "mode": "labels",
  "timestamp": "2024-01-01T12:00:00Z",
  "imageUrl": "https://...",
  "result": {
    "labels": [
      {
        "name": "Dog",
        "confidence": 98.7,
        "categories": ["Animals and Pets"],
        "parents": ["Animal", "Mammal", "Pet"]
      },
      {
        "name": "Golden Retriever",
        "confidence": 95.2,
        "categories": ["Animals and Pets"],
        "parents": ["Animal", "Dog", "Mammal", "Pet"]
      }
    ],
    "labelCount": 15
  }
}
```

**Response** (200 OK) - Processing:
```json
{
  "imageId": "20240101-120000-abc123",
  "status": "processing",
  "message": "Image is being analyzed..."
}
```

**Response** (404 Not Found):
```json
{
  "error": "Result not found"
}
```

---

### 5. Delete Result

Delete a recognition result and its associated image.

**Endpoint**: `DELETE /results/{imageId}`

**Headers**:
- `x-api-key: your_api_key` (required for external requests)

**Path Parameters**:
- `imageId`: The image identifier to delete

**Response** (200 OK):
```json
{
  "message": "Result deleted successfully",
  "imageId": "20240101-120000-abc123"
}
```

---

## Error Responses

All endpoints may return these error responses:

**401 Unauthorized** (Missing or invalid API key):
```json
{
  "message": "Unauthorized"
}
```

**400 Bad Request**:
```json
{
  "error": "Invalid request. Missing required field: filename"
}
```

**500 Internal Server Error**:
```json
{
  "error": "Internal server error"
}
```

---

## Rate Limits

| Plan | Requests/Second | Requests/Day |
|------|-----------------|--------------|
| Free | 10 | 1,000 |
| Standard | 50 | 10,000 |
| Enterprise | 200 | Unlimited |

---

## Code Examples

### Python

```python
import requests
import time

API_KEY = "rk_your_api_key_here"
BASE_URL = "https://oxa9vjcw2d.execute-api.eu-west-2.amazonaws.com"

headers = {"x-api-key": API_KEY}

# 1. Get presigned URL
response = requests.post(
    f"{BASE_URL}/upload",
    headers={**headers, "Content-Type": "application/json"},
    json={
        "filename": "photo.jpg",
        "contentType": "image/jpeg",
        "mode": "celebrity"
    }
)
data = response.json()
upload_url = data["uploadUrl"]
image_id = data["imageId"]

# 2. Upload image
with open("photo.jpg", "rb") as f:
    requests.put(upload_url, data=f, headers={"Content-Type": "image/jpeg"})

# 3. Poll for results
for _ in range(30):
    result = requests.get(f"{BASE_URL}/results/{image_id}", headers=headers).json()
    if result.get("status") == "completed":
        print("Recognition complete!")
        print(result)
        break
    time.sleep(1)
```

### JavaScript

```javascript
const API_KEY = 'rk_your_api_key_here';
const BASE_URL = 'https://oxa9vjcw2d.execute-api.eu-west-2.amazonaws.com';

async function recognizeImage(file, mode = 'celebrity') {
  // 1. Get presigned URL
  const uploadResponse = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': API_KEY
    },
    body: JSON.stringify({
      filename: file.name,
      contentType: file.type,
      mode: mode
    })
  });
  const { uploadUrl, imageId } = await uploadResponse.json();

  // 2. Upload image
  await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': file.type }
  });

  // 3. Poll for results
  for (let i = 0; i < 30; i++) {
    const result = await fetch(`${BASE_URL}/results/${imageId}`, {
      headers: { 'x-api-key': API_KEY }
    }).then(r => r.json());
    
    if (result.status === 'completed') {
      return result;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  throw new Error('Timeout waiting for results');
}
```

### cURL

```bash
# Get presigned URL
curl -X POST https://oxa9vjcw2d.execute-api.eu-west-2.amazonaws.com/upload \
  -H "Content-Type: application/json" \
  -H "x-api-key: rk_your_api_key_here" \
  -d '{"filename":"photo.jpg","contentType":"image/jpeg","mode":"celebrity"}'

# Upload image (use uploadUrl from response)
curl -X PUT "PRESIGNED_URL" \
  -H "Content-Type: image/jpeg" \
  --data-binary @photo.jpg

# Get results
curl https://oxa9vjcw2d.execute-api.eu-west-2.amazonaws.com/results/IMAGE_ID \
  -H "x-api-key: rk_your_api_key_here"
```

---

## Supported Image Formats

| Format | MIME Type | Max Size |
|--------|-----------|----------|
| JPEG | image/jpeg | 5 MB |
| PNG | image/png | 5 MB |

---

## Recognition Modes

### Celebrity Mode (`mode: "celebrity"`)
- Identifies famous people (actors, athletes, politicians, etc.)
- Returns Wikipedia summaries and links
- Provides face bounding boxes
- Best for: Photos of people

### Labels Mode (`mode: "labels"`)
- Detects objects, scenes, activities, and concepts
- Returns hierarchical categories
- Confidence scores for each label
- Best for: General image analysis

---

## Support

For API key requests or technical support, contact: [your-email@example.com]

---

## Changelog

### v1.0.0 (2024)
- Initial release
- Celebrity recognition
- Object/scene detection
- Presigned URL uploads
- Results management
