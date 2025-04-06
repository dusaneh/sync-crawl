import asyncio
import platform
import os
import math
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Request
from playwright.async_api import async_playwright, Browser, Page, Playwright
import uvicorn
from watchfiles import awatch
from urllib.parse import urlparse, parse_qs
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import datetime
import sys
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import json
import requests
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse
import json
from pathlib import Path

from playwright.async_api import Error  # Import the correct error class
from log_config import get_logger

logger = get_logger(__name__)  # Use module name for easier identification




async def retry_evaluate(page, script, args=None, retries=3):
    for attempt in range(retries):
        try:
            logger.info(f"Script evaluated successfully: Attempt {attempt + 1}")
            return await page.evaluate(script, args)
        except Error as e:  # Use the correct Playwright error
            if "Execution context was destroyed" in str(e) and attempt < retries - 1:
                logger.warning(f"Retrying evaluate due to execution context destruction: Attempt {attempt + 1}")
                await asyncio.sleep(1)  # Allow navigation to stabilize
            else:
                raise e



# Set up logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('app.log'),
#         logging.StreamHandler(sys.stdout)
#     ]
# )
# logger = logging.getLogger(__name__)



class NavigationRequest(BaseModel):
    url_metadata: dict






# "dot_for_element_present": string,  // State if the dots appear in the image for this element, where in relation to the exact center of the element the dot is, and what the likely coordinates are in from the description.
                        
# "dot_needs_adjustment": string, // if you were to change the coordinates of the dot (if present) describe how the dot needs to be adjusted  (e.g., "move 2 pixels to the right and 3 pixels down"), or state "no adjustment needed" if the dot is already 100% perfectly on the element. But err on the side of adjusting toward perfection.

# #                 "confidence_that_element_is_visible": float, // Confidence level in the selection (0.0-1.0).
# "confidence_that_element_is_visible": float,  // Confidence level (0.0-1.0) that the element is visible.

# "element_visible_in_screenshot": boolean,  // Whether the element is clearly visible in the screenshot.
# "element_size": int,  // Size of the element in square pixels.

# "checked_again": boolean,  // Double-check if the element is visible; mark false if unsure.
# "confidence": float,  // Confidence that the element is the appropriate next action (0.0-1.0).

# "genealiziable": float,  // Score how generalizable the action is to any user's data or product configuration (0.0-1.0 with 1.0 being completely generalizable and 0.0 being very currently logged in user specific).



class Coordinates(BaseModel):
    x: float
    y: float


class Candidate(BaseModel):
    image_description: str  # Add this to match the payload
    element_description: str
    action: str
    type_text: Optional[str] = None  # Empty string is allowed by default for Optional[str]
    expected_outcome: str
    keyboard_action: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    combined_score: float
    rank: int
    to_act: bool
    candidate_id: int
    image_number: Optional[int] = None  # Make image_number optional if it might be missing
    coordinates_ready_to_act: Optional[Coordinates] = None
    coordinates_ready_to_draw: Optional[Coordinates] = None
    scroll_to: Optional[float] = None  # Keep this if future payloads might include it


class ActionTask(BaseModel):
    description: str
    action_id: int
    candidates: List[Candidate]


class ActionPayload(BaseModel):
    multiple_steps_required: bool
    visible_elements_from_instructions: str
    summary_of_steps_so_far: str
    action_tasks: List[ActionTask]
    error: Optional[str] = ""  # Allow empty string explicitly
    page_description: str
    expected_outcome_hopeful: str


# Define request models
class CoordinatePoint(BaseModel):
    x: float
    y: float


# Windows-specific event loop policy
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Global variables for Playwright instances
playwright: Optional[Playwright] = None
browser: Optional[Browser] = None
page: Optional[Page] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global playwright, browser, page

    try:
        logger.info("Starting Playwright...")
        playwright = await async_playwright().start()
        logger.debug(f"Initialized Playwright object: {playwright}")

        try:
            browser = await playwright.chromium.connect_over_cdp("http://127.0.0.1:9223")
            logger.info("Connected to existing browser session.")
        except Exception as e:
            logger.warning(f"Failed to connect via CDP. Launching new browser instance. Error: {str(e)}")
            browser = await playwright.chromium.launch(headless=True)

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()

        logger.debug(f"Browser contexts: {len(browser.contexts)}, Pages: {len(context.pages)}")
        yield

    finally:
        if browser:
            logger.info("Closing browser...")
            await browser.close()
        if playwright:
            logger.info("Stopping Playwright...")
            await playwright.stop()




# Initialize FastAPI with lifespan manager
app = FastAPI(lifespan=lifespan)


# Add logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    try:
        response = await call_next(request)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"Request: {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {duration:.3f}s"
        )
        return response
    except Exception as e:
        logger.error(
            f"Request failed: {request.method} {request.url.path} - "
            f"Error: {str(e)}"
        )
        raise


from pydantic import BaseModel

class NavigatePayload(BaseModel):
    full_url: str

@app.post("/navigate")
async def navigate_to_state(payload: NavigatePayload):
    """
    Navigates to a specific state based on the provided URL metadata.
    """
    try:
        full_url = payload.full_url
        print(f"Navigating to: {full_url}")
        global page
        
        # Navigate and wait for load state
        await page.goto(full_url)
        await page.wait_for_load_state("load")
        
        # Optional: wait for network to be idle
        try:
            await page.wait_for_load_state("networkidle", timeout=3000)
        except PlaywrightTimeoutError:
            print("Network did not reach idle state, continuing anyway")
            
        return {"status": "success", "message": f"Navigated to {full_url}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Navigation failed: {e}")





from pydantic import BaseModel
import time
import asyncio
from fastapi import FastAPI, HTTPException

class ListenRequest(BaseModel):
    watch_url: str = ""           # Empty => capture all requests
    silence_ms: int = 5000        # Wait for this inactivity threshold
    max_runtime_ms: int = 10000   # Absolute max run time


