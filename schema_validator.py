import json
import jsonschema
from jsonschema import validate
import sys

def main():
    if len(sys.argv) < 3:
        print("Usage: python schema_validator.py <schema_file> <json_file>")
        sys.exit(1)
        
    schema_file = sys.argv[1]
    json_file = sys.argv[2]
    
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema = json.load(f)
        
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    try:
        validate(instance=data, schema=schema)
        print(f"Validation successful: {json_file} conforms to the schema.")
    except jsonschema.exceptions.ValidationError as err:
        print(f"Validation error in {json_file}:")
        print(f"Message: {err.message}")
        sys.exit(1)
    except json.decoder.JSONDecodeError as err:
        print(f"JSON decode error in {json_file}: {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
