#!/usr/bin/env python
"""
Quick Audit Log Inspector - View audit logs easily from command line
Usage: python inspect_audit_logs.py [--user <email>] [--days <N>] [--event <TYPE>]
"""

import sys
from pathlib import Path
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base, AuditLog

# Database
db_dir = Path(__file__).parent / "database"

# Try test database first, then production
db_paths = [
    db_dir / "spbe_rag.db",
    db_dir / "test_audit.db",
]

db_path = None
for path in db_paths:
    if path.exists():
        db_path = path
        break

if not db_path:
    print(f"❌ Database not found in {db_dir}")
    print(f"   Looked for: {', '.join(str(p.name) for p in db_paths)}")
    sys.exit(1)

print(f"📊 Using database: {db_path.name}")
DATABASE_URL = f"sqlite:///{db_path.absolute()}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

def format_row(log):
    """Format audit log row for display"""
    return f"{str(log.timestamp):20} | {log.event_type:18} | {log.username:30} | {log.ip_address:15} | {log.status:10}"

def main():
    parser = argparse.ArgumentParser(description="Inspect audit logs")
    parser.add_argument("--user", help="Filter by username/email")
    parser.add_argument("--days", type=int, default=7, help="Show logs from last N days (default: 7)")
    parser.add_argument("--event", help="Filter by event type (LOGIN_SUCCESS, LOGIN_FAILURE, etc.)")
    parser.add_argument("--limit", type=int, default=50, help="Limit number of results (default: 50)")
    parser.add_argument("--bruteforce", action="store_true", help="Show potential bruteforce attempts")
    parser.add_argument("--summary", action="store_true", help="Show summary by event type")
    
    args = parser.parse_args()
    
    cutoff = datetime.utcnow() - timedelta(days=args.days)
    query = session.query(AuditLog).filter(AuditLog.timestamp >= cutoff)
    
    if args.user:
        query = query.filter(AuditLog.username == args.user)
    
    if args.event:
        query = query.filter(AuditLog.event_type == args.event)
    
    print("\n" + "=" * 120)
    print(f"AUDIT LOG INSPECTOR — Last {args.days} days")
    print("=" * 120)
    
    if args.bruteforce:
        # Show potential bruteforce attempts
        print("\n🔴 BRUTEFORCE DETECTION — Failed logins by IP (last 24h)")
        print("-" * 120)
        
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        bruteforce_ips = session.query(
            AuditLog.ip_address,
            AuditLog.event_type,
            AuditLog.username,
        ).filter(
            AuditLog.event_type == "LOGIN_FAILURE",
            AuditLog.timestamp >= cutoff_24h
        ).group_by(AuditLog.ip_address).all()
        
        failed_by_ip = {}
        for log in session.query(AuditLog).filter(
            AuditLog.event_type == "LOGIN_FAILURE",
            AuditLog.timestamp >= cutoff_24h
        ).all():
            ip = log.ip_address
            if ip not in failed_by_ip:
                failed_by_ip[ip] = 0
            failed_by_ip[ip] += 1
        
        for ip, count in sorted(failed_by_ip.items(), key=lambda x: x[1], reverse=True):
            alert = "⚠️" if count > 5 else "ℹ️"
            print(f"{alert} {ip:20} | {count:3} failed attempts")
        
    elif args.summary:
        # Show summary by event type
        print(f"\n📊 SUMMARY — Event counts by type (last {args.days} days)")
        print("-" * 120)
        
        summary = {}
        for log in query.all():
            event_type = log.event_type
            if event_type not in summary:
                summary[event_type] = 0
            summary[event_type] += 1
        
        for event_type, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
            print(f"  {event_type:20} | {count:5} events")
        
        print(f"\n  {'TOTAL':20} | {sum(summary.values()):5} events")
    
    else:
        # Show audit logs
        logs = query.order_by(AuditLog.timestamp.desc()).limit(args.limit).all()
        
        print(f"\n📋 Audit Logs ({len(logs)} results)")
        print("-" * 120)
        print(f"{'Timestamp':20} | {'Event Type':18} | {'Username':30} | {'IP Address':15} | {'Status':10}")
        print("-" * 120)
        
        for log in logs:
            print(format_row(log))
        
        if len(logs) == args.limit:
            print(f"\n(Showing {args.limit} most recent — use --limit to show more)")
    
    # Total stats
    total_logs = session.query(AuditLog).filter(AuditLog.timestamp >= cutoff).count()
    print("\n" + "-" * 120)
    print(f"Total audit logs (last {args.days} days): {total_logs}")
    print("=" * 120 + "\n")
    
    session.close()

if __name__ == "__main__":
    main()