# --- Your /listen_for_requests endpoint (CORRECTED) ---
@app.post("/listen_for_requests")
async def listen_for_requests(payload: ListenRequest):
    """
    Listens for requests on the global page. Captures those matching `watch_url`.
    Returns early if no new *matching* request arrives for `silence_ms` ms.
    Also terminates if total time reaches `max_runtime_ms`, whichever happens first.

    Body example:
    {
      "watch_url": "https://eventbus.intuit.com/v2/intuit-clickstream",
      "silence_ms": 5000,
      "max_runtime_ms": 10000
    }
    """
    global page # Access the globally initialized page object
    if not page:
        print("[/listen_for_requests] ERROR: No global page available!")
        logger.error("[/listen_for_requests] ERROR: No global page available!") # Use logger
        raise HTTPException(status_code=503, detail="No global page available.")

    watch_url = payload.watch_url.strip()
    silence_ms = payload.silence_ms
    max_runtime_ms = payload.max_runtime_ms

    # Use logger instead of print for consistency
    logger.info("\n[/listen_for_requests]")
    logger.info(f"  watch_url: {watch_url or '(none — capturing all)'}")
    logger.info(f"  silence_ms: {silence_ms}, max_runtime_ms: {max_runtime_ms}")
    logger.info(f"  Using page URL: {page.url}")

    captured_requests = []
    last_request_time = time.time()    # track last matching request
    start_time = time.time()           # track overall start

    # --- CORRECTED on_request function ---
    def on_request(req): # req is playwright.async_api.Request
        # Log the request event
        logger.debug(f"  [Request Event] {req.method} {req.url}")

        # If watch_url is empty, we match all. Otherwise, must contain watch_url
        if (not watch_url) or (watch_url in req.url):
            nonlocal last_request_time
            last_request_time = time.time()

            req_info = {
                "method": req.method,
                "request_url": req.url,
                "page_url": page.url,
                # ***** CORRECTED LINE: Access headers as a property *****
                "request_headers": req.headers # Gets headers as a dictionary (no parentheses)
            }
            # Capture POST body
            if req.method.upper() == "POST":
                # Use the .post_data property
                req_info["post_data"] = req.post_data or ""

            captured_requests.append(req_info)

            logger.info(f"    => MATCHED: {req.url}") # Log matched requests
        else:
            logger.debug(f"    => Did NOT match watch_url: {req.url}") # Log non-matches if needed

    # Attach listener
    page.on("request", on_request)
    logger.info("  Request listener attached. Waiting...")

    try:
        # Keep looping until silence or max-time
        while True:
            # Use asyncio.sleep for cooperative multitasking in async functions
            await asyncio.sleep(0.2)
            elapsed_since_last_request = (time.time() - last_request_time) * 1000
            total_elapsed = (time.time() - start_time) * 1000

            if elapsed_since_last_request > silence_ms:
                # We had no matching requests for `silence_ms`
                logger.info(f"  Inactivity threshold reached: {elapsed_since_last_request:.0f}ms > {silence_ms}ms")
                break

            if total_elapsed > max_runtime_ms:
                # We reached max overall runtime
                logger.info(f"  Max runtime reached: {total_elapsed:.0f}ms > {max_runtime_ms}ms")
                break

    # NOTE: The 'Error occurred in event listener' message in your log
    # indicates the listener itself raised an exception (the TypeError).
    # Playwright catches this and emits an 'error' event, but the listener
    # might stop processing further requests correctly after the error.
    # It's crucial to detach the listener in the finally block regardless.
    finally:
        # Detach listener to prevent memory leaks
        # This runs even if an error occurred inside the try block
        page.remove_listener("request", on_request)
        logger.info("  Request listener detached.")

    logger.info(f"[/listen_for_requests] Returning {len(captured_requests)} captured requests.\n")
    return {"captured_requests": captured_requests}


