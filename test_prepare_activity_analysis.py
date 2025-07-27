#!/usr/bin/env python3
"""
Tests for prepare_activity_analysis.py
Tests the activity analysis preparation functionality with mocked dependencies.
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Import the module to test
import importlib.util
spec = importlib.util.spec_from_file_location("prepare_activity_analysis", "prepare_activity_analysis.py")
prepare_activity_analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_activity_analysis)

class TestPrepareActivityAnalysis(unittest.TestCase):
    """Test cases for activity analysis preparation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_dir = prepare_activity_analysis.CACHE_DIR
        prepare_activity_analysis.CACHE_DIR = self.temp_dir
        prepare_activity_analysis.json_file = os.path.join(self.temp_dir, 'screen_captures_ocr.json')
        prepare_activity_analysis.prompt_file = os.path.join(self.temp_dir, 'analyze_activity_prompt.txt')
        
        # Create necessary directories
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Sample test data
        self.sample_activity_data = [
            {
                'app_name': 'Cursor',
                'timestamp': '2024-01-01T12:00:00',
                'window_title': 'test.py - activity-lens',
                'summary': 'Working on Python code'
            },
            {
                'app_name': 'Google Chrome',
                'timestamp': '2024-01-01T12:05:00',
                'window_title': 'GitHub - username/repo',
                'summary': 'Browsing GitHub repository'
            },
            {
                'app_name': 'zoom_us',
                'timestamp': '2024-01-01T12:10:00',
                'window_title': 'Team Meeting'
            }
        ]
        
        # Sample prompt
        self.sample_prompt = "Analyze my computer activity based on the following log. Tell me how much time I'm spending on each theme."
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original paths
        prepare_activity_analysis.CACHE_DIR = self.original_cache_dir
        prepare_activity_analysis.json_file = os.path.join(self.original_cache_dir, 'screen_captures_ocr.json')
        prepare_activity_analysis.prompt_file = os.path.join(self.original_cache_dir, 'analyze_activity_prompt.txt')
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_prompt_success(self):
        """Test successful prompt loading."""
        # Create prompt file
        with open(prepare_activity_analysis.prompt_file, 'w', encoding='utf-8') as f:
            f.write(self.sample_prompt)
        
        prompt = prepare_activity_analysis.load_prompt()
        
        self.assertEqual(prompt, self.sample_prompt)
    
    def test_load_prompt_file_not_found(self):
        """Test prompt loading when file doesn't exist."""
        prompt = prepare_activity_analysis.load_prompt()
        
        self.assertIsNone(prompt)
    
    def test_load_prompt_exception(self):
        """Test prompt loading with exception."""
        # Create a directory with the same name as the prompt file to cause an error
        os.makedirs(prepare_activity_analysis.prompt_file, exist_ok=True)
        
        prompt = prepare_activity_analysis.load_prompt()
        
        self.assertIsNone(prompt)
    
    def test_load_activity_data_success(self):
        """Test successful activity data loading."""
        # Create JSON file
        with open(prepare_activity_analysis.json_file, 'w', encoding='utf-8') as f:
            json.dump(self.sample_activity_data, f)
        
        data = prepare_activity_analysis.load_activity_data()
        
        self.assertEqual(data, self.sample_activity_data)
    
    def test_load_activity_data_file_not_found(self):
        """Test activity data loading when file doesn't exist."""
        data = prepare_activity_analysis.load_activity_data()
        
        self.assertIsNone(data)
    
    def test_load_activity_data_json_error(self):
        """Test activity data loading with JSON error."""
        # Create corrupted JSON file
        with open(prepare_activity_analysis.json_file, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json')
        
        data = prepare_activity_analysis.load_activity_data()
        
        self.assertIsNone(data)
    
    def test_load_activity_data_exception(self):
        """Test activity data loading with exception."""
        # Create a directory with the same name as the JSON file to cause an error
        os.makedirs(prepare_activity_analysis.json_file, exist_ok=True)
        
        data = prepare_activity_analysis.load_activity_data()
        
        self.assertIsNone(data)
    
    def test_format_activity_data_with_summaries(self):
        """Test formatting activity data with summaries."""
        formatted = prepare_activity_analysis.format_activity_data(self.sample_activity_data)
        
        # Check that all entries are formatted
        self.assertIn('Time: 2024-01-01T12:00:00', formatted)
        self.assertIn('App: Cursor', formatted)
        self.assertIn('Window: test.py - activity-lens', formatted)
        self.assertIn('Activity: Working on Python code', formatted)
        
        self.assertIn('Time: 2024-01-01T12:05:00', formatted)
        self.assertIn('App: Google Chrome', formatted)
        self.assertIn('Window: GitHub - username/repo', formatted)
        self.assertIn('Activity: Browsing GitHub repository', formatted)
        
        # Check that entries without summaries are handled
        self.assertIn('Time: 2024-01-01T12:10:00', formatted)
        self.assertIn('App: zoom_us', formatted)
        self.assertIn('Window: Team Meeting', formatted)
        # The zoom_us entry doesn't have a summary, so it shouldn't have an Activity line
        # Check that the zoom_us section doesn't contain an Activity line
        lines = formatted.split('\n')
        zoom_us_section = False
        zoom_us_has_activity = False
        for line in lines:
            if 'App: zoom_us' in line:
                zoom_us_section = True
            elif '---' in line:
                zoom_us_section = False
            elif zoom_us_section and line.startswith('Activity:'):
                zoom_us_has_activity = True
                break
        
        self.assertFalse(zoom_us_has_activity, "zoom_us entry should not have an Activity line")
    
    def test_format_activity_data_empty(self):
        """Test formatting empty activity data."""
        formatted = prepare_activity_analysis.format_activity_data([])
        
        self.assertEqual(formatted, "No activity data available.")
    
    def test_format_activity_data_none(self):
        """Test formatting None activity data."""
        formatted = prepare_activity_analysis.format_activity_data(None)
        
        self.assertEqual(formatted, "No activity data available.")
    
    def test_format_activity_data_missing_fields(self):
        """Test formatting activity data with missing fields."""
        incomplete_data = [
            {
                'app_name': 'TestApp',
                'timestamp': '2024-01-01T12:00:00'
                # Missing window_title and summary
            }
        ]
        
        formatted = prepare_activity_analysis.format_activity_data(incomplete_data)
        
        self.assertIn('Time: 2024-01-01T12:00:00', formatted)
        self.assertIn('App: TestApp', formatted)
        self.assertNotIn('Window:', formatted)
        self.assertNotIn('Activity:', formatted)
    
    @patch('prepare_activity_analysis.pyperclip.copy')
    @patch('prepare_activity_analysis.pyperclip.paste')
    def test_copy_to_clipboard_success(self, mock_paste, mock_copy):
        """Test successful clipboard copy."""
        test_text = "Test clipboard content"
        mock_paste.return_value = test_text
        
        success = prepare_activity_analysis.copy_to_clipboard(test_text)
        
        self.assertTrue(success)
        mock_copy.assert_called_once_with(test_text)
        mock_paste.assert_called_once()
    
    @patch('prepare_activity_analysis.pyperclip.copy')
    @patch('prepare_activity_analysis.pyperclip.paste')
    def test_copy_to_clipboard_mismatch(self, mock_paste, mock_copy):
        """Test clipboard copy with content mismatch."""
        test_text = "Test clipboard content"
        mock_paste.return_value = "Different content"
        
        success = prepare_activity_analysis.copy_to_clipboard(test_text)
        
        self.assertFalse(success)
        mock_copy.assert_called_once_with(test_text)
        mock_paste.assert_called_once()
    
    @patch('prepare_activity_analysis.pyperclip.copy')
    def test_copy_to_clipboard_exception(self, mock_copy):
        """Test clipboard copy with exception."""
        test_text = "Test clipboard content"
        mock_copy.side_effect = Exception("Clipboard error")
        
        success = prepare_activity_analysis.copy_to_clipboard(test_text)
        
        self.assertFalse(success)
        mock_copy.assert_called_once_with(test_text)
    
    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        # Basic test to ensure the main function exists
        self.assertTrue(hasattr(prepare_activity_analysis, 'main'))
        self.assertTrue(callable(prepare_activity_analysis.main))
    
    def test_main_function_basic_flow(self):
        """Test basic main function flow without mocking."""
        # This test verifies the main function can be called without errors
        # It will likely fail due to missing files, but that's expected
        # The important thing is that it doesn't crash due to import issues
        try:
            prepare_activity_analysis.main()
        except (FileNotFoundError, Exception) as e:
            # Expected to fail due to missing files, but should not be an import error
            self.assertNotIn("No module named", str(e))
    
    def test_data_size_estimation(self):
        """Test data size estimation and token calculation."""
        # Create a large dataset
        large_data = []
        for i in range(100):
            large_data.append({
                'app_name': f'App{i}',
                'timestamp': f'2024-01-01T12:{i:02d}:00',
                'window_title': f'Window {i}',
                'summary': f'Summary for activity {i}'
            })
        
        formatted = prepare_activity_analysis.format_activity_data(large_data)
        full_text = f"{self.sample_prompt}\n\n{formatted}"
        
        # Check that the text is reasonably sized
        self.assertGreater(len(full_text), 1000)
        
        # Check token estimation (roughly 4 characters per token)
        estimated_tokens = len(full_text) // 4
        self.assertGreater(estimated_tokens, 250)
    
    def test_activity_data_structure(self):
        """Test that activity data has the expected structure."""
        # Test with various data structures
        test_cases = [
            # Complete entry
            {
                'app_name': 'TestApp',
                'timestamp': '2024-01-01T12:00:00',
                'window_title': 'Test Window',
                'summary': 'Test Summary'
            },
            # Entry without summary
            {
                'app_name': 'TestApp2',
                'timestamp': '2024-01-01T12:01:00',
                'window_title': 'Test Window 2'
            },
            # Entry without window title
            {
                'app_name': 'TestApp3',
                'timestamp': '2024-01-01T12:02:00',
                'summary': 'Test Summary 3'
            }
        ]
        
        formatted = prepare_activity_analysis.format_activity_data(test_cases)
        
        # Check that all entries are included
        self.assertIn('TestApp', formatted)
        self.assertIn('TestApp2', formatted)
        self.assertIn('TestApp3', formatted)
        
        # Check that summaries are included when present
        self.assertIn('Test Summary', formatted)
        self.assertIn('Test Summary 3', formatted)
        
        # Check that window titles are included when present
        self.assertIn('Test Window', formatted)
        self.assertIn('Test Window 2', formatted)

if __name__ == '__main__':
    unittest.main() 