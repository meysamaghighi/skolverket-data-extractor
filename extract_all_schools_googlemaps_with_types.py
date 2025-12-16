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
        school_type = row.get('Typ av huvudman', 'Unknown')
        
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
            'school_type': school_type,
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
        
        # Different shapes for private vs municipal
        if school['school_type'] == 'Enskild':
            # Private schools: Diamond shape (square rotated)
            folium.RegularPolygonMarker(
                location=[school['latitude'], school['longitude']],
                number_of_sides=4,
                radius=8,
                rotation=45,
                popup=f"<b>{school['school_name']}</b><br>Type: Private (Enskild)<br>Merit: {school['merit_value']:.1f}/340<br>Municipality: {school['municipality']}<br>Address: {school['address']}",
                color='black',
                fill=True,
                fillColor=color,
                fillOpacity=0.8,
                weight=2
            ).add_to(m)
        else:
            # Municipal schools: Circle shape
            folium.CircleMarker(
                location=[school['latitude'], school['longitude']],
                radius=6,
                popup=f"<b>{school['school_name']}</b><br>Type: Municipal (Kommunal)<br>Merit: {school['merit_value']:.1f}/340<br>Municipality: {school['municipality']}<br>Address: {school['address']}",
                color='black',
                fill=True,
                fillColor=color,
                fillOpacity=0.8,
                weight=2
            ).add_to(m)
    
    # Create 10-level color legend with school type info
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
    
    # Count school types
    private_count = len([s for s in school_data if s['school_type'] == 'Enskild'])
    municipal_count = len([s for s in school_data if s['school_type'] == 'Kommunal'])
    
    legend_html = f'''
    <div style="position: fixed; 
                top: 20px; right: 20px; width: 220px; height: 480px; 
                background-color: white; border: 3px solid #333; z-index:9999; 
                font-size: 14px; padding: 12px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
    <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">School Types & Merit</h3>
    
    <div style="margin-bottom: 12px; border-bottom: 1px solid #ccc; padding-bottom: 8px;">
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 12px; height: 12px; background-color: #666; transform: rotate(45deg); margin-right: 8px;"></div>
            <span style="font-size: 13px;">Private (Enskild): {private_count}</span>
        </div>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 12px; height: 12px; background-color: #666; border-radius: 50%; margin-right: 8px;"></div>
            <span style="font-size: 13px;">Municipal (Kommunal): {municipal_count}</span>
        </div>
    </div>
    
    <h4 style="margin: 8px 0 5px 0; color: #333; font-size: 14px;">Merit Value Scale</h4>
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
    print(f"Private schools: {private_count}")
    print(f"Municipal schools: {municipal_count}")
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
        
        # Different shapes for private vs municipal
        if school['school_type'] == 'Enskild':
            # Private schools: Diamond shape
            folium.RegularPolygonMarker(
                location=[school['latitude'], school['longitude']],
                number_of_sides=4,
                radius=10,
                rotation=45,
                popup=f"<b>#{school['rank']} - {school['school_name']}</b><br>Type: Private (Enskild)<br>Merit: {school['merit_value']:.1f}/340<br>Rank: {school['rank']} of {len(ranked_schools)} in Sweden<br>Municipality: {school['municipality']}<br>Address: {school['address']}",
                color='black',
                fill=True,
                fillColor=color,
                fillOpacity=0.8,
                weight=2
            ).add_to(m)
        else:
            # Municipal schools: Circle shape
            folium.CircleMarker(
                location=[school['latitude'], school['longitude']],
                radius=8,
                popup=f"<b>#{school['rank']} - {school['school_name']}</b><br>Type: Municipal (Kommunal)<br>Merit: {school['merit_value']:.1f}/340<br>Rank: {school['rank']} of {len(ranked_schools)} in Sweden<br>Municipality: {school['municipality']}<br>Address: {school['address']}",
                color='black',
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
    
    # Count school types for ranked map
    private_count = len([s for s in ranked_schools if s['school_type'] == 'Enskild'])
    municipal_count = len([s for s in ranked_schools if s['school_type'] == 'Kommunal'])
    
    legend_html = f'''
    <div style="position: fixed; 
                top: 20px; right: 20px; width: 270px; height: 550px; 
                background-color: white; border: 3px solid #333; z-index:9999; 
                font-size: 14px; padding: 15px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
    <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">🏆 School Rankings</h3>
    <div style="margin-bottom: 12px; font-size: 12px; color: #666; border-bottom: 1px solid #ccc; padding-bottom: 8px;">
        <b>Numbers show rank in Sweden</b><br>
        #1 = Highest merit value<br>
        #{len(ranked_schools)} = Lowest merit value
    </div>
    
    <div style="margin-bottom: 12px; border-bottom: 1px solid #ccc; padding-bottom: 8px;">
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 12px; height: 12px; background-color: #666; transform: rotate(45deg); margin-right: 8px;"></div>
            <span style="font-size: 13px;">Private (Enskild): {private_count}</span>
        </div>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 12px; height: 12px; background-color: #666; border-radius: 50%; margin-right: 8px;"></div>
            <span style="font-size: 13px;">Municipal (Kommunal): {municipal_count}</span>
        </div>
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

if __name__ == "__main__":
    create_map_from_cache()