@app.get("/health")
async def health_check():
    """
    Extended endpoint to verify the health of the Playwright instance, browser connection, and page.
    """
    global playwright, browser, page
    try:
        # Check if Playwright is initialized
        if not playwright:
            logger.error("Playwright is not initialized.")
            return {"status": "error", "message": "Playwright is not initialized."}

        # Check if the browser is connected
        if not browser:
            logger.error("Browser is not connected.")
            return {"status": "error", "message": "Browser is not connected."}

        # Check if the page is initialized
        if not page:
            logger.error("Page is not initialized.")
            return {"status": "error", "message": "Page is not initialized."}

        # Check if the page is loaded
        if not await page.is_visible("body"):
            logger.error("Page is not loaded or body is not visible.")
            return {"status": "error", "message": "Page is not loaded or body is not visible."}

        # Log types for debugging
        logger.info(f"Type of playwright: {type(playwright)}")
        logger.info(f"Type of browser: {type(browser)}")
        logger.info(f"Type of page: {type(page)}")

        return {
            "status": "ok",
            "message": "Playwright instance, browser, and page are healthy.",
            "details": {
                "playwright_type": str(type(playwright)),
                "browser_type": str(type(browser)),
                "page_type": str(type(page))
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Health check failed: {str(e)}"}




# Add error handling
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error occurred: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled error occurred: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status_code": 500}
    )

@app.get("/ping")
async def ping():
    """Simple endpoint to check if the server is running."""
    logger.info("Ping request received")
    return {
        "status": "ok",
        "message": "Server is running"
    }

@app.get("/ping")
async def ping():
    """Simple endpoint to check if the server is running."""
    return {
        "status": "ok",
        "message": "Server is running"
    }

@app.get("/ping-pw")
async def ping_playwright():
    """Check if the Playwright connection is active and functioning."""
    global playwright, browser, page
    
    try:

        await page.wait_for_load_state("load")

        if not playwright or not browser or not page:
            raise HTTPException(
                status_code=503,
                detail="Playwright connection not initialized"
            )
            
        # Try to evaluate a simple script to verify the connection
        await retry_evaluate(page, "1 + 1")
        
        return {
            "status": "ok",
            "message": "Playwright connection is active",
            "details": {
                "browser_type": browser.browser_type.name,
                "contexts": len(browser.contexts),
                "pages": len(browser.contexts[0].pages) if browser.contexts else 0
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Playwright connection error: {str(e)}"
        )


async def get_element_metadata(page, x: float, y: float) -> dict:
    """
    Get comprehensive metadata about the element at specified coordinates,
    including properly scaled bounding box coordinates.
    """
    try:
        # Wait for page load and ensure coordinates are valid
        await page.wait_for_load_state("load")
        
        # Get the device pixel ratio to account for screen scaling
        device_pixel_ratio = await retry_evaluate(page, "window.devicePixelRatio")
        
        # Get element at coordinates
        element_handle = await page.evaluate_handle(
            '''({ x, y }) => {
                const element = document.elementFromPoint(x, y);
                if (!element) return null;
                
                // Check if element is actually visible
                const style = window.getComputedStyle(element);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    return null;
                }
                
                return element;
            }''',
            {'x': x, 'y': y}
        )

        if not element_handle:
            return None

        # Get detailed element information including accurate bounding box
        element_json = await element_handle.evaluate('''element => {
            // Get all attributes
            const attributes = {};
            for (let attr of element.attributes) {
                attributes[attr.name] = attr.value;
            }
            
            // Get computed style
            const computedStyle = window.getComputedStyle(element);
            
            // Get accurate bounding box with scroll offset
            const rect = element.getBoundingClientRect();
            const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
            const scrollY = window.pageYOffset || document.documentElement.scrollTop;
            
            // Account for any CSS transforms
            const transform = computedStyle.transform;
            const matrix = new DOMMatrixReadOnly(transform);
            const scale = Math.hypot(matrix.a, matrix.b);
            
            // Get zoom level
            const zoom = parseFloat(computedStyle.zoom) || 1;
            
            // Calculate final coordinates accounting for all factors
            const boundingBox = {
                x: (rect.left + scrollX) / (scale * zoom),
                y: (rect.top + scrollY) / (scale * zoom),
                width: rect.width / (scale * zoom),
                height: rect.height / (scale * zoom)
            };
            
            // Get element's text content, handling different cases
            let textContent = element.innerText || element.textContent || '';
            textContent = textContent.trim();
            
            // Check visibility more thoroughly
            const isVisible = (() => {
                if (computedStyle.display === 'none') return false;
                if (computedStyle.visibility === 'hidden') return false;
                if (parseFloat(computedStyle.opacity) === 0) return false;
                if (rect.width === 0 || rect.height === 0) return false;
                return true;
            })();

            return {
                tagName: element.tagName,
                id: element.id || null,
                class: element.className || null,
                attributes: attributes,
                innerText: textContent,
                outerHTML: element.outerHTML || null,
                boundingBox: boundingBox,
                computedStyle: {
                    visibility: computedStyle.visibility,
                    display: computedStyle.display,
                    opacity: computedStyle.opacity,
                    zIndex: computedStyle.zIndex,
                    backgroundColor: computedStyle.backgroundColor,
                    transform: transform,
                    zoom: zoom
                },
                isVisible: isVisible,
                devicePixelRatio: window.devicePixelRatio
            };
        }''')

        # Add helpful identification information
        if element_json:
            element_json['identifiers'] = {
                'xpath': await element_handle.evaluate('''element => {
                    const getXPath = node => {
                        let xpath = '';
                        let parent = node.parentNode;
                        
                        if (!parent) return xpath;
                        
                        if (node.id) {
                            return `//*[@id="${node.id}"]`;
                        }
                        
                        xpath = getXPath(parent);
                        const sameTypeCount = Array.from(parent.children)
                            .filter(child => child.tagName === node.tagName)
                            .indexOf(node) + 1;
                            
                        const tagName = node.tagName.toLowerCase();
                        xpath += `/${tagName}[${sameTypeCount}]`;
                        
                        return xpath;
                    };
                    return getXPath(element);
                }'''),
                'selector': await element_handle.evaluate('''element => {
                    const getSelector = node => {
                        if (node.id) return `#${node.id}`;
                        if (node.className) {
                            const classes = Array.from(node.classList).join('.');
                            return classes ? `.${classes}` : null;
                        }
                        return null;
                    };
                    return getSelector(element);
                }''')
            }

        return element_json

    except Exception as e:
        logger.error(f"Error getting element metadata at ({x}, {y}): {str(e)}")
        return {
            "error": f"Error getting element metadata at ({x}, {y}): {str(e)}",
            "coordinates": {"x": x, "y": y}
        }



async def ensure_load_state(
    page,
    load_timeout: int = 30000,
    networkidle_timeout: int = 10
) -> None:
    """
    Ensures the page has reached at least the 'load' state and optionally the 'networkidle' state.

    Args:
        page: The Playwright page instance.
        load_timeout: Maximum time to wait for the 'load' state (in milliseconds).
        networkidle_timeout: Maximum time to wait for the 'networkidle' state (in milliseconds).

    Raises:
        Exception: If both 'load' and 'networkidle' states fail to be reached.
    """
    try:
        # Wait for 'load' state
        logger.info("Waiting for page 'load' state...")
        await page.wait_for_load_state("load", timeout=load_timeout)
        logger.info("'Load' state reached.")
    except Exception as e:
        logger.warning(f"Page 'load' state not reached within {load_timeout / 1000} seconds: {str(e)}")

    try:
        # Wait for 'networkidle' state
        logger.info("Waiting for page 'networkidle' state...")
        await page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
        logger.info("'Networkidle' state reached.")
    except Exception as e:
        logger.warning(f"Page 'networkidle' state not reached within {networkidle_timeout / 1000} seconds: {str(e)}. Proceeding with soft load.")


async def scroll_to_position(page, scroll_to: float) -> None:
    """
    Scrolls the page to a specific y position smoothly.
    
    Args:
        page: Playwright page instance
        scroll_to: Y coordinate to scroll to
    """
    try:
        await retry_evaluate(page, f'''async () => {{
            // Smooth scroll to position
            window.scrollTo({{
                top: {scroll_to},
                left: 0,
                behavior: 'smooth'
            }});
            
            // Wait for scroll and any animations
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Ensure we're at exact position (smooth scroll might not be exact)
            window.scrollTo(0, {scroll_to});
            
            // Final wait for stability
            await new Promise(resolve => setTimeout(resolve, 100));
        }}''')
        
        logger.debug(f"Scrolled to y-position: {scroll_to}")
    except Exception as e:
        logger.error(f"Error scrolling to position {scroll_to}: {str(e)}")
        raise

async def draw_dots_internal(
    elements: dict,
    diameter: int = 10,
    duration: int = 3000,
    center_opacity: float = 0.0,     # Transparency at the inner center (0 = fully transparent)
    mid_opacity: float = 0.4,        # Opacity at mid ring
    outer_opacity: float = 0.0,      # Opacity at the outer ring
    border_thickness: int = 0,       # Optional hard line at the outer edge; 0 = no line
    screenshot_info: Optional[dict] = None
):
    """
    Draw a "flare" dot at the given coordinates, with a radial gradient that
    transitions from 'center_opacity' to 'mid_opacity' to 'outer_opacity'.
    Optionally draw a hard line (border) around the circle if 'border_thickness' > 0.

    Args:
        elements (dict): Must contain {'x': <int>, 'y': <int>, 'action_id': <Any>} 
                         for the dot's center coordinates and optional ID.
        diameter (int): Base diameter for the dot. The flare will be sized at ~3x this for effect.
        duration (int): How long (ms) to keep the dot in the DOM (then remove it).
        center_opacity (float): Opacity at the center region (0.0 to 1.0).
        mid_opacity (float): Opacity at the mid radius region (0.0 to 1.0).
        outer_opacity (float): Opacity near the outer radius region (0.0 to 1.0).
        border_thickness (int): Thickness in px of an optional outer border; 0 = none.
        screenshot_info (dict, optional): If you still want to do an immediate screenshot,
                                          pass the relevant info here; otherwise ignore.

    Example radial gradient stops:
      0-10%:    center_opacity
      10-40%:   mid_opacity
      40-80%:   outer_opacity
      beyond 80%: fully transparent

    Returns:
        dict: Information about the success status and how many elements were drawn.
    """
    global page
    logger.info("Starting internal dot drawing with radial gradient...")

    try:
        if not page:
            raise ValueError("Page not initialized")

        # Ensure page is fully loaded
        await ensure_load_state(page)

        # We increase the "flare" size around the center.  
        # You can adjust the multiplier for a bigger or smaller glow radius.
        script = '''({
            x, y, diameter, duration,
            centerOpacity, midOpacity, outerOpacity, borderThickness
        }) => {
            const dot = document.createElement('div');
            
            // Expand the diameter to produce a bigger glow area
            const flareDiameter = diameter * 3; 

            // Build the radial gradient with multi-stop fade:
            //  - 0-10% uses centerOpacity
            //  - 10-40% uses midOpacity
            //  - 40-80% uses outerOpacity
            //  - beyond 80% is fully transparent
            const gradientCSS = `
                radial-gradient(circle,
                  rgba(0, 123, 255, ${centerOpacity}) 10%,
                  rgba(0, 123, 255, ${midOpacity}) 40%,
                  rgba(0, 123, 255, ${outerOpacity}) 80%,
                  rgba(0, 123, 255, 0) 100%
                )
            `;

            const styleMap = {
                position: 'absolute',
                left: x + 'px',
                top: y + 'px',
                width: flareDiameter + 'px',
                height: flareDiameter + 'px',
                background: gradientCSS,
                pointerEvents: 'none',
                zIndex: '999999',
                transform: 'translate(-50%, -50%)'
            };

            // If borderThickness > 0, draw a solid ring around the entire circle
            if (borderThickness > 0) {
                styleMap.border = borderThickness + 'px solid rgba(0, 123, 255, 1)';
                styleMap.borderRadius = '50%';
            }

            // Apply all styles
            for (const [prop, val] of Object.entries(styleMap)) {
                dot.style[prop] = val;
            }

            // Add the dot to the DOM
            document.body.appendChild(dot);

            // Remove after 'duration' ms
            setTimeout(() => dot.remove(), duration);
        }''';

        await retry_evaluate(page, script, {
            'x': elements['x'],
            'y': elements['y'],
            'diameter': diameter,
            'duration': duration,
            'centerOpacity': center_opacity,
            'midOpacity': mid_opacity,
            'outerOpacity': outer_opacity,
            'borderThickness': border_thickness
        })

        logger.info("Radial flare dot drawn successfully.")

        # If you want an immediate screenshot for each dot (not recommended if you only want one final screenshot),
        # you could do:
        #
        # if screenshot_info:
        #     output_path = os.path.join(
        #         screenshot_info['base_path'],
        #         'dots',
        #         f"chunk_{elements['action_id']}.png"
        #     )
        #     logger.info(f"Taking screenshot -> {output_path}")
        #     await take_screenshot_internal(output_path)

        return {
            "status": "success",
            "message": "Flare dot(s) drawn successfully",
            "count": len(elements)
        }

    except Exception as e:
        logger.error(f"Failed to draw radial dots: {str(e)}")
        raise


async def perform_single_action(
    page, 
    task: ActionTask, 
    feedback_metadata: list, 
    wait_time: int,
    run_rerun_path: str,
    draw_no_action: bool = False,
    center_opacity=0.2,
    mid_opacity=0.6,
    outer_opacity=0.1,
    border_thickness=2,
    diameter = 20
):
    await page.wait_for_load_state("load")

    for candidate in task.candidates:
        if not candidate.to_act:
            continue

        coordinates = candidate.coordinates_ready_to_act
        coordinates_to_draw = candidate.coordinates_ready_to_draw

        # 1) If we are in "draw only" mode:
        if draw_no_action:
            if coordinates_to_draw:
                # Draw the dot, but do NOT sleep afterwards
                # await draw_dots_internal(
                #     elements={
                #         'x': coordinates_to_draw.x,
                #         'y': coordinates_to_draw.y,
                #         'action_id': task.action_id
                #     },
                #     diameter=20,
                #     duration=3000,
                #     opacity=0.8,
                #     screenshot_info={'base_path': f"{run_rerun_path}"}
                # )
                await draw_dots_internal(
                    elements={
                        'x': coordinates_to_draw.x,
                        'y': coordinates_to_draw.y,
                        'action_id': task.action_id
                    },
                    diameter=diameter,
                    duration=3000,
                    center_opacity=center_opacity,
                    mid_opacity=mid_opacity,
                    outer_opacity=outer_opacity,
                    border_thickness=border_thickness,
                    screenshot_info={'base_path': f"{run_rerun_path}"}
                )
            
            # We can still collect metadata if desired
            if coordinates:
                metadata = await get_element_metadata(page, coordinates.x, coordinates.y)
                feedback_metadata.append({
                    "action_id": task.action_id,
                    "description": task.description,
                    "candidate_id": candidate.candidate_id,
                    "coordinates": {"x": coordinates.x, "y": coordinates.y},
                    "element_metadata": metadata,
                    "expected_outcome": candidate.expected_outcome
                })

            # **No sleep** here at all.

        # 2) If we're performing real actions:
        else:
            if coordinates:
                # Optionally gather metadata
                metadata = await get_element_metadata(page, coordinates.x, coordinates.y)
                feedback_metadata.append({
                    "action_id": task.action_id,
                    "description": task.description,
                    "candidate_id": candidate.candidate_id,
                    "coordinates": {"x": coordinates.x, "y": coordinates.y},
                    "element_metadata": metadata,
                    "expected_outcome": candidate.expected_outcome
                })

                # Perform the actual user action
                if candidate.action == "click":
                    await page.mouse.click(coordinates.x, coordinates.y)

                elif candidate.action == "type" and candidate.type_text:
                    await page.mouse.click(coordinates.x, coordinates.y)
                    await page.keyboard.type(candidate.type_text)

                # If you want to wait *after each action*, do it here:
                await asyncio.sleep(wait_time / 1000)

            elif candidate.keyboard_action:
                # Keyboard-only action
                await page.keyboard.press(candidate.keyboard_action)
                feedback_metadata.append({
                    "action_id": task.action_id,
                    "description": task.description,
                    "candidate_id": candidate.candidate_id,
                    "keyboard_action": candidate.keyboard_action,
                    "expected_outcome": candidate.expected_outcome
                })

                # If you want to wait after keyboard actions, do it here:
                await asyncio.sleep(wait_time / 1000)



@app.post("/perform-actions")
async def perform_actions(
    payload: ActionPayload,
    wait_time: int,
    run_rerun_path: str,
    draw_no_action: bool = False,  # <-- New flag
    center_opacity: float = 0.2,
    mid_opacity: float=0.6,
    outer_opacity: float=0.1,
    border_thickness: float=2,
    diameter: int=20
) -> List[dict]:
    """
    Perform a series of actions on the page based on the provided payload.

    Args:
        payload (ActionPayload): Complex action payload containing tasks and candidates.
        wait_time (int): Time to wait between actions in milliseconds.
        run_rerun_path (str): Base path used for any potential screenshot.
        draw_no_action (bool): 
            - If True, only draw dots (no clicks), then take ONE final screenshot. 
            - If False, perform the real actions (clicks, typing, etc.) with NO screenshot.

    Returns:
        List[dict]: Feedback metadata for all performed actions.

    Raises:
        HTTPException: If Playwright session is not initialized or actions fail.
    """
    global playwright, browser, page
    logger.info("Starting perform-actions endpoint.")

    try:
        # 1. Ensure Playwright session and page readiness
        if not playwright or not browser or not page:
            logger.error("Playwright session not initialized.")
            raise HTTPException(
                status_code=503,
                detail="Playwright session not initialized"
            )

        logger.info("Ensuring page load state...")
        await ensure_load_state(page)
        logger.info("Page load state ensured.")

        feedback_metadata = []

        # 2. Process each action task
        for task in payload.action_tasks:
            logger.info(f"Processing task with action_id={task.action_id}")
            try:
                await perform_single_action(
                    page=page,
                    task=task,
                    feedback_metadata=feedback_metadata,
                    wait_time=wait_time,
                    run_rerun_path=run_rerun_path,
                    draw_no_action=draw_no_action,  # <--- Important
                    center_opacity=center_opacity,
                    mid_opacity=mid_opacity,
                    outer_opacity=outer_opacity,
                    border_thickness=border_thickness,
                    diameter=diameter
                )
            except Exception as e:
                logger.error(f"Failed to perform action for action_id={task.action_id}: {str(e)}")
                feedback_metadata.append({
                    "action_id": task.action_id,
                    "error": f"Failed to perform action: {str(e)}",
                    "description": task.description
                })

        # 3. If we are drawing dots (draw_no_action=True), 
        #    take ONE final screenshot after all dots are in place.
        if draw_no_action:
            # Example: "final_screenshot.png"
            final_screenshot_path = os.path.join(run_rerun_path, "dots", f"final_screenshot.png")
            logger.info(f"Taking ONE final screenshot of all dots: {final_screenshot_path}")
            await take_screenshot_internal(final_screenshot_path)

        logger.info("All actions processed successfully.")
        return feedback_metadata

    except Exception as e:
        logger.error(f"Failed to perform actions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform actions: {str(e)}"
        )



@app.post("/draw_dots")
async def draw_dots(elements: List[CoordinatePoint], diameter: int = 10, duration=3000, opacity: float = 0.8) -> JSONResponse:
    """
    Draws temporary dots at specified coordinates with configurable diameter and opacity.
    Includes timeout handling and better error management.
    """
    global playwright, browser, page
    logger.info("Starting draw_dots endpoint.")

    try:
        # Ensure Playwright session and page readiness
        if not playwright or not browser or not page:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Playwright session not initialized"
                }
            )

        # Use asyncio.wait_for to add timeout to ensure_load_state
        try:
            await asyncio.wait_for(
                ensure_load_state(page),
                timeout=5.0  # 5 second timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Page load state timeout, proceeding anyway")

        # Draw dots on the page with timeout protection
        for point in elements:
            try:
                await asyncio.wait_for(
                    retry_evaluate(page, '''({ x, y, diameter, opacity, duration }) => {
                        const dot = document.createElement('div');
                        Object.assign(dot.style, {
                            position: 'absolute',
                            left: `${x}px`,
                            top: `${y}px`,
                            width: `${diameter}px`,
                            height: `${diameter}px`,
                            backgroundColor: `rgba(0, 123, 255, ${opacity})`,
                            borderRadius: '50%',
                            pointerEvents: 'none',
                            zIndex: '999999',
                            transition: 'opacity 0.3s ease'
                        });
                        
                        document.body.appendChild(dot);
                        
                        // Add fade out effect
                        setTimeout(() => {
                            dot.style.opacity = '0';
                            setTimeout(() => dot.remove(), 300);
                        }, duration - 300);
                        
                        return true;
                    }''', {
                        'x': point.x,
                        'y': point.y,
                        'diameter': diameter,
                        'opacity': opacity,
                        'duration': duration
                    }),
                    timeout=2.0  # 2 second timeout per dot
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout drawing dot at ({point.x}, {point.y})")
                continue

        logger.info(f"Successfully drew {len(elements)} dots.")
        return JSONResponse(
            content={
                "status": "success",
                "message": "Dots drawn successfully",
                "count": len(elements)
            }
        )

    except Exception as e:
        logger.error(f"Failed to draw dots: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to draw dots: {str(e)}",
                "details": str(e)
            }
        )
    

@app.get("/extract_metadata")
async def extract_metadata(
    x: Optional[float] = None,
    y: Optional[float] = None,
    steps: int = 10,
    wait_per_step_ms: int = 500,
    overlap_percent: int = 10
) -> dict:
    """
    Scrolls down in steps until the bottom is reached or steps are exhausted.
    Then scrolls back to the top and extracts metadata.
    """
    global playwright, browser, page

    try:
        # 1) Get viewport height
        viewport_height = await page.evaluate("window.innerHeight")

        # Fraction of viewport to scroll each step
        overlap_fraction = 1 - (overlap_percent / 100.0)
        scroll_increment = viewport_height * overlap_fraction

        current_scroll_position = 0
        max_scroll_height = await page.evaluate(
            "document.documentElement.scrollHeight"
        )

        # 2) Scroll down in overlapping steps
        for step in range(steps):
            # Check if at or near the bottom
            if current_scroll_position + viewport_height >= max_scroll_height:
                print(f"Reached bottom of the page at step {step + 1}.")
                break

            # Scroll down
            current_scroll_position += scroll_increment
            await page.evaluate(f"window.scrollTo(0, {current_scroll_position})")
            await asyncio.sleep(wait_per_step_ms / 1000.0)

            # Update max_scroll_height dynamically (e.g., for infinite scrolling pages)
            max_scroll_height = await page.evaluate(
                "document.documentElement.scrollHeight"
            )

        # 3) Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1.0)

        # 4) Extract metadata
        from urllib.parse import urlparse  # if not already imported
        metadata = {
            "status": "success",
            "url_metadata": {
                "full_url": page.url,
                "scheme": urlparse(page.url).scheme,
                "domain": urlparse(page.url).hostname,
            },
            "dimensions": await retry_evaluate(page, '''() => ({
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                fullPage: {
                    width: Math.max(
                        document.documentElement.scrollWidth,
                        document.body.scrollWidth
                    ),
                    height: Math.max(
                        document.documentElement.scrollHeight,
                        document.body.scrollHeight
                    )
                },
                percentageViewable: 100
            })''')
        }

        # 5) Extract element info if coordinates provided
        if x is not None and y is not None:
            element_info = await retry_evaluate(
                page,
                '''({ x, y }) => {
                    const element = document.elementFromPoint(x, y);
                    if (!element) return null;

                    const rect = element.getBoundingClientRect();
                    return {
                        tagName: element.tagName,
                        id: element.id,
                        className: element.className,
                        innerText: element.innerText,
                        boundingBox: {
                            x: rect.left + window.scrollX,
                            y: rect.top + window.scrollY,
                            width: rect.width,
                            height: rect.height
                        }
                    };
                }''',
                {'x': x, 'y': y}
            )
            if element_info:
                metadata["element_info"] = element_info

        return metadata

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract metadata: {str(e)}"
        )


