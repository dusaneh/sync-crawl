
# Sync-crawl

Sync-crawl is an intelligent web automation framework that combines browser automation with AI-powered decision making to create reliable, maintainable web workflows. Unlike traditional web scrapers or automation tools, Sync-crawl understands UI context and user interaction patterns, making it ideal for complex web applications where static selectors and rigid automation scripts often fail.

## Overview

Sync-crawl provides a framework for automating web application interactions by analyzing UI states and performing actions in a way that mimics natural user behavior. The system uses Playwright for browser automation and Claude AI for intelligent decision-making about UI interactions.

## Key Features

### 🧠 Intelligent UI Understanding
- AI-powered element detection and classification
- Context-aware decision making that mimics human navigation patterns
- Dynamic adjustment to UI changes and varying page states

### 🔄 Robust Workflow Execution
- Self-healing automation that adapts to UI changes
- Intelligent retry mechanisms with state awareness
- Coordinate validation and precise element targeting
- Visual verification of interactions

### 📊 Comprehensive Documentation Generation
- Automatic capture of workflow steps and decisions
- Visual documentation with annotated screenshots
- Hierarchical logging of process states and outcomes
- Detailed interaction analysis for debugging

### 🛠 Enterprise-Ready Architecture
- Modular design for easy integration and extension
- Support for complex multi-step workflows
- Built-in error recovery and state management
- Detailed logging and monitoring capabilities

## Perfect For

- **Quality Assurance Teams**: Automate complex test scenarios with human-like interaction patterns
- **Process Documentation**: Generate comprehensive guides with visual elements and detailed steps
- **UI/UX Research**: Analyze user journeys and interaction patterns systematically
- **Training Material Creation**: Automatically generate visual tutorials and workflow documentation
- **Application Analysis**: Understand and document complex web application behaviors

## What Sets Sync-crawl Apart

Unlike traditional automation tools, Sync-crawl:

- **Understands Context**: Makes intelligent decisions based on full page context, not just individual elements
- **Adapts Dynamically**: Adjusts to UI changes and varying page states automatically
- **Documents Everything**: Creates comprehensive visual and textual documentation of all processes
- **Learns and Improves**: Uses AI to refine interaction patterns and improve reliability
- **Validates Visually**: Ensures accuracy through visual validation and coordinate precision
- **Maintains State**: Tracks and manages complex workflow states for reliable execution

Whether you're automating complex workflows, generating documentation, or analyzing web applications, Sync-crawl provides the intelligence and reliability needed for modern web automation challenges.

## Documentation

- [Installation Guide](docs/installation.md)
- [Architecture Overview](docs/architecture.md)
- [Configuration Guide](docs/configuration.md)
- [API Reference](docs/api.md)
- [Development](docs/development.md)

## Quick Start

0. Create Claude and Gemini API key file as "keys.py" in the root dir and include:
```bash
GOOGLE_API_KEY='your google gemini key here'
claude_key="your claude key here"
```

1. Clone the repository:
```bash
git clone [repository-url]
cd sync-crawl
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install
```

5. Start Chrome in debugging mode:
```bash
# On Windows:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="C:\my-chrome-profile"

# On Mac:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9223 --user-data-dir="~/chrome-debug-profile"
```

6. Start the FastAPI server:
```bash
python fastAPIServ.py
```

7. Open `crawl.ipynb` in Jupyter and follow the notebook instructions

## Features

- 🤖 Intelligent UI Analysis & Navigation
- 📸 Automated Screenshot Capture & Analysis
- 🔄 Workflow State Management
- 📝 Hierarchical Logging System
- 🎯 Precise Coordinate Validation
- 🔍 Visual Element Detection
- 📊 Process Documentation Generation

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support:
1. Check the documentation in the `docs` folder
2. Open an issue in the GitHub repository
3. Contact the development team

## Acknowledgments

- Anthropic's Claude for AI capabilities
- Microsoft Playwright for browser automation
- FastAPI for the server framework