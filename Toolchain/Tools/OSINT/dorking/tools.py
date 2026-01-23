#!/usr/bin/env python3
"""
LangChain tool integration for the dorking toolkit.

Provides structured tools that can be added to agent tool lists.
"""

from typing import List, Optional
from langchain_core.tools import StructuredTool

from .config import DorkingConfig
from .mapper import DorkingMapper
from .schemas import (
    FileDorkInput,
    LoginDorkInput,
    DeviceDorkInput,
    MisconfigDorkInput,
    PeopleDorkInput,
    CustomDorkInput,
    ComprehensiveDorkInput,
    UnifiedDorkInput,
    QuickSearchInput
)


def add_dorking_tools(tool_list: List, agent):
    """
    Add comprehensive dorking tools to agent tool list.
    
    Includes both new unified keyword/custom dork tools and
    all original category-specific tools.
    
    Args:
        tool_list: List to append tools to
        agent: Agent instance with memory system
    
    Returns:
        Modified tool list
    """
    
    # =========================================================================
    # NEW: UNIFIED KEYWORD + CUSTOM DORK TOOLS
    # =========================================================================
    
    def unified_search_wrapper(search: str, target: Optional[str] = None,
                               file_type: Optional[str] = None, site: Optional[str] = None,
                               exclude_sites: Optional[List[str]] = None,
                               date_range: Optional[str] = None,
                               max_results: Optional[int] = 50,
                               engines: Optional[List[str]] = None,
                               mode: Optional[str] = "smart"):
        """Wrapper for unified search"""
        config = DorkingConfig.stealth_mode()
        
        if engines:
            config.engines = engines
        if date_range:
            config.date_filter = date_range
        
        config.max_results_per_engine = max_results or 50
        
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.unified_search(
            search, target, file_type, site, exclude_sites, max_results, mode
        ):
            yield chunk
    
    def quick_search_wrapper(keywords: str, target: Optional[str] = None):
        """Wrapper for quick keyword search"""
        config = DorkingConfig.stealth_mode()
        config.max_results_per_engine = 30
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.quick_search(keywords, target):
            yield chunk
    
    # =========================================================================
    # ORIGINAL: CATEGORY-SPECIFIC TOOLS
    # =========================================================================
    
    def search_files_wrapper(target: str, file_types: Optional[List[str]] = None,
                            keywords: Optional[List[str]] = None):
        """Wrapper for file search"""
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_files(target, file_types, keywords):
            yield chunk
    
    def search_logins_wrapper(target: str, login_types: Optional[List[str]] = None):
        """Wrapper for login search"""
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_logins(target, login_types):
            yield chunk
    
    def search_devices_wrapper(target: str, device_types: Optional[List[str]] = None):
        """Wrapper for device search"""
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_devices(target, device_types):
            yield chunk
    
    def search_misconfigs_wrapper(target: str, misconfig_types: Optional[List[str]] = None):
        """Wrapper for misconfiguration search"""
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_misconfigs(target, misconfig_types):
            yield chunk
    
    def search_people_wrapper(target: str, info_types: Optional[List[str]] = None):
        """Wrapper for people/OSINT search"""
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_people(target, info_types):
            yield chunk
    
    def custom_dork_wrapper(target: str, dork_query: str, engine: str = "google"):
        """Wrapper for custom dork execution"""
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.custom_dork(dork_query, engine):
            yield chunk
    
    def comprehensive_dork_wrapper(target: str, categories: Optional[List[str]] = None,
                                   depth: str = "standard"):
        """Wrapper for comprehensive multi-category dorking"""
        if depth == "quick":
            config = DorkingConfig()
            config.max_results_per_engine = 20
        elif depth == "deep":
            config = DorkingConfig.aggressive_mode()
        else:
            config = DorkingConfig.stealth_mode()
        
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.comprehensive_dork(target, categories, depth):
            yield chunk
    
    # =========================================================================
    # CREATE TOOLS - NEW + ORIGINAL
    # =========================================================================
    
    tool_list.extend([
        # NEW: Unified keyword/custom dork tools
        StructuredTool.from_function(
            func=unified_search_wrapper,
            name="dork_search",
            description=(
                "🔍 INTELLIGENT DORKING TOOL - Supports both simple keywords and advanced dorks\n\n"
                "SIMPLE KEYWORD EXAMPLES:\n"
                "  • search='webcam' - Find webcams/cameras\n"
                "  • search='admin login' - Find admin panels\n"
                "  • search='database' - Find exposed databases\n"
                "  • search='config', file_type='env' - Find .env files\n"
                "  • search='camera', target='example.com' - Find cameras on specific domain\n\n"
                "CUSTOM DORK EXAMPLES:\n"
                "  • search='intitle:\"webcam\" inurl:view.shtml'\n"
                "  • search='filetype:sql \"password\"'\n"
                "  • search='site:s3.amazonaws.com filetype:pdf'\n\n"
                "FEATURES:\n"
                "  • Auto-detects keywords vs custom dorks\n"
                "  • Generates multiple search variations\n"
                "  • Extracts emails, phones, IPs\n"
                "  • Deduplicates results\n"
                "  • Multi-engine support\n"
                "  • Anti-detection measures\n\n"
                "PARAMETERS:\n"
                "  • target: Focus on domain/keyword\n"
                "  • file_type: Filter by file extension\n"
                "  • site: Restrict to specific domain\n"
                "  • mode: 'smart' (auto), 'keyword', 'custom'"
            ),
            args_schema=UnifiedDorkInput
        ),
        
        StructuredTool.from_function(
            func=quick_search_wrapper,
            name="dork_quick",
            description=(
                "⚡ QUICK KEYWORD SEARCH - Fast keyword-based dorking\n\n"
                "Perfect for quick searches with simple keywords:\n"
                "  • 'webcam'\n"
                "  • 'admin panel'\n"
                "  • 'exposed database'\n"
                "  • 'printer'\n\n"
                "Returns top 30 results, minimal configuration."
            ),
            args_schema=QuickSearchInput
        ),
        
        # ORIGINAL: Category-specific tools (all preserved)
        StructuredTool.from_function(
            func=search_files_wrapper,
            name="dork_search_files",
            description=(
                "Search for exposed files using Google dorks. "
                "Finds SQL dumps, config files, logs, backups, credentials. "
                "File types: sql, log, env, config, bak, xml, json. "
                "Anti-detection with delays and rotation."
            ),
            args_schema=FileDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_logins_wrapper,
            name="dork_search_logins",
            description=(
                "Search for login portals and admin panels. "
                "Finds admin panels, webmail, phpMyAdmin, CMS logins, control panels. "
                "Login types: admin, webmail, cpanel, phpmyadmin, wordpress."
            ),
            args_schema=LoginDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_devices_wrapper,
            name="dork_search_devices",
            description=(
                "Search for exposed network devices. "
                "Finds webcams, printers, routers, NAS, IoT devices, SCADA systems. "
                "Device types: camera, webcam, printer, router, nas, scada."
            ),
            args_schema=DeviceDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_misconfigs_wrapper,
            name="dork_search_misconfigs",
            description=(
                "Search for server misconfigurations. "
                "Finds directory listings, error pages, exposed .git/.svn, debug pages. "
                "Types: directory_listing, error_page, debug, git, svn."
            ),
            args_schema=MisconfigDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_people_wrapper,
            name="dork_search_people",
            description=(
                "Search for people information and OSINT. "
                "Finds emails, phone numbers, social profiles, resumes. "
                "Extracts and correlates personal information. "
                "Info types: email, phone, social, resume, linkedin."
            ),
            args_schema=PeopleDorkInput
        ),
        
        StructuredTool.from_function(
            func=custom_dork_wrapper,
            name="dork_custom",
            description=(
                "Execute custom Google dork query. "
                "For advanced users who know exact dork syntax. "
                "Supports all search engines: google, bing, duckduckgo."
            ),
            args_schema=CustomDorkInput
        ),
        
        StructuredTool.from_function(
            func=comprehensive_dork_wrapper,
            name="dork_comprehensive",
            description=(
                "Comprehensive multi-category dorking scan. "
                "Searches files, logins, devices, misconfigs in one operation. "
                "Depth: quick (fast), standard (balanced), deep (thorough). "
                "Automatically correlates findings across categories."
            ),
            args_schema=ComprehensiveDorkInput
        ),
    ])
    
    return tool_list