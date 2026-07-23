path = r"C:\Users\dhruv\AppData\Roaming\npm\node_modules\zcatalyst-cli\lib\fn-utils\lib\common.js"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "env_var" in line or "env_variables" in line:
        print(f"Line {idx+1}: {line.strip()}")
        # print surrounding lines
        for j in range(max(0, idx - 5), min(len(lines), idx + 8)):
            print(f"  {j+1}: {lines[j].strip()}")
        print("-" * 50)
