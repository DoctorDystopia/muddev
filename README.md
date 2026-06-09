# MUD DEVELOPMENT

## Local Development Setup

This repository contains the game files (`blackout/`) and the Evennia engine as a pinned Git submodule (`evennia/`). 

### 1. Clone the Repository
Because Evennia is a submodule, must use the `--recurse-submodules` flag to pull down the engine code alongside the game code:
```bash
git clone --recurse-submodules [https://github.com/DoctorDystopia/muddev.git](https://github.com/DoctorDystopia/muddev.git)
cd muddev
```

*(Note: If already cloned normally and the `evennia` folder is empty, run `git submodule update --init --recursive` to fix it).*

### 2. Set Up the Virtual Environment

**On Windows:**

```cmd
python -m venv evenv
evenv\Scripts\activate
```

#### OR if you are using PowerShell / Git Bash:
```powershell
.\evenv\scripts\activate
```

**On Mac/Linux:**

```bash
python3 -m venv evenv
source evenv/bin/activate
```

### 3. Install the Engine and Dependencies

Make sure the virtual environment is active. Install the local Evennia submodule in "editable" mode:

```bash
pip install -e evennia
```

### 4. Initialize and Run the Game

Navigate into the actual game directory to build the database and start the server.

```bash
cd blackout
evennia migrate
evennia start
```

The game should now be running locally. Can connect via a MUD client at `localhost:4000` or the web browser at `http://localhost:4001`.

### A Quick Tip for Windows
If running into issues executing scripts on Windows, might need to run PowerShell as an administrator and execute `Set-ExecutionPolicy Unrestricted -Scope CurrentUser` so Windows allows the virtual environment's `activate` script to run.

#### Update Evennia
To update Evennia to a newer version, step into the submodule, pull the changes, and then commit the new hash at the top level:

```bash
cd evennia
git checkout master
git pull
cd ..
git add evennia
git commit -m "build: bump evennia submodule hash"
```

## Ref
- https://www.evennia.com/docs/latest/api/evennia.objects.objects.html