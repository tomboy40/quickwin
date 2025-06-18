# Configuration Migration: From dotenv to configparser

## Overview

This project has been migrated from using `python-dotenv` to Python's built-in `configparser` module to minimize third-party dependencies while maintaining backward compatibility.

## Changes Made

### Files Modified
- `http-request.py`
- `snow-v3.py` 
- `snow.py`

### Key Changes
1. Removed `from dotenv import load_dotenv` imports
2. Added `import configparser` imports
3. Added `load_config_file()` function to each script
4. Modified `get_config()` functions to read from config files first, then environment variables

## Configuration Priority

The new configuration loading follows this priority order:
1. **Command-line arguments** (highest priority, for supported options)
2. **Config file values** (config.ini, .env.ini, or settings.ini)
3. **Environment variables** (lowest priority, backward compatibility)

## Configuration File Format

### New Format (config.ini)
```ini
[proxy]
host = proxy.example.com
user = your_proxy_username
pass = your_proxy_password

[api]
report_url = https://api.example.com/report

[snow]
proxy_user = your_proxy_username
proxy_pass = your_proxy_password
proxy_host = proxy.example.com
user_email = your_email@example.com
user_password = your_password
homepage_url = https://your-instance.service-now.com
saml_acs_url = https://your-instance.service-now.com/navpage.do
report_url = https://your-instance.service-now.com/api/now/table/incident
report_request_payload = {"short_description": "Test incident"}
referer = https://your-instance.service-now.com
x_user_token = your_user_token

[ssl]
disable_warnings = true
verify = false
```

### Old Format (.env) - Still Supported
```bash
# Proxy Configuration
PROXY_HOST=proxy.example.com
PROXY_USER=your_proxy_username
PROXY_PASS=your_proxy_password

# Target URL for requests
REPORT_URL=https://api.example.com/report
```

## Migration Steps

1. **Copy the example config file:**
   ```bash
   cp config.ini.example config.ini
   ```

2. **Fill in your actual values in config.ini**

3. **Optional: Keep your existing .env file for backward compatibility**

## Supported Config Files

The scripts will automatically look for configuration files in this order:
1. `config.ini`
2. `.env.ini`
3. `settings.ini`

## Benefits

- **Reduced Dependencies**: No longer requires `python-dotenv` package
- **Better Organization**: INI format allows logical grouping of settings
- **Backward Compatibility**: Environment variables still work as fallback
- **Built-in Support**: Uses Python's standard library `configparser`

## Usage Examples

### Using config file only:
```bash
python http-request.py
python snow-v3.py
```

### Using command-line arguments (overrides config file):
```bash
python http-request.py --proxy-user myuser --proxy-pass mypass
python snow-v3.py --proxy-user myuser --proxy-pass mypass
```

### Using environment variables (fallback):
```bash
export PROXY_USER=myuser
export PROXY_PASS=mypass
python http-request.py
```

## Troubleshooting

- If no config file is found, the scripts will fall back to environment variables
- Check that your config.ini file is in the same directory as the scripts
- Ensure proper INI file syntax (no quotes around values unless needed)
- Use the `[section]` headers as shown in the examples