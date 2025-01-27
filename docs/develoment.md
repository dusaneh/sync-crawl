# Developer Guide

## Development Environment Setup

### Local Development Environment

1. **Fork and Clone**
   ```bash
   git clone https://github.com/[your-username]/sync-crawl.git
   cd sync-crawl
   ```

2. **Create Development Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Install Development Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

   Additional development dependencies:
   - pytest
   - black
   - flake8
   - mypy
   - jupyter

### Code Style Guidelines

We follow PEP 8 with some modifications:

1. **Line Length**
   - Maximum line length: 100 characters
   - Exception for URLs and long strings

2. **Naming Conventions**
   ```python
   # Classes
   class CamelCase:
       pass

   # Functions and variables
   def snake_case_function():
       pass

   # Constants
   MAX_RETRIES = 3
   ```

3. **Documentation**
   ```python
   def example_function(param1: str, param2: int) -> bool:
       """
       Brief description of function.

       Args:
           param1 (str): Description of param1
           param2 (int): Description of param2

       Returns:
           bool: Description of return value

       Raises:
           ValueError: Description of when this is raised
       """
       pass
   ```

## Project Structure

### Core Components

1. **FastAPI Server (`fastAPIServ.py`)**
   - Route handlers
   - Middleware
   - Browser automation

2. **Helper Functions (`helper.py`)**
   - Utility functions
   - AI integration
   - Image processing

3. **Logging System (`hlogger.py`)**
   - Hierarchical logging
   - State tracking

### Adding New Features

1. **Server Endpoints**
   ```python
   from fastapi import APIRouter

   router = APIRouter()

   @router.post("/new-endpoint")
   async def new_endpoint():
       """
       Template for new endpoints.
       """
       pass
   ```

2. **Helper Functions**
   ```python
   def new_helper_function(param1: str, param2: int) -> dict:
       """
       Template for new helper functions.
       """
       result = {}
       return result
   ```

## Testing

### Unit Tests

1. **Test Structure**
   ```python
   import pytest
   from helper import new_helper_function

   def test_new_helper_function():
       # Arrange
       param1 = "test"
       param2 = 42

       # Act
       result = new_helper_function(param1, param2)

       # Assert
       assert isinstance(result, dict)
   ```

2. **Running Tests**
   ```bash
   # Run all tests
   pytest

   # Run specific test file
   pytest tests/test_helper.py

   # Run with coverage
   pytest --cov=.
   ```

### Integration Tests

1. **Browser Tests**
   ```python
   import pytest
   from playwright.sync_api import Page

   def test_browser_interaction(page: Page):
       # Setup
       page.goto("http://example.com")

       # Action
       page.click("#button")

       # Verify
       assert page.is_visible("#result")
   ```

2. **API Tests**
   ```python
   from fastapi.testclient import TestClient
   from main import app

   client = TestClient(app)

   def test_api_endpoint():
       response = client.post("/api/endpoint", json={})
       assert response.status_code == 200
   ```

## Error Handling

### Best Practices

1. **Custom Exceptions**
   ```python
   class BrowserConnectionError(Exception):
       """Raised when browser connection fails."""
       pass

   class ElementNotFoundError(Exception):
       """Raised when UI element is not found."""
       pass
   ```

2. **Error Recovery**
   ```python
   async def safe_browser_action(action_func):
       max_retries = 3
       for attempt in range(max_retries):
           try:
               return await action_func()
           except Exception as e:
               if attempt == max_retries - 1:
                   raise
               await asyncio.sleep(1)
   ```

## Debugging

### Tools and Techniques

1. **Browser Debugging**
   ```python
   # Enable verbose logging
   await page.set_viewport_size({"width": 1280, "height": 720})
   await page.screenshot(path="debug.png", full_page=True)
   ```

2. **Server Debugging**
   ```python
   from fastapi import HTTPException

   @app.exception_handler(HTTPException)
   async def http_exception_handler(request, exc):
       logger.error(f"HTTP error: {exc.detail}")
       return {"detail": exc.detail}
   ```

3. **AI Integration Debugging**
   ```python
   def debug_ai_response(prompt: str, response: dict):
       logger.debug(f"Prompt: {prompt}")
       logger.debug(f"Response: {json.dumps(response, indent=2)}")
   ```

## Performance Optimization

### Guidelines

1. **Browser Interaction**
   - Use element selectors efficiently
   - Minimize page reloads
   - Implement proper waiting strategies

2. **Image Processing**
   - Optimize screenshot sizes
   - Use appropriate image formats
   - Implement caching when possible

3. **AI Integration**
   - Cache common responses
   - Batch similar requests
   - Implement timeout handling

## Deployment

### Development to Production

1. **Environment Configuration**
   ```python
   # config.py
   from pydantic_settings import BaseSettings

   class Settings(BaseSettings):
       debug: bool = False
       chrome_port: int = 9223
       api_timeout: int = 30

       class Config:
           env_file = ".env"
   ```

2. **Docker Support**
   ```dockerfile
   FROM python:3.12-slim

   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt

   COPY . .
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
   ```

## Contributing

### Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make Changes**
   - Follow style guidelines
   - Add tests
   - Update documentation

3. **Submit Pull Request**
   - Describe changes
   - Link related issues
   - Include test results

### Code Review Checklist

- [ ] Follows style guidelines
- [ ] Includes tests
- [ ] Updates documentation
- [ ] Handles errors appropriately
- [ ] Optimizes performance
- [ ] Maintains backward compatibility