async def take_screenshot_internal(
    output_path: str,
    timeout: int = 60000
) -> None:
    """Internal function to take a screenshot for a specific chunk."""
    global page
    
    try:
        # Create the output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        

        # Take screenshot
        await page.screenshot(
            path=output_path,
            full_page=False,
            timeout=timeout
        )
    except Exception as e:
        logger.error(f"Error taking screenshot: {str(e)}")
        raise

from fastapi.responses import JSONResponse  # Add this import at the top
import os
import math
from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


#router = APIRouter()
@app.get("/screenshot")
async def screenshot(
    output_path: str,
    overlap_percentage: float = Query(30, ge=0, le=100,
                                      description="Overlap percentage between chunks"),
    max_chunks: int = 10,
    wait_after_scroll: int = 500,
    action_id: int = None,
    candidate_id: int = None,
    single_chunk_override_id: int = None
) -> JSONResponse:
    """
    Take viewport screenshots at specified heights. Parameters maintained for interface compatibility.
    """
    global playwright, browser, page
    start_time = datetime.now()
    logger.info(f"Starting screenshot process for viewport {single_chunk_override_id}")

    try:
        if not playwright or not browser or not page:
            return JSONResponse(
                status_code=503,
                content={"error": "Playwright session not initialized"}
            )

        os.makedirs(output_path, exist_ok=True)

        await ensure_load_state(page)
        
        # Get viewport dimensions
        dimensions = await retry_evaluate(page, '''async () => {
            return {
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                full: {
                    height: document.documentElement.scrollHeight,
                    width: document.documentElement.scrollWidth
                }
            };
        }''')

        viewport_height = dimensions['viewport']['height']
        viewport_width = dimensions['viewport']['width']
        full_height = dimensions['full']['height']
        full_width = dimensions['full']['width']

        filename = f"chunk_{single_chunk_override_id}.png"
        file_path = os.path.join(output_path, filename)

        try:
            await page.screenshot( # Take screenshot using Playwright API method for the page object. the page.screenshot 
                path=file_path,
                full_page=False,
                timeout=6000 # Timeout in milliseconds for the screenshot action
            )
            logger.info(f"Screenshot saved to {file_path}")
        except PlaywrightTimeoutError:
            logger.error(f"Screenshot timeout for viewport {single_chunk_override_id}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Screenshot timeout for viewport {single_chunk_override_id}"}
            )

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Screenshot completed in {duration:.3f} seconds")

        return JSONResponse(content={
            "status": "success",
            "message": "Viewport screenshot taken",
            "chunks": [{
                "chunk_number": 1,
                "file_path": file_path,
                "coordinates": {
                    "top": 0,
                    "bottom": viewport_height,
                    "left": 0,
                    "right": viewport_width
                },
                "dimensions": {
                    "height": viewport_height,
                    "width": viewport_width,
                    "is_last_chunk": True
                },
                "scroll_position": 0
            }],
            "num_chunks": 1,
            "overlap_percentage": overlap_percentage,
            "page_dimensions": {
                "viewport_height": viewport_height,
                "viewport_width": viewport_width,
                "full_height": full_height,
                "full_width": full_width,
                "chunk_height": viewport_height,
                "overlap_height": 0
            },
            "duration_seconds": duration
        })

    except Exception as e:
        logger.error(f"Error during screenshot process: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Screenshot error: {str(e)}", "details": str(e)}
        )


