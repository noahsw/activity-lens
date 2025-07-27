#!/usr/bin/env python3
"""
Simple test runner for Activity Lens
Run this script to execute all tests before committing.
"""

import sys
import os
import subprocess

def run_tests():
    """Run all tests and return success/failure."""
    print("🧪 Running Activity Lens Tests")
    print("=" * 50)
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Run the main test runner
    try:
        result = subprocess.run([
            sys.executable, 
            os.path.join(script_dir, 'test_runner.py')
        ], capture_output=True, text=True, cwd=script_dir)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1) 