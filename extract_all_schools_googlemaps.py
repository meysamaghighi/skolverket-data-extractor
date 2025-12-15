import pandas as pd
import folium
import requests
import googlemaps
import time
import re
from bs4 import BeautifulSoup
import json
import os
import argparse

class SchoolMapper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Load Google Maps API key
        api_key = self.load_api_key()
        if not api_key:
            raise ValueError("Google Maps API key not found. Please create 'google_maps_api_key.txt' file with your API key.")
        
        self.gmaps = googlemaps.Client(key=api_key)
        self.address_cache = self.load_address_cache()
        self.coord_cache = self.load_coord_cache()
    
    def load_api_key(self):
        """Load Google Maps API key from file"""
        try:
            with open('google_maps_api_key.txt', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
        
    def load_address_cache(self):
        """Load previously extracted addresses"""
        if os.path.exists('address_cache.json'):
            with open('address_cache.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_address_cache(self):
        """Save address cache to file"""
        with open('address_cache.json', 'w', encoding='utf-8') as f:
            json.dump(self.address_cache, f, indent=2, ensure_ascii=False)
    
    def load_coord_cache(self):
        """Load previously geocoded coordinates"""
        if os.path.exists('coord_cache.json'):
            with open('coord_cache.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_coord_cache(self):
        """Save coordinate cache to file"""
        with open('coord_cache.json', 'w', encoding='utf-8') as f:
            json.dump(self.coord_cache, f, indent=2, ensure_ascii=False)
    
    def get_school_address(self, school_id):
        """Extract address from school page with caching"""
        # Check cache first
        if school_id in self.address_cache:
            return self.address_cache[school_id]
        
        url = f"https://utbildningsguiden.skolverket.se/skolenhet?schoolUnitID={school_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text()
                
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if line.strip() == 'Adress' and i + 1 < len(lines):
                        address_line = lines[i + 1].strip()
                        if address_line and len(address_line) > 3:
                            # Cache the result
                            self.address_cache[school_id] = address_line
                            return address_line
                
                # Fallback pattern
                address_match = re.search(r'Adress:?\s*([^\n]+)', text)
                if address_match:
                    address = address_match.group(1).strip()
                    self.address_cache[school_id] = address
                    return address
            
            # Cache negative result
            self.address_cache[school_id] = None
            return None
        except:
            self.address_cache[school_id] = None
            return None
    
    def geocode_address(self, address, municipality):
        """Get coordinates using Google Maps API with caching"""
        # Create cache key
        cache_key = f"{address or 'None'}|{municipality}"
        
        # Check coordinate cache first
        if cache_key in self.coord_cache:
            cached_coords = self.coord_cache[cache_key]
            if cached_coords:  # Not None
                return cached_coords[0], cached_coords[1]
            else:
                return None  # Previously failed
        
        # Try multiple address formats
        if address:
            search_addresses = [
                f"{address}, {municipality}, Sweden",
                f"{address}, Sweden",
                f"{municipality}, Sweden"  # Fallback to municipality
            ]
        else:
            search_addresses = [f"{municipality}, Sweden"]
        
        for search_addr in search_addresses:
            try:
                result = self.gmaps.geocode(search_addr)
                if result:
                    location = result[0]['geometry']['location']
                    coords = [location['lat'], location['lng']]
                    self.coord_cache[cache_key] = coords
                    return coords[0], coords[1]
            except Exception as e:
                print(f"            Google Maps API error: {e}")
                continue
        
        # Cache negative result
        self.coord_cache[cache_key] = None
        return None
def create_map_from_cache():
    """Create map using only cached data without querying addresses"""
    print("=" * 60)
    print("SKOLVERKET MAP GENERATOR - CACHE-ONLY MODE")
    print("=" * 60)
    
    # Read CSV
    print("\n[1/4] Reading school data from CSV...")
    df = pd.read_csv('Grundskola - Slutbetyg årskurs 9, samtliga elever 2025 Skolenhet.csv', 
                     sep=';', skiprows=5)
    
    # Process merit values
    df = df.dropna(subset=['Skol-enhetskod'])
    df['merit_clean'] = df['Genomsnittligt meritvärde (17 ämnen)'].astype(str).str.replace(',', '.')
    df['merit_value'] = pd.to_numeric(df['merit_clean'], errors='coerce')
    schools_with_merit = df[df['merit_value'].notna()].copy()
    schools_with_merit = schools_with_merit.sort_values('merit_value', ascending=False)
    
    print(f"      Processing ALL {len(schools_with_merit)} schools with merit values")
    
    # Load caches
    print("\n[2/4] Loading cached data...")
    mapper = SchoolMapper()
    address_count = len(mapper.address_cache)
    coord_count = len([v for v in mapper.coord_cache.values() if v is not None])
    print(f"      Found {address_count} cached addresses")
    print(f"      Found {coord_count} cached coordinates")
    
    # Process schools using cache only
    print("\n[3/4] Processing schools from cache...")
    school_data = []
    
    for _, row in schools_with_merit.iterrows():
        school_id = str(row['Skol-enhetskod'])
        school_name = row['Skola']
        municipality = row['Skolkommun']
        merit_value = row['merit_value']
        
        # Get cached address
        address = mapper.address_cache.get(school_id)
        if not address:
            continue
            
        # Get cached coordinates
        cache_key = f"{address}|{municipality}"
        cached_coords = mapper.coord_cache.get(cache_key)
        if not cached_coords:
            continue
            
        school_data.append({
            'school_id': school_id,
            'school_name': school_name,
            'municipality': municipality,
            'address': address,
            'merit_value': merit_value,
            'latitude': cached_coords[0],
            'longitude': cached_coords[1]
        })
    
    print(f"      Successfully loaded {len(school_data)} schools from cache")
    
    # Create map with color spectrum
    print("\n[4/4] Creating map with color spectrum...")
    m = folium.Map(location=[62.0, 15.0], zoom_start=5)
    
    # Calculate merit value range for color mapping
    df_schools = pd.DataFrame(school_data)
    min_merit = df_schools['merit_value'].min()
    max_merit = df_schools['merit_value'].max()
    print(f"      Merit range: {min_merit:.1f} - {max_merit:.1f}")
    
    def get_color(merit_value):
        """Map merit value to 10-level color spectrum from red to blue"""
        # Normalize merit value to 0-1 range
        normalized = (merit_value - min_merit) / (max_merit - min_merit)
        
        # 10 color levels from red (lowest) to blue (highest)
        colors = [
            '#FF0000',  # 0-10%: Deep Red
            '#FF4000',  # 10-20%: Red-Orange
            '#FF8000',  # 20-30%: Orange
            '#FFB000',  # 30-40%: Orange-Yellow
            '#FFD700',  # 40-50%: Yellow
            '#B8FF00',  # 50-60%: Yellow-Green
            '#80FF00',  # 60-70%: Light Green
            '#00FF80',  # 70-80%: Green-Cyan
            '#0080FF',  # 80-90%: Light Blue
            '#0040FF'   # 90-100%: Deep Blue
        ]
        
        # Determine which color bucket (0-9)
        bucket = min(int(normalized * 10), 9)
        return colors[bucket]
    
    for school in school_data:
        color = get_color(school['merit_value'])
        
        folium.CircleMarker(
            location=[school['latitude'], school['longitude']],
            radius=6,
            popup=f"<b>{school['school_name']}</b><br>Merit: {school['merit_value']:.1f}/340<br>Municipality: {school['municipality']}<br>Address: {school['address']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=2
        ).add_to(m)
    
    # Create 10-level color legend
    colors = ['#FF0000', '#FF4000', '#FF8000', '#FFB000', '#FFD700', 
              '#B8FF00', '#80FF00', '#00FF80', '#0080FF', '#0040FF']
    
    legend_items = []
    for i in range(10):
        range_start = min_merit + (max_merit - min_merit) * (i / 10)
        range_end = min_merit + (max_merit - min_merit) * ((i + 1) / 10)
        legend_items.append(f'''
        <div style="display: flex; align-items: center; margin: 3px 0;">
            <div style="width: 16px; height: 16px; border: 2px solid {colors[i]}; border-radius: 50%; margin-right: 8px;"></div>
            <span style="font-size: 13px;">{range_start:.0f} - {range_end:.0f}</span>
        </div>''')
    
    legend_html = f'''
    <div style="position: fixed; 
                top: 20px; right: 20px; width: 200px; height: 380px; 
                background-color: white; border: 3px solid #333; z-index:9999; 
                font-size: 14px; padding: 12px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
    <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">Merit Value Scale</h3>
    <div style="margin-bottom: 8px; font-size: 12px; color: #666;">Red (Low) → Blue (High)</div>
    {''.join(legend_items)}
    <div style="margin-top: 12px; font-size: 12px; color: #666; border-top: 1px solid #ccc; padding-top: 8px;">
        Total: {len(school_data)} schools mapped<br>
        Range: {min_merit:.1f} - {max_merit:.1f}
    </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save results
    m.save('schools_merit_map.html')
    df_schools.to_csv('schools_with_coordinates.csv', index=False)
    
    print(f"\n" + "=" * 60)
    print(f"MAP GENERATION COMPLETE")
    print(f"=" * 60)
    print(f"Schools mapped: {len(school_data)}")
    print(f"Average merit value: {df_schools['merit_value'].mean():.1f}")
    print(f"\nFiles updated:")
    print(f"- schools_merit_map.html (interactive map)")
    print(f"- schools_with_coordinates.csv (data file)")
    
    # Create ranked map
    create_ranked_map(school_data, min_merit, max_merit)

def create_ranked_map(school_data, min_merit, max_merit):
    """Create a second map showing school rankings"""
    print(f"\n[BONUS] Creating ranked map...")
    
    # Sort schools by merit value (highest first) and add ranks
    ranked_schools = sorted(school_data, key=lambda x: x['merit_value'], reverse=True)
    for i, school in enumerate(ranked_schools):
        school['rank'] = i + 1
    
    m = folium.Map(location=[62.0, 15.0], zoom_start=5)
    
    def get_color(merit_value):
        normalized = (merit_value - min_merit) / (max_merit - min_merit)
        colors = ['#FF0000', '#FF4000', '#FF8000', '#FFB000', '#FFD700', 
                  '#B8FF00', '#80FF00', '#00FF80', '#0080FF', '#0040FF']
        bucket = min(int(normalized * 10), 9)
        return colors[bucket]
    
    for school in ranked_schools:
        color = get_color(school['merit_value'])
        
        # Add circle marker
        folium.CircleMarker(
            location=[school['latitude'], school['longitude']],
            radius=8,
            popup=f"<b>#{school['rank']} - {school['school_name']}</b><br>Merit: {school['merit_value']:.1f}/340<br>Rank: {school['rank']} of {len(ranked_schools)} in Sweden<br>Municipality: {school['municipality']}<br>Address: {school['address']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=2
        ).add_to(m)
        
        # Add rank number to the right side of circle
        folium.Marker(
            location=[school['latitude'], school['longitude']],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 11px; font-weight: bold; color: white; text-shadow: 1px 1px 2px black; background: rgba(0,0,0,0.6); padding: 1px 3px; border-radius: 3px; white-space: nowrap;">{school["rank"]}</div>',
                icon_size=(30, 15),
                icon_anchor=(-15, 8)
            )
        ).add_to(m)
    
    # Add enhanced legend for ranked map
    colors = ['#FF0000', '#FF4000', '#FF8000', '#FFB000', '#FFD700', 
              '#B8FF00', '#80FF00', '#00FF80', '#0080FF', '#0040FF']
    
    legend_items = []
    for i in range(10):
        range_start = min_merit + (max_merit - min_merit) * (i / 10)
        range_end = min_merit + (max_merit - min_merit) * ((i + 1) / 10)
        legend_items.append(f'''
        <div style="display: flex; align-items: center; margin: 3px 0;">
            <div style="width: 16px; height: 16px; background-color: {colors[i]}; border-radius: 50%; margin-right: 8px;"></div>
            <span style="font-size: 13px;">{range_start:.0f} - {range_end:.0f}</span>
        </div>''')
    
    legend_html = f'''
    <div style="position: fixed; 
                top: 20px; right: 20px; width: 250px; height: 450px; 
                background-color: white; border: 3px solid #333; z-index:9999; 
                font-size: 14px; padding: 15px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
    <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">🏆 School Rankings</h3>
    <div style="margin-bottom: 12px; font-size: 12px; color: #666; border-bottom: 1px solid #ccc; padding-bottom: 8px;">
        <b>Numbers show rank in Sweden</b><br>
        #1 = Highest merit value<br>
        #{len(ranked_schools)} = Lowest merit value
    </div>
    <h4 style="margin: 8px 0 5px 0; color: #333; font-size: 14px;">Merit Value Scale</h4>
    <div style="margin-bottom: 8px; font-size: 12px; color: #666;">Red (Low) → Blue (High)</div>
    {''.join(legend_items)}
    <div style="margin-top: 12px; font-size: 12px; color: #666; border-top: 1px solid #ccc; padding-top: 8px;">
        Total: {len(ranked_schools)} schools ranked<br>
        Range: {min_merit:.1f} - {max_merit:.1f}
    </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save ranked map
    m.save('schools_ranked_map.html')
    print(f"      Ranked map saved: schools_ranked_map.html")
    print(f"      Each school shows its rank (1-{len(ranked_schools)}) in Sweden")

def main():
    start_time = time.time()
    
    print("=" * 60)
    print("SKOLVERKET DATA EXTRACTOR - GOOGLE MAPS VERSION")
    print("=" * 60)
    
    # Read CSV
    print("\n[1/6] Reading school data from CSV...")
    df = pd.read_csv('Grundskola - Slutbetyg årskurs 9, samtliga elever 2025 Skolenhet.csv', 
                     sep=';', skiprows=5)
    print(f"      Loaded {len(df)} total schools from CSV")
    
    # Clean data
    print("\n[2/6] Processing merit values...")
    df = df.dropna(subset=['Skol-enhetskod'])
    df['merit_clean'] = df['Genomsnittligt meritvärde (17 ämnen)'].astype(str).str.replace(',', '.')
    df['merit_value'] = pd.to_numeric(df['merit_clean'], errors='coerce')
    
    schools_with_merit = df[df['merit_value'].notna()].copy()
    # Sort by merit value - process ALL schools
    schools_with_merit = schools_with_merit.sort_values('merit_value', ascending=False)
    print(f"      Found {len(df[df['merit_value'].notna()])} schools with valid merit values")
    print(f"      Processing ALL {len(schools_with_merit)} schools with merit values")
    print(f"      Merit range: {schools_with_merit['merit_value'].min():.1f} - {schools_with_merit['merit_value'].max():.1f}")
    
    # Initialize mapper
    print("\n[3/6] Initializing Google Maps geocoder...")
    try:
        mapper = SchoolMapper()
        cached_count = len(mapper.address_cache)
        print(f"      Google Maps API initialized successfully")
        print(f"      Loaded {cached_count} previously extracted addresses from cache")
    except ValueError as e:
        print(f"      ERROR: {e}")
        return
    
    # Process schools
    print(f"\n[4/6] Processing {len(schools_with_merit)} schools...")
    school_data = []
    failed_addresses = 0
    failed_geocoding = 0
    cache_hits = 0
    
    for idx, (_, row) in enumerate(schools_with_merit.iterrows()):
        school_id = str(row['Skol-enhetskod'])
        school_name = row['Skola']
        municipality = row['Skolkommun']
        merit_value = row['merit_value']
        
        # Progress reporting
        if idx % 100 == 0 or idx < 10:
            elapsed = time.time() - start_time
            progress = (idx / len(schools_with_merit)) * 100
            eta = (elapsed / (idx + 1)) * (len(schools_with_merit) - idx - 1) if idx > 0 else 0
            print(f"\n      Progress: {idx+1}/{len(schools_with_merit)} ({progress:.1f}%) - {elapsed:.1f}s elapsed, ETA: {eta:.1f}s")
        
        print(f"      {idx+1:4d}. {school_name[:50]:<50} (ID: {school_id})")
        
        # Check if address is cached
        was_cached = school_id in mapper.address_cache
        if was_cached:
            cache_hits += 1
        
        # Get address
        address = mapper.get_school_address(school_id)
        
        if address:
            print(f"            Address: {address} {'[CACHED]' if was_cached else '[NEW]'}")
        else:
            print(f"            Address: Not found {'[CACHED]' if was_cached else '[FAILED]'}")
            failed_addresses += 1
        
        # Get coordinates using Google Maps
        coords = mapper.geocode_address(address, municipality)
        
        if coords:
            school_data.append({
                'school_id': school_id,
                'school_name': school_name,
                'municipality': municipality,
                'address': address or municipality,
                'merit_value': merit_value,
                'latitude': coords[0],
                'longitude': coords[1]
            })
            print(f"            Coords: {coords[0]:.4f}, {coords[1]:.4f} [OK]")
        else:
            print(f"            Coords: Failed to geocode [FAIL]")
            failed_geocoding += 1
        
        # Save caches periodically
        if idx % 100 == 0:
            mapper.save_address_cache()
            mapper.save_coord_cache()
        
        # Minimal delay for Skolverket scraping
        if not was_cached:
            time.sleep(0.2)
    
    # Save final caches
    mapper.save_address_cache()
    mapper.save_coord_cache()
    
    # Create map
    print(f"\n[5/6] Creating interactive map...")
    print(f"      Mapping {len(school_data)} successfully processed schools")
    
    m = folium.Map(location=[62.0, 15.0], zoom_start=5)
    
    # Calculate merit value range for color mapping
    df_schools = pd.DataFrame(school_data)
    min_merit = df_schools['merit_value'].min()
    max_merit = df_schools['merit_value'].max()
    
    def get_color(merit_value):
        """Map merit value to 10-level color spectrum from red to blue"""
        normalized = (merit_value - min_merit) / (max_merit - min_merit)
        colors = ['#FF0000', '#FF4000', '#FF8000', '#FFB000', '#FFD700', 
                  '#B8FF00', '#80FF00', '#00FF80', '#0080FF', '#0040FF']
        bucket = min(int(normalized * 10), 9)
        return colors[bucket]
    
    for school in school_data:
        color = get_color(school['merit_value'])
        
        folium.CircleMarker(
            location=[school['latitude'], school['longitude']],
            radius=6,
            popup=f"<b>{school['school_name']}</b><br>Merit: {school['merit_value']:.1f}/340<br>Municipality: {school['municipality']}<br>Address: {school['address']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=2
        ).add_to(m)
    
    # Add 10-level color legend
    colors = ['#FF0000', '#FF4000', '#FF8000', '#FFB000', '#FFD700', 
              '#B8FF00', '#80FF00', '#00FF80', '#0080FF', '#0040FF']
    
    legend_items = []
    for i in range(10):
        range_start = min_merit + (max_merit - min_merit) * (i / 10)
        range_end = min_merit + (max_merit - min_merit) * ((i + 1) / 10)
        legend_items.append(f'''
        <div style="display: flex; align-items: center; margin: 3px 0;">
            <div style="width: 16px; height: 16px; background-color: {colors[i]}; border-radius: 50%; margin-right: 8px;"></div>
            <span style="font-size: 13px;">{range_start:.0f} - {range_end:.0f}</span>
        </div>''')
    
    legend_html = f'''
    <div style="position: fixed; 
                top: 20px; right: 20px; width: 200px; height: 380px; 
                background-color: white; border: 3px solid #333; z-index:9999; 
                font-size: 14px; padding: 12px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
    <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">Merit Value Scale</h3>
    <div style="margin-bottom: 8px; font-size: 12px; color: #666;">Red (Low) → Blue (High)</div>
    {''.join(legend_items)}
    <div style="margin-top: 12px; font-size: 12px; color: #666; border-top: 1px solid #ccc; padding-top: 8px;">
        Total: {len(school_data)} schools mapped<br>
        Range: {min_merit:.1f} - {max_merit:.1f}
    </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save results
    print(f"\n[6/6] Saving results...")
    m.save('schools_merit_map.html')
    df_schools.to_csv('schools_with_coordinates.csv', index=False)
    
    total_time = time.time() - start_time
    
    print(f"\n" + "=" * 60)
    print(f"EXTRACTION COMPLETE - GOOGLE MAPS VERSION")
    print(f"=" * 60)
    print(f"Total time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    print(f"Schools processed: {len(schools_with_merit)}")
    print(f"Schools successfully mapped: {len(school_data)}")
    print(f"Success rate: {len(school_data)/len(schools_with_merit)*100:.1f}%")
    print(f"Address cache hits: {cache_hits}")
    print(f"Failed address extractions: {failed_addresses}")
    print(f"Failed geocoding: {failed_geocoding}")
    print(f"Average merit value: {df_schools['merit_value'].mean():.1f}")
    print(f"\nFiles created:")
    print(f"- schools_merit_map.html (interactive map)")
    print(f"- schools_ranked_map.html (ranked map with numbers)")
    print(f"- schools_with_coordinates.csv (data file)")
    print(f"- address_cache.json (cached addresses)")
    print(f"- coord_cache.json (cached coordinates)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Skolverket Data Extractor - Google Maps Version')
    parser.add_argument('--map-only', action='store_true', 
                       help='Generate map using cached data only (no address queries)')
    parser.add_argument('--top', type=int, default=100,
                       help='Number of top schools to process (default: 100)')
    
    args = parser.parse_args()
    
    if args.map_only:
        create_map_from_cache()
    else:
        main()