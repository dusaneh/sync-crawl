# Sync-crawl

A Python-based intelligent web crawler for workflow automation and documentation generation through UI analysis and interaction.

## Overview

Sync-crawl provides a framework for automating web application interactions by analyzing UI states and performing actions in a way that mimics natural user behavior. The system uses Playwright for browser automation and Claude AI for intelligent decision-making about UI interactions.

## Documentation

- [Installation Guide](docs/installation.md)
- [Architecture Overview](docs/architecture.md)
- [Configuration Guide](docs/configuration.md)
- [API Reference](docs/api.md)

## Quick Start

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