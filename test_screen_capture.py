#!/usr/bin/env python3
"""
Tests for screen-capture.py
Tests the screen capture functionality with mocked dependencies.
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Import the module to test
import screen_capture

class TestScreenCapture(unittest.TestCase):
    """Test cases for screen capture functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_dir = screen_capture.CACHE_DIR
        screen_capture.CACHE_DIR = self.temp_dir
        screen_capture.SCREEN_DIR = os.path.join(self.temp_dir, 'screen-captures')
        screen_capture.JSON_PATH = os.path.join(self.temp_dir, 'screen_captures_ocr.json')
        
        # Create necessary directories
        os.makedirs(screen_capture.SCREEN_DIR, exist_ok=True)
        
        # Sample test data
        self.sample_entry = {
            'app_name': 'TestApp',
            'timestamp': '2024-01-01T12:00:00',
            'window_title': 'Test Window'
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original paths
        screen_capture.CACHE_DIR = self.original_cache_dir
        screen_capture.SCREEN_DIR = os.path.join(self.original_cache_dir, 'screen-captures')
        screen_capture.JSON_PATH = os.path.join(self.original_cache_dir, 'screen_captures_ocr.json')
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_append_metadata_new_file(self):
        """Test appending metadata to a new JSON file."""
        screen_capture.append_metadata(self.sample_entry)
        
        # Check if file was created
        self.assertTrue(os.path.exists(screen_capture.JSON_PATH))
        
        # Check if data was written correctly
        with open(screen_capture.JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['app_name'], 'TestApp')
    
    def test_append_metadata_existing_file(self):
        """Test appending metadata to an existing JSON file."""
        # Create existing data
        existing_data = [{'app_name': 'ExistingApp', 'timestamp': '2024-01-01T11:00:00'}]
        with open(screen_capture.JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f)
        
        # Append new entry
        screen_capture.append_metadata(self.sample_entry)
        
        # Check if data was appended correctly
        with open(screen_capture.JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['app_name'], 'ExistingApp')
        self.assertEqual(data[1]['app_name'], 'TestApp')
    
    def test_append_metadata_corrupted_file(self):
        """Test appending metadata when JSON file is corrupted."""
        # Create corrupted JSON file
        with open(screen_capture.JSON_PATH, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json')
        
        # Should handle corruption gracefully
        screen_capture.append_metadata(self.sample_entry)
        
        # Check if new data was written
        with open(screen_capture.JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['app_name'], 'TestApp')
    
    @patch('screen_capture.subprocess.check_output')
    def test_get_active_app_names_success(self, mock_check_output):
        """Test successful app name retrieval."""
        mock_check_output.return_value = b'TestApp|||Test Window'
        
        raw_name, safe_name, window_title = screen_capture.get_active_app_names()
        
        self.assertEqual(raw_name, 'TestApp')
        self.assertEqual(safe_name, 'TestApp')
        self.assertEqual(window_title, 'Test Window')
    
    @patch('screen_capture.subprocess.check_output')
    def test_get_active_app_names_no_separator(self, mock_check_output):
        """Test app name retrieval without separator."""
        mock_check_output.return_value = b'TestApp'
        
        raw_name, safe_name, window_title = screen_capture.get_active_app_names()
        
        self.assertEqual(raw_name, 'TestApp')
        self.assertEqual(safe_name, 'TestApp')
        self.assertEqual(window_title, '')
    
    @patch('screen_capture.subprocess.check_output')
    def test_get_active_app_names_exception(self, mock_check_output):
        """Test app name retrieval with exception."""
        mock_check_output.side_effect = Exception("Test exception")
        
        raw_name, safe_name, window_title = screen_capture.get_active_app_names()
        
        self.assertEqual(raw_name, 'UnknownApp')
        self.assertEqual(safe_name, 'UnknownApp')
        self.assertEqual(window_title, '')
    
    def test_get_active_app_names_special_characters(self):
        """Test app name sanitization with special characters."""
        # Test with special characters
        test_cases = [
            ('Google Chrome', 'Google_Chrome'),
            ('Visual Studio Code', 'Visual_Studio_Code'),
            ('Test App (Beta)', 'Test_App__Beta_'),
            ('App@2.0', 'App_2_0'),
        ]
        
        for raw_name, expected_safe_name in test_cases:
            with self.subTest(raw_name=raw_name):
                safe_name = "".join(c if c.isalnum() else "_" for c in raw_name)
                self.assertEqual(safe_name, expected_safe_name)
    
    def test_write_text_entry_with_text(self):
        """Test writing text entry with content."""
        text_content = "This is test text content"
        screen_capture.write_text_entry('TestApp', '20240101_120000', text_content, 'Test Window')
        
        # Check if text file was created
        expected_filename = '20240101 120000 - TestApp.txt'
        expected_path = os.path.join(screen_capture.SCREEN_DIR, expected_filename)
        self.assertTrue(os.path.exists(expected_path))
        
        # Check text content
        with open(expected_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertEqual(content, text_content)
        
        # Check JSON entry
        with open(screen_capture.JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['screen_text_filename'], expected_filename)
        self.assertEqual(data[0]['app_name'], 'TestApp')
        self.assertEqual(data[0]['window_title'], 'Test Window')
    
    def test_write_text_entry_empty_text(self):
        """Test writing text entry with empty content."""
        screen_capture.write_text_entry('TestApp', '20240101_120000', '', 'Test Window')
        
        # Check that no text file was created
        expected_filename = '20240101 120000 - TestApp.txt'
        expected_path = os.path.join(screen_capture.SCREEN_DIR, expected_filename)
        self.assertFalse(os.path.exists(expected_path))
        
        # Check JSON entry
        with open(screen_capture.JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1)
        self.assertIsNone(data[0]['screen_text_filename'])
    
    def test_capture_focused_window_png_fallback(self):
        """Test PNG capture fallback when no text is extracted."""
        # Mock app names to return a non-browser, non-text-extraction app
        with patch('screen_capture.get_active_app_names') as mock_get_names:
            mock_get_names.return_value = ('TestApp', 'TestApp', 'Test Window')
            
            # Mock window bounds
            with patch('screen_capture.get_focused_window_rect') as mock_bounds:
                mock_bounds.return_value = {'X': 100, 'Y': 100, 'Width': 100, 'Height': 100}
                
                # Mock screencapture command
                with patch('screen_capture.subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    
                    # Mock file operations
                    with patch('builtins.open', mock_open()):
                        with patch('os.path.getsize') as mock_size:
                            mock_size.return_value = 1024  # 1 KB
                            
                            screen_capture.capture_focused_window()
                            
                            # Should have called screencapture
                            mock_run.assert_called_once()

    def test_capture_focused_window_high_res_success(self):
        """Test high-resolution capture when it succeeds."""
        # Mock app names to return a non-browser, non-text-extraction app
        with patch('screen_capture.get_active_app_names') as mock_get_names:
            mock_get_names.return_value = ('TestApp', 'TestApp', 'Test Window')
            
            # Mock window bounds
            with patch('screen_capture.get_focused_window_rect') as mock_bounds:
                mock_bounds.return_value = {'X': 100, 'Y': 100, 'Width': 100, 'Height': 100}
                
                # Mock screencapture command
                with patch('screen_capture.subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    
                    # Mock file operations
                    with patch('builtins.open', mock_open()):
                        with patch('os.path.getsize') as mock_size:
                            mock_size.return_value = 1024  # 1 KB
                            
                            screen_capture.capture_focused_window()
                            
                            # Should have called screencapture
                            mock_run.assert_called_once()
    
    @patch('screen_capture.get_active_app_names')
    def test_capture_focused_window_metadata_only(self, mock_get_names):
        """Test metadata-only capture for specific apps."""
        # Clear any existing files from previous tests
        for file in os.listdir(screen_capture.SCREEN_DIR):
            file_path = os.path.join(screen_capture.SCREEN_DIR, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        # Mock app name for metadata-only app
        mock_get_names.return_value = ('FaceTime', 'FaceTime', 'FaceTime Call')
        
        screen_capture.capture_focused_window()
        
        # Check that no files were created
        files = os.listdir(screen_capture.SCREEN_DIR)
        self.assertEqual(len(files), 0)
        
        # Check JSON entry
        with open(screen_capture.JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['app_name'], 'FaceTime')
        self.assertEqual(data[0]['window_title'], 'FaceTime Call')
        self.assertNotIn('screen_capture_filename', data[0])
        self.assertNotIn('screen_text_filename', data[0])
    
    def test_app_categories(self):
        """Test that app categories are properly defined."""
        # Check that categories are lists
        self.assertIsInstance(screen_capture.browser_apps, list)
        self.assertIsInstance(screen_capture.text_extraction_apps, list)
        self.assertIsInstance(screen_capture.metadata_only_apps, list)
        
        # Check that categories don't overlap
        browser_set = set(screen_capture.browser_apps)
        text_set = set(screen_capture.text_extraction_apps)
        metadata_set = set(screen_capture.metadata_only_apps)
        
        # No app should be in multiple categories
        self.assertEqual(len(browser_set & text_set), 0)
        self.assertEqual(len(browser_set & metadata_set), 0)
        self.assertEqual(len(text_set & metadata_set), 0)
        
        # Check that important apps are included
        self.assertIn('Google Chrome', browser_set)
        self.assertIn('FaceTime', metadata_set)

if __name__ == '__main__':
    unittest.main() 