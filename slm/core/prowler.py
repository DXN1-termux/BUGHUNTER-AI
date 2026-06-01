"""TITAN PROWLER - Automated Reconnaissance & Asset Management Engine.
Part of the BUGHUNTER-AI TITAN EDITION v2.4 upgrade.

The Prowler engine handles background asset discovery, service fingerprinting,
and vulnerability correlation.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import pathlib
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from slm.tools import dispatch

logger = logging.getLogger("titan.prowler")

@dataclass
class Asset:
    """Represents a discovered host or service."""
    host: str
    ip: Optional[str] = None
    port: Optional[int] = None
    service: Optional[str] = None
    banner: Optional[str] = None
    status_code: Optional[int] = None
    last_seen: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)

class ProwlerEngine:
    """The background engine for TITAN recon operations."""
    
    def __init__(self, db_path: Optional[pathlib.Path] = None):
        self.db_path = db_path or pathlib.Path.home() / ".slm" / "prowler.db"
        self._init_db()
        self.is_running = False
        self.active_tasks: List[asyncio.Task] = []

    def _init_db(self):
        """Initialize the asset tracking database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    host TEXT PRIMARY KEY,
                    ip TEXT,
                    port INTEGER,
                    service TEXT,
                    banner TEXT,
                    status_code INTEGER,
                    last_seen REAL,
                    meta TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vulnerabilities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host TEXT,
                    name TEXT,
                    severity TEXT,
                    description TEXT,
                    poc TEXT,
                    discovered_at REAL
                )
            """)

    async def start_recon_cycle(self, target: str):
        """Perform a full recon cycle on a target domain."""
        logger.info(f"Prowler initializing recon on {target}")
        
        # 1. Subdomain Discovery
        subdomains = await self._run_subfinder(target)
        for sub in subdomains:
            self._upsert_asset(Asset(host=sub))
            
        # 2. HTTP Probing
        live_services = await self._run_httpx(subdomains)
        for service in live_services:
            self._upsert_asset(service)
            
        # 3. Vulnerability Scanning (Nuclei)
        await self._run_nuclei(target)
        
        logger.info(f"Prowler cycle complete for {target}")

    async def _run_subfinder(self, domain: str) -> List[str]:
        """Wrapper for subfinder tool."""
        res = dispatch("subfinder", {"target": domain})
        if "error" in res.lower():
            return []
        # Filter out CLI noise and return unique lines
        lines = [line.strip() for line in res.splitlines() if "." in line]
        return list(set(lines))

    async def _run_httpx(self, targets: List[str]) -> List[Asset]:
        """Wrapper for httpx tool."""
        assets = []
        # Process in chunks of 50 to avoid shell overflow
        for i in range(0, len(targets), 50):
            chunk = targets[i:i+50]
            targets_str = ",".join(chunk)
            res = dispatch("httpx", {"target": targets_str, "extra": "-status-code -title -tech-detect -json"})
            
            for line in res.splitlines():
                try:
                    data = json.loads(line)
                    assets.append(Asset(
                        host=data.get("url", ""),
                        ip=data.get("host", ""),
                        port=data.get("port", 80),
                        service=data.get("tech", ""),
                        status_code=data.get("status-code", 0),
                        meta=data
                    ))
                except json.JSONDecodeError:
                    continue
        return assets

    async def _run_nuclei(self, target: str):
        """Wrapper for nuclei tool."""
        # This will save findings via report_finding tool internally if logic permits,
        # but here we also track in Prowler DB.
        res = dispatch("nuclei", {"target": target, "extra": "-severity medium,high,critical -json"})
        
        for line in res.splitlines():
            try:
                data = json.loads(line)
                self._log_vuln(
                    host=data.get("matched-at", target),
                    name=data.get("info", {}).get("name", "Unknown"),
                    severity=data.get("info", {}).get("severity", "info"),
                    description=data.get("info", {}).get("description", ""),
                    poc=data.get("curl-command", "")
                )
            except json.JSONDecodeError:
                continue

    def _upsert_asset(self, asset: Asset):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO assets (host, ip, port, service, banner, status_code, last_seen, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(host) DO UPDATE SET
                    ip=excluded.ip,
                    port=excluded.port,
                    service=excluded.service,
                    banner=excluded.banner,
                    status_code=excluded.status_code,
                    last_seen=excluded.last_seen,
                    meta=excluded.meta
            """, (asset.host, asset.ip, asset.port, asset.service, asset.banner, 
                  asset.status_code, asset.last_seen, json.dumps(asset.meta)))

    def _log_vuln(self, host: str, name: str, severity: str, description: str, poc: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO vulnerabilities (host, name, severity, description, poc, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (host, name, severity, description, poc, time.time()))

    def get_stats(self) -> Dict[str, Any]:
        """Get summary stats for TITAN dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            assets_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            vulns_count = conn.execute("SELECT COUNT(*) FROM vulnerabilities").fetchone()[0]
            criticals = conn.execute("SELECT COUNT(*) FROM vulnerabilities WHERE severity='critical'").fetchone()[0]
            return {
                "total_assets": assets_count,
                "total_vulns": vulns_count,
                "critical_vulns": criticals
            }

class ProwlerReporter:
    """Generates high-fidelity markdown reports from Prowler data."""
    
    @staticmethod
    def generate_summary(engine: ProwlerEngine) -> str:
        stats = engine.get_stats()
        report = f"# TITAN PROWLER RECON SUMMARY\n"
        report += f"Generated at: {datetime.now().isoformat()}\n\n"
        report += f"- **Total Assets Discovered**: {stats['total_assets']}\n"
        report += f"- **Total Vulnerabilities**: {stats['total_vulns']}\n"
        report += f"- **Critical Findings**: {stats['critical_vulns']}\n\n"
        
        report += "## Recent Critical Findings\n"
        with sqlite3.connect(engine.db_path) as conn:
            cursor = conn.execute("SELECT host, name, severity FROM vulnerabilities WHERE severity IN ('critical', 'high') ORDER BY discovered_at DESC LIMIT 10")
            for row in cursor:
                report += f"- [{row[2].upper()}] **{row[1]}** on {row[0]}\n"
                
        return report
