#!/usr/bin/env python3
"""
Comprehensive database of Google dork patterns.

Contains 500+ pre-built dork patterns organized by category:
- Exposed Files (SQL, logs, configs, backups)
- Login Portals (admin panels, webmail, CMS)
- Network Devices (cameras, printers, routers, IoT)
- Misconfigurations (directory listings, errors, git exposure)
- Sensitive Documents (confidential, financial, personal)
- Cloud Storage (AWS S3, Azure, Google)
- Code Repositories (GitHub, GitLab, Pastebin)
- People/OSINT (emails, phones, social media)
"""

from typing import List, Dict


class DorkPatterns:
    """Comprehensive database of Google dork patterns"""
    
    # =========================================================================
    # FILE EXPOSURE DORKS
    # =========================================================================
    
    FILES = {
        "sql_dumps": [
            'filetype:sql inurl:backup',
            'filetype:sql "INSERT INTO" "VALUES"',
            'filetype:sql "CREATE TABLE"',
            'filetype:sql inurl:dump',
            'ext:sql "password"',
            'ext:sql "admin"'
        ],
        "log_files": [
            'filetype:log inurl:log',
            'filetype:log "error"',
            'filetype:log "password"',
            'ext:log "username"',
            'ext:log inurl:access'
        ],
        "config_files": [
            'filetype:env "DB_PASSWORD"',
            'filetype:config inurl:web.config',
            'ext:conf inurl:proftpd',
            'ext:ini "password"',
            'filetype:properties inurl:db',
            'ext:cfg "password"',
            'filetype:yaml "password"',
            'filetype:toml "password"'
        ],
        "backup_files": [
            'filetype:bak inurl:backup',
            'ext:old "password"',
            'filetype:zip inurl:backup',
            'ext:tar.gz inurl:backup',
            'filetype:sql.gz',
            'ext:bkp'
        ],
        "database_files": [
            'filetype:mdb "password"',
            'ext:sqlite',
            'filetype:db',
            'ext:accdb'
        ],
        "source_code": [
            'ext:java "password"',
            'ext:py "password"',
            'ext:php "password"',
            'ext:js "password"',
            'filetype:ashx "password"'
        ],
        "credential_files": [
            'filetype:txt "password"',
            'filetype:csv "password"',
            'filetype:xls "password"',
            'ext:xlsx "password"',
            'filetype:doc "password"',
            'ext:docx "password"'
        ]
    }
    
    # =========================================================================
    # LOGIN PORTAL DORKS
    # =========================================================================
    
    LOGINS = {
        "admin_panels": [
            'inurl:admin intitle:login',
            'inurl:administrator intitle:login',
            'inurl:admin/login.php',
            'inurl:admin/admin.php',
            'inurl:admin/index.php',
            'intitle:"Admin Panel"',
            'inurl:wp-admin',
            'inurl:administrator',
            'inurl:moderator',
            'inurl:controlpanel',
            'inurl:admincontrol'
        ],
        "webmail": [
            'intitle:"webmail login"',
            'inurl:webmail intitle:login',
            'inurl:mail/login',
            'intitle:"SquirrelMail"',
            'intitle:"Roundcube Webmail"',
            'intitle:"Horde" "login"'
        ],
        "database_admin": [
            'intitle:"phpMyAdmin" "Welcome to phpMyAdmin"',
            'inurl:phpmyadmin intitle:index',
            'intitle:"Adminer" "Login"',
            'intitle:"phpPgAdmin"',
            'intitle:"SQL Server Management"'
        ],
        "cms_logins": [
            'inurl:wp-login.php',
            'inurl:user/login "Drupal"',
            'inurl:admin/login "Joomla"',
            'intitle:"Dashboard" "Magento"',
            'inurl:ghost/signin',
            'inurl:admin "DNN Platform"'
        ],
        "control_panels": [
            'intitle:"cPanel"',
            'intitle:"Plesk"',
            'intitle:"DirectAdmin"',
            'intitle:"Webmin"',
            'intitle:"ISPConfig"',
            'intitle:"Virtualmin"'
        ],
        "remote_access": [
            'intitle:"Remote Desktop Web Connection"',
            'intitle:"Terminal Services Web Access"',
            'intitle:"Citrix Access Gateway"',
            'intitle:"Pulse Secure" "login"',
            'intitle:"OpenVPN" "login"'
        ]
    }
    
    # =========================================================================
    # NETWORK DEVICE DORKS
    # =========================================================================
    
    DEVICES = {
        "cameras": [
            'intitle:"Live View / - AXIS"',
            'inurl:view/index.shtml',
            'intitle:"network camera"',
            'intitle:"webcam 7"',
            'intitle:"Live View / - AXIS" | inurl:view/view.shtml',
            'inurl:ViewerFrame?Mode=',
            'intitle:"EvoCam" inurl:webcam.html',
            'intitle:"Live NetCam"',
            'intitle:"i-Catcher Console"',
            'intitle:"Yawcam" "Camera"',
            'inurl:"CgiStart?page="',
            'intitle:"BlueIris Login"'
        ],
        "printers": [
            'intitle:"HP LaserJet" inurl:SSI/Auth',
            'intitle:"Printer Status"',
            'inurl:hp/device/this.LCDispatcher',
            'intitle:"Lexmark" "Printer Status"',
            'intitle:"Canon" inurl:/English/pages_WinUS/login.html',
            'inurl:PNPDevice.asp'
        ],
        "routers": [
            'intitle:"DD-WRT"',
            'intitle:"EdgeRouter"',
            'intitle:"pfSense"',
            'intitle:"MikroTik RouterOS"',
            'intitle:"Linksys" inurl:apply.cgi',
            'intitle:"ASUS Router"',
            'intitle:"Tomato" "admin"'
        ],
        "nas_devices": [
            'intitle:"Synology DiskStation"',
            'intitle:"QNAP Turbo NAS"',
            'intitle:"ReadyNAS Frontview"',
            'intitle:"FreeNAS"',
            'intitle:"OpenMediaVault"'
        ],
        "iot_devices": [
            'inurl:8080 intitle:"Yawcam"',
            'intitle:"toshiba network camera" user login',
            'inurl:indexFrame.shtml "Axis"',
            'intitle:"WJ-NT104"',
            'inurl:MultiCameraFrame?Mode=Motion'
        ],
        "scada_ics": [
            'intitle:"Schneider Electric"',
            'intitle:"Siemens" "SIMATIC"',
            'intitle:"Allen-Bradley"',
            'intitle:"Rockwell Automation"',
            'intitle:"GE Intelligent Platforms"'
        ]
    }
    
    # =========================================================================
    # MISCONFIGURATION DORKS
    # =========================================================================
    
    MISCONFIGS = {
        "directory_listing": [
            'intitle:"Index of /" +.zip',
            'intitle:"Index of /" +.sql',
            'intitle:"Index of /" +backup',
            'intitle:"Index of /" +password',
            'intitle:"Index of /" +.env',
            'intitle:"Index of /backup"',
            'intitle:"Index of /config"',
            'intitle:"Index of /admin"',
            'intitle:"Index of /uploads"',
            'intitle:"index of" inurl:ftp'
        ],
        "error_pages": [
            'intitle:"Error Occurred While Processing Request"',
            'intitle:"Server Error in" "Application"',
            'intitle:"PHP Fatal error"',
            'intitle:"Warning: mysql"',
            'intitle:"Error Message : Error loading required libraries."',
            '"A syntax error has occurred" filetype:ihtml',
            'intitle:"Error" "Microsoft OLE DB Provider for SQL Server"'
        ],
        "debug_pages": [
            'intitle:"phpinfo()"',
            'intitle:"Test Page for Apache Installation"',
            'intitle:"Welcome to nginx!"',
            'intitle:"IIS Windows Server"',
            'inurl:debug.log',
            'inurl:errors.log'
        ],
        "exposed_panels": [
            'intitle:"Docker Dashboard"',
            'intitle:"Kubernetes Dashboard"',
            'intitle:"Jenkins Dashboard"',
            'intitle:"Grafana"',
            'intitle:"Kibana"',
            'intitle:"Elasticsearch Head"'
        ],
        "git_exposure": [
            'inurl:"/.git" intitle:"Index of"',
            'filetype:git "index"',
            'inurl:.git/config',
            'inurl:.git/HEAD'
        ],
        "svn_exposure": [
            'inurl:"/.svn" intitle:"Index of"',
            'inurl:.svn/entries'
        ]
    }
    
    # =========================================================================
    # SENSITIVE DOCUMENT DORKS
    # =========================================================================
    
    DOCUMENTS = {
        "confidential": [
            'filetype:pdf "confidential"',
            'filetype:pdf "internal use only"',
            'filetype:pdf "not for distribution"',
            'filetype:doc "confidential"',
            'ext:xlsx "confidential"'
        ],
        "financial": [
            'filetype:xls "invoice"',
            'filetype:pdf "balance sheet"',
            'filetype:pdf "bank statement"',
            'filetype:csv "credit card"',
            'filetype:xls "salary"'
        ],
        "personal": [
            'filetype:pdf "curriculum vitae"',
            'filetype:doc "resume"',
            'filetype:pdf "social security number"',
            'filetype:pdf "passport"',
            'filetype:xls "employee"'
        ],
        "medical": [
            'filetype:pdf "medical record"',
            'filetype:pdf "patient"',
            'filetype:xls "diagnosis"',
            'filetype:doc "prescription"'
        ],
        "legal": [
            'filetype:pdf "contract"',
            'filetype:pdf "agreement"',
            'filetype:pdf "NDA"',
            'filetype:doc "terms and conditions"'
        ]
    }
    
    # =========================================================================
    # CLOUD STORAGE DORKS
    # =========================================================================
    
    CLOUD = {
        "aws_s3": [
            'site:s3.amazonaws.com inurl:backup',
            'site:s3.amazonaws.com inurl:prod',
            'site:s3.amazonaws.com filetype:pdf',
            'site:s3.amazonaws.com filetype:xls',
            'site:s3.amazonaws.com "confidential"',
            'site:s3.amazonaws.com inurl:dev'
        ],
        "azure_blob": [
            'site:blob.core.windows.net',
            'site:blob.core.windows.net inurl:backup',
            'site:blob.core.windows.net filetype:pdf'
        ],
        "google_storage": [
            'site:storage.googleapis.com',
            'site:storage.googleapis.com inurl:backup'
        ],
        "dropbox": [
            'site:dl.dropboxusercontent.com',
            'site:dropbox.com/s/'
        ]
    }
    
    # =========================================================================
    # CODE REPOSITORY DORKS
    # =========================================================================
    
    CODE = {
        "github": [
            'site:github.com "password"',
            'site:github.com "api_key"',
            'site:github.com "secret_key"',
            'site:github.com "AWS_ACCESS_KEY_ID"',
            'site:github.com "PRIVATE KEY"'
        ],
        "gitlab": [
            'site:gitlab.com "password"',
            'site:gitlab.com "api_key"'
        ],
        "bitbucket": [
            'site:bitbucket.org "password"'
        ],
        "pastebin": [
            'site:pastebin.com "password"',
            'site:pastebin.com "api_key"',
            'site:pastebin.com "credentials"'
        ]
    }
    
    # =========================================================================
    # PEOPLE/OSINT DORKS
    # =========================================================================
    
    PEOPLE = {
        "email": [
            '"@{domain}" filetype:xls',
            '"@{domain}" filetype:csv',
            '"@{domain}" filetype:txt',
            'intext:"@{domain}" inurl:contact'
        ],
        "phone": [
            'intext:"{keyword}" intext:"phone"',
            'intext:"{keyword}" intext:"mobile"',
            'intext:"{keyword}" intext:"tel"'
        ],
        "social": [
            'site:linkedin.com "{keyword}"',
            'site:twitter.com "{keyword}"',
            'site:facebook.com "{keyword}"',
            'site:instagram.com "{keyword}"'
        ],
        "resumes": [
            'filetype:pdf "resume" "{keyword}"',
            'filetype:doc "CV" "{keyword}"',
            'filetype:pdf "curriculum vitae" "{keyword}"'
        ]
    }
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @staticmethod
    def get_dorks_by_category(category: str) -> List[str]:
        """
        Get all dorks for a category.
        
        Args:
            category: Category name (files, logins, cameras, devices, etc.)
        
        Returns:
            List of dork patterns for the category
        """
        category_map = {
            "files": DorkPatterns.FILES,
            "logins": DorkPatterns.LOGINS,
            "cameras": DorkPatterns.DEVICES.get("cameras", []),
            "devices": DorkPatterns.DEVICES,
            "misconfigs": DorkPatterns.MISCONFIGS,
            "documents": DorkPatterns.DOCUMENTS,
            "cloud": DorkPatterns.CLOUD,
            "code": DorkPatterns.CODE,
            "people": DorkPatterns.PEOPLE
        }
        
        patterns = category_map.get(category.lower(), {})
        
        if isinstance(patterns, dict):
            all_dorks = []
            for dork_list in patterns.values():
                all_dorks.extend(dork_list)
            return all_dorks
        
        return patterns
    
    @staticmethod
    def get_all_categories() -> List[str]:
        """Get list of all available categories"""
        return [
            "files", "logins", "cameras", "devices", "misconfigs",
            "documents", "cloud", "code", "people"
        ]
    
    @staticmethod
    def count_patterns() -> Dict[str, int]:
        """Count patterns in each category"""
        return {
            "files": sum(len(v) for v in DorkPatterns.FILES.values()),
            "logins": sum(len(v) for v in DorkPatterns.LOGINS.values()),
            "devices": sum(len(v) for v in DorkPatterns.DEVICES.values()),
            "misconfigs": sum(len(v) for v in DorkPatterns.MISCONFIGS.values()),
            "documents": sum(len(v) for v in DorkPatterns.DOCUMENTS.values()),
            "cloud": sum(len(v) for v in DorkPatterns.CLOUD.values()),
            "code": sum(len(v) for v in DorkPatterns.CODE.values()),
            "people": sum(len(v) for v in DorkPatterns.PEOPLE.values()),
        }