@app.post("/resize-window")
async def resize_window(
    width: int = Query(gt=0, lt=10000),
    height: int = Query(gt=0, lt=80000)
) -> JSONResponse:
    """
    Resize the browser window and viewport to specified dimensions.
    
    Args:
        width: Desired window width (1-9999 pixels)
        height: Desired window height (1-9999 pixels)
        
    Returns:
        JSONResponse: Status and new window dimensions
    """
    global page
    
    try:
        if not page:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "Page not initialized"
                }
            )

        context = page.context
        
        # Create and manage CDP session
        session = await context.new_cdp_session(page)
        try:
            # Get window info
            window_info = await session.send('Browser.getWindowForTarget')
            
            if not window_info or 'windowId' not in window_info:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": "Failed to get window information"
                    }
                )
            
            # Resize window
            await session.send('Browser.setWindowBounds', {
                'windowId': window_info['windowId'],
                'bounds': {
                    'width': width,
                    'height': height
                }
            })
            
            # Set viewport size
            await page.set_viewport_size({"width": width, "height": height})
            
            # Verify the new size
            viewport_size = await retry_evaluate(page, '''() => ({
                width: window.innerWidth,
                height: window.innerHeight,
                windowWidth: window.outerWidth,
                windowHeight: window.outerHeight
            })''')
            
            # Check for significant size mismatch
            width_diff = abs(viewport_size['width'] - width)
            height_diff = abs(viewport_size['height'] - height)
            
            if width_diff > 100 or height_diff > 100:
                return JSONResponse(content={
                    "success": False,
                    "new_size": viewport_size,
                    "message": "Warning: Actual size differs significantly from requested size"
                })

            return JSONResponse(content={
                "success": True,
                "new_size": viewport_size,
                "message": f"Window resized to {viewport_size['width']}x{viewport_size['height']}"
            })

        finally:
            await session.detach()
                
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in resize_window: {error_msg}")
        
        if "Browser.getWindowForTarget" in error_msg:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "Failed to get browser window. Ensure browser is running in non-headless mode."
                }
            )
        elif "Browser.setWindowBounds" in error_msg:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Failed to resize window: {error_msg}"
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"Unexpected error: {error_msg}"
                }
            )


