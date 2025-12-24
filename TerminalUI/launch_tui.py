#!/usr/bin/env python3
"""
Vera TUI Launcher - Robust version with proper event loop handling
"""

import sys
import os
import argparse


def check_dependencies():
    """Check if required dependencies are installed"""
    missing = []
    
    try:
        import textual
    except ImportError:
        missing.append("textual>=0.47.0")
    
    try:
        import nest_asyncio
    except ImportError:
        missing.append("nest-asyncio>=1.5.0")
    
    if missing:
        print("❌ Missing required dependencies:")
        for dep in missing:
            print(f"   - {dep}")
        print("\nInstall with:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Launch Vera Terminal UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Launch with default config
  %(prog)s --config custom_config.yaml       # Use custom config
  %(prog)s --no-vera                          # Launch UI only (no Vera)
  %(prog)s --enable-infrastructure            # Enable infrastructure features
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        default="Configuration/vera_config.yaml",
        help="Path to Vera configuration file"
    )
    parser.add_argument(
        "--no-vera",
        action="store_true",
        help="Launch TUI without initializing Vera (UI only)"
    )
    parser.add_argument(
        "--enable-infrastructure",
        action="store_true",
        help="Enable infrastructure orchestration"
    )
    parser.add_argument(
        "--enable-docker",
        action="store_true",
        help="Enable Docker integration"
    )
    parser.add_argument(
        "--use-enhanced",
        action="store_true",
        help="Use enhanced TUI with deep logging integration"
    )
    
    args = parser.parse_args()
    
    # Check dependencies first
    print("🔍 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("✓ All dependencies satisfied\n")
    
    # Import after dependency check
    import nest_asyncio
    nest_asyncio.apply()  # Apply immediately to handle any event loops
    
    vera_instance = None
    
    # Initialize Vera if requested
    if not args.no_vera:
        print("🔵 Initializing Vera AI System...")
        print("=" * 60)
        
        try:
            # Add parent directory to path if needed
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            # Try multiple import paths
            try:
                from Vera import Vera
            except ImportError:
                try:
                    import Vera as VeraModule
                    Vera = VeraModule.Vera
                except ImportError:
                    # Last resort - try importing from current directory
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    sys.path.insert(0, current_dir)
                    from Vera import Vera
            
            # Initialize Vera with options
            vera_instance = Vera(
                config_file=args.config,
                enable_infrastructure=args.enable_infrastructure,
                enable_docker=args.enable_docker
            )
            
            print("✓ Vera initialized successfully!")
            print("=" * 60)
            print()
        
        except Exception as e:
            print(f"❌ Failed to initialize Vera: {e}")
            print("\nError details:")
            import traceback
            traceback.print_exc()
            print("\n⚠️  Launching TUI in view-only mode...")
            print()
            vera_instance = None
    
    # Launch TUI
    print("🖥️  Starting Vera Terminal UI...")
    print("=" * 60)
    print("Interface: Textual-based Terminal UI")
    print("Mode:", "Enhanced" if args.use_enhanced else "Standard")
    print("Vera:", "Loaded" if vera_instance else "Not loaded (view-only)")
    print("=" * 60)
    print()
    print("📌 Quick Tips:")
    print("   • Press F1 for help")
    print("   • Press Ctrl+Q to quit")
    print("   • Press Ctrl+S to submit queries")
    print()
    
    try:
        # Import TUI module
        if args.use_enhanced:
            print("Loading enhanced TUI...")
            from vera_tui_enhanced import run_enhanced_tui
            run_enhanced_tui(vera_instance=vera_instance)
        else:
            print("Loading standard TUI...")
            from vera_tui import run_tui
            run_tui(vera_instance=vera_instance, config_file=args.config)
    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    
    except Exception as e:
        print(f"\n❌ TUI Error: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n🔧 Troubleshooting:")
        print("   1. Check dependencies: pip install -r requirements_tui.txt")
        print("   2. Verify terminal size (minimum 80x24)")
        print("   3. Try: python -m vera_tui")
        print("   4. Check logs in ./logs/")
        
        sys.exit(1)


if __name__ == "__main__":
    main()