#!/usr/bin/env python3
"""
Pydantic schemas for dorking tool inputs.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FlexibleDorkInput(BaseModel):
    """Base schema for dorking"""
    target: str = Field(description="Target domain, keyword, or dork query")


class FileDorkInput(FlexibleDorkInput):
    """Input schema for file dorking"""
    file_types: Optional[List[str]] = Field(
        default=None,
        description="File types: sql, log, env, config, bak, xml, json, csv"
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Additional keywords to include"
    )


class LoginDorkInput(FlexibleDorkInput):
    """Input schema for login portal dorking"""
    login_types: Optional[List[str]] = Field(
        default=None,
        description="Login types: admin, webmail, cpanel, phpmyadmin, wordpress"
    )


class DeviceDorkInput(FlexibleDorkInput):
    """Input schema for device dorking"""
    device_types: Optional[List[str]] = Field(
        default=None,
        description="Device types: camera, webcam, printer, router, nas, scada"
    )


class MisconfigDorkInput(FlexibleDorkInput):
    """Input schema for misconfiguration dorking"""
    misconfig_types: Optional[List[str]] = Field(
        default=None,
        description="Types: directory_listing, error_page, debug, trace"
    )


class PeopleDorkInput(FlexibleDorkInput):
    """Input schema for people/OSINT dorking"""
    info_types: Optional[List[str]] = Field(
        default=None,
        description="Info types: email, phone, social, resume, linkedin"
    )


class CustomDorkInput(FlexibleDorkInput):
    """Input schema for custom dork queries"""
    dork_query: str = Field(description="Custom Google dork query")
    engine: str = Field(default="google", description="Search engine to use")


class ComprehensiveDorkInput(FlexibleDorkInput):
    """Input schema for comprehensive multi-category dorking"""
    categories: Optional[List[str]] = Field(
        default=None,
        description="Categories to search: files, logins, cameras, devices, misconfigs"
    )
    depth: str = Field(
        default="standard",
        description="Search depth: quick, standard, deep"
    )


class UnifiedDorkInput(BaseModel):
    """
    Unified schema for keyword and custom dork searches.
    
    This is the main search interface supporting both simple keywords
    and advanced custom dorks with intelligent auto-detection.
    
    Examples:
        Simple keyword: search="webcam"
        With target: search="webcam", target="example.com"
        Custom dork: search='intitle:"webcam" inurl:view.shtml'
        Hybrid: search="admin login", file_type="php"
    """
    search: str = Field(
        description=(
            "Search query - can be:\n"
            "1. Simple keyword: 'webcam', 'admin panel', 'database'\n"
            "2. Custom dork: 'intitle:\"login\" inurl:admin'\n"
            "3. Multiple keywords: 'exposed camera streaming'\n"
            "Auto-detects and generates appropriate dork queries"
        )
    )
    
    target: Optional[str] = Field(
        default=None,
        description="Optional target domain or keyword to focus on (e.g., 'example.com' or 'company name')"
    )
    
    file_type: Optional[str] = Field(
        default=None,
        description="File type filter: sql, pdf, xls, doc, log, env, config, etc."
    )
    
    site: Optional[str] = Field(
        default=None,
        description="Limit to specific site/domain (e.g., 'example.com')"
    )
    
    exclude_sites: Optional[List[str]] = Field(
        default=None,
        description="Domains to exclude from results"
    )
    
    date_range: Optional[str] = Field(
        default=None,
        description="Time filter: 'day', 'week', 'month', 'year'"
    )
    
    max_results: Optional[int] = Field(
        default=50,
        description="Maximum results to return per engine"
    )
    
    engines: Optional[List[str]] = Field(
        default=None,
        description="Search engines to use: ['google', 'bing', 'duckduckgo']"
    )
    
    mode: Optional[str] = Field(
        default="smart",
        description="Search mode: 'smart' (auto), 'keyword' (force keyword search), 'custom' (force as custom dork)"
    )


class QuickSearchInput(BaseModel):
    """Quick search with just keywords"""
    keywords: str = Field(
        description="Keywords to search for (e.g., 'webcam', 'admin login')"
    )
    target: Optional[str] = Field(
        default=None,
        description="Optional target domain"
    )