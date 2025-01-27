# API Documentation

## Overview

The sync-crawl application exposes a FastAPI server that provides endpoints for browser automation, screenshot management, and workflow coordination. The server runs on `http://127.0.0.1:8000` by default.

## Endpoints

### Health Checks

#### GET `/health`
Extended health check for the Playwright instance.

**Response:**
```json
{
    "status": "ok",
    "message": "Playwright instance, browser, and page are healthy.",
    "details": {
        "playwright_type": "str",
        "browser_type": "str",
        "page_type": "str"
    }
}
```

#### GET `/ping`
Simple server health check.

**Response:**
```json
{
    "status": "ok",
    "message": "Server is running"
}
```

#### GET `/ping-pw`
Verify Playwright connection health.

**Response:**
```json
{
    "status": "ok",
    "message": "Playwright connection is active",
    "details": {
        "browser_type": "string",
        "contexts": "integer",
        "pages": "integer"
    }
}
```

### Browser Control

#### POST `/navigate`
Navigate to a specific URL.

**Request Body:**
```json
{
    "full_url": "string"
}
```

**Response:**
```json
{
    "status": "success",
    "message": "Navigated to {url}"
}
```

#### POST `/resize-window`
Resize the browser window.

**Query Parameters:**
- `width`: integer (1-9999)
- `height`: integer (1-9999)

**Response:**
```json
{
    "success": true,
    "new_size": {
        "width": "integer",
        "height": "integer",
        "windowWidth": "integer",
        "windowHeight": "integer"
    }
}
```

### Page Interaction

#### GET `/extract_metadata`
Extract metadata from the current page.

**Query Parameters:**
- `x` (optional): float - X coordinate for element lookup
- `y` (optional): float - Y coordinate for element lookup
- `steps` (optional): integer = 10 - Number of scroll steps
- `wait_per_step_ms` (optional): integer = 500 - Wait time between steps
- `overlap_percent` (optional): integer = 10 - Overlap percentage for scrolling

**Response:**
```json
{
    "status": "success",
    "url_metadata": {
        "full_url": "string",
        "scheme": "string",
        "domain": "string"
    },
    "dimensions": {
        "viewport": {
            "width": "integer",
            "height": "integer"
        },
        "fullPage": {
            "width": "integer",
            "height": "integer"
        }
    }
}
```

#### POST `/perform-actions`
Execute actions on the page.

**Request Body:**
```json
{
    "multiple_steps_required": "boolean",
    "visible_elements_from_instructions": "string",
    "summary_of_steps_so_far": "string",
    "action_tasks": [
        {
            "description": "string",
            "action_id": "integer",
            "candidates": [
                {
                    "element_description": "string",
                    "action": "string",
                    "type_text": "string",
                    "keyboard_action": "string",
                    "coordinates": {
                        "x": "float",
                        "y": "float"
                    }
                }
            ]
        }
    ]
}
```

**Query Parameters:**
- `wait_time`: integer - Wait time between actions
- `run_rerun_path`: string - Path for saving screenshots
- `draw_no_action`: boolean - Draw indicators without performing actions
- `center_opacity`: float = 0.4
- `mid_opacity`: float = 0.0
- `outer_opacity`: float = 0.5
- `border_thickness`: integer = 4
- `diameter`: integer = 15

### Screenshots and Visual Elements

#### GET `/screenshot`
Take screenshots of the page.

**Query Parameters:**
- `output_path`: string - Path to save screenshots
- `overlap_percentage`: float (0-100) = 30
- `max_chunks`: integer = 10
- `wait_after_scroll`: integer = 500
- `action_id`: integer (optional)
- `candidate_id`: integer (optional)
- `single_chunk_override_id`: integer (optional)

#### POST `/draw_dots`
Draw visual indicators on the page.

**Request Body:**
```json
[
    {
        "x": "float",
        "y": "float"
    }
]
```

**Query Parameters:**
- `diameter`: integer = 10
- `duration`: integer = 3000
- `opacity`: float = 0.8

### Page Stability

#### GET `/check-stability`
Check if the page is stable (no active animations or network requests).

**Query Parameters:**
- `timeout_ms`: integer = 1000
- `window_size_ms`: integer = 100

**Response:**
```json
{
    "is_stable": "boolean",
    "checks": {
        "network_idle": "boolean",
        "no_animations": "boolean",
        "dom_stable": "boolean"
    },
    "message": "string",
    "elapsed_ms": "integer"
}
```

### User Interface

#### GET `/show_message`
Display a message banner in the browser.

**Query Parameters:**
- `message`: string
- `duration`: integer = 3000
- `font_size`: integer = 16
- `background_opacity`: float = 0.8
- `font_color`: string = "#FFFFFF"

## Error Handling

All endpoints return appropriate HTTP status codes:
- 200: Success
- 400: Bad Request
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error
- 503: Service Unavailable (Playwright not initialized)

Error responses include detailed messages in the following format:
```json
{
    "detail": "Error description",
    "status_code": "integer"
}
```