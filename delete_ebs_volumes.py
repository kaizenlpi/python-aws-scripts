'''
PURPOSE: THIS SCRIPT USES AN OUTPUTTED EXCEL SPREADSHEET OF EBS VOLUMES NOT IN USE THAT NEED TO BE DELETED. THE EBS VOLUMES ARE IN A LIST
SOME GENERAL LEARNING NOTES HERE...
SOURCE URL: https://stackoverflow.com/questions/45708626/read-data-in-excel-column-into-python-list
READ DATA FROM EXCEL WORKBOOK/SHEET INTO PYTHON LIST

NOTE: THE INITIAL QUOTES YOU SEE IN THE PPRINT OUTPUT ARE NOT PART OF YOUR STRINGS AND WON'T 
EXIST WHEN YOU ITERATE OVER THE LIST
python3 delete-ebs-vol.py
['Volume Id vol-00a1f3aff3ff57b01 vol-04bd4cada863ee544 vol-02147928b7cb0e19e '
 'vol-0079ea32b16aeede1 vol-06097f05fbcab73db vol-0b80038092795093a ']

'''
# Purpose: Cost Optimization

import boto3 
import pprint
from openpyxl import load_workbook
AWS_REGION = "us-gov-west-1"
ec2 = boto3.client('ec2', region_name = AWS_REGION)

wb = load_workbook("CREPCE.xlsx")  
ws = wb['Sheet1']  
column = ws['D']  
column_list = [column[x].value for x in range(len(column))]  


# USE MAP TO CONVERT LIST TO STRING https://www.simplilearn.com/tutorials/python-tutorial/list-to-string-in-python 
# USE SPLIT METHOD TO DIVIDE STRINGS AS MULTIPLE SUBSSTRINGS WITH COMMAS SEPARATOR REMOVED
volumes_string =" ".join(map(str,column_list)).split(",")
pprint.pprint(volumes_string) 


for volume in volumes_string:
    print(f"Volumes {volume} are deleting")
    response = ec2.delete_volume(VolumeId=volume)
    print(f"Volumes {volume} have been deleted")
