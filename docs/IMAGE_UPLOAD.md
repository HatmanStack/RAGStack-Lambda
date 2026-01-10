# Image Upload API

Upload images with AI-generated or manual captions for multimodal search.

## Overview

Images are indexed with both:
- **Visual embeddings** (Nova Multimodal) - find visually similar images
- **Text embeddings** (captions) - find images by description

## Dashboard Image Tab

The Image Upload tab provides:

### Caption Prompt Editor
Customize the AI prompt used to generate image captions. Changes apply immediately to new uploads.

**Location:** Image Upload tab → Caption Prompt (expandable section)

**Default prompt:** Generates concise, searchable captions focusing on main subject, setting, and visual elements.

## Single Image Upload (Auto-Process)

For the simplest workflow, use `autoProcess: true` to let AI generate captions automatically:

```graphql
mutation CreateImageUploadUrl($filename: String!, $autoProcess: Boolean, $userCaption: String) {
  createImageUploadUrl(filename: $filename, autoProcess: $autoProcess, userCaption: $userCaption) {
    uploadUrl    # Presigned S3 POST URL
    imageId      # Unique identifier for this upload
    s3Uri        # S3 URI for the image
    fields       # Form fields for S3 POST (JSON string)
  }
}
```

**Parameters:**
- `filename` (required): Original filename with extension
- `autoProcess`: Set to `true` for automatic AI caption generation after upload
- `userCaption`: Optional user-provided caption (combined with AI caption if autoProcess=true)

With `autoProcess: true`, just upload the file and processing happens automatically via EventBridge.

### Auto-Process JavaScript Example

```javascript
async function uploadImageAutoProcess(imageFile, userCaption = '') {
  // 1. Get presigned URL with autoProcess enabled
  const urlRes = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
    body: JSON.stringify({
      query: `mutation($filename: String!, $autoProcess: Boolean!, $userCaption: String) {
        createImageUploadUrl(filename: $filename, autoProcess: $autoProcess, userCaption: $userCaption) {
          uploadUrl, imageId, fields
        }
      }`,
      variables: { filename: imageFile.name, autoProcess: true, userCaption: userCaption }
    })
  });
  const { uploadUrl, imageId, fields } = (await urlRes.json()).data.createImageUploadUrl;

  // 2. Upload to S3 - processing starts automatically
  const form = new FormData();
  Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
  form.append('file', imageFile);
  await fetch(uploadUrl, { method: 'POST', body: form });

  return imageId;  // Image will be processed and indexed automatically
}
```

## Single Image Upload (Manual Steps)

For more control, use the 4-step process:

### Step 1: Get Upload URL

```graphql
mutation CreateImageUploadUrl($filename: String!) {
  createImageUploadUrl(filename: $filename) {
    uploadUrl    # Presigned S3 POST URL
    imageId      # Unique identifier for this upload
    s3Uri        # S3 URI for caption generation
    fields       # Form fields for S3 POST (JSON string)
  }
}
```

### Step 2: Upload to S3

```javascript
const form = new FormData();
Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
form.append('file', imageFile);
await fetch(uploadUrl, { method: 'POST', body: form });
```

### Step 3: Generate AI Caption (Optional)

Use Bedrock vision models to generate a descriptive caption:

```graphql
mutation GenerateCaption($imageS3Uri: String!) {
  generateCaption(imageS3Uri: $imageS3Uri) {
    caption      # AI-generated description
  }
}
```

The caption is optimized for search with relevant keywords.

### Step 4: Submit Image

Finalize the upload with caption(s) to trigger processing:

```graphql
mutation SubmitImage($input: SubmitImageInput!) {
  submitImage(input: $input) {
    imageId
    filename
    status       # PROCESSING → INDEXED
  }
}

# Input
{
  "input": {
    "imageId": "abc123",
    "userCaption": "My manual description",  # Optional
    "aiCaption": "AI-generated description"  # Optional
  }
}
```

