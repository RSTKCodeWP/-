"""Script to check localization consistency."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.texts import TEXTS


def check_localization():
    """Check if all keys are present in both languages."""
    ru_keys = set(TEXTS["ru"].keys())
    en_keys = set(TEXTS["en"].keys())
    
    missing_in_en = ru_keys - en_keys
    missing_in_ru = en_keys - ru_keys
    
    print("=" * 60)
    print("LOCALIZATION CHECK")
    print("=" * 60)
    
    if missing_in_en:
        print("\n❌ Missing keys in ENGLISH:")
        for key in sorted(missing_in_en):
            print(f"  - {key}")
    
    if missing_in_ru:
        print("\n❌ Missing keys in RUSSIAN:")
        for key in sorted(missing_in_ru):
            print(f"  - {key}")
    
    if not missing_in_en and not missing_in_ru:
        print("\n✅ All localization keys are present in both languages!")
        print(f"\nTotal keys: {len(ru_keys)}")
    else:
        print(f"\n⚠️  Found inconsistencies!")
        print(f"RU keys: {len(ru_keys)}")
        print(f"EN keys: {len(en_keys)}")
    
    # Check for duplicate or similar keys
    print("\n" + "=" * 60)
    print("CHECKING FOR COMMON PATTERNS")
    print("=" * 60)
    
    all_keys = sorted(ru_keys | en_keys)
    
    # Group by prefix
    prefixes = {}
    for key in all_keys:
        prefix = key.split('_')[0]
        if prefix not in prefixes:
            prefixes[prefix] = []
        prefixes[prefix].append(key)
    
    print("\nKeys grouped by prefix:")
    for prefix, keys in sorted(prefixes.items()):
        if len(keys) > 2:
            print(f"\n{prefix}: ({len(keys)} keys)")
            for key in keys[:5]:
                print(f"  - {key}")
            if len(keys) > 5:
                print(f"  ... and {len(keys) - 5} more")


if __name__ == "__main__":
    check_localization()
