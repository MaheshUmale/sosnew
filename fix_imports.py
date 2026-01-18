import os

def fix_imports():
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                if path.endswith('fix_imports.py'): continue

                with open(path, 'r') as f:
                    lines = f.readlines()

                new_lines = []
                for line in lines:
                    # Replace the previous failed attempts
                    line = line.replace('from python_engine.utils.symbol_master import SymbolMaster', 'from python_engine.utils.symbol_master import MASTER as SymbolMaster')
                    line = line.replace('from python_engine.utils.symbol_master from python_engine.utils.symbol_master import SymbolMaster', 'from python_engine.utils.symbol_master import MASTER as SymbolMaster')
                    line = line.replace('SymbolMaster().', 'SymbolMaster.')
                    new_lines.append(line)

                content = "".join(new_lines)
                with open(path, 'w') as f:
                    f.write(content)
                print(f"Fixed imports in {path}")

if __name__ == '__main__':
    fix_imports()
