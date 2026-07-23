import os
import zipfile
import shutil
import sys

def package_frontend():
    # Enforce UTF-8 encoding for stdout on Windows
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client_dir = os.path.join(project_root, "client")
    output_zip = os.path.join(project_root, "ksp_frontend_slate.zip")
    dist_dir = os.path.join(project_root, "dist")

    print(f"[+] Packaging isolated frontend from '{client_dir}'...")

    if not os.path.exists(client_dir):
        print(f"[-] Error: Client directory not found at {client_dir}")
        return

    # Create dist directory if needed
    os.makedirs(dist_dir, exist_ok=True)
    dist_zip = os.path.join(dist_dir, "ksp_frontend_slate.zip")

    # Create ZIP file with maximum GZIP compression (compresslevel=9)
    file_count = 0
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(client_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, client_dir)
                zipf.write(file_path, rel_path)
                file_count += 1
                print(f"  + Added: {rel_path}")

    # Copy zip to dist directory as well
    shutil.copy2(output_zip, dist_zip)

    # Also create a tar.gz archive
    output_tar_gz = os.path.join(project_root, "ksp_frontend_slate.tar.gz")
    import tarfile
    with tarfile.open(output_tar_gz, "w:gz") as tar:
        tar.add(client_dir, arcname="")

    zip_size_kb = os.path.getsize(output_zip) / 1024
    tar_size_kb = os.path.getsize(output_tar_gz) / 1024
    print("\n[SUCCESS] Packaging & Gzip compression complete!")
    print(f"  Total files packaged: {file_count}")
    print(f"  ZIP Archive (Gzip L9): {output_zip} ({zip_size_kb:.2f} KB)")
    print(f"  TAR.GZ Archive: {output_tar_gz} ({tar_size_kb:.2f} KB)")
    print(f"  Dist Archive: {dist_zip} ({zip_size_kb:.2f} KB)")

if __name__ == "__main__":
    package_frontend()