If both captions provided, they're combined: `"{userCaption}. {aiCaption}"`

## Complete JavaScript Example

```javascript
const ENDPOINT = 'https://your-api.appsync-api.region.amazonaws.com/graphql';
const API_KEY = 'your-api-key';

async function uploadImageWithCaption(imageFile) {
  // 1. Get presigned URL
  const urlRes = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
    body: JSON.stringify({
      query: `mutation($filename: String!) {
        createImageUploadUrl(filename: $filename) {
          uploadUrl, imageId, s3Uri, fields
        }
      }`,
      variables: { filename: imageFile.name }
    })
  });
  const { uploadUrl, imageId, s3Uri, fields } = (await urlRes.json()).data.createImageUploadUrl;

  // 2. Upload to S3
  const form = new FormData();
  Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
  form.append('file', imageFile);
  await fetch(uploadUrl, { method: 'POST', body: form });

  // 3. Generate AI caption
  const captionRes = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
    body: JSON.stringify({
      query: `mutation($imageS3Uri: String!) {
        generateCaption(imageS3Uri: $imageS3Uri) { caption }
      }`,
      variables: { imageS3Uri: s3Uri }
    })
  });
  const aiCaption = (await captionRes.json()).data.generateCaption.caption;

  // 4. Submit with caption
  await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
    body: JSON.stringify({
      query: `mutation($input: SubmitImageInput!) {
        submitImage(input: $input) { imageId, status }
      }`,
      variables: { input: { imageId, aiCaption } }
    })
  });

  return imageId;
}
```

## Batch Upload (ZIP Archive)

Upload multiple images at once with optional automatic caption generation.

### Create ZIP Upload URL

```graphql
mutation CreateZipUploadUrl($generateCaptions: Boolean) {
  createZipUploadUrl(generateCaptions: $generateCaptions) {
    uploadUrl
    uploadId
    fields
  }
}
```

Set `generateCaptions: true` to auto-generate AI captions for images without manual captions.

### ZIP File Structure

```
images.zip
├── photo1.jpg
├── photo2.png
├── subfolder/
│   └── photo3.gif
└── captions.json    # Optional manifest
```

### captions.json Format

Provide manual captions for specific images:

```json
{
  "photo1.jpg": "Sunset over the mountains with golden clouds",
  "photo2.png": "City skyline at night with lights reflecting on water",
  "subfolder/photo3.gif": "Animated loading spinner"
}
```

Images not in the manifest will get AI-generated captions if `generateCaptions=true`.

### JavaScript Example

```javascript
async function uploadImageZip(zipFile, generateCaptions = true) {
  // 1. Get presigned URL
  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
    body: JSON.stringify({
      query: `mutation($generateCaptions: Boolean) {
        createZipUploadUrl(generateCaptions: $generateCaptions) {
          uploadUrl, uploadId, fields
        }
      }`,
      variables: { generateCaptions }
    })
  });
  const { uploadUrl, uploadId, fields } = (await res.json()).data.createZipUploadUrl;

  // 2. Upload ZIP to S3
  const form = new FormData();
  Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
  form.append('file', zipFile);
  await fetch(uploadUrl, { method: 'POST', body: form });

  // Processing happens automatically via EventBridge
  return uploadId;
}
```

## Supported Formats

- **Images:** JPG, JPEG, PNG, GIF, WebP, AVIF
- **Max size:** 50 MB per image, 500 MB per ZIP

## Querying Images

After indexing, images are searchable via:

```graphql
query SearchKnowledgeBase($query: String!) {
  searchKnowledgeBase(query: $query) {
    results {
      content      # Caption text
      s3Uri        # Image location
      score        # Relevance score
    }
  }
}
```

Both text queries ("sunset mountains") and image similarity work through the unified Bedrock KB.

## Authentication

All mutations require either:
- **API Key:** `x-api-key` header
- **Cognito:** JWT token in `Authorization` header

Get your API key from the Settings page in the web UI.
