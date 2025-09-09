import os
import sys
from datetime import datetime
from sysconfig import get_config_h_filename
from dotenv import load_dotenv
from langfuse import observe,get_client

repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_path)
from evals.eval_1_3 import pipeline

repo_root = os.path.dirname(os.path.dirname(__file__))
dotenv_path = os.path.join(repo_root, ".env")
load_dotenv(dotenv_path)

langfuse = get_client()

def verify_langfuse_connection():
    """Verify Langfuse connection and provide setup guidance."""
    try:
        auth_check = langfuse.auth_check()
        if auth_check:
            print(" Langfuse connected successfully!")
            return True
        else:
            print(" Langfuse authentication failed")
            print("\n Setup required:")
            print("1. Go to https://cloud.langfuse.com")
            print("2. Create a project or select existing one")
            print("3. Go to Settings → API Keys")
            print("4. Add to your .env file:")
            print("   LANGFUSE_SECRET_KEY=sk-lf-...")
            print("   LANGFUSE_PUBLIC_KEY=pk-lf-...")
            print("   LANGFUSE_HOST=https://cloud.langfuse.com")
            return False
    except Exception as e:
        print(f" Langfuse connection error: {e}")
        return False

@observe(name="Ad Copy Evaluation Session")
def main():
    """
    Main execution with Langfuse session tracking.
    Structure: Session → Pipeline → Individual Trend Evaluations → Single Normalized Score
    """
    
    print("=" * 80)
    print(" AD COPY ANALYSIS & EVALUATION SYSTEM")
    print("=" * 80)
    
    if not verify_langfuse_connection():
        print("\n  Langfuse not configured - evaluation will still run but won't be logged")
        proceed = input("Continue anyway? (y/N): ").lower().strip()
        if proceed != 'y':
            sys.exit(1)
    
    # Configuration
    input_path = "C:/ZZZZ-MINE/Aqxle/Inputs/1.3_Input_0809.json"
    output_path = "C:/ZZZZ-MINE/Aqxle/evals/1.3_Evaluations_0809.csv"
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
        
        # Execute the pipeline - this will:
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
            print(f"    Langfuse Dashboard: Individual trend scores logged")
            print(f"")
            print(f" Next Steps:")
            print(f"   1. Review CSV for detailed analysis")
            print(f"   2. Check Langfuse dashboard for trend-by-trend scores")
            print(f"   3. Look for 'evaluation_score' (0-100%) for each trend")
            
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
        print("\n Troubleshooting:")
        print("   1. Check your .env file has all required API keys")
        print("   2. Verify input JSON file format")
        print("   3. Ensure output directory exists and is writable")
        print("   4. Check network connection for API calls")
        sys.exit(1)
    
    finally:
        # Ensure Langfuse data is sent
        try:
            langfuse.flush()
            print(f"\n Langfuse data synchronized")
        except:
            pass

if __name__ == "__main__":
    main()