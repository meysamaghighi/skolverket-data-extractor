import pandas as pd
import json

def test_extractor():
    """Test the extractor output"""
    print("Testing Skolverket Data Extractor...")
    
    # Test JSON output
    try:
        with open('schools_data.json', 'r', encoding='utf-8') as f:
            schools_data = json.load(f)
        print(f"[OK] JSON file loaded: {len(schools_data)} schools")
        
        # Verify structure
        first_school = schools_data[0]
        required_fields = ['school_code', 'school_name', 'municipality', 'grades']
        for field in required_fields:
            assert field in first_school, f"Missing field: {field}"
        print("[OK] JSON structure is correct")
        
    except Exception as e:
        print(f"[ERROR] JSON test failed: {e}")
        return False
    
    # Test CSV output
    try:
        df = pd.read_csv('schools_grades.csv')
        print(f"[OK] CSV file loaded: {len(df)} grade records")
        
        # Verify columns
        expected_columns = ['school_code', 'school_name', 'municipality', 'school_type', 'subject', 'grade', 'year', 'students_count']
        for col in expected_columns:
            assert col in df.columns, f"Missing column: {col}"
        print("[OK] CSV structure is correct")
        
        # Show statistics
        print(f"\nStatistics:")
        print(f"- Unique schools: {df['school_code'].nunique()}")
        print(f"- Municipalities: {df['municipality'].nunique()}")
        print(f"- School types: {df['school_type'].nunique()}")
        print(f"- Subjects: {df['subject'].nunique()}")
        print(f"- Grade distribution:")
        print(df['grade'].value_counts().sort_index())
        
    except Exception as e:
        print(f"[ERROR] CSV test failed: {e}")
        return False
    
    print("\n[SUCCESS] All tests passed!")
    return True

if __name__ == "__main__":
    test_extractor()