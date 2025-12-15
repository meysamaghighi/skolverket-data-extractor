# Google Maps API Setup Instructions

## 1. Get Google Maps API Key

### Step 1: Go to Google Cloud Console
- Visit: https://console.cloud.google.com/
- Sign in with your Google account

### Step 2: Create or Select Project
- Click "Select a project" at the top
- Either create a new project or select existing one
- Name it something like "Skolverket-Geocoding"

### Step 3: Enable Geocoding API
- Go to "APIs & Services" > "Library"
- Search for "Geocoding API"
- Click on it and press "ENABLE"

### Step 4: Create API Key
- Go to "APIs & Services" > "Credentials"
- Click "CREATE CREDENTIALS" > "API key"
- Copy the generated API key (starts with "AIza...")

### Step 5: Restrict API Key (Optional but Recommended)
- Click on your new API key to edit it
- Under "API restrictions", select "Restrict key"
- Choose "Geocoding API" from the list
- Save

## 2. Save API Key to File

Create a file named `google_maps_api_key.txt` in your project folder:

```
AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**IMPORTANT**: 
- Replace with your actual API key
- Keep this file private (don't commit to Git)
- The file should contain ONLY the API key, no extra text

## 3. Install Required Package

```bash
pip install googlemaps
```

## 4. Run the Google Maps Version

```bash
python extract_all_schools_googlemaps.py
```

## Cost Estimate

- **Geocoding API**: $5 per 1,000 requests
- **Your 100 schools**: ~$0.50 (first 200/day are free)
- **All 1,582 schools**: ~$8 (if processing all)

## Rate Limits

- **Google Maps**: 50 requests/second (much faster than Nominatim)
- **Expected speed**: 100 schools in ~30 seconds vs 30+ minutes with Nominatim

## Backup Files

- `extract_all_schools_nominatim_backup.py` - Your original working code
- `extract_all_schools_googlemaps.py` - New Google Maps version
- Both use the same cache files, so you can switch between them