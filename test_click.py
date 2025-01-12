from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        # 1. Connect to existing Chrome on 127.0.0.1:9223
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9223")
        except Exception as ex:
            print("ERROR: Could not connect to Chrome at 127.0.0.1:9223.")
            print("Make sure Chrome is running with: ")
            print('"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9223')
            raise ex

        print("Connected to existing Chrome session.")

        # Keep track of pages we've already attached listeners to
        known_pages = set()

        def attach_listeners_to_page(page):
            """Attach request listener(s) to a single page."""
            def on_request(request):
                # Print the request URL and the current page URL
                print(f"[REQUEST on {page.url}] {request.method} {request.url}")

            page.on("request", on_request)
            print(f"Attached request listener to page: {page.url}")

        print("Monitoring all existing pages, and will detect new ones. (Ctrl+C to stop)")

        # 2. Infinite loop: check for new contexts/pages every second
        while True:
            # For each context in the browser
            for context in browser.contexts:
                # For each page in that context
                for page in context.pages:
                    if page not in known_pages:
                        known_pages.add(page)
                        attach_listeners_to_page(page)

            # Sleep briefly, then check again
            time.sleep(1)


if __name__ == "__main__":
    main()
