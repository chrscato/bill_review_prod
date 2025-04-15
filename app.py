def get_dashboard_data():
    """
    Get data for the dashboard including validation statistics and recent activity.
    """
    try:
        # Get failed files
        failed_files = hcfa_service.get_failed_files()
        
        # Calculate statistics
        total_failures = len(failed_files)
        failures_by_type = {}
        recent_failures = []
        
        for file_data in failed_files:
            # Count failures by type
            for msg in file_data.get('validation_messages', []):
                failure_type = msg.get('type', 'Unknown')
                failures_by_type[failure_type] = failures_by_type.get(failure_type, 0) + 1
            
            # Add to recent failures (last 10)
            if len(recent_failures) < 10:
                recent_failures.append({
                    'filename': file_data['filename'],
                    'order_id': file_data['order_id'],
                    'patient_name': file_data['patient_name'],
                    'date_of_service': file_data['date_of_service'],
                    'total_charge': file_data['total_charge'],
                    'last_modified': file_data['last_modified']
                })
        
        # Get file statistics from logs
        log_file = Path('logs/app.log')
        total_files = 0
        skipped_files = 0
        error_files = 0
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                for line in f:
                    if 'Total JSON files found:' in line:
                        total_files = int(line.split(':')[1].strip())
                    elif 'Skipped files (invalid format):' in line:
                        skipped_files = int(line.split(':')[1].strip())
                    elif 'Error files:' in line:
                        error_files = int(line.split(':')[1].strip())
        
        return {
            'total_failures': total_failures,
            'total_files': total_files,
            'skipped_files': skipped_files,
            'error_files': error_files,
            'failures_by_type': failures_by_type,
            'recent_failures': recent_failures
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        return {
            'total_failures': 0,
            'total_files': 0,
            'skipped_files': 0,
            'error_files': 0,
            'failures_by_type': {},
            'recent_failures': []
        } 