from fastapi.responses import JSONResponse

@app.get("/check-stability")
async def check_stability(timeout_ms: int = 1000,window_size_ms: int = 100):
    """
    Check if the page is stable by monitoring network and DOM activity over short windows.
    """
    global page
    start_time = datetime.now()
    
    try:
        stability_checks = {
            "network_idle": False,
            "no_animations": False,
            "dom_stable": False
        }

        # We'll check in 100ms windows, up to the timeout
        window_size_ms = window_size_ms
        max_attempts = timeout_ms // window_size_ms

        for attempt in range(max_attempts):
            if (datetime.now() - start_time).total_seconds() * 1000 >= timeout_ms:
                break

            # Monitor both requests and responses
            active_requests = set()
            finished_requests = set()
            
            def on_request(request):
                active_requests.add(request)
            
            def on_response(response):
                if response.request in active_requests:
                    active_requests.remove(response.request)
                    finished_requests.add(response.request)
                    
            def on_request_failed(request):
                if request in active_requests:
                    active_requests.remove(request)
                    finished_requests.add(request)
            
            page.on("request", on_request)
            page.on("response", on_response)
            page.on("requestfailed", on_request_failed)

            try:
                # Monitor DOM changes
                dom_changes = await retry_evaluate(page, f'''async () => {{
                    let changes = 0;
                    const observer = new MutationObserver(() => changes++);
                    
                    observer.observe(document.body, {{
                        childList: true,
                        subtree: true,
                        attributes: true
                    }});
                    
                    await new Promise(resolve => setTimeout(resolve, {window_size_ms}));
                    observer.disconnect();
                    return changes;
                }}''')

                # More precise animation check
                animations_running = await retry_evaluate(page, '''() => {
                    const animations = document.getAnimations();
                    if (animations.length === 0) return 0;
                    
                    return animations.filter(animation => {
                        // Skip if not actually animating
                        if (animation.playState !== 'running') return false;
                        if (!animation.effect) return false;
                        
                        const timing = animation.effect.getComputedTiming();
                        // Skip if effectively complete
                        if (timing.progress === null || timing.progress === 1) return false;
                        
                        // Check if animation target is visible
                        if (animation.effect.target) {
                            const style = window.getComputedStyle(animation.effect.target);
                            if (style.display === 'none' || 
                                style.visibility === 'hidden' || 
                                parseFloat(style.opacity) === 0) {
                                return false;
                            }
                        }
                        
                        return true;
                    }).length;
                }''')

                # Update stability checks - consider network idle only if no active requests
                stability_checks["network_idle"] = len(active_requests) == 0
                
                # Log network activity for debugging
                if len(active_requests) > 0:
                    logger.debug(f"Active requests: {len(active_requests)}, Finished: {len(finished_requests)}")
                stability_checks["no_animations"] = animations_running == 0
                stability_checks["dom_stable"] = dom_changes < 2

                # If all checks pass, page is stable
                if all(stability_checks.values()):
                    elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    return JSONResponse(content={
                        "is_stable": True,
                        "checks": stability_checks,
                        "message": f"Page stable after {attempt + 1} checks",
                        "elapsed_ms": elapsed_ms
                    })

            finally:
                # Clean up all listeners
                page.remove_listener("request", on_request)
                page.remove_listener("response", on_response)
                page.remove_listener("requestfailed", on_request_failed)

            # Small delay before next check
            await asyncio.sleep(window_size_ms / 1000)

        # If we get here, we hit the timeout
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return JSONResponse(content={
            "is_stable": False,
            "checks": stability_checks,
            "message": "Timeout reached before stability achieved",
            "elapsed_ms": elapsed_ms
        })

    except Exception as e:
        logger.error(f"Error checking stability: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "message": "Failed to check page stability"
            }
        )


