# GitHub Push Guide

## Current Repository Structure

```
bomb-master/
├── README.md
├── CODE_STRUCTURE.md (in docs/)
├── code.py (in src/)
├── circuit-diagrams/
│   ├── circuit_diagrams.pdf
│   └── circuit_diagrams.kicad_sch
└── .gitignore
```

## Steps to Push to GitHub

### 1. Navigate to your local repository
```bash
cd /Users/tong/511/bomb-master
```

### 2. Initialize git (if not already initialized)
```bash
git init
```

### 3. Add remote repository
```bash
git remote add origin https://github.com/tong0701/512_finalproject.git
```

Or if remote already exists:
```bash
git remote set-url origin https://github.com/tong0701/512_finalproject.git
```

### 4. Check current status
```bash
git status
```

### 5. Add all files
```bash
git add .
```

### 6. Commit changes
```bash
git commit -m "Update Bomb Master project structure"
```

### 7. Force push to GitHub (to overwrite existing files)
**⚠️ WARNING: This will delete existing files on GitHub that are not in your local directory**

```bash
git push -f origin main
```

Or if your default branch is `master`:
```bash
git push -f origin master
```

### Alternative: Safe Push (Recommended)

If you want to be safer, you can:

1. First, fetch and see what's on GitHub:
```bash
git fetch origin
git branch -a  # See all branches
```

2. Create a backup branch (optional):
```bash
git checkout -b backup-$(date +%Y%m%d)
git push origin backup-$(date +%Y%m%d)
```

3. Switch back to main and force push:
```bash
git checkout main  # or master
git push -f origin main
```

## After Pushing

Verify the repository structure on GitHub:
- https://github.com/tong0701/512_finalproject

The repository should show:
- `README.md` in root
- `src/code.py`
- `docs/CODE_STRUCTURE.md` (or move it to root if preferred)
- `circuit-diagrams/` folder with PDF and KiCad files
