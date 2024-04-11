# Note: except captures the 2c2.delete(snapshot) command STDERR in the variable "e". It prints the "e" variable, then continues iterating through the list of values. 
# list of values came from excel spreadsheet see line 10
# Purpose: Cost Optimization

import boto3 
import pprint
import logging
from openpyxl import load_workbook
AWS_REGION = "ap-southeast-2"
ec2 = boto3.client('ec2', region_name = AWS_REGION)
wb = load_workbook("WORKBOOK.xlsx")  
ws = wb['Sheet1']
column = ws['D'][1:3089]  
column_list = [column[x].value for x in range(len(column))]
for snap in column_list:
    #print(f"Try deleting Snapshot {snap}")
    try:
        ec2.delete_snapshot(SnapshotId=snap)
    except Exception as e:
        print(e)
        continue
    print("Loop has finished")
