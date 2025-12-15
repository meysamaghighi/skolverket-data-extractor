import pandas as pd
import folium
import requests
from geopy.geocoders import Nominatim
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
        self.geolocator = Nominatim(user_agent="skolverket_mapper")
        self.address_cache = self.load_address_cache()
        self.coord_cache = self.load_coord_cache()
        
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
        """Get coordinates for address with caching and retries"""
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
                f"{address.split()[0]}, {municipality}, Sweden",  # Just street name
                f"{municipality}, Sweden"  # Fallback to municipality
            ]
        else:
            search_addresses = [f"{municipality}, Sweden"]
        
        for search_addr in search_addresses:
            for attempt in range(2):  # 2 attempts per address
                try:
                    location = self.geolocator.geocode(search_addr, timeout=15)
                    if location:
                        coords = [location.latitude, location.longitude]
                        self.coord_cache[cache_key] = coords
                        return coords[0], coords[1]
                    time.sleep(1)  # Wait between attempts
                except Exception as e:
                    if attempt == 0:  # Only sleep on first attempt
                        time.sleep(2)
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
    schools_with_merit = schools_with_merit.sort_values('merit_value', ascending=False).head(100)
    
    print(f"      Processing top {len(schools_with_merit)} schools by merit value")
    
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
    
    # Create map
    print("\n[4/4] Creating map...")
    m = folium.Map(location=[62.0, 15.0], zoom_start=5)
    
    for school in school_data:
        if school['merit_value'] >= 250:
            color = 'green'
        elif school['merit_value'] >= 200:
            color = 'orange'
        else:
            color = 'red'
        
        folium.CircleMarker(
            location=[school['latitude'], school['longitude']],
            radius=8,
            popup=f"{school['school_name']}<br>Merit: {school['merit_value']}<br>{school['address']}",
            color=color,
            fill=True,
            fillColor=color
        ).add_to(m)
    
    # Save results
    m.save('schools_merit_map.html')
    df_schools = pd.DataFrame(school_data)
    df_schools.to_csv('schools_with_coordinates.csv', index=False)
    
    print(f"\n" + "=" * 60)
    print(f"MAP GENERATION COMPLETE")
    print(f"=" * 60)
    print(f"Schools mapped: {len(school_data)}")
    print(f"Average merit value: {df_schools['merit_value'].mean():.1f}")
    print(f"\nFiles updated:")
    print(f"- schools_merit_map.html (interactive map)")
    print(f"- schools_with_coordinates.csv (data file)")

def main():
    start_time = time.time()
    
    print("=" * 60)
    print("SKOLVERKET DATA EXTRACTOR - VERBOSE MODE")
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
    # Sort by merit value and take top 100
    schools_with_merit = schools_with_merit.sort_values('merit_value', ascending=False).head(100)
    print(f"      Found {len(df[df['merit_value'].notna()])} schools with valid merit values")
    print(f"      Processing top {len(schools_with_merit)} schools by merit value")
    print(f"      Merit range: {schools_with_merit['merit_value'].min():.1f} - {schools_with_merit['merit_value'].max():.1f}")
    
    # Initialize mapper
    print("\n[3/6] Initializing mapper and loading cache...")
    mapper = SchoolMapper()
    cached_count = len(mapper.address_cache)
    print(f"      Loaded {cached_count} previously extracted addresses from cache")
    
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
            print(f"\n      Progress: {idx+1}/{len(schools_with_merit)} ({progress:.1f}%) - {elapsed:.1f}s elapsed, ETA: {eta/60:.1f}min")
        
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
        
        # Get coordinates
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
        if idx % 50 == 0:
            mapper.save_address_cache()
            mapper.save_coord_cache()
        
        time.sleep(0.5)  # Rate limiting
    
    # Save final caches
    mapper.save_address_cache()
    mapper.save_coord_cache()
    
    # Create map
    print(f"\n[5/6] Creating interactive map...")
    print(f"      Mapping {len(school_data)} successfully processed schools")
    
    m = folium.Map(location=[62.0, 15.0], zoom_start=5)
    
    for school in school_data:
        if school['merit_value'] >= 250:
            color = 'green'
        elif school['merit_value'] >= 200:
            color = 'orange'
        else:
            color = 'red'
        
        folium.CircleMarker(
            location=[school['latitude'], school['longitude']],
            radius=8,
            popup=f"{school['school_name']}<br>Merit: {school['merit_value']}<br>{school['address']}",
            color=color,
            fill=True,
            fillColor=color
        ).add_to(m)
    
    # Save results
    print(f"\n[6/6] Saving results...")
    m.save('schools_merit_map.html')
    df_schools = pd.DataFrame(school_data)
    df_schools.to_csv('schools_with_coordinates.csv', index=False)
    
    total_time = time.time() - start_time
    
    print(f"\n" + "=" * 60)
    print(f"EXTRACTION COMPLETE")
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
    print(f"- schools_with_coordinates.csv (data file)")
    print(f"- address_cache.json (cached addresses)")
    print(f"- coord_cache.json (cached coordinates)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Skolverket Data Extractor')
    parser.add_argument('--map-only', action='store_true', 
                       help='Generate map using cached data only (no address queries)')
    parser.add_argument('--top', type=int, default=100,
                       help='Number of top schools to process (default: 100)')
    
    args = parser.parse_args()
    
    if args.map_only:
        create_map_from_cache()
    else:
        main()