# Devilnet — Minimal Documentation Checklist

Kept (essential):
- README.md
- ARCHITECTURE.md
- QUICK_REFERENCE.md

Removed (non-essential):
- INTERACTIVE_UI_GUIDE.md
- PERFORMANCE_TUNING.md
- TESTING_GUIDE.md
- IMPLEMENTATION_SUMMARY.md
- CHANGELOG.md
- REFERENCE.md
- Any other `.md` files not listed above

Safe removal commands (preview first):

PowerShell (preview):
```powershell
Get-ChildItem -Path . -Recurse -Filter *.md |
  Where-Object { $_.Name -notin @('README.md','ARCHITECTURE.md','QUICK_REFERENCE.md') } |
  Remove-Item -WhatIf
```

PowerShell (delete):
```powershell
Get-ChildItem -Path . -Recurse -Filter *.md |
  Where-Object { $_.Name -notin @('README.md','ARCHITECTURE.md','QUICK_REFERENCE.md') } |
  Remove-Item
```

Unix (preview):
```bash
find . -type f -name '*.md' ! -name 'README.md' ! -name 'ARCHITECTURE.md' ! -name 'QUICK_REFERENCE.md' -print
```

Unix (delete):
```bash
find . -type f -name '*.md' ! -name 'README.md' ! -name 'ARCHITECTURE.md' ! -name 'QUICK_REFERENCE.md' -delete
```

Notes:
- Run preview commands first (-WhatIf / print) to verify files to be removed.
- If you use git, prefer `git rm <file>` so deletions are tracked.
