import os
import sys
from datetime import datetime
from sysconfig import get_config_h_filename
from dotenv import load_dotenv

repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_path)
from tests.test_1_3 import pipeline

repo_root = os.path.dirname(os.path.dirname(__file__))
dotenv_path = os.path.join(repo_root, ".env")
load_dotenv(dotenv_path)

def main():
    """
    Structure: Session → Pipeline → Individual Trend Evaluations → Single Normalized Score
    """
    
    print("=" * 80)
    print(" AD COPY ANALYSIS & EVALUATION SYSTEM")
    print("=" * 80)
    

    input_path = "C:/ZZZZ-MINE/Aqxle/Inputs/output/2025-09-09/Lenovo_ad_analysis_data.json"
    output_path = "C:/ZZZZ-MINE/Aqxle/evals/1.3_Lenovo_Evaluations_0909.csv"
    brand = "Lenovo"
    
    print(f"\n Session Configuration:")
    print(f"    Brand: {brand}")
    print(f"    Input: {os.path.basename(input_path)}")
    print(f"    Output: {os.path.basename(output_path)}")
    print(f"    Version: 1.3")
    
    try:
        start_time = datetime.now()
        
        print(f"\n Starting evaluation pipeline at {start_time.strftime('%H:%M:%S')}")
        print("=" * 50)
        
        # 1. Create main pipeline trace
        # 2. For each trend: create separate trace + single normalized score
        # 3. Save detailed results to CSV
        result = pipeline(input_path, output_path, brand)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print("=" * 50)
        print(f"  Total processing time: {processing_time:.1f} seconds")
        
        if result["status"] == "success":
            print(f"\n EVALUATION COMPLETED SUCCESSFULLY!")
            print(f"")
            print(f" Summary:")
            print(f"    Trends processed: {result['total_trends']}")
            print(f"    Successful evaluations: {result['successful']}")  
            print(f"    Success rate: {result.get('success_rate', 0):.1f}%")
            print(f"    Processing speed: {result['total_trends']/processing_time*60:.1f} trends/minute")
            print(f"")
            print(f" Outputs:")
            print(f"    CSV Report: {result['output_path']}")
            
        else:
            print(" Pipeline completed with errors - check logs above")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n  Evaluation interrupted by user")
        print(" Partial results may be available in output file")
        sys.exit(130)
        
    except FileNotFoundError as e:
        print(f"\n File not found: {e}")
        print(" Please check your file paths:")
        print(f" Input: {input_path}")
        print(f" Output directory: {os.path.dirname(output_path)}")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n Evaluation failed: {e}")
        sys.exit(1)
    

if __name__ == "__main__":
    main()