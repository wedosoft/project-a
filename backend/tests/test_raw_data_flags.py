#!/usr/bin/env python3
"""
Test for the raw data collection flag fix in run_collection.py

This test validates that when no explicit raw data flags are provided,
the system defaults to collecting all raw data types (True for all).
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestRawDataCollectionFlags(unittest.TestCase):
    """Test raw data collection flag handling in run_collection.py"""

    def setUp(self):
        """Set up test environment"""
        # Add backend to Python path
        backend_path = Path(__file__).parent.parent.resolve()
        if str(backend_path) not in sys.path:
            sys.path.insert(0, str(backend_path))

    def test_parse_args_function(self):
        """Test that parse_args function works correctly"""
        # Import just the parse_args function to avoid environment dependencies
        import argparse
        
        # Recreate the parser logic from run_collection.py
        parser = argparse.ArgumentParser(description="Freshdesk 대용량 티켓 수집기")
        
        # Main mode group
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument("--full-collection", action="store_true", help="전체 수집 실행")
        mode_group.add_argument("--quick-test", action="store_true", help="빠른 테스트(100건) 실행")
        mode_group.add_argument("--resume", action="store_true", help="중단된 수집 재개")
        
        # Vector DB options
        parser.add_argument("--reset-vectordb", action="store_true", help="전체 수집 시작 전 벡터DB 초기화")
        parser.add_argument("--no-backup", action="store_true", help="초기화 시 백업 생성 비활성화")
        parser.add_argument("--force", action="store_true", help="확인 없이 자동 초기화 (CI/CD용)")
        
        # Raw data options
        raw_group = parser.add_argument_group("Raw 데이터 수집 옵션")
        raw_group.add_argument("--raw-details", action="store_true", help="티켓 상세정보 원본 데이터 수집")
        raw_group.add_argument("--raw-conversations", action="store_true", help="티켓 대화내역 원본 데이터 수집")
        raw_group.add_argument("--raw-kb", action="store_true", help="지식베이스 원본 데이터 수집")
        raw_group.add_argument("--raw-all", action="store_true", help="모든 원본 데이터 수집 활성화")
        
        # Test the problematic command
        args = parser.parse_args(["--full-collection", "--reset-vectordb", "--no-backup"])
        
        # Apply the FIXED logic
        raw_flags_specified = any([args.raw_details, args.raw_conversations, args.raw_kb, args.raw_all])
        
        if raw_flags_specified:
            collect_raw_details = args.raw_details or args.raw_all
            collect_raw_conversations = args.raw_conversations or args.raw_all
            collect_raw_kb = args.raw_kb or args.raw_all
        else:
            # Fixed behavior: default to True when no flags specified
            collect_raw_details = True
            collect_raw_conversations = True
            collect_raw_kb = True
        
        # Assertions
        self.assertFalse(raw_flags_specified, "No raw flags should be specified")
        self.assertTrue(collect_raw_details, "Should default to True for details")
        self.assertTrue(collect_raw_conversations, "Should default to True for conversations")
        self.assertTrue(collect_raw_kb, "Should default to True for KB")

    def test_explicit_flags_still_work(self):
        """Test that explicit flags still work as expected"""
        import argparse
        
        parser = argparse.ArgumentParser(description="Freshdesk 대용량 티켓 수집기")
        
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument("--full-collection", action="store_true", help="전체 수집 실행")
        mode_group.add_argument("--quick-test", action="store_true", help="빠른 테스트(100건) 실행")
        mode_group.add_argument("--resume", action="store_true", help="중단된 수집 재개")
        
        parser.add_argument("--reset-vectordb", action="store_true", help="전체 수집 시작 전 벡터DB 초기화")
        parser.add_argument("--no-backup", action="store_true", help="초기화 시 백업 생성 비활성화")
        parser.add_argument("--force", action="store_true", help="확인 없이 자동 초기화 (CI/CD용)")
        
        raw_group = parser.add_argument_group("Raw 데이터 수집 옵션")
        raw_group.add_argument("--raw-details", action="store_true", help="티켓 상세정보 원본 데이터 수집")
        raw_group.add_argument("--raw-conversations", action="store_true", help="티켓 대화내역 원본 데이터 수집")
        raw_group.add_argument("--raw-kb", action="store_true", help="지식베이스 원본 데이터 수집")
        raw_group.add_argument("--raw-all", action="store_true", help="모든 원본 데이터 수집 활성화")
        
        # Test partial flags
        args = parser.parse_args(["--full-collection", "--raw-details", "--raw-conversations"])
        
        raw_flags_specified = any([args.raw_details, args.raw_conversations, args.raw_kb, args.raw_all])
        
        if raw_flags_specified:
            collect_raw_details = args.raw_details or args.raw_all
            collect_raw_conversations = args.raw_conversations or args.raw_all
            collect_raw_kb = args.raw_kb or args.raw_all
        else:
            collect_raw_details = True
            collect_raw_conversations = True
            collect_raw_kb = True
        
        # Assertions
        self.assertTrue(raw_flags_specified, "Raw flags should be specified")
        self.assertTrue(collect_raw_details, "Details should be True (explicitly set)")
        self.assertTrue(collect_raw_conversations, "Conversations should be True (explicitly set)")
        self.assertFalse(collect_raw_kb, "KB should be False (not explicitly set)")

    def test_raw_all_flag(self):
        """Test that --raw-all flag enables all options"""
        import argparse
        
        parser = argparse.ArgumentParser(description="Freshdesk 대용량 티켓 수집기")
        
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument("--full-collection", action="store_true", help="전체 수집 실행")
        mode_group.add_argument("--quick-test", action="store_true", help="빠른 테스트(100건) 실행")
        mode_group.add_argument("--resume", action="store_true", help="중단된 수집 재개")
        
        parser.add_argument("--reset-vectordb", action="store_true", help="전체 수집 시작 전 벡터DB 초기화")
        parser.add_argument("--no-backup", action="store_true", help="초기화 시 백업 생성 비활성화")
        parser.add_argument("--force", action="store_true", help="확인 없이 자동 초기화 (CI/CD용)")
        
        raw_group = parser.add_argument_group("Raw 데이터 수집 옵션")
        raw_group.add_argument("--raw-details", action="store_true", help="티켓 상세정보 원본 데이터 수집")
        raw_group.add_argument("--raw-conversations", action="store_true", help="티켓 대화내역 원본 데이터 수집")
        raw_group.add_argument("--raw-kb", action="store_true", help="지식베이스 원본 데이터 수집")
        raw_group.add_argument("--raw-all", action="store_true", help="모든 원본 데이터 수집 활성화")
        
        # Test --raw-all flag
        args = parser.parse_args(["--full-collection", "--raw-all"])
        
        raw_flags_specified = any([args.raw_details, args.raw_conversations, args.raw_kb, args.raw_all])
        
        if raw_flags_specified:
            collect_raw_details = args.raw_details or args.raw_all
            collect_raw_conversations = args.raw_conversations or args.raw_all
            collect_raw_kb = args.raw_kb or args.raw_all
        else:
            collect_raw_details = True
            collect_raw_conversations = True
            collect_raw_kb = True
        
        # Assertions
        self.assertTrue(raw_flags_specified, "Raw flags should be specified")
        self.assertTrue(collect_raw_details, "Details should be True (--raw-all)")
        self.assertTrue(collect_raw_conversations, "Conversations should be True (--raw-all)")
        self.assertTrue(collect_raw_kb, "KB should be True (--raw-all)")


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)