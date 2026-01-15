import json
import os
from jsonschema import validate
from asteval import Interpreter

def validate_expressions(strategy_file, strategy_data):
    """
    Validates the asteval expressions in a strategy file.
    """
    errors = []
    asteval = Interpreter()

    # Check conditions and capture expressions in phases
    for i, phase in enumerate(strategy_data.get('phases', [])):
        for j, condition in enumerate(phase.get('conditions', [])):
            try:
                asteval.parse(condition)
            except Exception as e:
                errors.append(f"    - Invalid condition in phase {i}, condition {j} ('{condition}'): {e}")
        for name, expression in phase.get('capture', {}).items():
            try:
                asteval.parse(expression)
            except Exception as e:
                errors.append(f"    - Invalid capture expression for '{name}' in phase {i} ('{expression}'): {e}")

    # Check execution expressions
    execution = strategy_data.get('execution', {})
    for name, expression in execution.items():
        if name != 'side' and name != 'option_selection':
            try:
                asteval.parse(expression)
            except Exception as e:
                errors.append(f"    - Invalid execution expression for '{name}' ('{expression}'): {e}")

    return errors

def main():
    """
    Validates all strategy files in the 'strategies' directory.
    """
    schema_file = 'strategy.schema.json'
    strategies_dir = 'strategies'
    has_errors = False

    with open(schema_file) as f:
        schema = json.load(f)

    for filename in os.listdir(strategies_dir):
        if filename.endswith(".json"):
            strategy_file = os.path.join(strategies_dir, filename)
            with open(strategy_file) as f:
                try:
                    strategy_data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Error in {strategy_file}:")
                    print(f"  - Invalid JSON: {e}")
                    has_errors = True
                    continue

            errors = []
            try:
                validate(instance=strategy_data, schema=schema)
            except Exception as e:
                errors.append(f"  - Schema validation failed: {e.message}")

            expression_errors = validate_expressions(strategy_file, strategy_data)
            errors.extend(expression_errors)

            if errors:
                print(f"Error in {strategy_file}:")
                for error in errors:
                    print(error)
                has_errors = True

    if not has_errors:
        print("All strategy files are valid.")

if __name__ == "__main__":
    main()