@app.get("/show_message")
async def show_message(
    message: str,
    duration: int = 3000,
    font_size: int = 16,
    background_opacity: float = 0.8,
    font_color: str = "#FFFFFF"
):
    """Display a message across the top of the browser viewport."""
    try:
        await page.wait_for_load_state("load")

        await retry_evaluate(page, """
            ({ message, duration, fontSize, backgroundOpacity, fontColor }) => {
                const existingMessage = document.getElementById('custom-message-banner');
                if (existingMessage) existingMessage.remove();

                const banner = document.createElement('div');
                banner.id = 'custom-message-banner';
                banner.innerText = message;
                
                Object.assign(banner.style, {
                    position: 'fixed',
                    top: '0',
                    left: '0',
                    width: '100%',
                    padding: '10px',
                    backgroundColor: `rgba(0, 0, 0, ${backgroundOpacity})`,
                    color: fontColor,
                    fontSize: `${fontSize}px`,
                    textAlign: 'center',
                    zIndex: '999999',
                    pointerEvents: 'none',
                    transition: 'opacity 0.5s ease'
                });

                document.body.appendChild(banner);

                setTimeout(() => {
                    banner.style.opacity = '0';
                    setTimeout(() => banner.remove(), 500);
                }, duration);
            }
        """, {
            'message': message,
            'duration': duration,
            'fontSize': font_size,
            'backgroundOpacity': background_opacity,
            'fontColor': font_color
        })
        
        return {"status": "Message displayed", "message": message, "duration": duration}
    except Exception as e:
        return {"error": str(e)}

