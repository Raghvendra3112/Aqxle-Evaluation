import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from langfuse import observe, get_client

repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_path)
from eval_pipeline.eval_1_2 import pipeline

repo_root = os.path.dirname(os.path.dirname(__file__))
dotenv_path = os.path.join(repo_root, ".env")
load_dotenv(dotenv_path)

langfuse = get_client()

def verify_langfuse_connection():
    try:
        auth_check = langfuse.auth_check()
        if auth_check:
            print(" Langfuse connected successfully!")
            return True
        else:
            print(" Langfuse authentication failed")
            return False
    except Exception as e:
        print(f" Langfuse connection error: {e}")
        return False

@observe(as_type="agent", name="Insights Evaluation Session")
def main():
    """
    Structure: Session → Pipeline → Individual Datapoint Evaluations → Single Normalized Score
    """
    
    print("=" * 80)
    print(" INSIGHTS ANALYSIS & EVALUATION SYSTEM (v1.2)")
    print("=" * 80)
    
    if not verify_langfuse_connection():
        print("\n  Langfuse not configured - evaluation will still run but won't be logged")
        proceed = input("Continue anyway? (y/N): ").lower().strip()
        if proceed != 'y':
            sys.exit(1)
    

    input_path = "C:/ZZZZ-MINE/Aqxle/Inputs/1.2_Input.json"
    output_path = "C:/ZZZZ-MINE/Aqxle/evals/1.2_Evaluations_langfuse.csv"
    brand = "Lenovo"
    
    print(f"\n Session Configuration:")
    print(f"    Brand: {brand}")
    print(f"    Input: {os.path.basename(input_path)}")
    print(f"    Output: {os.path.basename(output_path)}")
    print(f"    Version: 1.2")
    
    try:
        start_time = datetime.now()
        
        print(f"\n Starting evaluation pipeline at {start_time.strftime('%H:%M:%S')}")
        print("=" * 50)
        
        # 1. Create main pipeline trace
        # 2. For each datapoint: create separate trace + single normalized score
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
            print(f"    Datapoints processed: {result['total_datapoints']}")
            print(f"    Successful evaluations: {result['successful']}")  
            print(f"    Success rate: {result.get('success_rate', 0):.1f}%")
            print(f"    Processing speed: {result['total_datapoints']/processing_time*60:.1f} datapoints/minute")
            print(f"")
            print(f" Outputs:")
            print(f"    CSV Report: {result['output_path']}")
            print(f"    Langfuse Dashboard: Individual datapoint scores logged")
            print(f"")
            
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
    
    finally:
        try:
            langfuse.flush()
            print(f"\n Langfuse data synchronized")
        except:
            pass

if __name__ == "__main__":
    main()