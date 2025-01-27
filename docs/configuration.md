# Configuration Guide

## Environment Setup

### Chrome Configuration

1. **Debug Port Setup**
   ```bash
   # Windows
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="C:\my-chrome-profile"

   # macOS
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9223 --user-data-dir="~/chrome-debug-profile"
   ```

2. **Profile Management**
   - Use a separate Chrome profile for automation
   - Keep the profile clean of extensions
   - Regularly clear browsing data

### Server Configuration

The FastAPI server (`fastAPIServ.py`) supports the following configurations:

```python
# Server settings
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8000       # Default port
RELOAD = True     # Auto-reload on code changes
RELOAD_DELAY = 0.25  # Delay between reloads

# Browser settings
STABILITY_TIMEOUT_MS = 10000  # Max time to wait for page stability
STABILITY_WINDOW_MS = 1000    # Window size for stability checks
CHECK_STABILITY_RETRIES = 5   # Number of stability check attempts
```

### Logging Configuration

The logging system (`log_config.py`) provides hierarchical logging:

```python
# Log levels
LOG_LEVEL = logging.INFO

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(funcName)s - Line: %(lineno)d - %(levelname)s - %(message)s"

# Output locations
LOG_FILE = "app.log"
CONSOLE_OUTPUT = True
```

## Folder Structure

The system requires specific folder structure:

```
clients/
└── [client_name]/
    └── [workflow_id]/
        └── [sample_id]/
            └── [rerun_id]/
                └── [run_id]/
                    └── [run_retry_id]/
                        ├── dots/       # Visual indicators
                        ├── temp/       # Temporary files
                        ├── highlights/ # Highlighted screenshots
                        └── chunks/     # Screenshot segments
```

## Visual Settings

### Screenshot Configuration

```python
# Screenshot settings
MAX_WIDTH = 1092
MAX_HEIGHT = 1092
OVERLAP_PERCENTAGE = 30
MAX_CHUNKS = 10
```

### Visual Indicators

```python
# Dot visualization
DOT_DIAMETER = 15
DOT_DURATION = 3000
CENTER_OPACITY = 0.4
MID_OPACITY = 0.0
OUTER_OPACITY = 0.5
BORDER_THICKNESS = 4
```

## API Keys

Create a `keys.py` file with the following structure:

```python
# API Keys
GOOGLE_API_KEY = "your_google_api_key"  # For Google AI services
claude_key = "your_claude_api_key"      # For Claude AI services
```

## Browser Automation

### Playwright Settings

```python
# Browser launch options
BROWSER_OPTIONS = {
    "headless": False,
    "viewport": {
        "width": 1256,
        "height": 1369
    }
}

# Connection settings
CDP_URL = "http://127.0.0.1:9223"
```

### Action Configuration

```python
# Action timing
WAIT_AFTER_SCROLL = 500  # ms
WAIT_BETWEEN_ACTIONS = 2000  # ms

# Stability checks
STABILITY_CHECKS = {
    "network_idle": True,
    "no_animations": True,
    "dom_stable": True
}
```

## Error Recovery

Configure error recovery behavior:

```python
# Retry settings
MAX_RUN = 7        # Maximum workflow runs
MAX_RERUN = 4      # Maximum retry attempts
MAX_RUN_RERUN = 4  # Maximum retries per run

# Recovery delays
RETRY_DELAY = 1000  # ms
ERROR_COOLDOWN = 5000  # ms
```

## AI Integration

### Claude AI Settings

```python
# Claude configuration
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
MAX_TOKENS = 8192
TEMPERATURE = 0.0
```

### Google AI Settings

```python
# Google AI configuration
CR_MODEL_NAME = "gemini-1.5-flash-002"
GENERATION_CONFIG = {
    "temperature": 0,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json"
}
```

## Performance Tuning

Optimize performance with these settings:

```python
# Memory management
MAX_SCREENSHOTS = 100  # Maximum stored screenshots
CLEANUP_INTERVAL = 3600  # Cleanup interval in seconds

# Browser performance
MAX_CONCURRENT_PAGES = 1
PAGE_TIMEOUT = 30000  # ms
RESOURCE_TIMEOUT = 10000  # ms
```