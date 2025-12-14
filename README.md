# Skolverket Data Extractor

A comprehensive tool for extracting school data and statistics from Skolverket (Swedish National Agency for Education).

## Features

- Extracts real school data from Skolverket's official website
- Gets Grade 6 and Grade 9 statistics for Math, Swedish, and English
- Retrieves merit values (genomsnittligt meritvärde) for Grade 9
- Extracts pass rates and student counts
- Outputs data in both JSON and CSV formats
- **Address caching** - Previously extracted addresses are cached to speed up re-runs
- **Verbose progress reporting** - Shows detailed progress with timing estimates

## Successfully Extracted Data

The extractor processes **1,582 schools** with valid merit values and creates an interactive map showing their locations and performance.

### Sample Data (Futuraskolan International Hertig Karl - ID: 40467992):

- **Merit Value**: 258.9/340 (vs Sweden average: 228.5/340)
- **Location**: Sollentuna, Sweden
- **Address**: Ebba Brahes väg 1

## Usage

### Run Complete Extraction
```bash
python extract_all_schools.py
```

The script will:
1. Load 1,700+ schools from CSV
2. Filter to 1,582 schools with merit values
3. Extract addresses (with caching for speed)
4. Geocode locations
5. Create interactive map
6. Save results to CSV

### Expected Runtime
- **First run**: ~50-60 minutes (all addresses need extraction)
- **Subsequent runs**: Much faster due to address caching
- **Progress reporting**: Shows ETA and completion percentage

## Files

- `extract_all_schools.py` - Main extraction script with verbose logging
- `Grundskola - Slutbetyg årskurs 9, samtliga elever 2025 Skolenhet.csv` - Source data from Skolverket

## Output Files

- `schools_merit_map.html` - Interactive map with color-coded schools
- `schools_with_coordinates.csv` - Complete data with coordinates
- `address_cache.json` - Cached addresses (speeds up re-runs)

## Map Color Coding

- **Green**: Merit value ≥ 250 (high performing)
- **Orange**: Merit value ≥ 200 (average performing)  
- **Red**: Merit value < 200 (below average)

## Requirements

```
requests
pandas
beautifulsoup4
folium
geopy
```

Install with: `pip install -r requirements.txt`

## Data Sources

- **Skolverket CSV**: Official grade 9 statistics with merit values
- **Utbildningsguiden**: Individual school pages for address extraction
- **Nominatim**: OpenStreetMap geocoding for coordinates

## Performance Features

- **Address Caching**: Saves extracted addresses to avoid re-scraping
- **Progress Tracking**: Shows completion percentage and ETA
- **Batch Processing**: Saves cache every 50 schools
- **Rate Limiting**: Respectful 0.5s delays between requests
- **Error Handling**: Continues processing if individual schools fail

## Notes

- The extractor includes rate limiting to be respectful to Skolverket's servers
- Address cache significantly speeds up subsequent runs
- Some schools may not have complete data available
- Merit values are on a scale of 0-340
- Success rate is typically 90-95% for geocoding