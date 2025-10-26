"""
Knowledge Base Query Lambda

AppSync resolver for searching/chatting with the Knowledge Base.

Input (AppSync):
{
    "query": "What is in this document?",
    "max_results": 5
}

Output:
{
    "results": [
        {
            "content": "...",
            "source": "document_id",
            "score": 0.85
        }
    ]
}
"""

import json
import logging
import os
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Query Bedrock Knowledge Base.
    """
    # Get environment variables (moved here for testability)
    knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
    if not knowledge_base_id:
        raise ValueError("KNOWLEDGE_BASE_ID environment variable is required")

    bedrock_agent = boto3.client('bedrock-agent-runtime')

    logger.info(f"Querying Knowledge Base: {json.dumps(event)}")

    try:
        # Extract query
        query = event.get('query', '')
        max_results = event.get('max_results', 5)

        if not query:
            return {
                'results': [],
                'message': 'No query provided'
            }

        # Query Knowledge Base
        response = bedrock_agent.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={
                'text': query
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        )

        # Parse results
        results = []
        for item in response.get('retrievalResults', []):
            results.append({
                'content': item.get('content', {}).get('text', ''),
                'source': item.get('location', {}).get('s3Location', {}).get('uri', ''),
                'score': item.get('score', 0.0)
            })

        logger.info(f"Found {len(results)} results")

        return {
            'results': results,
            'query': query,
            'total': len(results)
        }

    except Exception as e:
        logger.error(f"Knowledge Base query failed: {e}", exc_info=True)
        return {
            'results': [],
            'error': str(e)
        }
