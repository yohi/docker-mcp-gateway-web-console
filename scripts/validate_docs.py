#!/usr/bin/env python3
import os
import json
import sys

def check_file_exists(path):
    if not os.path.exists(path):
        print(f"❌ Missing file: {path}")
        return False
    print(f"✅ Found file: {path}")
    return True

def check_file_content(path, search_string):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            if search_string in content:
                print(f"✅ Found '{search_string}' in {path}")
                return True
            else:
                print(f"❌ Missing '{search_string}' in {path}")
                return False
    except Exception as e:
        print(f"❌ Error reading {path}: {e}")
        return False

def validate_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "servers" in data and isinstance(data["servers"], list):
                print(f"✅ Valid JSON structure in {path}")
                return True
            else:
                print(f"❌ Invalid JSON structure in {path}: missing 'servers' list")
                return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {path}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading {path}: {e}")
        return False

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    files_to_check = [
        "README.md",
        "docs/ENVIRONMENT_VARIABLES.md",
        "docs/DEPLOYMENT.md",
        "docs/sample-catalog.json",
        "docs/QUICK_START.md",
        "docs/FAQ.md",
        "docs/ARCHITECTURE.md"
    ]

    all_passed = True

    print("--- Checking Documentation Files ---")
    for file_rel_path in files_to_check:
        full_path = os.path.join(base_dir, file_rel_path)
        if not check_file_exists(full_path):
            all_passed = False
            continue
        
        if file_rel_path == "README.md":
            if not check_file_content(full_path, "Docker MCP Gateway Console"):
                all_passed = False
        elif file_rel_path == "docs/ENVIRONMENT_VARIABLES.md":
            if not check_file_content(full_path, "BITWARDEN_CLI_PATH"):
                all_passed = False
        elif file_rel_path == "docs/sample-catalog.json":
            if not validate_json(full_path):
                all_passed = False

    if all_passed:
        print("\n✨ All documentation checks passed!")
        sys.exit(0)
    else:
        print("\n💀 Some documentation checks failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