async def watch_for_changes():
    """Watch for file changes and trigger server restart."""
    async for changes in awatch('fastAPIServ.py'):
        print("File changes detected. Restarting server...")
        os._exit(3)  # Exit code 3 triggers uvicorn to reload

async def start_server():
    """Start the server with the file watcher."""
    config = uvicorn.Config(
        "fastAPIServ:app",
        host="0.0.0.0",
        port=8000,
        loop="asyncio",
        reload=True,
        reload_delay=0.25,
    )
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        watch_for_changes(),
        server.serve()
    )


# Google OAuth 2.0 client information (replace with your details)
CLIENT_ID = "899752177953-4l5gj26h6d4i7at284ek2jfbh6j1vg4p.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://127.0.0.1:8000/google-auth/callback"
TOKEN_URL = "https://oauth2.googleapis.com/token"

@app.get("/google-auth/callback")
async def auth_callback(request: Request):
    # Extract the authorization code from the query parameters
    code = request.query_params.get("code")
    if not code:
        return {"error": "Authorization code not found"}

    # Exchange the authorization code for tokens
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    response = requests.post(TOKEN_URL, data=data)

    if response.status_code == 200:
        tokens = response.json()
        # Save tokens (e.g., access_token, refresh_token) securely
        with open("google_tokens.json", "w") as token_file:
            json.dump(tokens, token_file)
        return {"message": "Tokens received and saved successfully", "tokens": tokens}
    else:
        return {"error": "Failed to retrieve tokens", "details": response.json()}



# Path to your existing JSON file
JSON_FILE_PATH = Path("sms_records.json")

# Ensure the JSON file exists and initialize it as an empty list if it's not already present
if not JSON_FILE_PATH.exists():
    JSON_FILE_PATH.write_text("[]")


@app.post("/sms")
async def receive_sms(
    From: str = Form(...),  # Sender's phone number
    To: str = Form(...),    # Your Twilio phone number
    Body: str = Form(...),  # The SMS content
    MessageSid: str = Form(...),  # Unique ID for the message
):
    try:
        # Create a new record
        new_record = {
            "From": From,
            "To": To,
            "Body": Body,
            "MessageSid": MessageSid,
        }

        # Load the existing JSON data
        with JSON_FILE_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)

        # Append the new record
        data.append(new_record)

        # Save the updated data back to the JSON file
        with JSON_FILE_PATH.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        # Return a 204 No Content response to Twilio (no automatic reply)
        return JSONResponse(status_code=204)

    except Exception as e:
        # Log and return an error response if something goes wrong
        raise HTTPException(status_code=500, detail=f"Error saving SMS: {str(e)}")


@app.get("/sms-records")
async def get_sms_records():
    """Endpoint to retrieve all stored SMS records for debugging or monitoring."""
    with JSON_FILE_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data


if __name__ == "__main__":
    asyncio.run(start_server())