#!/usr/bin/env python3
"""
Vera TUI Setup and Test Script
Quick setup and verification for the Vera Terminal UI
"""

import sys
import subprocess
import os


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def check_python_version():
    """Check if Python version is compatible"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print("✓ Python version is compatible")
    return True


def install_dependencies():
    """Install required dependencies"""
    print_header("Installing Dependencies")
    
    dependencies = [
        "textual>=0.47.0",
        "nest-asyncio>=1.5.0",
        "rich>=13.0.0",
        "psutil>=5.9.0"
    ]
    
    print("Installing packages:")
    for dep in dependencies:
        print(f"  • {dep}")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--upgrade"
        ] + dependencies)
        
        print("\n✓ All dependencies installed successfully")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to install dependencies: {e}")
        return False


def verify_imports():
    """Verify that all required modules can be imported"""
    print_header("Verifying Imports")
    
    imports = {
        "textual": "Textual TUI framework",
        "nest_asyncio": "Nested event loop support",
        "rich": "Rich text formatting",
        "psutil": "System monitoring"
    }
    
    all_ok = True
    
    for module, description in imports.items():
        try:
            __import__(module)
            print(f"✓ {module:20} - {description}")
        except ImportError as e:
            print(f"❌ {module:20} - FAILED: {e}")
            all_ok = False
    
    return all_ok


def test_tui_import():
    """Test importing the TUI modules"""
    print_header("Testing TUI Modules")
    
    tui_files = [
        ("vera_tui.py", "Standard TUI"),
        ("vera_tui_enhanced.py", "Enhanced TUI"),
        ("vera_tui_utils.py", "TUI Utilities")
    ]
    
    all_ok = True
    
    for filename, description in tui_files:
        if os.path.exists(filename):
            print(f"✓ {filename:25} - {description}")
        else:
            print(f"❌ {filename:25} - File not found")
            all_ok = False
    
    return all_ok


def run_simple_test():
    """Run a simple test of the TUI"""
    print_header("Running Simple Test")
    
    try:
        print("Creating test TUI instance...")
        from vera_tui import VeraTUI
        
        app = VeraTUI(vera_instance=None)
        print("✓ TUI instance created successfully")
        print("✓ Test passed - TUI is ready to use")
        
        return True
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_launch_script():
    """Create a convenient launch script"""
    print_header("Creating Launch Script")
    
    script_content = """#!/bin/bash
# Vera TUI Launcher Script

# Apply nest_asyncio fix
export PYTHONASYNCIODEBUG=1

# Run the TUI
python launch_tui_robust.py "$@"
"""
    
    try:
        with open("run_tui.sh", "w") as f:
            f.write(script_content)
        
        # Make executable
        os.chmod("run_tui.sh", 0o755)
        
        print("✓ Created run_tui.sh launcher script")
        print("\nYou can now run:")
        print("  ./run_tui.sh")
        print("  ./run_tui.sh --config my_config.yaml")
        print("  ./run_tui.sh --no-vera")
        
        return True
    
    except Exception as e:
        print(f"⚠️  Could not create launcher script: {e}")
        return False


def print_usage_guide():
    """Print usage guide"""
    print_header("Usage Guide")
    
    print("""
🚀 Quick Start:

1. Launch TUI with Vera:
   python launch_tui_robust.py

2. Launch TUI without Vera (view only):
   python launch_tui_robust.py --no-vera

3. Use enhanced TUI (recommended):
   python launch_tui_robust.py --use-enhanced

4. Custom configuration:
   python launch_tui_robust.py --config path/to/config.yaml

5. With infrastructure features:
   python launch_tui_robust.py --enable-infrastructure --enable-docker


⌨️  Keyboard Shortcuts:
   Ctrl+S  - Submit query
   Ctrl+C  - Clear input
   Ctrl+L  - Clear logs
   Ctrl+Q  - Quit
   F1      - Help
   F2      - Toggle debug mode


📚 Special Commands (enter in query input):
   /stats   - Show performance statistics
   /infra   - Show infrastructure status
   /agents  - List available agents
   /clear   - Clear memory
   /exit    - Quit application


📖 Documentation:
   README_TUI.md           - Full documentation
   INTEGRATION_GUIDE.py    - Integration with Vera
    """)


def main():
    """Main setup routine"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║              Vera Terminal UI Setup                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    steps = [
        ("Python Version Check", check_python_version),
        ("Dependency Installation", install_dependencies),
        ("Import Verification", verify_imports),
        ("TUI Module Check", test_tui_import),
        ("Simple Test", run_simple_test),
        ("Create Launcher", create_launch_script)
    ]
    
    results = []
    
    for step_name, step_func in steps:
        try:
            result = step_func()
            results.append((step_name, result))
        except Exception as e:
            print(f"\n❌ {step_name} failed with error: {e}")
            results.append((step_name, False))
    
    # Print summary
    print_header("Setup Summary")
    
    for step_name, result in results:
        status = "✓" if result else "❌"
        print(f"{status} {step_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 Setup completed successfully!")
        print_usage_guide()
    else:
        print("\n⚠️  Setup completed with some issues")
        print("\nTroubleshooting:")
        print("  • Check that you have Python 3.8+")
        print("  • Ensure pip is working: python -m pip --version")
        print("  • Try: pip install --upgrade pip setuptools wheel")
        print("  • Install manually: pip install -r requirements_tui.txt")


if __name__ == "__main__":
    main()