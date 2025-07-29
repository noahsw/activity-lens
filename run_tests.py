#!/usr/bin/env python3
"""
Simplified Test Runner for Activity Lens
Directly imports and runs all tests without complex module copying.
"""

import sys
import os
import time
import unittest
import importlib.util

def load_module_from_file(module_name, file_path):
    """Load a Python module from a file path, even with hyphens in the name."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def run_tests():
    """Run all test suites and return results."""
    print("🧪 Running Activity Lens Tests (Simplified)")
    print("=" * 50)
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add current directory to path for imports
    sys.path.insert(0, script_dir)
    
    # Define test modules and their corresponding main modules
    test_configs = [
        {
            'test_module': 'test_prepare_activity_analysis',
            'main_module': 'prepare_activity_analysis',
            'main_file': 'prepare_activity_analysis.py'
        },
        {
            'test_module': 'test_screen_capture', 
            'main_module': 'screen_capture',
            'main_file': 'screen-capture.py'
        },
        {
            'test_module': 'test_analyze_screen_captures',
            'main_module': 'analyze_screen_captures', 
            'main_file': 'analyze-screen-captures.py'
        },
        {
            'test_module': 'test_reset_analysis',
            'main_module': 'reset_analysis',
            'main_file': 'reset-analysis.py'
        }
    ]
    
    # Load and run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for config in test_configs:
        test_module_name = config['test_module']
        main_module_name = config['main_module']
        main_file_path = os.path.join(script_dir, config['main_file']) if config['main_file'] else None
        
        try:
            # Load the main module (with hyphenated filename) into sys.modules
            if main_file_path and os.path.exists(main_file_path):
                main_module = load_module_from_file(main_module_name, main_file_path)
                sys.modules[main_module_name] = main_module
            
            # Import and load the test module
            test_module = __import__(test_module_name)
            tests = loader.loadTestsFromModule(test_module)
            suite.addTests(tests)
            print(f"✓ Loaded tests from {test_module_name}")
            
        except Exception as e:
            print(f"✗ Failed to load {test_module_name}: {e}")
    
    # Run tests
    print(f"\n🏃 Running {suite.countTestCases()} tests...")
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Time: {end_time - start_time:.2f} seconds")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n💥 ERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    # Return success/failure
    success = len(result.failures) == 0 and len(result.errors) == 0
    if success:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ {len(result.failures) + len(result.errors)} test(s) failed!")
    
    return success

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1) 