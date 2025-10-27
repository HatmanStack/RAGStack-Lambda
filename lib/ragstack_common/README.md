# ragstack_common - Shared Library

This directory contains utilities shared across multiple RAGStack Lambda functions.

## Overview

The `ragstack_common` package is installed as a Python package during the SAM build process. It provides common functionality for:

- **bedrock.py** - Bedrock client and model interactions
- **ocr.py** - OCR backends (Textract and Bedrock)
- **image.py** - Image processing utilities
- **storage.py** - S3 operations
- **models.py** - Data models and schemas

## Package Structure

```
lib/
  setup.py                    <- Package configuration (installable via pip)
  ragstack_common/            <- The actual package
    __init__.py
    bedrock.py
    ocr.py
    image.py
    storage.py
    models.py
    test_*.py                 <- Unit tests
```

## Usage in Lambda Functions

Lambda functions that need this library reference it in their `requirements.txt`:

```
./lib
boto3>=1.34.0
```

During `sam build`, pip installs the package from `./lib` into the Lambda deployment package, making it available for import:

```python
from ragstack_common import storage
from ragstack_common.bedrock import BedrockClient
from ragstack_common.ocr import extract_text_from_pdf
```

## Lambda Functions Using This Library

- **process_document** - Uses ocr, storage, bedrock, image modules for document processing
- **generate_embeddings** - Uses bedrock, storage modules for embedding generation

### Lambda Functions NOT Using This Library

The following Lambda functions do not import from ragstack_common and therefore do not include it:

- **query_kb** - Uses boto3 directly for Bedrock KB queries, no shared utilities needed
- **kb_custom_resource** - Uses boto3 directly for CloudFormation custom resource, standalone
- **appsync_resolvers** - Uses boto3 directly for AppSync resolvers, standalone DynamoDB/S3/SFN operations

**Note**: If future requirements dictate that these functions need shared utilities, add `./lib` to their `requirements.txt` files.

## Development

### Making Changes

1. Edit files in `lib/ragstack_common/`
2. Run `sam build` to rebuild Lambda functions with updated library
3. Test changes locally or deploy to AWS

### Running Tests

```bash
pytest lib/ragstack_common/test_*.py -v
```

### Dependencies

Dependencies are declared in `lib/setup.py` and automatically installed with the package:

- `boto3>=1.34.0` - AWS SDK
- `PyMuPDF>=1.23.0` - PDF processing
- `Pillow>=10.0.0` - Image processing

## Important Notes

- **Source of truth**: This directory (`lib/ragstack_common/`) is the source code
- **Package installation**: The package is installed by pip during SAM build
- **No copying**: Unlike some approaches, we don't copy files - pip installs the package properly
- **Test files**: The `test_*.py` files are excluded from the package via setup.py configuration
- **Build artifacts**: `.egg-info` and `build/` directories are git-ignored (created during development)

## Adding New Lambda Functions

To use this library in a new Lambda function:

1. Add `./lib` to the Lambda's `requirements.txt`
2. Import modules as needed: `from ragstack_common import <module>`
3. Run `sam build` - the package will be automatically installed

## Comparison to Base Repository

This structure mirrors the base repository pattern at `~/accelerated-intelligent-document-processing-on-aws`:

- **Base repo**: `lib/idp_common_pkg/` with `setup.py` and `idp_common/` subdirectory
- **Our repo**: `lib/` with `setup.py` and `ragstack_common/` subdirectory

Both use the same pip-based package installation approach during SAM build.
