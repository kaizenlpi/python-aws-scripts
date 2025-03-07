# Author: Matt Brady
# Date: 3/7/25  
# Goal: Finds all volumes with status: available in the AWS account. 

import boto3 
import pprint

AWS_REGION = "us-gov-west-1"

# Create an EC2 client
ec2_client = boto3.client('ec2', region_name = AWS_REGION)

# Describe volumes with the "available" state
response = ec2_client.describe_volumes(
    Filters=[{'Name': 'status', 'Values': ['available']}]
)

# Print the details of available volumes
print("Available EBS Volumes:")
for volume in response['Volumes']:
    print(f"Volume ID: {volume['VolumeId']}, Size: {volume['Size']} GiB, "
          f"State: {volume['State']}, AZ: {volume['AvailabilityZone']}")A
