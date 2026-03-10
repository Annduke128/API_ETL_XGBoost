"""
GPU Patch module cho xgboost_forecast.py

Usage trong Dockerfile:
    COPY xgboost_forecast_gpu_patch.py /tmp/
    RUN python3 /tmp/xgboost_forecast_gpu_patch.py
"""

import os
import re

def apply_gpu_patch():
    """Apply GPU support patch to xgboost_forecast.py"""
    
    file_path = '/app/xgboost_forecast.py'
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 1. Thêm helper functions sau logger definition
    helper_code = '''

# ============================================================================
# GPU SUPPORT HELPER FUNCTIONS
# ============================================================================

def get_xgboost_tree_method() -> str:
    """
    Xác định tree_method dựa trên environment variable USE_GPU.
    
    Returns:
        str: 'gpu_hist' nếu USE_GPU=true và GPU available, 'hist' nếu không
    """
    use_gpu = os.environ.get('USE_GPU', 'false').lower() == 'true'
    
    if use_gpu:
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("🎮 GPU detected via nvidia-smi, using tree_method='gpu_hist'")
                return 'gpu_hist'
            else:
                logger.warning("⚠️  USE_GPU=true but nvidia-smi failed, falling back to CPU (hist)")
                return 'hist'
        except Exception as e:
            logger.warning(f"⚠️  USE_GPU=true but GPU check failed: {e}, falling back to CPU (hist)")
            return 'hist'
    
    return 'hist'


def get_xgboost_device() -> str:
    """
    Xác định device cho XGBoost.
    
    Returns:
        str: 'cuda' nếu GPU available, 'cpu' nếu không
    """
    tree_method = get_xgboost_tree_method()
    return 'cuda' if tree_method == 'gpu_hist' else 'cpu'


# Tạo alias để dễ dùng
TREE_METHOD = get_xgboost_tree_method()
DEVICE = get_xgboost_device()

if TREE_METHOD == 'gpu_hist':
    logger.info("🚀 XGBoost GPU mode enabled (gpu_hist)")
else:
    logger.info("🖥️  XGBoost CPU mode (hist)")
'''
    
    # Tìm và thêm sau logger = logging.getLogger(__name__)
    pattern = r'(logger = logging\.getLogger\(__name__\))'
    if re.search(pattern, content):
        content = re.sub(pattern, r'\1' + helper_code, content)
        print("✅ Added GPU helper functions")
    else:
        print("⚠️  Could not find logger definition")
    
    # 2. Thay thế tree_method='hist' bằng tree_method=TREE_METHOD
    content = re.sub(r"tree_method='hist'", "tree_method=TREE_METHOD", content)
    print("✅ Replaced tree_method='hist' with tree_method=TREE_METHOD")
    
    # 3. Thay thế trong dictionary
    content = re.sub(r"'tree_method': 'hist'", "'tree_method': TREE_METHOD", content)
    print("✅ Replaced dict tree_method")
    
    # 4. Cập nhật comments
    content = re.sub(
        r'# Fast histogram method cho CPU',
        '# Auto-detected: gpu_hist for GPU, hist for CPU',
        content
    )
    content = re.sub(
        r'# Fast histogram \(CPU optimized\)',
        '# Auto-detected: gpu_hist for GPU, hist for CPU',
        content
    )
    print("✅ Updated comments")
    
    # Ghi file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Patched: {file_path}")
    return True


if __name__ == '__main__':
    apply_gpu_patch()
