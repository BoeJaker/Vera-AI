#!/usr/bin/env python3
"""
Vulnerability Intelligence Ingestor for Hybrid Memory System
Ingests CVE, OSV, GHSA, MSRC, RHSA, USN and other vulnerability databases
into the graph-based memory system with rich semantic relationships.

Dependencies:
    pip install requests aiohttp nvdlib python-dateutil packaging

Usage:
    ingestor = VulnerabilityIngestor(memory_system)
    
    # Ingest single CVE
    await ingestor.ingest_cve("CVE-2024-1234")
    
    # Ingest OSV vulnerability
    await ingestor.ingest_osv("GHSA-xxxx-yyyy-zzzz")
    
    # Bulk ingest from NVD feed
    await ingestor.ingest_nvd_feed(start_date="2024-01-01", end_date="2024-12-31")
    
    # Query vulnerabilities affecting specific package
    vulns = ingestor.query_package_vulnerabilities("log4j", version="2.14.1")
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin

import aiohttp
import requests
from dateutil import parser as date_parser
from packaging import version as pkg_version

# Import your memory system
# from hybrid_memory import HybridMemory, Node, Edge


@dataclass
class VulnerabilityRecord:
    """Normalized vulnerability record"""
    id: str  # Primary ID (CVE, GHSA, etc.)
    aliases: List[str]  # Other IDs referencing same vuln
    summary: str
    details: str
    severity: Optional[str] = None  # CRITICAL, HIGH, MEDIUM, LOW
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    cwe_ids: List[str] = None
    published: Optional[str] = None
    modified: Optional[str] = None
    references: List[Dict[str, str]] = None
    affected_packages: List[Dict[str, Any]] = None
    source: str = "UNKNOWN"
    
    def __post_init__(self):
        if self.cwe_ids is None:
            self.cwe_ids = []
        if self.references is None:
            self.references = []
        if self.affected_packages is None:
            self.affected_packages = []


class VulnerabilityIngestor:
    """
    Multi-source vulnerability ingestor with graph knowledge building.
    Creates rich semantic relationships between:
    - Vulnerabilities
    - Software packages/products
    - Versions
    - CWE weakness types
    - Attack patterns (CAPEC)
    - Vendors/maintainers
    """
    
    # API Endpoints
    NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    OSV_API = "https://api.osv.dev/v1"
    GITHUB_API = "https://api.github.com/advisories"
    MITRE_CVE_API = "https://cveawg.mitre.org/api/cve"
    
    def __init__(self, memory: Any, api_keys: Optional[Dict[str, str]] = None):
        """
        Args:
            memory: HybridMemory instance
            api_keys: Optional dict with API keys (nvd_api_key, github_token)
        """
        self.memory = memory
        self.api_keys = api_keys or {}
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Caches to avoid duplicate ingestion
        self.ingested_vulns: Set[str] = set()
        self.package_cache: Dict[str, str] = {}  # {package_name: entity_id}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    # ==================== CVE Ingestion ====================
    
    async def ingest_cve(self, cve_id: str) -> Dict[str, Any]:
        """
        Ingest a single CVE from NVD database.
        
        Args:
            cve_id: CVE identifier (e.g., CVE-2024-1234)
            
        Returns:
            Dict with ingestion results including entity IDs created
        """
        if cve_id in self.ingested_vulns:
            return {"status": "already_ingested", "cve_id": cve_id}
        
        # Fetch from NVD
        cve_data = await self._fetch_nvd_cve(cve_id)
        if not cve_data:
            return {"status": "not_found", "cve_id": cve_id}
        
        # Parse and normalize
        vuln_record = self._parse_nvd_cve(cve_data)
        
        # Ingest into memory system
        result = await self._ingest_vulnerability(vuln_record)
        
        self.ingested_vulns.add(cve_id)
        return result
    
    async def _fetch_nvd_cve(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """Fetch CVE data from NVD API"""
        url = f"{self.NVD_API}"
        params = {"cveId": cve_id}
        headers = {}
        
        if self.api_keys.get("nvd_api_key"):
            headers["apiKey"] = self.api_keys["nvd_api_key"]
        
        try:
            async with self.session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("vulnerabilities"):
                        return data["vulnerabilities"][0]["cve"]
        except Exception as e:
            print(f"Error fetching {cve_id} from NVD: {e}")
        
        return None
    
    def _parse_nvd_cve(self, cve_data: Dict[str, Any]) -> VulnerabilityRecord:
        """Parse NVD CVE JSON into normalized record"""
        cve_id = cve_data.get("id", "UNKNOWN")
        
        # Extract descriptions
        descriptions = cve_data.get("descriptions", [])
        summary = next((d["value"] for d in descriptions if d["lang"] == "en"), "")
        
        # Extract CVSS scores
        cvss_score = None
        cvss_vector = None
        severity = None
        
        metrics = cve_data.get("metrics", {})
        if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
            cvss_data = metrics["cvssMetricV31"][0]["cvssData"]
            cvss_score = cvss_data.get("baseScore")
            cvss_vector = cvss_data.get("vectorString")
            severity = cvss_data.get("baseSeverity")
        elif "cvssMetricV2" in metrics and metrics["cvssMetricV2"]:
            cvss_data = metrics["cvssMetricV2"][0]["cvssData"]
            cvss_score = cvss_data.get("baseScore")
            cvss_vector = cvss_data.get("vectorString")
        
        # Extract CWE IDs
        cwe_ids = []
        weaknesses = cve_data.get("weaknesses", [])
        for weakness in weaknesses:
            for desc in weakness.get("description", []):
                if desc["value"].startswith("CWE-"):
                    cwe_ids.append(desc["value"])
        
        # Extract references
        references = []
        for ref in cve_data.get("references", []):
            references.append({
                "url": ref.get("url"),
                "source": ref.get("source"),
                "tags": ref.get("tags", [])
            })
        
        # Extract affected packages (from CPE data)
        affected_packages = []
        configurations = cve_data.get("configurations", [])
        for config in configurations:
            for node in config.get("nodes", []):
                for match in node.get("cpeMatch", []):
                    cpe = match.get("criteria", "")
                    vulnerable = match.get("vulnerable", False)
                    
                    if vulnerable and cpe:
                        # Parse CPE: cpe:2.3:a:vendor:product:version:*:*:*:*:*:*:*
                        parts = cpe.split(":")
                        if len(parts) >= 5:
                            affected_packages.append({
                                "ecosystem": "cpe",
                                "vendor": parts[3] if len(parts) > 3 else None,
                                "name": parts[4] if len(parts) > 4 else None,
                                "version": parts[5] if len(parts) > 5 else None,
                                "version_start": match.get("versionStartIncluding"),
                                "version_end": match.get("versionEndExcluding"),
                            })
        
        return VulnerabilityRecord(
            id=cve_id,
            aliases=[],
            summary=summary,
            details=summary,
            severity=severity,
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            cwe_ids=cwe_ids,
            published=cve_data.get("published"),
            modified=cve_data.get("lastModified"),
            references=references,
            affected_packages=affected_packages,
            source="NVD"
        )
    
    # ==================== OSV Ingestion ====================
    
    async def ingest_osv(self, osv_id: str) -> Dict[str, Any]:
        """
        Ingest vulnerability from OSV (Open Source Vulnerabilities) database.
        Supports GHSA, PYSEC, RUSTSEC, GO, npm, etc.
        
        Args:
            osv_id: OSV identifier (e.g., GHSA-xxxx-yyyy-zzzz, PYSEC-2024-1234)
        """
        if osv_id in self.ingested_vulns:
            return {"status": "already_ingested", "osv_id": osv_id}
        
        # Fetch from OSV API
        osv_data = await self._fetch_osv(osv_id)
        if not osv_data:
            return {"status": "not_found", "osv_id": osv_id}
        
        # Parse and normalize
        vuln_record = self._parse_osv(osv_data)
        
        # Ingest into memory system
        result = await self._ingest_vulnerability(vuln_record)
        
        self.ingested_vulns.add(osv_id)
        return result
    
    async def _fetch_osv(self, osv_id: str) -> Optional[Dict[str, Any]]:
        """Fetch vulnerability from OSV API"""
        url = f"{self.OSV_API}/vulns/{osv_id}"
        
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            print(f"Error fetching {osv_id} from OSV: {e}")
        
        return None
    
    def _parse_osv(self, osv_data: Dict[str, Any]) -> VulnerabilityRecord:
        """Parse OSV JSON into normalized record"""
        osv_id = osv_data.get("id", "UNKNOWN")
        
        # Extract aliases (CVE, GHSA, etc.)
        aliases = osv_data.get("aliases", [])
        
        # Extract summary and details
        summary = osv_data.get("summary", "")
        details = osv_data.get("details", summary)
        
        # Extract severity
        severity_data = osv_data.get("severity", [])
        severity = None
        cvss_score = None
        cvss_vector = None
        
        for sev in severity_data:
            if sev.get("type") == "CVSS_V3":
                cvss_score = sev.get("score")
                # Map score to severity
                if cvss_score >= 9.0:
                    severity = "CRITICAL"
                elif cvss_score >= 7.0:
                    severity = "HIGH"
                elif cvss_score >= 4.0:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"
        
        # Extract references
        references = []
        for ref in osv_data.get("references", []):
            references.append({
                "url": ref.get("url"),
                "type": ref.get("type")
            })
        
        # Extract affected packages
        affected_packages = []
        for affected in osv_data.get("affected", []):
            package = affected.get("package", {})
            ecosystem = package.get("ecosystem")
            name = package.get("name")
            
            # Extract version ranges
            for version_range in affected.get("ranges", []):
                range_type = version_range.get("type")
                events = version_range.get("events", [])
                
                version_start = None
                version_end = None
                
                for event in events:
                    if "introduced" in event:
                        version_start = event["introduced"]
                    if "fixed" in event:
                        version_end = event["fixed"]
                
                affected_packages.append({
                    "ecosystem": ecosystem,
                    "name": name,
                    "purl": package.get("purl"),
                    "version_start": version_start,
                    "version_end": version_end,
                    "range_type": range_type
                })
        
        # Extract CWE IDs from database_specific
        cwe_ids = []
        db_specific = osv_data.get("database_specific", {})
        if "cwe_ids" in db_specific:
            cwe_ids = db_specific["cwe_ids"]
        
        return VulnerabilityRecord(
            id=osv_id,
            aliases=aliases,
            summary=summary,
            details=details,
            severity=severity,
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            cwe_ids=cwe_ids,
            published=osv_data.get("published"),
            modified=osv_data.get("modified"),
            references=references,
            affected_packages=affected_packages,
            source="OSV"
        )
    
    # ==================== GHSA (GitHub Security Advisory) ====================
    
    async def ingest_ghsa(self, ghsa_id: str) -> Dict[str, Any]:
        """
        Ingest GitHub Security Advisory.
        Note: GHSA data is typically available through OSV, but this provides
        direct GitHub API access for additional metadata.
        """
        # GHSA IDs are OSV-compatible, delegate to OSV ingestor
        return await self.ingest_osv(ghsa_id)
    
    # ==================== Vendor-Specific Advisories ====================
    
    async def ingest_microsoft_advisory(self, msrc_id: str) -> Dict[str, Any]:
        """
        Ingest Microsoft Security Response Center advisory.
        MSRC format: ADV######, CVE-####-####
        """
        # Placeholder - would need MSRC API integration
        # For now, check if it's a CVE reference
        if msrc_id.startswith("CVE-"):
            return await self.ingest_cve(msrc_id)
        
        return {"status": "not_implemented", "msrc_id": msrc_id}
    
    async def ingest_redhat_advisory(self, rhsa_id: str) -> Dict[str, Any]:
        """
        Ingest Red Hat Security Advisory.
        RHSA format: RHSA-YYYY:NNNN
        """
        # Placeholder - would need Red Hat API integration
        return {"status": "not_implemented", "rhsa_id": rhsa_id}
    
    async def ingest_ubuntu_advisory(self, usn_id: str) -> Dict[str, Any]:
        """
        Ingest Ubuntu Security Notice.
        USN format: USN-####-#
        """
        # Placeholder - would need Ubuntu API integration
        return {"status": "not_implemented", "usn_id": usn_id}
    
    # ==================== Core Ingestion Logic ====================
    
    async def _ingest_vulnerability(self, vuln: VulnerabilityRecord) -> Dict[str, Any]:
        """
        Core ingestion logic: creates vulnerability node and all relationships
        in the graph memory system.
        """
        result = {
            "vuln_id": vuln.id,
            "entities_created": [],
            "relationships_created": []
        }
        
        # 1. Create main vulnerability node
        vuln_entity_id = self._generate_id(f"vuln_{vuln.id}")
        
        vuln_properties = {
            "vuln_id": vuln.id,
            "summary": vuln.summary,
            "details": vuln.details,
            "severity": vuln.severity,
            "cvss_score": vuln.cvss_score,
            "cvss_vector": vuln.cvss_vector,
            "published": vuln.published,
            "modified": vuln.modified,
            "source": vuln.source,
            "aliases": vuln.aliases
        }
        
        self.memory.upsert_entity(
            entity_id=vuln_entity_id,
            etype="vulnerability",
            labels=["Vulnerability", vuln.severity] if vuln.severity else ["Vulnerability"],
            properties=vuln_properties
        )
        result["entities_created"].append(vuln_entity_id)
        
        # 2. Store full details in vector store
        doc_id = f"doc_{vuln.id}"
        full_text = f"{vuln.summary}\n\n{vuln.details}"
        self.memory.attach_document(
            entity_id=vuln_entity_id,
            doc_id=doc_id,
            text=full_text,
            metadata={"type": "vulnerability_details", "source": vuln.source}
        )
        
        # 3. Link to aliases (other IDs for same vulnerability)
        for alias in vuln.aliases:
            alias_id = self._generate_id(f"vuln_{alias}")
            self.memory.upsert_entity(
                entity_id=alias_id,
                etype="vulnerability_alias",
                labels=["VulnerabilityAlias"],
                properties={"alias_id": alias, "primary_id": vuln.id}
            )
            self.memory.link(vuln_entity_id, alias_id, "HAS_ALIAS")
            result["entities_created"].append(alias_id)
            result["relationships_created"].append(f"{vuln_entity_id} -[HAS_ALIAS]-> {alias_id}")
        
        # 4. Link to CWE (weakness types)
        for cwe_id in vuln.cwe_ids:
            cwe_entity_id = await self._get_or_create_cwe(cwe_id)
            self.memory.link(vuln_entity_id, cwe_entity_id, "EXPLOITS_WEAKNESS")
            result["relationships_created"].append(f"{vuln_entity_id} -[EXPLOITS_WEAKNESS]-> {cwe_entity_id}")
        
        # 5. Link to affected packages
        for pkg in vuln.affected_packages:
            pkg_entity_id = await self._get_or_create_package(
                ecosystem=pkg.get("ecosystem"),
                name=pkg.get("name"),
                vendor=pkg.get("vendor")
            )
            
            # Create version-specific relationship
            rel_props = {
                "version_start": pkg.get("version_start"),
                "version_end": pkg.get("version_end"),
                "version": pkg.get("version")
            }
            self.memory.link(vuln_entity_id, pkg_entity_id, "AFFECTS_PACKAGE", rel_props)
            result["relationships_created"].append(f"{vuln_entity_id} -[AFFECTS_PACKAGE]-> {pkg_entity_id}")
        
        # 6. Store references as document nodes
        for i, ref in enumerate(vuln.references):
            ref_id = self._generate_id(f"ref_{vuln.id}_{i}")
            self.memory.upsert_entity(
                entity_id=ref_id,
                etype="reference",
                labels=["Reference"],
                properties={
                    "url": ref.get("url"),
                    "source": ref.get("source"),
                    "tags": ref.get("tags", [])
                }
            )
            self.memory.link(vuln_entity_id, ref_id, "HAS_REFERENCE")
            result["entities_created"].append(ref_id)
        
        return result
    
    async def _get_or_create_cwe(self, cwe_id: str) -> str:
        """Get or create CWE (Common Weakness Enumeration) entity"""
        entity_id = self._generate_id(f"cwe_{cwe_id}")
        
        # Check cache
        if entity_id not in self.package_cache:
            # Extract CWE number
            cwe_num = cwe_id.replace("CWE-", "")
            
            self.memory.upsert_entity(
                entity_id=entity_id,
                etype="weakness",
                labels=["CWE", "Weakness"],
                properties={
                    "cwe_id": cwe_id,
                    "cwe_number": cwe_num,
                    "reference_url": f"https://cwe.mitre.org/data/definitions/{cwe_num}.html"
                }
            )
            self.package_cache[entity_id] = entity_id
        
        return entity_id
    
    async def _get_or_create_package(self, ecosystem: Optional[str], name: Optional[str], vendor: Optional[str] = None) -> str:
        """Get or create software package entity"""
        if not name:
            name = "UNKNOWN"
        
        cache_key = f"{ecosystem}:{vendor}:{name}"
        
        if cache_key in self.package_cache:
            return self.package_cache[cache_key]
        
        entity_id = self._generate_id(f"pkg_{cache_key}")
        
        self.memory.upsert_entity(
            entity_id=entity_id,
            etype="package",
            labels=["Package", ecosystem] if ecosystem else ["Package"],
            properties={
                "ecosystem": ecosystem,
                "name": name,
                "vendor": vendor
            }
        )
        
        self.package_cache[cache_key] = entity_id
        return entity_id
    
    def _generate_id(self, key: str) -> str:
        """Generate consistent entity ID from key"""
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    # ==================== Bulk Ingestion ====================
    
    async def ingest_nvd_feed(self, start_date: str, end_date: str, batch_size: int = 100) -> Dict[str, Any]:
        """
        Bulk ingest CVEs from NVD within date range.
        
        Args:
            start_date: ISO format date string (YYYY-MM-DD)
            end_date: ISO format date string (YYYY-MM-DD)
            batch_size: Number of CVEs to fetch per request
        """
        results = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        # NVD API pagination
        start_index = 0
        
        while True:
            url = self.NVD_API
            params = {
                "pubStartDate": f"{start_date}T00:00:00.000",
                "pubEndDate": f"{end_date}T23:59:59.999",
                "resultsPerPage": batch_size,
                "startIndex": start_index
            }
            
            headers = {}
            if self.api_keys.get("nvd_api_key"):
                headers["apiKey"] = self.api_keys["nvd_api_key"]
            
            try:
                async with self.session.get(url, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        break
                    
                    data = await resp.json()
                    vulnerabilities = data.get("vulnerabilities", [])
                    
                    if not vulnerabilities:
                        break
                    
                    # Process batch
                    for vuln_wrapper in vulnerabilities:
                        cve_data = vuln_wrapper.get("cve")
                        if cve_data:
                            cve_id = cve_data.get("id")
                            try:
                                vuln_record = self._parse_nvd_cve(cve_data)
                                await self._ingest_vulnerability(vuln_record)
                                results["successful"] += 1
                            except Exception as e:
                                results["failed"] += 1
                                results["errors"].append({"cve_id": cve_id, "error": str(e)})
                        
                        results["total_processed"] += 1
                    
                    # Check if more results
                    total_results = data.get("totalResults", 0)
                    if start_index + batch_size >= total_results:
                        break
                    
                    start_index += batch_size
                    
                    # Rate limiting (NVD allows 5 requests/30s without key, 50/30s with key)
                    await asyncio.sleep(6 if not self.api_keys.get("nvd_api_key") else 0.6)
                    
            except Exception as e:
                results["errors"].append({"batch_start": start_index, "error": str(e)})
                break
        
        return results
    
    async def ingest_osv_ecosystem(self, ecosystem: str, max_vulns: int = 1000) -> Dict[str, Any]:
        """
        Bulk ingest vulnerabilities for an entire ecosystem from OSV.
        
        Args:
            ecosystem: Ecosystem name (e.g., "PyPI", "npm", "Go", "Maven")
            max_vulns: Maximum number of vulnerabilities to ingest
        """
        results = {
            "ecosystem": ecosystem,
            "total_processed": 0,
            "successful": 0,
            "failed": 0
        }
        
        # Query OSV for ecosystem vulnerabilities
        url = f"{self.OSV_API}/query"
        payload = {
            "package": {
                "ecosystem": ecosystem
            }
        }
        
        try:
            async with self.session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    vulns = data.get("vulns", [])[:max_vulns]
                    
                    for vuln_summary in vulns:
                        osv_id = vuln_summary.get("id")
                        if osv_id:
                            try:
                                await self.ingest_osv(osv_id)
                                results["successful"] += 1
                            except Exception as e:
                                results["failed"] += 1
                        
                        results["total_processed"] += 1
                        
                        # Rate limiting
                        await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error ingesting {ecosystem} from OSV: {e}")
        
        return results
    
    # ==================== Query Interface ====================
    
    def query_package_vulnerabilities(self, package_name: str, version: Optional[str] = None, ecosystem: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query vulnerabilities affecting a specific package.
        
        Args:
            package_name: Package name
            version: Optional specific version
            ecosystem: Optional ecosystem filter (PyPI, npm, etc.)
            
        Returns:
            List of vulnerability records
        """
        # Generate package entity ID
        cache_key = f"{ecosystem}:None:{package_name}"
        pkg_entity_id = self._generate_id(f"pkg_{cache_key}")
        
        # Extract subgraph around package
        subgraph = self.memory.extract_subgraph([pkg_entity_id], depth=2)
        
        # Filter for vulnerability nodes
        vulnerabilities = []
        for node in subgraph.get("nodes", []):
            if node.get("properties", {}).get("vuln_id"):
                vuln_data = node["properties"]
                
                # Version filtering if specified
                if version:
                    # Check if version is in affected range
                    # (Would need more sophisticated version comparison logic)
                    pass
                
                vulnerabilities.append(vuln_data)
        
        return vulnerabilities
    
    def query_cwe_vulnerabilities(self, cwe_id: str) -> List[Dict[str, Any]]:
        """Query all vulnerabilities exploiting a specific CWE weakness"""
        cwe_entity_id = self._generate_id(f"cwe_{cwe_id}")
        subgraph = self.memory.extract_subgraph([cwe_entity_id], depth=1)
        
        vulnerabilities = []
        for node in subgraph.get("nodes", []):
            if "Vulnerability" in node.get("labels", []):
                vulnerabilities.append(node["properties"])
        
        return vulnerabilities
    
    def semantic_search_vulnerabilities(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Semantic search for vulnerabilities by description.
        
        Args:
            query: Natural language query (e.g., "SQL injection in web frameworks")
            k: Number of results
        """
        results = self.memory.semantic_retrieve(query, k=k)
        return results


# ==================== CLI Example ====================

async def main():
    """Example usage"""
    from hybrid_memory import HybridMemory  # Your memory system
    
    # Initialize memory system
    memory = HybridMemory(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        chroma_dir="./chroma_db"
    )
    
    async with VulnerabilityIngestor(memory) as ingestor:
        # Ingest single CVE
        print("Ingesting CVE-2021-44228 (Log4Shell)...")
        result = await ingestor.ingest_cve("CVE-2021-44228")
        print(f"Result: {result}")
        
        # Ingest GHSA
        print("\nIngesting GHSA-jfh8-c2jp-5v3w...")
        result = await ingestor.ingest_ghsa("GHSA-jfh8-c2jp-5v3w")
        print(f"Result: {result}")
        
        # Bulk ingest from NVD (last 30 days)
        print("\nBulk ingesting recent CVEs...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        result = await ingestor.ingest_nvd_feed(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        print(f"Bulk ingest result: {result}")
        
        # Query vulnerabilities for a package
        print("\nQuerying vulnerabilities for log4j...")
        vulns = ingestor.query_package_vulnerabilities("log4j-core", ecosystem="Maven")
        print(f"Found {len(vulns)} vulnerabilities")
        
        # Semantic search
        print("\nSemantic search for 'remote code execution'...")
        results = ingestor.semantic_search_vulnerabilities("remote code execution", k=5)
        for r in results:
            print(f"  - {r['id']}: {r['text'][:100]}...")


if __name__ == "__main__":
    asyncio.run(main())


# ==================== Additional Utility Classes ====================

class VulnerabilityAnalyzer:
    """
    Advanced analytics on the vulnerability knowledge graph.
    """
    
    def __init__(self, memory: Any):
        self.memory = memory
    
    def get_vulnerability_trends(self, start_date: str, end_date: str, group_by: str = "month") -> Dict[str, Any]:
        """
        Analyze vulnerability trends over time.
        
        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            group_by: Grouping period (day, week, month, year)
        """
        # Query graph for vulnerabilities in date range
        # Group by publication date
        # Return trend data
        pass
    
    def get_most_vulnerable_packages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Find packages with the most known vulnerabilities.
        """
        # Query graph for package nodes
        # Count incoming AFFECTS_PACKAGE relationships
        # Sort and return top packages
        pass
    
    def get_severity_distribution(self, ecosystem: Optional[str] = None) -> Dict[str, int]:
        """
        Get distribution of vulnerabilities by severity.
        """
        distribution = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "UNKNOWN": 0
        }
        
        # Query vulnerabilities and count by severity
        # Filter by ecosystem if specified
        
        return distribution
    
    def find_related_vulnerabilities(self, vuln_id: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """
        Find vulnerabilities related by shared CWEs, packages, or patterns.
        """
        vuln_entity_id = hashlib.md5(f"vuln_{vuln_id}".encode()).hexdigest()[:16]
        subgraph = self.memory.extract_subgraph([vuln_entity_id], depth=max_depth)
        
        related = []
        for node in subgraph.get("nodes", []):
            if "Vulnerability" in node.get("labels", []) and node["id"] != vuln_entity_id:
                related.append(node["properties"])
        
        return related
    
    def get_exploit_chains(self, target_package: str) -> List[List[str]]:
        """
        Identify potential exploit chains (vulnerabilities that can be chained).
        """
        # Find vulnerabilities affecting target package
        # Identify relationships between vulnerabilities
        # Build exploit chain paths
        pass
    
    def generate_security_report(self, package_name: str, version: str, ecosystem: str) -> Dict[str, Any]:
        """
        Generate comprehensive security report for a package version.
        """
        report = {
            "package": f"{ecosystem}:{package_name}@{version}",
            "scan_date": datetime.now().isoformat(),
            "vulnerabilities": [],
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "recommendations": []
        }
        
        # Query vulnerabilities
        vulns = self.memory.semantic_retrieve(
            f"{ecosystem} {package_name} {version}",
            k=50
        )
        
        for vuln in vulns:
            severity = vuln.get("metadata", {}).get("severity", "UNKNOWN")
            if severity in report["severity_counts"]:
                report["severity_counts"][severity] += 1
            
            report["vulnerabilities"].append({
                "id": vuln["id"],
                "severity": severity,
                "summary": vuln["text"][:200]
            })
        
        # Generate recommendations
        if report["severity_counts"]["CRITICAL"] > 0:
            report["recommendations"].append("URGENT: Critical vulnerabilities found. Update immediately.")
        
        if report["severity_counts"]["HIGH"] > 0:
            report["recommendations"].append("High severity vulnerabilities present. Schedule update soon.")
        
        return report


class VulnerabilityEnricher:
    """
    Enrich vulnerability data with additional intelligence sources.
    """
    
    def __init__(self, memory: Any, ingestor: VulnerabilityIngestor):
        self.memory = memory
        self.ingestor = ingestor
    
    async def enrich_with_exploit_db(self, vuln_id: str) -> Dict[str, Any]:
        """
        Check if exploits are available in Exploit-DB.
        """
        # Query Exploit-DB API or scrape
        # Link exploit information to vulnerability
        pass
    
    async def enrich_with_epss(self, cve_id: str) -> Dict[str, Any]:
        """
        Add EPSS (Exploit Prediction Scoring System) scores.
        """
        # Fetch EPSS score from first.org API
        url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
        
        try:
            async with self.ingestor.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data"):
                        epss_data = data["data"][0]
                        
                        # Update vulnerability entity with EPSS score
                        vuln_entity_id = self.ingestor._generate_id(f"vuln_{cve_id}")
                        
                        # Add EPSS properties
                        self.memory.upsert_entity(
                            entity_id=vuln_entity_id,
                            etype="vulnerability",
                            properties={
                                "epss_score": epss_data.get("epss"),
                                "epss_percentile": epss_data.get("percentile"),
                                "epss_date": epss_data.get("date")
                            }
                        )
                        
                        return epss_data
        except Exception as e:
            print(f"Error fetching EPSS for {cve_id}: {e}")
        
        return {}
    
    async def enrich_with_threat_intelligence(self, vuln_id: str) -> Dict[str, Any]:
        """
        Add threat intelligence (IOCs, TTPs, threat actors).
        """
        # Query threat intelligence feeds
        # Link to MITRE ATT&CK techniques
        # Link to known threat actors exploiting this vulnerability
        pass
    
    async def enrich_with_social_sentiment(self, vuln_id: str) -> Dict[str, Any]:
        """
        Analyze social media discussions and security researcher sentiment.
        """
        # Scrape Twitter/X, Reddit, security blogs
        # Sentiment analysis
        # Track discussion volume over time
        pass
    
    async def cross_reference_advisories(self, vuln_id: str) -> List[Dict[str, Any]]:
        """
        Cross-reference across multiple advisory databases.
        Find all related IDs (CVE, GHSA, PYSEC, etc.)
        """
        references = []
        
        # If it's a CVE, look for OSV equivalents
        if vuln_id.startswith("CVE-"):
            # Query OSV by CVE alias
            url = f"{self.ingestor.OSV_API}/query"
            payload = {"version": vuln_id}
            
            try:
                async with self.ingestor.session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for vuln in data.get("vulns", []):
                            references.append({
                                "id": vuln.get("id"),
                                "source": "OSV",
                                "url": f"https://osv.dev/vulnerability/{vuln.get('id')}"
                            })
            except Exception as e:
                print(f"Error cross-referencing {vuln_id}: {e}")
        
        return references


class VulnerabilitySBOM:
    """
    Software Bill of Materials (SBOM) integration for vulnerability management.
    """
    
    def __init__(self, memory: Any, ingestor: VulnerabilityIngestor):
        self.memory = memory
        self.ingestor = ingestor
    
    async def ingest_sbom(self, sbom_data: Dict[str, Any], sbom_format: str = "cyclonedx") -> Dict[str, Any]:
        """
        Ingest SBOM and cross-reference with vulnerability database.
        
        Args:
            sbom_data: SBOM JSON data
            sbom_format: Format (cyclonedx, spdx)
        """
        results = {
            "components_scanned": 0,
            "vulnerabilities_found": 0,
            "vulnerable_components": []
        }
        
        if sbom_format == "cyclonedx":
            components = sbom_data.get("components", [])
            
            for component in components:
                results["components_scanned"] += 1
                
                # Extract component info
                name = component.get("name")
                version = component.get("version")
                purl = component.get("purl")  # Package URL
                
                # Query OSV for vulnerabilities
                if purl:
                    vulns = await self._query_osv_by_purl(purl)
                    
                    if vulns:
                        results["vulnerabilities_found"] += len(vulns)
                        results["vulnerable_components"].append({
                            "component": f"{name}@{version}",
                            "purl": purl,
                            "vulnerabilities": vulns
                        })
                        
                        # Ingest each vulnerability
                        for vuln_id in vulns:
                            await self.ingestor.ingest_osv(vuln_id)
        
        elif sbom_format == "spdx":
            # Parse SPDX format
            packages = sbom_data.get("packages", [])
            # Similar logic for SPDX format
            pass
        
        return results
    
    async def _query_osv_by_purl(self, purl: str) -> List[str]:
        """Query OSV API by Package URL"""
        url = f"{self.ingestor.OSV_API}/query"
        payload = {"package": {"purl": purl}}
        
        try:
            async with self.ingestor.session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [v.get("id") for v in data.get("vulns", [])]
        except Exception as e:
            print(f"Error querying OSV for {purl}: {e}")
        
        return []
    
    def generate_vex(self, sbom_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate VEX (Vulnerability Exploitability eXchange) document.
        """
        vex = {
            "version": "1.0",
            "statements": []
        }
        
        # For each component in SBOM, determine exploitability status
        # - Not Affected
        # - Affected
        # - Fixed
        # - Under Investigation
        
        return vex


# ==================== Specialized Ingestors ====================

class ContainerImageScanner:
    """
    Scan container images for vulnerabilities using image layers and installed packages.
    """
    
    def __init__(self, memory: Any, ingestor: VulnerabilityIngestor):
        self.memory = memory
        self.ingestor = ingestor
    
    async def scan_image(self, image_name: str, image_tag: str = "latest") -> Dict[str, Any]:
        """
        Scan Docker/OCI container image for vulnerabilities.
        """
        # Extract image layers
        # Identify installed packages
        # Query vulnerability databases
        # Generate report
        pass


class DependencyGraphScanner:
    """
    Scan dependency graphs for transitive vulnerabilities.
    """
    
    def __init__(self, memory: Any, ingestor: VulnerabilityIngestor):
        self.memory = memory
        self.ingestor = ingestor
    
    async def scan_dependencies(self, dependencies: List[Dict[str, Any]], ecosystem: str) -> Dict[str, Any]:
        """
        Scan dependency tree for vulnerabilities including transitive dependencies.
        """
        results = {
            "total_dependencies": len(dependencies),
            "vulnerable_dependencies": [],
            "transitive_vulnerabilities": []
        }
        
        for dep in dependencies:
            name = dep.get("name")
            version = dep.get("version")
            
            # Query vulnerabilities
            vulns = self.ingestor.query_package_vulnerabilities(name, version, ecosystem)
            
            if vulns:
                results["vulnerable_dependencies"].append({
                    "name": name,
                    "version": version,
                    "vulnerabilities": vulns
                })
        
        return results