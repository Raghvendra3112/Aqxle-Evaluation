import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from langfuse import get_client,observe


# Get absolute path of repo (parent of 'main' folder)
repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_path)
from evals.eval_1_3 import pipeline

repo_root = os.path.dirname(os.path.dirname(__file__))  # one level up from main/
dotenv_path = os.path.join(repo_root, ".env")
load_dotenv(dotenv_path)

langfuse = get_client()
 
# Verify connection, do not use in production as this is a synchronous call
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

@observe(name="Main")
def main():
    """Main execution function."""
    
    print("=" * 60)
    print("AD COPY ANALYSIS PIPELINE")
    print("=" * 60)
    
    result = {}
    try:
        # Import and run pipeline
        
        
        input_path = "C:/ZZZZ-MINE/Aqxle/Inputs/1.3_Input_0309.json"
        output_path = "C:/ZZZZ-MINE/Aqxle/evals/1.3_Evaluations_0309.csv"
        brand = "Lenovo"
        print(f"\n[INFO] Starting pipeline execution...")
        print(f"[INFO] Input: {input_path}")
        print(f"[INFO] Output: {output_path}") 
        print(f"[INFO] Brand: {brand}")
        
        # Execute pipeline
        result = pipeline(input_path, output_path, brand)
    
        if result["status"] == "success":
            print(f"\n[SUCCESS] Pipeline completed successfully!")
            print(f"[INFO] Processed {result['total_trends']} trends")
            print(f"[INFO] Success rate: {(result['successful']/result['total_trends'])*100:.1f}%")
            print(f"[INFO] Processing time: {result['processing_time']:.2f} seconds")
            print(f"[INFO] Results saved to: {result['output_path']}")
            
        else:
            print("[ERROR] Pipeline completed with errors")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n[WARNING] Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()