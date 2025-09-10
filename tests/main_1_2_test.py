from openai import OpenAI
import anthropic
import json
import sys
import os
import pandas as pd
import re


repo_path = r"C:/ZZZZ-MINE/Aqxle/Aqxle-Evaluation"
sys.path.append(repo_path)

from tests.test_1_2 import pipeline

if __name__ == "__main__":
    pipeline( input="C:/ZZZZ-MINE/Aqxle/Inputs/1.2_Input.json", output="C:/ZZZZ-MINE/Aqxle/evals/1.2_Evaluations2.csv", brand="Lenovo")