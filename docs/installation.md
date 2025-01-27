# Installation Guide

## System Requirements

- Python 3.12 or higher
- Google Chrome browser
- At least 4GB RAM
- 1GB free disk space
- Operating System:
  - Windows 10 or higher
  - macOS 10.15 or higher
  - Ubuntu 20.04 or higher

## Dependencies

All dependencies are listed in `requirements.txt`:

```plaintext
fastapi>=0.109.0
uvicorn>=0.27.0
watchfiles>=0.21.0
playwright>=1.41.0
Pillar>=10.2.0
pycairo>=1.25.1
anthropic>=0.7.0
google-generativeai>=0.3.0
python-multipart>=0.0.9
requests>=2.31.0
```

## Detailed Installation Steps

1. **Create a Virtual Environment**
   ```bash
   python -m venv .venv
   ```

2. **Activate the Virtual Environment**
   ```bash
   # Windows
   .venv\Scripts\activate
   
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright Browsers**
   ```bash
   playwright install
   ```

5. **Configure API Keys**
   
   Create a `keys.py` file in the root directory:
   ```python
   GOOGLE_API_KEY = "your_google_api_key"
   claude_key = "your_claude_api_key"
   ```

6. **Verify Installation**
   ```bash
   python -c "import playwright; print(playwright.__version__)"
   python -c "import anthropic; print(anthropic.__version__)"
   ```

## Troubleshooting

### Common Issues

1. **Playwright Installation Failures**
   ```bash
   # Try running with administrative privileges
   sudo playwright install
   
   # Or install browsers manually
   playwright install chromium
   playwright install firefox
   ```

2. **Cairo Installation Issues**
   - Windows: Install GTK3 runtime
   - Ubuntu: `sudo apt-get install libcairo2-dev`
   - macOS: `brew install cairo`

3. **Chrome Debug Port Issues**
   - Ensure no other processes are using port 9223
   - Check firewall settings
   - Verify Chrome installation path

### Environment Variables

Required environment variables:
```bash
PYTHONPATH=.
CHROME_DEBUG_PORT=9223
```

## Post-Installation Setup

1. **Create Required Directories**
   ```bash
   mkdir -p clients
   mkdir -p logs
   ```

2. **Configure Logging**
   ```bash
   # Verify log file permissions
   touch app.log
   chmod 666 app.log
   ```

3. **Test Browser Connection**
   ```bash
   # Start the FastAPI server
   python fastAPIServ.py
   
   # In another terminal, test the connection
   curl http://localhost:8000/health
   ```

## Security Considerations

1. **API Keys**
   - Store API keys securely
   - Use environment variables in production
   - Don't commit keys.py to version control

2. **Browser Profile**
   - Use a separate Chrome profile for automation
   - Don't use your main browser profile
   - Regularly clear automation profile data

3. **Network Access**
   - Configure firewall rules for port 9223
   - Limit access to localhost only
   - Use HTTPS for external connections