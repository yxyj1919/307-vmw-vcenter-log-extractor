# Changelog

## [v1.0.0] - 2024-01-26

### Changed
- Upgraded to official release 1.0.0
- UI Improvements:
  - Enhanced navigation bar layout and styling
  - Added back navigation button
  - Improved version selector interface
  - Unified service status display
- Feature Enhancements:
  - Improved service status analysis accuracy
  - Optimized log processing performance
  - Enhanced error handling and notifications
- Code Improvements:
  - Added comprehensive code documentation
  - Improved code structure
  - Enhanced error handling mechanisms

## [v0.1.0] - 2024-01-22

### Added
- Initial release of vCenter vMon Service Checker
- Core Features:
  - Web-based interface for vmon.log analysis
  - Support for vCenter 7.x and 8.x versions
  - Interactive service dependency visualization
  - Service status analysis and monitoring
  - Detailed service logs inspection

### Features
- File Upload:
  - Direct file upload with drag & drop support
  - URL-based file upload
  - Support for vmon.log files
- Service Matrix:
  - Color-coded service status:
    - Blue: System Control Services
    - Green: Running Services
    - Red: Failed Services
    - Yellow: Stopped Services
    - Gray: Other Status
  - Interactive dependency highlighting
  - Detailed service information on hover
- Configuration Support:
  - vCenter 8.x configuration (vcsa8u3-all-services.yaml)
  - vCenter 7.x configuration (vcsa7u3-all-services-20250122.yaml)

### Technical
- Project Structure:
  - Flask-based web application
  - Docker containerization support
  - Modular Python utilities for log analysis
  - Responsive HTML templates
  - Permission management scripts
- Dependencies:
  - Python 3.9+
  - Flask 3.0.0
  - PyYAML 6.0.1
  - Pandas 2.1.4
  - Requests 2.31.0
  - Werkzeug 3.0.1

### Documentation
- README.md with comprehensive documentation
- Installation and setup instructions
- Docker deployment guide
- Development setup guide
- Directory structure documentation
- Usage instructions

### Scripts
- check_setup.py for environment verification
- check_permissions.sh for permission management

### Contact
Bug Reports: chang.wang@broadcom.com
