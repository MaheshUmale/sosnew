import sys

with open('run_ui.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "df = df[[c for c in cols if c in df.columns]]" in line:
        # Keep the original df or at least keep 'symbol'
        new_lines.append("    # Drop non-serializable columns but keep 'symbol' for trade matching\n")
        new_lines.append("    cols_to_keep = ['time', 'open', 'high', 'low', 'close', 'volume', 'oi', 'symbol']\n")
        new_lines.append("    df = df[[c for c in cols_to_keep if c in df.columns]]\n")
    else:
        new_lines.append(line)

with open('run_ui.py', 'w') as f:
    f.writelines(new_lines)
