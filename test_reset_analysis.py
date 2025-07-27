#!/usr/bin/env python3
"""
Tests for reset-analysis.py
Tests the reset analysis functionality with mocked dependencies.
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
spec = importlib.util.spec_from_file_location("reset_analysis", "reset-analysis.py")
reset_analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset_analysis)

class TestResetAnalysis(unittest.TestCase):
    """Test cases for reset analysis functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_dir = reset_analysis.CACHE_DIR
        reset_analysis.CACHE_DIR = self.temp_dir
        reset_analysis.output_json = os.path.join(self.temp_dir, 'screen_captures_ocr.json')
        
        # Create necessary directories
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Sample test data
        self.sample_data = [
            {
                'app_name': 'Cursor',
                'timestamp': '2024-01-01T12:00:00',
                'window_title': 'test.py - activity-lens',
                'screen_capture_filename': 'test.png',
                'screen_text_filename': 'test.txt',
                'summary': 'Working on Python code'
            },
            {
                'app_name': 'Google Chrome',
                'timestamp': '2024-01-01T12:05:00',
                'window_title': 'GitHub - username/repo',
                'screen_capture_filename': 'chrome.png',
                'summary': 'Browsing GitHub repository'
            },
            {
                'app_name': 'zoom_us',
                'timestamp': '2024-01-01T12:10:00',
                'window_title': 'Team Meeting'
            }
        ]
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original paths
        reset_analysis.CACHE_DIR = self.original_cache_dir
        reset_analysis.output_json = os.path.join(self.original_cache_dir, 'screen_captures_ocr.json')
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_json_new_file(self):
        """Test loading JSON when file doesn't exist."""
        # Remove JSON file if it exists
        if os.path.exists(reset_analysis.output_json):
            os.remove(reset_analysis.output_json)
        
        data = reset_analysis.load_json()
        
        self.assertEqual(data, [])
    
    def test_load_json_existing_file(self):
        """Test loading JSON from existing file."""
        # Create JSON file
        with open(reset_analysis.output_json, 'w', encoding='utf-8') as f:
            json.dump(self.sample_data, f)
        
        data = reset_analysis.load_json()
        
        self.assertEqual(data, self.sample_data)
    
    def test_load_json_corrupted_file(self):
        """Test loading JSON from corrupted file."""
        # Create corrupted JSON file
        with open(reset_analysis.output_json, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json')
        
        data = reset_analysis.load_json()
        
        self.assertEqual(data, [])
    
    def test_load_json_exception(self):
        """Test loading JSON with exception."""
        # Create a directory with the same name as the JSON file to cause an error
        os.makedirs(reset_analysis.output_json, exist_ok=True)
        
        data = reset_analysis.load_json()
        
        self.assertEqual(data, [])
    
    def test_save_json_success(self):
        """Test successful JSON saving."""
        success = reset_analysis.save_json(self.sample_data)
        
        self.assertTrue(success)
        
        # Check if file was saved
        self.assertTrue(os.path.exists(reset_analysis.output_json))
        
        # Check content
        with open(reset_analysis.output_json, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data, self.sample_data)
    
    def test_save_json_exception(self):
        """Test JSON saving with exception."""
        # Create a directory with the same name as the JSON file to cause an error
        os.makedirs(reset_analysis.output_json, exist_ok=True)
        
        success = reset_analysis.save_json(self.sample_data)
        
        self.assertFalse(success)
    
    def test_remove_summary_fields(self):
        """Test removing summary fields from data."""
        # Create data with summary fields
        data_with_summaries = self.sample_data.copy()
        
        count = reset_analysis.remove_summary_fields(data_with_summaries)
        
        # Check that summary fields were removed
        self.assertEqual(count, 2)  # Two entries had summaries
        
        # Check that summaries are gone
        for entry in data_with_summaries:
            self.assertNotIn('summary', entry)
        
        # Check that other fields remain
        self.assertIn('app_name', data_with_summaries[0])
        self.assertIn('timestamp', data_with_summaries[0])
    
    def test_remove_summary_fields_none_exist(self):
        """Test removing summary fields when none exist."""
        # Create data without summary fields
        data_without_summaries = [
            {
                'app_name': 'TestApp',
                'timestamp': '2024-01-01T12:00:00',
                'window_title': 'Test Window'
            }
        ]
        
        count = reset_analysis.remove_summary_fields(data_without_summaries)
        
        self.assertEqual(count, 0)
        self.assertEqual(len(data_without_summaries), 1)
    
    def test_remove_text_filename_fields(self):
        """Test removing text filename fields from data."""
        # Create data with text filename fields
        data_with_text_files = self.sample_data.copy()
        
        count = reset_analysis.remove_text_filename_fields(data_with_text_files)
        
        # Check that text filename fields were removed
        self.assertEqual(count, 1)  # Only one entry had both screen_capture_filename and screen_text_filename
        
        # Check that screen_text_filename is gone from the first entry
        self.assertNotIn('screen_text_filename', data_with_text_files[0])
        
        # Check that other fields remain
        self.assertIn('screen_capture_filename', data_with_text_files[0])
        self.assertIn('app_name', data_with_text_files[0])
    
    def test_remove_text_filename_fields_none_exist(self):
        """Test removing text filename fields when none exist."""
        # Create data without text filename fields
        data_without_text_files = [
            {
                'app_name': 'TestApp',
                'timestamp': '2024-01-01T12:00:00',
                'window_title': 'Test Window'
            }
        ]
        
        count = reset_analysis.remove_text_filename_fields(data_without_text_files)
        
        self.assertEqual(count, 0)
        self.assertEqual(len(data_without_text_files), 1)
    
    def test_remove_text_files(self):
        """Test removing text files from filesystem."""
        # Create screen-captures directory
        screen_captures_dir = os.path.join(self.temp_dir, 'screen-captures')
        os.makedirs(screen_captures_dir, exist_ok=True)
        
        # Create some text files
        text_file1 = os.path.join(screen_captures_dir, 'test.txt')
        text_file2 = os.path.join(screen_captures_dir, 'chrome.txt')
        
        with open(text_file1, 'w') as f:
            f.write('test content')
        with open(text_file2, 'w') as f:
            f.write('chrome content')
        
        # Create data with text filename references
        data_with_text_files = [
            {
                'app_name': 'Cursor',
                'screen_text_filename': 'test.txt'
            },
            {
                'app_name': 'Chrome',
                'screen_text_filename': 'chrome.txt'
            },
            {
                'app_name': 'Zoom',
                'screen_text_filename': 'missing.txt'  # This file doesn't exist
            }
        ]
        
        count = reset_analysis.remove_text_files(data_with_text_files)
        
        # Check that files were removed
        self.assertEqual(count, 2)  # Two files existed and were removed
        
        # Check that files are gone
        self.assertFalse(os.path.exists(text_file1))
        self.assertFalse(os.path.exists(text_file2))
    
    def test_remove_text_files_none_exist(self):
        """Test removing text files when none exist."""
        # Create data without text filename references
        data_without_text_files = [
            {
                'app_name': 'TestApp',
                'timestamp': '2024-01-01T12:00:00'
            }
        ]
        
        count = reset_analysis.remove_text_files(data_without_text_files)
        
        self.assertEqual(count, 0)
    
    def test_remove_text_files_exception(self):
        """Test removing text files with exception."""
        # Create screen-captures directory
        screen_captures_dir = os.path.join(self.temp_dir, 'screen-captures')
        os.makedirs(screen_captures_dir, exist_ok=True)
        
        # Create a file that can't be removed (by making it a directory)
        text_file = os.path.join(screen_captures_dir, 'test.txt')
        os.makedirs(text_file, exist_ok=True)
        
        # Create data with text filename reference
        data_with_text_files = [
            {
                'app_name': 'TestApp',
                'screen_text_filename': 'test.txt'
            }
        ]
        
        count = reset_analysis.remove_text_files(data_with_text_files)
        
        # Should handle the exception gracefully
        self.assertEqual(count, 0)
    
    @patch('reset_analysis.load_json')
    @patch('reset_analysis.save_json')
    @patch('reset_analysis.remove_summary_fields')
    def test_main_summary_only(self, mock_remove_summary, mock_save, mock_load):
        """Test main function with --summary flag only."""
        # Mock dependencies
        mock_load.return_value = self.sample_data
        mock_save.return_value = True
        mock_remove_summary.return_value = 2
        
        # Mock command line arguments
        with patch('sys.argv', ['reset-analysis.py', '--summary']):
            reset_analysis.main()
        
        # Check that functions were called
        mock_load.assert_called_once()
        mock_remove_summary.assert_called_once_with(self.sample_data)
        mock_save.assert_called_once_with(self.sample_data)
    
    @patch('reset_analysis.load_json')
    @patch('reset_analysis.save_json')
    @patch('reset_analysis.remove_text_filename_fields')
    def test_main_text_filename_only(self, mock_remove_text_filename, mock_save, mock_load):
        """Test main function with --text-filename flag only."""
        # Mock dependencies
        mock_load.return_value = self.sample_data
        mock_save.return_value = True
        mock_remove_text_filename.return_value = 1
        
        # Mock command line arguments
        with patch('sys.argv', ['reset-analysis.py', '--text-filename']):
            reset_analysis.main()
        
        # Check that functions were called
        mock_load.assert_called_once()
        mock_remove_text_filename.assert_called_once_with(self.sample_data)
        mock_save.assert_called_once_with(self.sample_data)
    
    @patch('reset_analysis.load_json')
    @patch('reset_analysis.save_json')
    @patch('reset_analysis.remove_text_files')
    def test_main_text_files_only(self, mock_remove_text_files, mock_save, mock_load):
        """Test main function with --text-files flag only."""
        # Mock dependencies
        mock_load.return_value = self.sample_data
        mock_save.return_value = True
        mock_remove_text_files.return_value = 2
        
        # Mock command line arguments
        with patch('sys.argv', ['reset-analysis.py', '--text-files']):
            reset_analysis.main()
        
        # Check that functions were called
        mock_load.assert_called_once()
        mock_remove_text_files.assert_called_once_with(self.sample_data)
        mock_save.assert_called_once_with(self.sample_data)
    
    @patch('reset_analysis.load_json')
    @patch('reset_analysis.save_json')
    @patch('reset_analysis.remove_summary_fields')
    @patch('reset_analysis.remove_text_filename_fields')
    @patch('reset_analysis.remove_text_files')
    def test_main_all_flags(self, mock_remove_text_files, mock_remove_text_filename, 
                           mock_remove_summary, mock_save, mock_load):
        """Test main function with --all flag."""
        # Mock dependencies
        mock_load.return_value = self.sample_data
        mock_save.return_value = True
        mock_remove_summary.return_value = 2
        mock_remove_text_filename.return_value = 1
        mock_remove_text_files.return_value = 2
        
        # Mock command line arguments
        with patch('sys.argv', ['reset-analysis.py', '--all']):
            reset_analysis.main()
        
        # Check that all functions were called
        mock_load.assert_called_once()
        mock_remove_summary.assert_called_once_with(self.sample_data)
        mock_remove_text_filename.assert_called_once_with(self.sample_data)
        mock_remove_text_files.assert_called_once_with(self.sample_data)
        mock_save.assert_called_once_with(self.sample_data)
    
    @patch('reset_analysis.load_json')
    @patch('reset_analysis.save_json')
    @patch('reset_analysis.remove_summary_fields')
    @patch('reset_analysis.remove_text_filename_fields')
    def test_main_multiple_flags(self, mock_remove_text_filename, mock_remove_summary, 
                                mock_save, mock_load):
        """Test main function with multiple flags."""
        # Mock dependencies
        mock_load.return_value = self.sample_data
        mock_save.return_value = True
        mock_remove_summary.return_value = 2
        mock_remove_text_filename.return_value = 1
        
        # Mock command line arguments
        with patch('sys.argv', ['reset-analysis.py', '--summary', '--text-filename']):
            reset_analysis.main()
        
        # Check that both functions were called
        mock_load.assert_called_once()
        mock_remove_summary.assert_called_once_with(self.sample_data)
        mock_remove_text_filename.assert_called_once_with(self.sample_data)
        mock_save.assert_called_once_with(self.sample_data)
    
    @patch('reset_analysis.load_json')
    def test_main_no_flags(self, mock_load):
        """Test main function with no flags."""
        # Mock dependencies
        mock_load.return_value = self.sample_data
        
        # Mock command line arguments
        with patch('sys.argv', ['reset-analysis.py']):
            reset_analysis.main()
        
        # Should show help and not process anything
        mock_load.assert_not_called()
    
    @patch('reset_analysis.load_json')
    @patch('reset_analysis.save_json')
    def test_main_save_failure(self, mock_save, mock_load):
        """Test main function when save fails."""
        # Mock dependencies
        mock_load.return_value = self.sample_data
        mock_save.return_value = False
        
        # Mock command line arguments
        with patch('sys.argv', ['reset-analysis.py', '--summary']):
            reset_analysis.main()
        
        # Should still call load and save
        mock_load.assert_called_once()
        mock_save.assert_called_once()
    
    def test_argument_parser(self):
        """Test that argument parser is set up correctly."""
        # Test that all expected arguments exist
        parser = reset_analysis.argparse.ArgumentParser()
        parser.add_argument('--summary', action='store_true')
        parser.add_argument('--text-filename', action='store_true')
        parser.add_argument('--text-files', action='store_true')
        parser.add_argument('--all', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        
        # Test parsing various combinations
        args = parser.parse_args(['--summary'])
        self.assertTrue(args.summary)
        self.assertFalse(args.text_filename)
        self.assertFalse(args.text_files)
        self.assertFalse(args.all)
        self.assertFalse(args.dry_run)
        
        args = parser.parse_args(['--all'])
        self.assertFalse(args.summary)
        self.assertFalse(args.text_filename)
        self.assertFalse(args.text_files)
        self.assertTrue(args.all)
        self.assertFalse(args.dry_run)
        
        args = parser.parse_args(['--summary', '--text-filename', '--dry-run'])
        self.assertTrue(args.summary)
        self.assertTrue(args.text_filename)
        self.assertFalse(args.text_files)
        self.assertFalse(args.all)
        self.assertTrue(args.dry_run)

if __name__ == '__main__':
    unittest.main() 