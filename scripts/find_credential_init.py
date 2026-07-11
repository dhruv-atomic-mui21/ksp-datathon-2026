import os

cli_dir = r"C:\Users\dhruv\AppData\Roaming\npm\node_modules\zcatalyst-cli\lib"

found = []
for root, dirs, files in os.walk(cli_dir):
    for file in files:
        if file.endswith(".js"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "Credential.init" in content or "Credential.initToken" in content:
                        found.append(path)
            except Exception:
                pass

print("Files calling Credential.init/initToken:")
for p in found:
    print(f" - {p}")
