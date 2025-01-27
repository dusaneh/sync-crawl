# Web Application Workflow Automation

A Python-based system for automating web application workflows and generating documentation through intelligent UI analysis and interaction.

## Overview

This project provides a framework for automating web application interactions by analyzing UI states and performing actions in a way that mimics natural user behavior. The system uses Playwright for browser automation and Claude AI for intelligent decision-making about UI interactions.

Key features:
- Automated UI element detection and interaction
- Intelligent workflow navigation
- Screenshot capture and analysis
- Hierarchical logging system
- Coordinate validation and adjustment
- Support for complex multi-step workflows

## System Components

### Core Components:
- `crawl.ipynb`: Main Jupyter notebook for executing workflow automation
- `fastAPIServ.py`: FastAPI server handling browser automation via Playwright
- `helper.py`: Core utility functions and AI integration
- `hlogger.py`: Hierarchical logging system
- `log_config.py`: Logging configuration

## Setup

### Prerequisites
- Python 3.12+
- Google Chrome browser
- Required Python packages (install via pip):
  ```
  fastapi
  playwright
  uvicorn
  watchfiles
  Pillow
  cairo
  anthropic
  google-generativeai
  ```

### Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install
```

## Usage

### Starting the System

1. Start Chrome in debugging mode:
```bash
# On Windows:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="C:\my-chrome-profile"

# On Mac:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9223 --user-data-dir="~/chrome-debug-profile"
```

2. Start the FastAPI server:
```bash
python fastAPIServ.py
```

3. Open `crawl.ipynb` in Jupyter and execute the workflow cells

### Configuration

Key configuration options are available in the notebook:
- `client`: Target application identifier
- `workflow_id`: Unique identifier for the workflow
- `workflow_instructions`: Specific instructions for the workflow
- `site_wide_instructions`: General guidelines for site navigation
- `client_url`: Starting URL for the workflow

### Logging

The system uses a hierarchical logging structure:
```
client_folder/
├── workflow_id/
│   ├── sample_id/
│   │   ├── rerun_id/
│   │   │   ├── run_id/
│   │   │   │   ├── run_retry_id/
│   │   │   │   │   ├── dots/
│   │   │   │   │   ├── temp/
│   │   │   │   │   ├── highlights/
│   │   │   │   │   └── chunks/
```

## Features

### Intelligent UI Analysis
- Element detection and classification
- Context-aware decision making
- Natural interaction patterns

### Screenshot Management
- Automated screenshot capture
- Visual element highlighting
- Coordinate validation

### Error Handling
- Automatic retry mechanisms
- Detailed error logging
- State recovery

### Logging and Documentation
- Hierarchical logging structure
- Detailed action tracking
- Process documentation

## API Reference

### FastAPI Endpoints

- `/navigate`: Navigate to a specific URL
- `/screenshot`: Capture page screenshots
- `/extract_metadata`: Extract page metadata
- `/perform-actions`: Execute UI actions
- `/resize-window`: Adjust browser window size
- `/draw_dots`: Visualize interaction points
- `/check-stability`: Monitor page stability

### Helper Functions

Key utility functions in `helper.py`:
- `analyze_page_actions()`: Analyze UI elements and determine actions
- `perform_llm_analysis()`: AI-powered workflow analysis
- `draw_with_cairo()`: Visualization utilities
- `resize_and_crop()`: Image processing utilities

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

[Insert chosen license information]

## Support

For support, please open an issue in the GitHub repository.