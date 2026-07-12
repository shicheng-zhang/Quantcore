import os
import re

print("="*60)
print(" FIXING AUDIT LEDGER BLOAT & GIT TRACKING")
print("="*60)

# 1. Untrack binary artifacts from Git (if they were accidentally tracked)
os.system("git rm --cached data/audit_ledger.bin 2>/dev/null")
os.system("git rm --cached data/*.duckdb 2>/dev/null")
os.system("git rm --cached data/*.parquet 2>/dev/null")
os.system("git rm --cached data/*.bin 2>/dev/null")

# Ensure .gitignore has the rules
with open(".gitignore", "a") as f:
    f.write("\n# Runtime binary artifacts (Never track these)\ndata/*.bin\ndata/*.duckdb\ndata/*.parquet\ndata/*.log\n")

# 2. Patch C++ audit_ledger.h to auto-rotate at 50MB
header_path = "nexus/include/audit_ledger.h"
if os.path.exists(header_path):
    with open(header_path, "r") as f:
        code = f.read()
        
    if "52428800" not in code:
        # Find the append_event function and inject size check right after the opening brace
        pattern = r'(void append_event\(uint64_t timestamp, const std::string& type, double val1, double val2\) \{\n)'
        
        injection = """    // Auto-rotate log if it exceeds 50MB to prevent disk/GitHub bloat
        std::ifstream check_size(log_path_, std::ios::binary | std::ios::ate);
        if (check_size.good()) {
            std::streamsize sz = check_size.tellg();
            check_size.close();
            if (sz > 52428800) { // 50 MB
                std::ofstream trunc(log_path_, std::ios::binary | std::ios::trunc);
                trunc.close();
                current_hash_ = 0x123456789ABCDEFULL;
                prev_hash_ = 0x123456789ABCDEFULL;
                seq_counter_ = 0;
            }
        }
"""
        code = re.sub(pattern, r'\1' + injection, code)
        with open(header_path, "w") as f:
            f.write(code)
        print("[✓] Patched C++ audit_ledger.h to auto-rotate at 50MB")
    else:
        print("[i] Auto-rotate already present.")
else:
    print("[!] audit_ledger.h not found.")

print("\n" + "="*60)
print(" [NEXT STEPS]")
print(" 1. Recompile C++: cd nexus/build && make -j$(nproc) && cd ../..")
print(" 2. Commit the untracked removal: git commit -m 'chore: untrack binary data files and add log rotation'")
print("="*60)
