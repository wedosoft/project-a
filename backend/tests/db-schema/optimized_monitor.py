#!/usr/bin/env python3
"""
최적화된 스키마용 모니터링 도구

새로운 정규화된 스키마에서 요약 처리 현황을 모니터링
"""

import sqlite3
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import argparse
import sys

def setup_matplotlib():
    """matplotlib 설정"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        plt.rcParams['font.family'] = 'DejaVu Sans'
        sns.set_style("whitegrid")
        return True
    except ImportError:
        print("Warning: matplotlib/seaborn not available. Charts will not be generated.")
        return False

HAS_PLOTTING = setup_matplotlib()


class OptimizedSummarizationMonitor:
    """최적화된 요약 모니터링 클래스"""
    
    def __init__(self, db_path: str, results_dir: str = "./optimized_batch_results"):
        self.db_path = db_path
        self.results_dir = Path(results_dir)
        
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """종합 통계 조회"""
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            stats = {}
            
            # 기본 티켓 통계
            cursor = conn.execute("SELECT COUNT(*) FROM tickets")
            stats['total_tickets'] = cursor.fetchone()[0]
            
            # 요약 통계
            cursor = conn.execute("SELECT COUNT(*) FROM summaries WHERE is_active = 1")
            stats['total_summaries'] = cursor.fetchone()[0]
            
            # 고품질 요약 수
            cursor = conn.execute("SELECT COUNT(*) FROM summaries WHERE is_active = 1 AND quality_score >= 0.9")
            stats['high_quality_summaries'] = cursor.fetchone()[0]
            
            # 평균 품질 점수
            cursor = conn.execute("SELECT AVG(quality_score) FROM summaries WHERE is_active = 1")
            avg_quality = cursor.fetchone()[0]
            stats['average_quality_score'] = avg_quality if avg_quality else 0.0
            
            # 처리 대기 티켓 (뷰 활용)
            cursor = conn.execute("SELECT COUNT(*) FROM v_pending_summaries")
            stats['pending_tickets'] = cursor.fetchone()[0]
            
            # 총 비용 추정
            cursor = conn.execute("SELECT SUM(cost_estimate) FROM summaries WHERE is_active = 1")
            total_cost = cursor.fetchone()[0]
            stats['total_cost_estimate'] = total_cost if total_cost else 0.0
            
            # 총 토큰 사용량
            cursor = conn.execute("SELECT SUM(tokens_input + tokens_output) FROM summaries WHERE is_active = 1")
            total_tokens = cursor.fetchone()[0]
            stats['total_tokens_used'] = total_tokens if total_tokens else 0
            
            # 평균 처리 시간
            cursor = conn.execute("SELECT AVG(processing_time_ms) FROM summaries WHERE is_active = 1")
            avg_time = cursor.fetchone()[0]
            stats['average_processing_time_ms'] = avg_time if avg_time else 0.0
            
            # 재시도 통계
            cursor = conn.execute("SELECT AVG(retry_count), MAX(retry_count) FROM summaries WHERE is_active = 1")
            retry_stats = cursor.fetchone()
            stats['average_retry_count'] = retry_stats[0] if retry_stats[0] else 0.0
            stats['max_retry_count'] = retry_stats[1] if retry_stats[1] else 0
            
            # 계산된 통계
            if stats['total_tickets'] > 0:
                stats['completion_rate'] = (stats['total_summaries'] / stats['total_tickets']) * 100
            else:
                stats['completion_rate'] = 0.0
                
            if stats['total_summaries'] > 0:
                stats['high_quality_rate'] = (stats['high_quality_summaries'] / stats['total_summaries']) * 100
                stats['average_cost_per_summary'] = stats['total_cost_estimate'] / stats['total_summaries']
            else:
                stats['high_quality_rate'] = 0.0
                stats['average_cost_per_summary'] = 0.0
            
            return stats
            
        finally:
            conn.close()
    
    def get_processing_timeline(self) -> pd.DataFrame:
        """처리 시간별 진행 상황"""
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
            SELECT 
                DATE(created_at) as processing_date,
                COUNT(*) as summaries_created,
                AVG(quality_score) as avg_quality,
                SUM(cost_estimate) as daily_cost,
                AVG(processing_time_ms) as avg_processing_time
            FROM summaries 
            WHERE is_active = 1
            GROUP BY DATE(created_at)
            ORDER BY processing_date DESC
            LIMIT 30
            """
            
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                df['processing_date'] = pd.to_datetime(df['processing_date'])
            return df
            
        finally:
            conn.close()
    
    def get_quality_distribution(self) -> pd.DataFrame:
        """품질 점수 분포"""
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
            SELECT 
                CASE 
                    WHEN quality_score >= 0.95 THEN 'Excellent (0.95+)'
                    WHEN quality_score >= 0.90 THEN 'Good (0.90-0.95)'
                    WHEN quality_score >= 0.80 THEN 'Fair (0.80-0.90)'
                    WHEN quality_score >= 0.70 THEN 'Poor (0.70-0.80)'
                    ELSE 'Failed (<0.70)'
                END as quality_category,
                COUNT(*) as count,
                AVG(cost_estimate) as avg_cost,
                AVG(processing_time_ms) as avg_time
            FROM summaries 
            WHERE is_active = 1
            GROUP BY quality_category
            ORDER BY MIN(quality_score) DESC
            """
            
            df = pd.read_sql_query(query, conn)
            return df
            
        finally:
            conn.close()
    
    def get_company_performance(self) -> pd.DataFrame:
        """회사별 성능 분석"""
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
            SELECT 
                c.company_name,
                COUNT(t.id) as total_tickets,
                COUNT(s.id) as summarized_tickets,
                AVG(s.quality_score) as avg_quality,
                SUM(s.cost_estimate) as total_cost
            FROM companies c
            LEFT JOIN tickets t ON c.id = t.company_id
            LEFT JOIN summaries s ON t.id = s.ticket_id AND s.is_active = 1
            GROUP BY c.id, c.company_name
            HAVING COUNT(t.id) > 0
            ORDER BY summarized_tickets DESC
            """
            
            df = pd.read_sql_query(query, conn)
            
            if not df.empty:
                df['completion_rate'] = (df['summarized_tickets'] / df['total_tickets'] * 100).round(2)
            
            return df
            
        finally:
            conn.close()
    
    def get_processing_logs_summary(self) -> pd.DataFrame:
        """처리 로그 요약"""
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
            SELECT 
                process_type,
                status,
                COUNT(*) as count,
                AVG(processing_time_ms) as avg_processing_time,
                MAX(completed_at) as last_processed
            FROM processing_logs
            WHERE started_at >= datetime('now', '-7 days')
            GROUP BY process_type, status
            ORDER BY process_type, status
            """
            
            df = pd.read_sql_query(query, conn)
            return df
            
        finally:
            conn.close()
    
    def get_failed_summaries(self, limit: int = 20) -> pd.DataFrame:
        """실패한 요약 분석"""
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
            SELECT 
                pl.record_id as ticket_id,
                t.freshdesk_id,
                t.subject,
                pl.error_message,
                pl.attempt_count,
                pl.started_at,
                t.conversation_count
            FROM processing_logs pl
            JOIN tickets t ON pl.record_id = t.id
            WHERE pl.process_type = 'summary_generation' 
            AND pl.status = 'failed'
            ORDER BY pl.started_at DESC
            LIMIT ?
            """
            
            df = pd.read_sql_query(query, conn, params=(limit,))
            return df
            
        finally:
            conn.close()
    
    def analyze_batch_results(self) -> Dict[str, Any]:
        """배치 결과 파일 분석"""
        
        if not self.results_dir.exists():
            return {"error": "결과 디렉토리가 존재하지 않습니다."}
        
        batch_files = list(self.results_dir.glob("optimized_batch_*_results.json"))
        
        if not batch_files:
            return {"error": "배치 결과 파일이 없습니다."}
        
        total_processed = 0
        total_high_quality = 0
        total_cost = 0.0
        batch_stats = []
        
        for batch_file in sorted(batch_files):
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                
                batch_processed = len(results)
                batch_high_quality = sum(1 for r in results if r.get('quality_score', 0) >= 0.9)
                batch_cost = sum(
                    r.get('token_usage', {}).get('input', 0) / 1000 * 0.005 + 
                    r.get('token_usage', {}).get('output', 0) / 1000 * 0.015 
                    for r in results
                )
                
                batch_stats.append({
                    'batch_file': batch_file.name,
                    'processed': batch_processed,
                    'high_quality': batch_high_quality,
                    'cost': batch_cost,
                    'quality_rate': batch_high_quality / batch_processed * 100 if batch_processed > 0 else 0
                })
                
                total_processed += batch_processed
                total_high_quality += batch_high_quality
                total_cost += batch_cost
                
            except Exception as e:
                print(f"배치 파일 분석 실패: {batch_file} - {e}")
                continue
        
        return {
            'total_batches': len(batch_files),
            'total_processed': total_processed,
            'total_high_quality': total_high_quality,
            'total_cost': total_cost,
            'overall_quality_rate': total_high_quality / total_processed * 100 if total_processed > 0 else 0,
            'average_cost_per_ticket': total_cost / total_processed if total_processed > 0 else 0,
            'batch_details': batch_stats
        }
    
    def generate_dashboard_html(self, output_file: str = "optimized_dashboard.html") -> Path:
        """최적화된 대시보드 HTML 생성"""
        
        # 데이터 수집
        stats = self.get_comprehensive_stats()
        timeline = self.get_processing_timeline()
        quality_dist = self.get_quality_distribution()
        company_perf = self.get_company_performance()
        batch_analysis = self.analyze_batch_results()
        failed_summaries = self.get_failed_summaries()
        processing_logs = self.get_processing_logs_summary()
        
        html_content = self._generate_html_content(
            stats, timeline, quality_dist, company_perf, 
            batch_analysis, failed_summaries, processing_logs
        )
        
        output_path = self.results_dir / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def _generate_html_content(self, stats, timeline, quality_dist, company_perf, batch_analysis, failed_summaries, processing_logs) -> str:
        """HTML 콘텐츠 생성"""
        
        html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>최적화된 요약 처리 대시보드</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            color: #333;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        .stat-card.success {{
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        }}
        .stat-card.warning {{
            background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
        }}
        .stat-card.info {{
            background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
        }}
        .stat-card.cost {{
            background: linear-gradient(135deg, #9C27B0 0%, #7B1FA2 100%);
        }}
        .stat-value {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .stat-label {{
            font-size: 1em;
            opacity: 0.9;
        }}
        .section {{
            margin-bottom: 40px;
            padding: 25px;
            background: #f8f9fa;
            border-radius: 10px;
        }}
        .section-title {{
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        .progress-container {{
            margin: 15px 0;
        }}
        .progress-label {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-weight: bold;
        }}
        .progress-bar {{
            width: 100%;
            height: 25px;
            background-color: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #45a049);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        .table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }}
        .table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: bold;
        }}
        .table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        .table tr:hover {{
            background-color: #f5f5f5;
        }}
        .alert {{
            padding: 20px;
            margin: 20px 0;
            border-radius: 10px;
            border-left: 5px solid #2196F3;
        }}
        .alert-info {{
            background-color: #e3f2fd;
            color: #1565c0;
        }}
        .alert-success {{
            background-color: #e8f5e8;
            color: #2e7d32;
            border-left-color: #4caf50;
        }}
        .alert-warning {{
            background-color: #fff3e0;
            color: #ef6c00;
            border-left-color: #ff9800;
        }}
        .timestamp {{
            text-align: center;
            color: #666;
            font-size: 0.9em;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }}
        @media (max-width: 768px) {{
            .grid-2 {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 최적화된 요약 처리 대시보드</h1>
            <p>대규모 Freshdesk 티켓 요약 처리 모니터링 시스템</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats['total_tickets']:,}</div>
                <div class="stat-label">전체 티켓</div>
            </div>
            <div class="stat-card success">
                <div class="stat-value">{stats['total_summaries']:,}</div>
                <div class="stat-label">완료된 요약</div>
            </div>
            <div class="stat-card success">
                <div class="stat-value">{stats['high_quality_summaries']:,}</div>
                <div class="stat-label">고품질 요약</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-value">{stats['pending_tickets']:,}</div>
                <div class="stat-label">처리 대기</div>
            </div>
            <div class="stat-card cost">
                <div class="stat-value">${stats['total_cost_estimate']:.2f}</div>
                <div class="stat-label">총 예상 비용</div>
            </div>
            <div class="stat-card info">
                <div class="stat-value">{stats['total_tokens_used']:,}</div>
                <div class="stat-label">사용된 토큰</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">📊 처리 진행률</div>
            
            <div class="progress-container">
                <div class="progress-label">
                    <span>전체 완료율</span>
                    <span>{stats['completion_rate']:.1f}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {stats['completion_rate']:.1f}%">
                        {stats['completion_rate']:.1f}%
                    </div>
                </div>
            </div>
            
            <div class="progress-container">
                <div class="progress-label">
                    <span>고품질 비율</span>
                    <span>{stats['high_quality_rate']:.1f}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {stats['high_quality_rate']:.1f}%">
                        {stats['high_quality_rate']:.1f}%
                    </div>
                </div>
            </div>
            
            <div class="progress-container">
                <div class="progress-label">
                    <span>평균 품질 점수</span>
                    <span>{stats['average_quality_score']:.3f}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {stats['average_quality_score']*100:.1f}%">
                        {stats['average_quality_score']:.3f}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="grid-2">
            <div class="section">
                <div class="section-title">💰 비용 분석</div>
                <div class="alert alert-info">
                    <strong>비용 효율성:</strong><br>
                    • 총 처리 비용: ${stats['total_cost_estimate']:.2f}<br>
                    • 요약당 평균 비용: ${stats['average_cost_per_summary']:.4f}<br>
                    • 평균 처리 시간: {stats['average_processing_time_ms']:.0f}ms<br>
                    • 평균 재시도 횟수: {stats['average_retry_count']:.2f}회
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">⚡ 성능 지표</div>
                <div class="alert alert-success">
                    <strong>처리 성능:</strong><br>
                    • 토큰 효율성: {stats['total_summaries']/max(stats['total_tokens_used']/1000, 1):.2f} 요약/1K토큰<br>
                    • 최대 재시도: {stats['max_retry_count']}회<br>
                    • 품질 유지율: {stats['high_quality_rate']:.1f}%<br>
                    • 시스템 안정성: 우수
                </div>
            </div>
        </div>
        """
        
        # 품질 분포 테이블
        if not quality_dist.empty:
            html += f"""
        <div class="section">
            <div class="section-title">📈 품질 분포 분석</div>
            <table class="table">
                <thead>
                    <tr>
                        <th>품질 등급</th>
                        <th>건수</th>
                        <th>비율</th>
                        <th>평균 비용</th>
                        <th>평균 처리시간</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            total_count = quality_dist['count'].sum()
            for _, row in quality_dist.iterrows():
                percentage = (row['count'] / total_count * 100) if total_count > 0 else 0
                html += f"""
                    <tr>
                        <td>{row['quality_category']}</td>
                        <td>{row['count']:,}</td>
                        <td>{percentage:.1f}%</td>
                        <td>${row['avg_cost']:.4f}</td>
                        <td>{row['avg_time']:.0f}ms</td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
        </div>
            """
        
        # 회사별 성능
        if not company_perf.empty:
            html += f"""
        <div class="section">
            <div class="section-title">🏢 회사별 처리 현황</div>
            <table class="table">
                <thead>
                    <tr>
                        <th>회사명</th>
                        <th>전체 티켓</th>
                        <th>요약 완료</th>
                        <th>완료율</th>
                        <th>평균 품질</th>
                        <th>총 비용</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for _, row in company_perf.head(10).iterrows():
                html += f"""
                    <tr>
                        <td>{row['company_name']}</td>
                        <td>{row['total_tickets']:,}</td>
                        <td>{row['summarized_tickets']:,}</td>
                        <td>{row['completion_rate']:.1f}%</td>
                        <td>{row['avg_quality']:.3f if pd.notna(row['avg_quality']) else 'N/A'}</td>
                        <td>${row['total_cost']:.2f if pd.notna(row['total_cost']) else '0.00'}</td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
        </div>
            """
        
        # 실패 분석
        if not failed_summaries.empty:
            html += f"""
        <div class="section">
            <div class="section-title">❌ 최근 실패 분석</div>
            <table class="table">
                <thead>
                    <tr>
                        <th>티켓 ID</th>
                        <th>Freshdesk ID</th>
                        <th>제목</th>
                        <th>실패 사유</th>
                        <th>시도 횟수</th>
                        <th>실패 시간</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for _, row in failed_summaries.head(10).iterrows():
                error_msg = row['error_message'][:80] + "..." if len(row['error_message']) > 80 else row['error_message']
                subject = row['subject'][:50] + "..." if len(row['subject']) > 50 else row['subject']
                html += f"""
                    <tr>
                        <td>{row['ticket_id']}</td>
                        <td>{row['freshdesk_id']}</td>
                        <td>{subject}</td>
                        <td>{error_msg}</td>
                        <td>{row['attempt_count']}</td>
                        <td>{row['started_at']}</td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
        </div>
            """
        
        # 배치 처리 현황
        if 'error' not in batch_analysis:
            html += f"""
        <div class="section">
            <div class="section-title">📦 배치 처리 현황</div>
            <div class="alert alert-info">
                <strong>배치 처리 요약:</strong><br>
                • 총 배치 수: {batch_analysis['total_batches']:,}개<br>
                • 처리된 티켓: {batch_analysis['total_processed']:,}건<br>
                • 고품질 비율: {batch_analysis['overall_quality_rate']:.1f}%<br>
                • 총 비용: ${batch_analysis['total_cost']:.2f}
            </div>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>배치 파일</th>
                        <th>처리 건수</th>
                        <th>고품질 건수</th>
                        <th>품질 비율</th>
                        <th>예상 비용</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for batch in batch_analysis['batch_details'][-10:]:  # 최근 10개
                html += f"""
                    <tr>
                        <td>{batch['batch_file']}</td>
                        <td>{batch['processed']:,}</td>
                        <td>{batch['high_quality']:,}</td>
                        <td>{batch['quality_rate']:.1f}%</td>
                        <td>${batch['cost']:.2f}</td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
        </div>
            """
        
        html += f"""
        <div class="timestamp">
            📅 생성 시간: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}<br>
            🗄️ 데이터베이스: {self.db_path}<br>
            📂 결과 디렉토리: {self.results_dir}
        </div>
    </div>
</body>
</html>
        """
        
        return html
    
    def print_summary_report(self):
        """요약 리포트 출력"""
        
        stats = self.get_comprehensive_stats()
        
        print("\n" + "="*60)
        print("📊 최적화된 요약 처리 현황 리포트")
        print("="*60)
        
        print(f"\n🎯 기본 통계:")
        print(f"  전체 티켓: {stats['total_tickets']:,}개")
        print(f"  완료된 요약: {stats['total_summaries']:,}개")
        print(f"  고품질 요약: {stats['high_quality_summaries']:,}개")
        print(f"  처리 대기: {stats['pending_tickets']:,}개")
        
        print(f"\n📈 성능 지표:")
        print(f"  완료율: {stats['completion_rate']:.1f}%")
        print(f"  고품질 비율: {stats['high_quality_rate']:.1f}%")
        print(f"  평균 품질 점수: {stats['average_quality_score']:.3f}")
        print(f"  평균 처리 시간: {stats['average_processing_time_ms']:.0f}ms")
        
        print(f"\n💰 비용 분석:")
        print(f"  총 예상 비용: ${stats['total_cost_estimate']:.2f}")
        print(f"  요약당 평균 비용: ${stats['average_cost_per_summary']:.4f}")
        print(f"  사용된 토큰: {stats['total_tokens_used']:,}개")
        
        print(f"\n⚙️ 시스템 안정성:")
        print(f"  평균 재시도: {stats['average_retry_count']:.2f}회")
        print(f"  최대 재시도: {stats['max_retry_count']}회")
        
        print("="*60)


def main():
    """메인 함수"""
    
    parser = argparse.ArgumentParser(description="최적화된 요약 처리 모니터링")
    parser.add_argument("--db-path", default="core/data/wedosoft_freshdesk_data_optimized.db", help="최적화된 데이터베이스 경로")
    parser.add_argument("--results-dir", default="./optimized_batch_results", help="배치 결과 디렉토리")
    parser.add_argument("--command", choices=['stats', 'dashboard', 'timeline', 'quality'], 
                       default='stats', help="실행할 명령")
    parser.add_argument("--output", help="출력 파일 경로")
    
    args = parser.parse_args()
    
    # 파일 존재 확인
    if not Path(args.db_path).exists():
        print(f"❌ 데이터베이스 파일이 존재하지 않습니다: {args.db_path}")
        print("먼저 create_optimized_schema.py를 실행해주세요.")
        sys.exit(1)
    
    monitor = OptimizedSummarizationMonitor(args.db_path, args.results_dir)
    
    if args.command == 'stats':
        # 기본 통계 출력
        monitor.print_summary_report()
        
    elif args.command == 'dashboard':
        # 대시보드 생성
        output_file = args.output or "optimized_dashboard.html"
        dashboard_path = monitor.generate_dashboard_html(output_file)
        print(f"✅ 최적화된 대시보드가 생성되었습니다: {dashboard_path}")
        
    elif args.command == 'timeline':
        # 타임라인 분석
        timeline = monitor.get_processing_timeline()
        if not timeline.empty:
            print("\n📅 최근 처리 타임라인:")
            print(timeline.to_string(index=False))
        else:
            print("📅 타임라인 데이터가 없습니다.")
            
    elif args.command == 'quality':
        # 품질 분석
        quality_dist = monitor.get_quality_distribution()
        if not quality_dist.empty:
            print("\n🏆 품질 분포 분석:")
            print(quality_dist.to_string(index=False))
        else:
            print("🏆 품질 데이터가 없습니다.")


if __name__ == "__main__":
    main()
