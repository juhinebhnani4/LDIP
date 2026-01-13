"""Timeline Engine tests package.

Test modules:
- test_date_extractor: Tests for DateExtractor service including:
  - Initialization and singleton factory
  - Response parsing (valid, empty, markdown-wrapped JSON)
  - Text chunking for long documents
  - Full extraction flow with mocked Gemini
  - Indian date format handling (DD/MM/YYYY, legal formats, FY)
  - Error handling and retry logic for rate limits
  - Integration pipeline tests
"""
