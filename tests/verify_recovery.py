
import sys
import os
import json
import time
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tests/recovery_result.log", encoding='utf-8', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_recovery():
    logger.info("🚀 Starting Recovery Verification Test")
    
    # 1. Import app and necessary components
    # We need to patch 'app.scheduler' before importing app to avoid starting it if it's auto-started
    with patch('apscheduler.schedulers.background.BackgroundScheduler'):
        import app
        from app import run_background_recovery, progress_manager
    
    # Re-configure logging to ensure we capture our test logs
    # app.py might have reset it
    logging.getLogger().handlers = []
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("tests/recovery_result.log", encoding='utf-8', mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger.info("✅ App imported successfully")
    
    # 2. Setup Mock Data
    test_session_id = "test_recovery_session"
    test_date = datetime.now().strftime("%Y-%m-%d")
    
    # Create a dummy failed session
    session_data = {
        "session_id": test_session_id,
        "start_date": test_date,
        "end_date": test_date,
        "status": "failed",
        "total": 10,
        "processed": 5,
        "success": 4,
        "failed": 1,
        "filter_by_handicap": False, # Simplify logic
        "created_at": datetime.now().isoformat()
    }
    
    # Save session file manually
    session_file = progress_manager.progress_dir / f"session_{test_session_id}.json"
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f)
    
    logger.info(f"✅ Created test session: {test_session_id} (Status: failed)")
    
    # 3. Mock Dependencies
    # Mock bifaw_client.fetch_finished_matches to return 1 match
    mock_match = {
        "label": "Test Match vs Test Opponent",
        "home": "Test Match",
        "away": "Test Opponent",
        "kickoff": f"{test_date} 12:00",
        "detail_url": "http://mock.url/detail",
        "detail_params": {}
    }
    
    app.bifaw_client.fetch_finished_matches = MagicMock(return_value=(None, [mock_match], {}))
    
    # Mock _collect_single_match_worker to simulate success
    # We need to patch it where it is used. Since it's imported/used in run_background_recovery,
    # and run_background_recovery is in app.py, we patch app._collect_single_match_worker
    
    # However, run_background_recovery calls _collect_single_match_worker directly.
    # If it was imported, we'd patch the import. Since it's defined in the same module, 
    # we can try to patch 'app._collect_single_match_worker'.
    
    with patch('app._collect_single_match_worker') as mock_worker:
        mock_worker.return_value = {'status': 'success', 'rows': 10}
        
        # 4. Run Recovery
        logger.info("🔄 Triggering run_background_recovery...")
        run_background_recovery(test_session_id)
        
        # 5. Verify Results
        # Check if fetch_finished_matches was called
        app.bifaw_client.fetch_finished_matches.assert_called()
        logger.info("✅ bifaw_client.fetch_finished_matches was called")
        
        # Check if worker was called
        mock_worker.assert_called()
        logger.info("✅ _collect_single_match_worker was called")
        
        # Check session status
        updated_session = progress_manager.load_session(test_session_id)
        if updated_session['status'] == 'completed':
            logger.info(f"✅ Session status updated to: {updated_session['status']}")
        else:
            logger.error(f"❌ Session status is: {updated_session['status']} (Expected: completed)")
            
    # Cleanup
    if session_file.exists():
        os.remove(session_file)
        logger.info("🧹 Cleaned up test session file")

if __name__ == "__main__":
    test_recovery()
