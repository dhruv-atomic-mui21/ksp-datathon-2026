import subprocess
import os

# Files to restore from our last successful commit
files_to_restore = [
    "functions/ksp_functions/main.py",
    "functions/ksp_functions/database.py",
    "functions/ksp_functions/nl2sql.py",
    "functions/ksp_functions/analytics.py",
    "functions/ksp_functions/requirements.txt",
    "functions/ksp_functions/catalyst-config.json",
    "client/index.html",
    "client/client-package.json",
    "client/js/app.js",
    "client/css/style.css",
    "client/challenge01/index.html",
    "client/challenge02/index.html",
]

def run():
    print("=========================================")
    print("REWRITING OVERWRITTEN FILES FROM HEAD")
    print("=========================================\n")
    
    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    for f in files_to_restore:
        relative_path = f.replace("/", os.sep)
        absolute_path = os.path.join(workspace, relative_path)
        print(f"Restoring: {f}...")
        
        try:
            # Get the exact file contents from the last commit
            content = subprocess.check_output(
                ["git", "show", f"HEAD:{f}"], 
                cwd=workspace, 
                stderr=subprocess.PIPE
            )
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
            
            # Rewrite the file content
            with open(absolute_path, "wb") as out:
                out.write(content)
            
            print(f"  [SUCCESS] Wrote {len(content)} bytes to {absolute_path}")
        except Exception as e:
            print(f"  [ERROR] Failed to restore {f}: {e}")
            
    print("\nFile restoration complete!")

if __name__ == "__main__":
    run()
