"""Resolver domain modules for AppSync Lambda handler.

Each module contains resolver functions for a specific domain:
- documents: Document CRUD, upload, reprocess, reindex
- images: Image upload, caption, submit, list, delete
- scrape: Scrape job management
- metadata: Metadata analysis, filter examples, key library
- chat: Async chat (queryKnowledgeBase, getConversation)
- shared: Shared utilities, clients, and configuration
"""
